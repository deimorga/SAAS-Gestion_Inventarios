# Especificaciones de Infraestructura — MicroNuba Inventory SaaS

**Versión:** 1.0  
**Estado:** Aprobada  
**Fecha:** 2026-04-24  
**Documento hermano:** [ARQUITECTURA_FISICA.md](./ARQUITECTURA_FISICA.md)

---

## 1. Topología de Contenedores

El sistema se compone de **5 contenedores** orquestados con Docker Compose:

```mermaid
graph LR
    subgraph "docker-compose.dev.yml"
        T["inv-traefik<br/>:80 / :443 / :8080"]
        A["inv-api<br/>:8000"]
        W["inv-worker"]
        B["inv-beat"]
        P["inv-postgres<br/>:5432"]
        R["inv-redis<br/>:6379"]
    end

    T -->|"inv_edge"| A
    A -->|"inv_app"| R
    A -->|"inv_data"| P
    W -->|"inv_app"| R
    W -->|"inv_data"| P
    B -->|"inv_app"| R

    style T fill:#2d6a4f,color:#fff
    style A fill:#264653,color:#fff
    style P fill:#1b4332,color:#fff
    style R fill:#e76f51,color:#fff
    style W fill:#e9c46a,color:#000
    style B fill:#e9c46a,color:#000
```

### Nomenclatura de Contenedores

| Service Name | Container Name | Prefijo | Propósito |
|-------------|---------------|---------|-----------|
| `traefik` | `inv-traefik` | `inv-` | Reverse proxy + TLS |
| `api` | `inv-api` | `inv-` | FastAPI backend |
| `worker` | `inv-worker` | `inv-` | Celery worker (tareas asíncronas) |
| `beat` | `inv-beat` | `inv-` | Celery beat (scheduler) |
| `postgres` | `inv-postgres` | `inv-` | Base de datos PostgreSQL |
| `redis` | `inv-redis` | `inv-` | Cache, locks, message broker |

> [!NOTE]
> El prefijo `inv-` identifica inequívocamente los contenedores de este proyecto, evitando conflictos con otros stacks Docker en el mismo host.

---

## 2. Especificación por Contenedor

### 2.1. `inv-traefik` — Reverse Proxy

| Atributo | Valor |
|----------|-------|
| **Service name** | `traefik` |
| **Container name** | `inv-traefik` |
| **Imagen** | `traefik:v3.0` |
| **Puertos expuestos** | `80` (HTTP → redirect HTTPS), `443` (HTTPS), `8080` (Dashboard, solo dev) |
| **Redes** | `inv_edge`, `inv_app` |
| **Volúmenes** | `./infra/traefik/traefik.yml:/etc/traefik/traefik.yml:ro`, `./infra/traefik/dynamic/:/etc/traefik/dynamic/:ro`, `/var/run/docker.sock:/var/run/docker.sock:ro` |
| **Healthcheck** | `traefik healthcheck --ping` |
| **Restart** | `unless-stopped` |
| **Responsabilidades** | TLS termination, routing por labels Docker, health checks, rate limiting global |
| **Labels de routing** | `traefik.http.routers.inv-api.rule=Host('api.inventory.local')` |

### 2.2. `inv-api` — FastAPI Backend

| Atributo | Valor |
|----------|-------|
| **Service name** | `api` |
| **Container name** | `inv-api` |
| **Imagen** | Build desde `core_backend/Dockerfile` |
| **Base image** | `python:3.12-slim` |
| **Puerto interno** | `8000` (no expuesto al host, solo vía `inv-traefik`) |
| **Redes** | `inv_app`, `inv_data` |
| **Comando (dev)** | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload` |
| **Comando (prod)** | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4` |
| **User** | `appuser` (UID 1000, non-root) |
| **Variables de entorno** | Ver sección 3 |
| **Healthcheck** | `curl -f http://localhost:8000/health \|\| exit 1` |
| **Restart** | `unless-stopped` |
| **Dependencias** | `inv-postgres` (healthy), `inv-redis` (healthy) |
| **Volúmenes (dev)** | `./core_backend:/app` (hot reload) |
| **Labels Traefik** | `traefik.http.services.inv-api.loadbalancer.server.port=8000` |

### 2.3. `inv-worker` — Celery Worker

| Atributo | Valor |
|----------|-------|
| **Service name** | `worker` |
| **Container name** | `inv-worker` |
| **Imagen** | Misma que `inv-api` (build compartido) |
| **Redes** | `inv_app`, `inv_data` |
| **Comando** | `celery -A app.tasks worker --loglevel=info --concurrency=4 -Q default,webhooks,bulk` |
| **User** | `appuser` (UID 1000, non-root) |
| **Restart** | `unless-stopped` |
| **Colas** | `default` (tareas generales), `webhooks` (notificaciones), `bulk` (procesamiento masivo) |
| **Dependencias** | `inv-redis` (healthy), `inv-postgres` (healthy) |

### 2.4. `inv-beat` — Celery Beat (Scheduler)

| Atributo | Valor |
|----------|-------|
| **Service name** | `beat` |
| **Container name** | `inv-beat` |
| **Imagen** | Misma que `inv-api` (build compartido) |
| **Redes** | `inv_app` |
| **Comando** | `celery -A app.tasks beat --loglevel=info --schedule=/tmp/celerybeat-schedule` |
| **Restart** | `unless-stopped` |
| **Tareas programadas** | `reservation_cleanup` (cada 1 min), `expiry_check` (cada 1 hora), `webhook_retry` (cada 5 min) |
| **Dependencias** | `inv-redis` (healthy) |

### 2.5. `inv-postgres` — PostgreSQL

| Atributo | Valor |
|----------|-------|
| **Service name** | `postgres` |
| **Container name** | `inv-postgres` |
| **Imagen** | `postgres:15-alpine` |
| **Puerto** | `5432` (solo expuesto al host en dev para DBeaver/pgAdmin) |
| **Redes** | `inv_data` |
| **Volúmenes** | `inv_postgres_data:/var/lib/postgresql/data`, `./infra/postgres/init/:/docker-entrypoint-initdb.d/:ro` |
| **Healthcheck** | `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` |
| **Restart** | `unless-stopped` |
| **Configuración** | `max_connections=100`, `shared_buffers=256MB`, `work_mem=8MB` |
| **Init Scripts** | `01_create_extensions.sql` (uuid-ossp), `02_enable_rls.sql` |

### 2.6. `inv-redis` — Redis

| Atributo | Valor |
|----------|-------|
| **Service name** | `redis` |
| **Container name** | `inv-redis` |
| **Imagen** | `redis:7-alpine` |
| **Puerto** | `6379` (solo expuesto al host en dev) |
| **Redes** | `inv_app`, `inv_data` |
| **Comando** | `redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --appendonly yes` |
| **Healthcheck** | `redis-cli ping` |
| **Restart** | `unless-stopped` |
| **Volúmenes** | `inv_redis_data:/data` |

---

## 3. Variables de Entorno

### 3.1. API (FastAPI)

```env
# === Base ===
APP_ENV=development
APP_DEBUG=true
APP_SECRET_KEY=<random-64-chars>

# === Database ===
DATABASE_URL=postgresql+asyncpg://inventory_user:${DB_PASSWORD}@inv-postgres:5432/inventory_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# === Redis ===
REDIS_URL=redis://inv-redis:6379/0
CELERY_BROKER_URL=redis://inv-redis:6379/1

# === Auth ===
JWT_PRIVATE_KEY_PATH=/app/keys/private.pem
JWT_PUBLIC_KEY_PATH=/app/keys/public.pem
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ALGORITHM=RS256

# === CORS ===
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:4200

# === Rate Limiting ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_RPM=60
```

### 3.2. PostgreSQL

```env
POSTGRES_USER=inventory_user
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=inventory_db
```

> [!CAUTION]
> Las contraseñas nunca se hardcodean. En desarrollo se usan archivos `.env` (incluidos en `.gitignore`). En producción se usan secrets del orquestador (Docker Swarm secrets o similar).

---

## 4. Scripts de Inicialización de Base de Datos

### 4.1. `infra/postgres/init/01_create_extensions.sql`

```sql
-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para búsquedas fuzzy en catálogo
```

### 4.2. `infra/postgres/init/02_enable_rls.sql`

```sql
-- Función helper para obtener el tenant actual
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS uuid AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true)::uuid;
EXCEPTION
    WHEN OTHERS THEN RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Template de política RLS (se aplica a cada tabla transaccional)
-- Ejemplo para products:
-- ALTER TABLE products ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON products
--     USING (tenant_id = current_tenant_id());
```

---

## 5. Estrategia de Índices Esenciales

| Tabla | Índice | Columnas | Justificación |
|-------|--------|----------|---------------|
| `products` | `idx_products_tenant_sku` | `(tenant_id, sku)` UNIQUE | Unicidad de SKU por tenant + búsqueda rápida |
| `products` | `idx_products_tenant_active` | `(tenant_id, is_active)` | Filtro frecuente |
| `stock_balances` | `idx_sb_tenant_product_warehouse` | `(tenant_id, product_id, warehouse_id)` UNIQUE | Saldo único por combinación |
| `inventory_ledger` | `idx_ledger_tenant_balance_created` | `(tenant_id, stock_balance_id, created_at DESC)` | Kardex ordenado cronológicamente |
| `inventory_ledger` | `idx_ledger_tenant_type_created` | `(tenant_id, type, created_at)` | Filtro por tipo de movimiento |
| `reservations` | `idx_res_tenant_status_expires` | `(tenant_id, status, expires_at)` | Cleanup de reservas expiradas |
| `audit_logs` | `idx_audit_tenant_entity_created` | `(tenant_id, entity, created_at DESC)` | Consulta de auditoría |
| `api_keys` | `idx_apikeys_key_id` | `(key_id)` UNIQUE | Lookup rápido de API Keys |

---

## 6. Dockerfile del Backend

```dockerfile
# === Build Stage ===
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === Runtime Stage ===
FROM python:3.12-slim

# Seguridad: usuario non-root
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

WORKDIR /app

# Copiar dependencias desde builder
COPY --from=builder /install /usr/local

# Copiar código
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Permisos
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 7. Health Checks y Monitoreo

| Contenedor | Endpoint/Comando | Intervalo | Timeout | Retries |
|------------|-----------------|-----------|---------|---------|
| `inv-api` | `GET /health` → `{"status": "healthy", "db": "ok", "redis": "ok"}` | 10s | 5s | 3 |
| `inv-postgres` | `pg_isready -U inventory_user -d inventory_db` | 10s | 5s | 5 |
| `inv-redis` | `redis-cli ping` → `PONG` | 10s | 5s | 3 |
| `inv-traefik` | `--ping=true` | 10s | 5s | 3 |

---

## 8. Entornos

| Entorno | Propósito | Docker Compose | Branch |
|---------|-----------|---------------|--------|
| **Development** | Desarrollo local con hot reload | `docker-compose.dev.yml` | `develop` |
| **Staging** | Validación pre-producción | `docker-compose.staging.yml` | `develop` |
| **Production** | Producción | `docker-compose.prod.yml` | `main` |

### Diferencias entre entornos

| Aspecto | Development | Staging | Production |
|---------|------------|---------|------------|
| Debug | `true` | `false` | `false` |
| Hot reload | ✅ | ❌ | ❌ |
| DB expuesta al host | ✅ (`:5432`) | ❌ | ❌ |
| Workers Uvicorn | 1 | 2 | 4 |
| TLS | Self-signed / HTTP | Let's Encrypt | Let's Encrypt |
| Logs | Verbose (DEBUG) | INFO | WARNING |

---

## 9. Diagrama de Despliegue (Producción)

```mermaid
graph TD
    subgraph "VPS / Cloud Server"
        subgraph "Docker Engine"
            T["Traefik v3<br/>:443 (TLS)"]
            A["FastAPI<br/>4 workers"]
            W["Celery Worker<br/>4 concurrency"]
            B["Celery Beat"]
            P["PostgreSQL 15<br/>RLS + Backups"]
            R["Redis 7<br/>AOF persistence"]
        end

        subgraph "Volúmenes Persistentes"
            V1["postgres_data"]
            V2["redis_data"]
            V3["traefik_certs"]
        end
    end

    DNS["DNS<br/>api.inventory.micronuba.com"] -->|"A Record"| T
    T --> A
    P --- V1
    R --- V2
    T --- V3

    style T fill:#2d6a4f,color:#fff
    style A fill:#264653,color:#fff
    style P fill:#1b4332,color:#fff
```

---

## 10. Referencias

| Documento | Ubicación |
|-----------|-----------|
| Arquitectura Física | Este documento |
| Definición Funcional | `doc/Funcional/mejorado/` |
| Arquitectura de Referencia (Original) | `doc/Documentacion de Idea/Arquitectura de Referencia_*.md` |
| Estructura del Proyecto | `doc/Estructura/estructura_proyecto.md` |
| Reglas Operativas | `.agent/RULES.md` |
