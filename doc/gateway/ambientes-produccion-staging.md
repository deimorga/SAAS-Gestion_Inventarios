# Ambientes Producción y Staging — Inventarios SaaS

> Documento creado: 2026-06-25  
> Estado: Staging operativo. Producción pendiente de arranque.

---

## Arquitectura de ambientes

```
Internet (148.230.82.172)
  :80 / :443
    │
  Traefik v3.3 (/root/micronuba-infra/) ← compartido con toda la infra MicroNuba
    │
    ├── api.inventarios.micronuba.net          → inv-api:8000            (prod)
    ├── admin.inventarios.micronuba.net        → inv-admin-portal:8080   (prod)
    ├── staging.inventarios.micronuba.net      → inv-api-staging:8000    (staging)
    ├── staging-admin.inventarios.micronuba.net→ inv-admin-portal-staging:8080 (staging)
    └── mail-staging.inventarios.micronuba.net → inv-mailpit-staging:8025 (staging)

VPS — directorios:
  /root/inventory-saas/          ← branch main  (producción)
  /root/inventory-saas-staging/  ← branch develop (staging)
```

---

## Dominios y DNS

Todos los registros están en **Cloudflare** (zona `micronuba.net`, ID: `1003493b90d5256fa7c8e20c8feeceb2`).

| Dominio | Tipo | IP | Proxy CF | Certificado |
|---|---|---|---|---|
| `api.inventarios.micronuba.net` | A | 148.230.82.172 | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `admin.inventarios.micronuba.net` | A | 148.230.82.172 | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `staging.inventarios.micronuba.net` | A | 148.230.82.172 | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `staging-admin.inventarios.micronuba.net` | A | 148.230.82.172 | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `mail-staging.inventarios.micronuba.net` | A | 148.230.82.172 | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |

> **Importante**: los registros deben mantenerse en DNS-only (nube gris) para que el challenge
> HTTP-01 de Let's Encrypt funcione. Si se activa el proxy Cloudflare (🟠) el cert fallará.

---

## Ambiente de Staging

### Rama y directorio
- **Rama Git**: `develop`
- **Directorio VPS**: `/root/inventory-saas-staging/`
- **Compose file**: `docker-compose.staging.yml`

### Contenedores

| Contenedor | Imagen | Puerto interno | Rol |
|---|---|---|---|
| `inv-api-staging` | `inv-api:staging` | 8000 | API FastAPI (2 workers) |
| `inv-worker-staging` | `inv-api:staging` | — | Celery worker (concurrencia 2) |
| `inv-beat-staging` | `inv-api:staging` | — | Celery beat (tareas programadas) |
| `inv-postgres-staging` | `postgres:15-alpine` | 5432 (interno) | Base de datos |
| `inv-redis-staging` | `redis:7-alpine` | 6379 (interno) | Broker Celery + caché |
| `inv-admin-portal-staging` | `inv-admin-portal:staging` | 8080 | Portal NiceGUI |
| `inv-mailpit-staging` | `axllent/mailpit:latest` | 8025 (web) + 1025 (smtp) | Captura de emails |

### Redes Docker
| Red | Tipo | Miembros |
|---|---|---|
| `micronuba_public` | bridge externo | `inv-api-staging`, `inv-admin-portal-staging`, `inv-mailpit-staging` + Traefik |
| `inv_app_staging` | bridge interno | `inv-api-staging`, `inv-worker-staging`, `inv-beat-staging`, `inv-redis-staging`, `inv-admin-portal-staging`, `inv-mailpit-staging` |
| `inv_data_staging` | bridge interno | `inv-api-staging`, `inv-worker-staging`, `inv-postgres-staging`, `inv-redis-staging` |

### Variables de entorno (.env)

| Variable | Valor en staging |
|---|---|
| `APP_ENV` | `staging` |
| `ENABLE_SWAGGER` | `true` |
| `POSTGRES_USER` | `inv_staging_user` |
| `POSTGRES_DB` | `inventory_staging` |
| `POSTGRES_PASSWORD` | *(generado con `openssl rand -hex 24`)* |
| `REDIS_PASSWORD` | *(generado con `openssl rand -hex 24`)* |
| `JWT_SECRET_KEY` | *(generado con `openssl rand -hex 32`)* |
| `ADMIN_BOOTSTRAP_SECRET` | *(generado con `openssl rand -hex 20`)* |
| `STORAGE_SECRET` | *(generado con `openssl rand -hex 32`)* |
| `RESEND_API_KEY` | `re_staging_placeholder` *(no se usa — email va a Mailpit)* |
| `RESEND_FROM_EMAIL` | `staging@micronuba.net` |
| `SMTP_HOST` | `inv-mailpit-staging` |
| `SMTP_PORT` | `1025` |
| `ACTIVATION_BASE_URL` | `https://staging-admin.inventarios.micronuba.net` |

> Los secrets reales están en `/root/inventory-saas-staging/.env` (permisos 600, nunca en git).
> Para verlos en el VPS: `ssh root@148.230.82.172 "cat /root/inventory-saas-staging/.env"`

### Diferencias clave vs producción
- `ENABLE_SWAGGER=true` → Swagger accesible en `/docs`
- 2 workers uvicorn (vs 4 en prod)
- 2 workers Celery (vs 4 en prod)
- Email va a **Mailpit** vía SMTP (no sale al exterior) → ver `app/tasks.py` bifurcación por `APP_ENV`
- Redis maxmemory: 256mb (vs 512mb en prod)
- `ADMIN_BOOTSTRAP_SECRET` puede mantenerse activo para resets de datos de prueba

### URLs de acceso
| Servicio | URL |
|---|---|
| API + Swagger | `https://staging.inventarios.micronuba.net/docs` |
| Health check | `https://staging.inventarios.micronuba.net/health` |
| Admin Portal | `https://staging-admin.inventarios.micronuba.net` |
| Mailpit (emails) | `https://mail-staging.inventarios.micronuba.net` |

---

## Ambiente de Producción

### Rama y directorio
- **Rama Git**: `main`
- **Directorio VPS**: `/root/inventory-saas/`
- **Compose file**: `docker-compose.prod.yml`

### Contenedores

| Contenedor | Imagen | Puerto interno | Rol |
|---|---|---|---|
| `inv-api` | `inv-api:prod` | 8000 | API FastAPI (4 workers) |
| `inv-worker` | `inv-api:prod` | — | Celery worker (concurrencia 4) |
| `inv-beat` | `inv-api:prod` | — | Celery beat (tareas programadas) |
| `inv-postgres` | `postgres:15-alpine` | 5432 (interno) | Base de datos |
| `inv-redis` | `redis:7-alpine` | 6379 (interno) | Broker Celery + caché |
| `inv-admin-portal` | `inv-admin-portal:prod` | 8080 | Portal NiceGUI |

### Redes Docker
| Red | Tipo |
|---|---|
| `micronuba_public` | bridge externo (compartido con Traefik) |
| `inv_app` | bridge interno |
| `inv_data` | bridge interno |

### Variables de entorno (.env)

| Variable | Valor en producción |
|---|---|
| `APP_ENV` | `production` |
| `ENABLE_SWAGGER` | `false` |
| `POSTGRES_USER` | `inv_prod_user` |
| `POSTGRES_DB` | `inventory_prod` |
| `POSTGRES_PASSWORD` | *(generado con `openssl rand -hex 24`)* |
| `REDIS_PASSWORD` | *(generado con `openssl rand -hex 24`)* |
| `JWT_SECRET_KEY` | *(generado con `openssl rand -hex 32`)* |
| `ADMIN_BOOTSTRAP_SECRET` | *(vaciar después del bootstrap inicial)* |
| `STORAGE_SECRET` | *(generado con `openssl rand -hex 32`)* |
| `RESEND_API_KEY` | *(API key real de Resend — pendiente de configurar)* |
| `RESEND_FROM_EMAIL` | `notification.inventory@micronuba.net` |
| `RESEND_FROM_NAME` | `MicroNuba` |
| `ACTIVATION_BASE_URL` | `https://admin.inventarios.micronuba.net` |

### URLs de acceso
| Servicio | URL |
|---|---|
| API (REST) | `https://api.inventarios.micronuba.net` |
| Health check | `https://api.inventarios.micronuba.net/health` |
| Admin Portal | `https://admin.inventarios.micronuba.net` |

> Swagger está **deshabilitado** en producción (`ENABLE_SWAGGER=false`).

---

## Email — bifurcación por ambiente

El task Celery `send_email` en `core_backend/app/tasks.py` bifurca según `APP_ENV`:

```python
if settings.APP_ENV == "staging":
    # SMTP → Mailpit (captura emails, no los envía al exterior)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.sendmail(...)
else:
    # Resend SDK (email real)
    resend.Emails.send(params)
```

| Ambiente | Mecanismo | Destino |
|---|---|---|
| `development` | Resend SDK (placeholder key) | Falla silenciosamente |
| `staging` | SMTP → Mailpit `:1025` | Bandeja de Mailpit UI |
| `production` | Resend SDK | Email real al destinatario |

---

## Comandos de operación

### Arrancar staging (primera vez)
```bash
ssh root@148.230.82.172
cd /root/inventory-saas-staging

# Build
docker compose -f docker-compose.staging.yml build api admin-portal

# Infraestructura
docker compose -f docker-compose.staging.yml up -d postgres redis mailpit
# Esperar ~15s

# API + migraciones
docker compose -f docker-compose.staging.yml up -d api
docker compose -f docker-compose.staging.yml exec api alembic upgrade head

# Resto de servicios
docker compose -f docker-compose.staging.yml up -d worker beat admin-portal
```

### Bootstrap primer super_admin en staging
```bash
curl -X POST https://staging.inventarios.micronuba.net/admin/auth/register \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Secret: <ADMIN_BOOTSTRAP_SECRET>" \
  -d '{"email":"admin@staging.micronuba.net","password":"<contraseña>","full_name":"Admin Staging"}'
```

### Actualización rutinaria de staging
```bash
cd /root/inventory-saas-staging
git pull origin develop
docker compose -f docker-compose.staging.yml build api admin-portal
docker compose -f docker-compose.staging.yml up -d --no-deps api
docker compose -f docker-compose.staging.yml exec api alembic upgrade head
docker compose -f docker-compose.staging.yml up -d --no-deps worker beat admin-portal
```

### Arrancar producción (primera vez)
```bash
ssh root@148.230.82.172
cd /root/inventory-saas

# Build
docker compose -f docker-compose.prod.yml build api admin-portal

# Infraestructura
docker compose -f docker-compose.prod.yml up -d postgres redis
# Esperar ~15s

# API + migraciones
docker compose -f docker-compose.prod.yml up -d api
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Bootstrap super_admin
curl -X POST https://api.inventarios.micronuba.net/admin/auth/register \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Secret: <ADMIN_BOOTSTRAP_SECRET>" \
  -d '{"email":"deimorga@gmail.com","password":"<contraseña_segura>","full_name":"Deiby Moreno"}'

# IMPORTANTE: vaciar ADMIN_BOOTSTRAP_SECRET en .env tras el bootstrap
# nano /root/inventory-saas/.env → ADMIN_BOOTSTRAP_SECRET=

# Resto de servicios
docker compose -f docker-compose.prod.yml up -d worker beat admin-portal
```

### Actualización rutinaria de producción
```bash
cd /root/inventory-saas
git pull origin main
docker compose -f docker-compose.prod.yml build api admin-portal
docker compose -f docker-compose.prod.yml up -d --no-deps api
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --no-deps worker beat admin-portal
```

### Ver estado de contenedores
```bash
# Staging
docker compose -f /root/inventory-saas-staging/docker-compose.staging.yml ps

# Producción
docker compose -f /root/inventory-saas/docker-compose.prod.yml ps
```

### Ver logs
```bash
# API staging
docker logs inv-api-staging -f --tail=50

# Worker staging
docker logs inv-worker-staging -f --tail=50

# Traefik (certs, routing)
docker logs micronuba-traefik --tail=100 2>&1 | grep inventarios
```

---

## Certificados TLS

Traefik gestiona los certificados automáticamente con Let's Encrypt (HTTP-01, resolver `le`).

- Los certs se almacenan en el volumen `micronuba_traefik_certs` (`acme.json`)
- Traefik renueva automáticamente antes del vencimiento (~30 días antes)
- El primer cert puede tardar 1-5 minutos en emitirse tras el primer request HTTPS

> Si Traefik muestra cert de auto-firma temporalmente, esperar unos minutos y refrescar.
> Los errores `503 Service Busy` de Let's Encrypt son transitorios — Traefik reintenta solo.

---

## Consideraciones de seguridad

| Item | Estado |
|---|---|
| Redes internas con `internal: true` | ✅ Worker y beat sin salida a internet |
| Secrets distintos entre prod y staging | ✅ Generados con `openssl rand` independientes |
| `.env` con permisos `600` en VPS | ✅ Solo root puede leer |
| `ADMIN_BOOTSTRAP_SECRET` vacío post-bootstrap | ⚠️ Pendiente en producción |
| Swagger deshabilitado en prod | ✅ `ENABLE_SWAGGER=false` |
| Rate limiting en API prod | ✅ 100 avg / 50 burst vía Traefik middleware |
| HTTPS forzado (redirect 80→443) | ✅ Configurado en Traefik global |
