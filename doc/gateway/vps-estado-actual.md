# Estado actual del VPS — Línea base pre-migración

> Relevado: 2026-04-29  
> Servidor: `srv1269581` — IP `148.230.82.172`  
> OS: Ubuntu 24.04 LTS (kernel 6.8.0) · Docker 29.4.0  
> Disco: 387 GB · 34 GB usados · 353 GB libres

---

## 1. Arquitectura actual (diagrama)

```
Internet
   │
   ├─ :80  ──► gateway-prod (nginx:alpine)
   └─ :443 ──► gateway-prod (nginx:alpine)
                  │
                  ├─ plagie.cloud / *.plagie.cloud
                  │     ├─ /storage/* ──► saas-minio-prod:9000
                  │     ├─ /api, /sanctum, /docs, /admin, /health
                  │     │       ──► saas-core-prod:8000
                  │     └─ /    ──► static files (/root/PLAGIE-SaaS/frontend/dist)
                  │
                  ├─ staging.plagie.cloud / *.staging.plagie.cloud
                  │     ├─ /storage/* ──► saas-minio:9000 (bucket plagie-staging-storage)
                  │     └─ /    ──► saas-core-staging:8000
                  │
                  └─ crm.micronuba.net
                        └─ / ──► 172.17.0.1:8080 (host bridge)
                                    └─► crm-nginx:80
                                            └─► crm-app:3000

   :8080 ──► crm-nginx (nginx:alpine) [solo accesible desde gateway-prod vía host bridge]
```

---

## 2. Containers en ejecución

### Proyecto `plagie-saas` — `/root/PLAGIE-SaaS/`

| Container | Imagen | Puertos expuestos | Estado |
|-----------|--------|-------------------|--------|
| `gateway-prod` | nginx:alpine | **0.0.0.0:80→80, 0.0.0.0:443→443** | Up 6d |
| `saas-core-prod` | saas-core-app:prod | 80/tcp (interno) | Up 6d ✓ healthy |
| `saas-worker-prod` | saas-core-app:prod | — | Up 12h |
| `saas-cron-prod` | saas-core-app:prod | — | Up 12h |
| `saas-db-prod` | pgvector/pgvector:pg15 | 127.0.0.1:5432→5432 | Up 13d ✓ healthy |
| `saas-redis-prod` | redis:alpine | — (interno) | Up 13d ✓ healthy |
| `saas-minio-prod` | minio/minio:latest | 127.0.0.1:9001→9001 | Up 13d |

### Proyecto `plagie-saas-staging` — `/root/PLAGIE-SaaS-Staging/`

| Container | Imagen | Puertos expuestos | Estado |
|-----------|--------|-------------------|--------|
| `saas-core-staging` | saas-core-app:prod | — (interno) | Up 13h ✓ healthy |
| `saas-worker-staging` | saas-core-app:prod | — | Up 13h |
| `saas-cron-staging` | saas-core-app:prod | — | Up 13h |
| `saas-db-staging` | pgvector/pgvector:pg15 | 127.0.0.1:5433→5432 | Up 11d ✓ healthy |
| `saas-redis-staging` | redis:7-alpine | 0.0.0.0:6380→6379 | Up 13d ✓ healthy |
| `saas-mail-staging` | axllent/mailpit | 0.0.0.0:1026→1025, 0.0.0.0:8026→8025 | Up 13d ✓ healthy |

### Proyecto `crm-comercial-micronuba` — `/root/crm-comercial-micronuba/`

| Container | Imagen | Puertos expuestos | Estado |
|-----------|--------|-------------------|--------|
| `crm-app-1` | crm-comercial-micronuba-crm-app | 3000/tcp (interno) | Up 30h |
| `crm-nginx-1` | nginx:alpine | **0.0.0.0:8080→80** | Up 5d |
| `crm-db-1` | postgres:15-alpine | 0.0.0.0:5435→5432 | Up 5d |
| `crm-minio-1` | minio/minio:latest | — (interno) | Up 5d |

---

## 3. Redes Docker actuales

| Red | Tipo | Miembros |
|-----|------|----------|
| `plagie-saas_plagie-prod-network` | bridge | **Todos los containers de prod + staging + gateway-prod** |
| `plagie-saas_plagie-network` | bridge | Vacía (sin uso) |
| `crm-comercial-micronuba_default` | bridge | crm-app, crm-nginx, crm-db, crm-minio |
| `bridge` (default) | bridge | — |

> **Nota:** Todos los containers de PLAGIE (prod y staging) comparten `plagie-prod-network`.  
> Staging no tiene red separada — depende de la misma red que prod.

---

## 4. Certificados SSL actuales

Montados en `gateway-prod` desde `/root/PLAGIE-SaaS/docker/certbot/conf`:

| Dominio | Ubicación en contenedor |
|---------|------------------------|
| `plagie.cloud` | `/etc/letsencrypt/live/plagie.cloud/` |
| `staging.plagie.cloud` | `/etc/letsencrypt/live/staging.plagie.cloud/` |
| `crm.micronuba.net` | `/etc/letsencrypt/live/crm.micronuba.net/` |

Los certs son gestionados por **certbot** (ACME HTTP challenge via `/var/www/certbot`).  
Cuando Traefik tome el control, gestionará sus propios certs via TLS challenge — los dominios no cambian.

---

## 5. Volúmenes Docker relevantes

| Volumen | Uso |
|---------|-----|
| `plagie-saas_saas-pgsql-prod` | PostgreSQL prod PLAGIE |
| `plagie-saas_saas-minio-prod` | MinIO prod PLAGIE |
| `plagie-saas_saas-redis-prod` | Redis prod PLAGIE |
| `plagie-saas_saas-logs-prod` | Logs prod PLAGIE |
| `plagie-saas_saas-db-staging-data` | PostgreSQL staging PLAGIE |
| `plagie-saas_saas-redis-staging-data` | Redis staging PLAGIE |
| `crm-comercial-micronuba_postgres_data` | PostgreSQL CRM |
| `crm-comercial-micronuba_minio_data` | MinIO CRM |

---

## 6. Ficheros de deploy en el VPS

```
/root/
├── PLAGIE-SaaS/
│   ├── docker-compose.yml          # base
│   ├── docker-compose.prod.yml     # override prod
│   ├── docker-compose.staging.yml  # override staging
│   ├── docker/
│   │   ├── nginx/nginx.prod.conf   # ← config montada en gateway-prod
│   │   └── certbot/                # ← certs SSL + challenge
│   └── frontend/dist/              # ← frontend Vue estático (montado en gateway-prod)
├── PLAGIE-SaaS-Staging/
│   └── (copia del repo, ramas staging)
└── crm-comercial-micronuba/
    └── docker-compose.yml
```

---

## 7. Hallazgos críticos para la migración

### 7.1 gateway-prod es el único punto de entrada público
Todos los dominios activos pasan por un único nginx en `:80/:443`.  
El staging de PLAGIE **no tiene gateway propio** — depende de `gateway-prod`.  
Al reemplazarlo con Traefik, todos los sitios se migran en el mismo corte.

### 7.2 CRM usa doble-hop vía host bridge
```
gateway-prod → 172.17.0.1:8080 (host bridge) → crm-nginx → crm-app:3000
```
Con Traefik se elimina este doble-hop: Traefik → crm-app directamente.  
Requiere que crm-app se una a `micronuba_public` y tenga labels Traefik.  
El `crm-nginx` puede eliminarse.

### 7.3 PLAGIE sirve frontend estático desde gateway-prod
`/root/PLAGIE-SaaS/frontend/dist` está montado en gateway-prod y servido directamente.  
Traefik no sirve archivos estáticos — **solución**: añadir un container `nginx-static` lightweight  
en el proyecto PLAGIE que sirva el frontend y reciba tráfico de Traefik.

### 7.4 Docker 29.4.0 en VPS — mismo problema que en Mac
Docker 29 requiere API ≥ 1.40; Traefik v3 pide 1.24 por defecto.  
`micronuba-infra` ya resuelve esto con el socket-proxy Go.  
En VPS (Linux) el socket está en `/var/run/docker.sock` — sin variable `DOCKER_SOCKET`.

### 7.5 Redes staging/prod mezcladas
Todos los containers (prod + staging) están en la misma red `plagie-prod-network`.  
Los containers de staging pueden resolver los de prod por nombre.  
Con Traefik esto se puede corregir: cada ambiente en su propia red interna,  
todos uniéndose a `micronuba_public` solo para la capa de routing.

---

## 8. Proyección de containers post-migración

```
ACTUALES (17 containers)
├── gateway-prod                    ← REEMPLAZADO por Traefik
├── crm-nginx                       ← ELIMINADO (Traefik lo reemplaza)
├── PLAGIE prod:    5 containers    ← se mantienen, agregan labels Traefik
├── PLAGIE staging: 6 containers    ← se mantienen, agregan labels Traefik
└── CRM:            3 containers    ← se mantienen (sin nginx propio)

POR AGREGAR
├── micronuba-infra: 2              (traefik + socket-proxy) ← NUEVO gateway global
├── PLAGIE nginx-static: 1         (serve frontend/dist)    ← nuevo por 7.3
├── Inventarios staging: 5         (api, worker, beat, postgres, redis)
├── Inventarios prod:    5
├── Talleres staging:    7         (api, worker, celery, postgres, redis, minio, frontend)
└── Talleres prod:       7

TOTAL PROYECTADO: ~48 containers
RAM en uso hoy: ~700 MB / 31.34 GB disponibles → amplio margen
Disco en uso:   34 GB / 387 GB → amplio margen
```

---

## 9. Dominios activos y futuros

| Dominio | Estado | Destino actual | Destino con Traefik |
|---------|--------|---------------|---------------------|
| `plagie.cloud` | PROD activo | gateway-prod → saas-core-prod | Traefik → saas-core-prod |
| `*.plagie.cloud` | PROD activo | gateway-prod → saas-core-prod | Traefik → saas-core-prod |
| `staging.plagie.cloud` | Staging activo | gateway-prod → saas-core-staging | Traefik → saas-core-staging |
| `crm.micronuba.net` | PROD activo | gateway-prod → crm-nginx → crm-app | Traefik → crm-app |
| `api.inventarios.micronuba.com` | Pendiente | — | Traefik → inv-api |
| `api.talleres.micronuba.com` | Pendiente | — | Traefik → talleres-api |
| `traefik.micronuba.com` | Pendiente | — | Traefik dashboard (auth) |
