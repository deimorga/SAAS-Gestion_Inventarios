# Entorno de desarrollo local — MicroNuba

Gateway centralizado `micronuba-infra` (Traefik en `:8090`) como único punto de entrada para todos los proyectos.

---

## Arquitectura

```
Navegador / curl  →  http://<dominio>.local:8090
                          │
                     Traefik :8090  (micronuba-infra)
                          │
                  Red Docker: micronuba_public
                  ┌────────────────────────────────┐
                  │  inv-api        :8000           │
                  │  backend_api    :8000           │
                  │  web_frontend   :80             │
                  │  crm-app        :3000           │
                  │  saas-core      :8000           │
                  │  portal-micronuba :80           │
                  └────────────────────────────────┘
```

Cada app corre en sus redes internas y expone solo su container de entrada a `micronuba_public`.

---

## Prerequisitos (una sola vez)

### Software

```bash
docker --version          # Docker 26+
docker compose version    # Compose v2+
```

### Variable de entorno — `micronuba-infra/.env`

```env
DOCKER_SOCKET=/Users/<tu-usuario>/.docker/run/docker.sock
```

Verificar con: `ls ~/.docker/run/docker.sock`

### /etc/hosts

```bash
sudo sh -c 'echo "127.0.0.1  api.inventarios.local api.talleres.local talleres.local crm.micronuba.local plagie.micronuba.local portal.micronuba.local traefik.micronuba.local" >> /etc/hosts'
```

---

## Mapa de proyectos

| Proyecto | Repo local | Overlay local | Dominio gateway |
|---------|-----------|---------------|----------------|
| Gateway | `micronuba-infra/` | — | `localhost:8888` (dashboard) |
| Inventarios | `SAAS - Plataforma Gestion Inventarios/` | `docker-compose.local.yml` ✓ | `api.inventarios.local:8090` |
| Talleres API | `SAAS-Gestion_Talleres/` | `docker-compose.local.yml` ✓ | `api.talleres.local:8090` |
| Talleres Frontend | `SAAS-Gestion_Talleres/` | `docker-compose.local.yml` ✓ | `talleres.local:8090` |
| CRM | `CRM-Comercial/` | `docker-compose.local.yml` ✓ | `crm.micronuba.local:8090` |
| PLAGIE | `Colegios/PLAGIE-SaaS/` | `docker-compose.local.yml` ✓ | `plagie.micronuba.local:8090` |
| Portal MicroNuba | `Portal MicroNuba/` | `docker-compose.local.yml` ✓ | `portal.micronuba.local:8090` |

---

## Puertos directos (sin gateway)

| Servicio | Puerto host |
|----------|------------|
| Inventarios API | `localhost:8002` |
| Talleres API | `localhost:8001` |
| Talleres Frontend | `localhost:4200` |
| Talleres MinIO API | `localhost:9002` |
| Talleres MinIO Console | `localhost:9003` |
| CRM App | `localhost:3000` |
| PLAGIE saas-core | `localhost:8000` |
| PLAGIE Vite | `localhost:5173` |
| PLAGIE MinIO | `localhost:9000 / 9001` |
| PLAGIE Mailpit | `localhost:8025` |
| Portal MicroNuba | `localhost:8080` |
| Inventarios PostgreSQL | `localhost:5433` |
| Talleres PostgreSQL | `localhost:5434` |
| CRM PostgreSQL | `localhost:5435` |
| PLAGIE PostgreSQL | `localhost:5432` |
| Inventarios Redis | `localhost:6380` |

---

## Orden de arranque

```
1. micronuba-infra   →  crea micronuba_public, arranca Traefik
2. cualquier app     →  se une a micronuba_public al levantar con el overlay
```

---

## Comandos por proyecto

### Gateway — `micronuba-infra`

```bash
cd ~/Proyectos/micronuba-infra

docker compose build          # primera vez (compila socket-proxy Go)
docker compose up -d

# Verificar: http://localhost:8888
```

### Inventarios

```bash
cd ~/Proyectos/"SAAS - Plataforma Gestion Inventarios"

docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d api
# Con worker/beat (requieren app/tasks.py):
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d

# Verificar: http://api.inventarios.local:8090/health
# Swagger:   http://api.inventarios.local:8090/docs
```

> `inv-worker` e `inv-beat` están en Restarting — requieren `app/tasks.py` (pendiente).

### Talleres

```bash
cd ~/Proyectos/SAAS-Gestion_Talleres

# Modo gateway (desactiva traefik_router propio):
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d

# Modo standalone (Traefik propio en :8180, sin micronuba-infra):
docker compose -f docker-compose.dev.yml up -d

# Verificar: http://api.talleres.local:8090/api
#            http://talleres.local:8090
```

### CRM

```bash
cd ~/Proyectos/CRM-Comercial

# Modo gateway (desactiva nginx intermediario):
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Modo standalone (acceso directo :3000):
docker compose up -d   # usa docker-compose.override.yml automáticamente

# Verificar: http://crm.micronuba.local:8090
```

### PLAGIE

```bash
cd ~/Proyectos/Colegios/PLAGIE-SaaS

# Modo gateway (desactiva gateway nginx y certbot):
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Modo standalone (acceso directo :8000):
docker compose up -d

# Verificar: http://plagie.micronuba.local:8090
```

### Portal MicroNuba

```bash
cd ~/Proyectos/"Portal MicroNuba"

# Modo gateway:
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Modo standalone (acceso directo :8080):
docker compose up -d

# Verificar: http://portal.micronuba.local:8090
```

---

## Cheatsheet — arranque completo

```bash
# 1. Gateway
cd ~/Proyectos/micronuba-infra && docker compose up -d

# 2. Inventarios
cd ~/Proyectos/"SAAS - Plataforma Gestion Inventarios"
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d api

# 3. Talleres
cd ~/Proyectos/SAAS-Gestion_Talleres
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d

# 4. CRM
cd ~/Proyectos/CRM-Comercial
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# 5. PLAGIE
cd ~/Proyectos/Colegios/PLAGIE-SaaS
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# 6. Portal
cd ~/Proyectos/"Portal MicroNuba"
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

### URLs de verificación

| URL | Esperado |
|-----|---------|
| `http://localhost:8888` | Traefik dashboard |
| `http://api.inventarios.local:8090/health` | `{"status":"healthy",...}` |
| `http://api.inventarios.local:8090/docs` | Swagger UI |
| `http://api.talleres.local:8090/api` | Talleres API |
| `http://talleres.local:8090` | Talleres Frontend |
| `http://crm.micronuba.local:8090` | CRM App |
| `http://plagie.micronuba.local:8090` | PLAGIE (Laravel) |
| `http://portal.micronuba.local:8090` | Portal MicroNuba |

---

## Comandos del día a día

```bash
# Estado de todos los containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Containers conectados al gateway
docker network inspect micronuba_public --format '{{range .Containers}}{{.Name}} {{end}}'

# Logs del gateway
docker logs -f micronuba-traefik

# Detener una app (el gateway sigue activo)
cd ~/Proyectos/SAAS-Gestion_Talleres
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml down

# Detener el gateway al final del día
cd ~/Proyectos/micronuba-infra && docker compose down
```

---

## Solución de problemas

### El container no aparece en el dashboard de Traefik

```bash
# Confirmar que está en micronuba_public
docker network inspect micronuba_public --format '{{range .Containers}}{{.Name}} {{end}}'

# Confirmar labels
docker inspect <container> | grep -A2 traefik
```

### "Connection refused" al acceder por el gateway

```bash
docker logs micronuba-traefik 2>&1 | tail -30
docker compose ps   # verificar que el overlay está activo
```

### Dominio .local no resuelve

```bash
grep -E "talleres|inventarios|crm|plagie|portal" /etc/hosts
```

### Conflicto de puerto al arrancar

```bash
lsof -i :8090   # Traefik gateway
lsof -i :80     # PLAGIE gateway (si está levantado en modo standalone)
```

### Inventarios worker/beat en Restarting

`inv-worker` e `inv-beat` requieren `app/tasks.py` que aún no existe. Arrancar solo la API:
```bash
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d api postgres redis
```

### macOS — Error al construir socket-proxy

```bash
cd ~/Proyectos/micronuba-infra
docker compose build --no-cache
docker compose up -d
```
