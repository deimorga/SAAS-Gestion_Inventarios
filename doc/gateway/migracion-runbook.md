# Runbook de migración — gateway-prod → Traefik

> Basado en el estado relevado en `vps-estado-actual.md`  
> Tiempo estimado de downtime: **< 60 segundos**  
> Prerequisito: `vps-estado-actual.md` leído y entendido

---

## Prerequisitos (hacer ANTES del corte, sin downtime)

### P1 — Preparar PLAGIE: agregar nginx-static + labels Traefik

PLAGIE sirve frontend estático desde gateway-prod. Al eliminarlo, necesita un container
propio para servir `/frontend/dist`. Agregar al `docker-compose.prod.yml` de PLAGIE:

```yaml
services:
  nginx-static:
    image: nginx:alpine
    container_name: saas-nginx-static
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
    networks:
      - micronuba_public
      - plagie-prod-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.plagie-frontend.rule=Host(`plagie.cloud`) && !PathPrefix(`/api`,`/sanctum`,`/docs`,`/admin`,`/health`,`/storage`)"
      - "traefik.http.routers.plagie-frontend.entrypoints=websecure"
      - "traefik.http.routers.plagie-frontend.tls.certresolver=le"
      - "traefik.http.services.plagie-frontend.loadbalancer.server.port=80"

  saas-core-prod:
    networks:
      - micronuba_public   # ← agregar
      - plagie-prod-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.plagie-api.rule=Host(`plagie.cloud`) && PathPrefix(`/api`,`/sanctum`,`/docs`,`/admin`,`/health`)"
      - "traefik.http.routers.plagie-api.entrypoints=websecure"
      - "traefik.http.routers.plagie-api.tls.certresolver=le"
      - "traefik.http.services.plagie-api.loadbalancer.server.port=8000"

  saas-core-staging:
    networks:
      - micronuba_public   # ← agregar
      - plagie-prod-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.plagie-staging.rule=Host(`staging.plagie.cloud`)"
      - "traefik.http.routers.plagie-staging.entrypoints=websecure"
      - "traefik.http.routers.plagie-staging.tls.certresolver=le"
      - "traefik.http.services.plagie-staging.loadbalancer.server.port=8000"

networks:
  micronuba_public:
    external: true   # ← la posee micronuba-infra
```

### P2 — Preparar CRM: agregar labels Traefik, eliminar crm-nginx

```yaml
services:
  crm-app-1:
    networks:
      - micronuba_public   # ← agregar
      - crm-comercial-micronuba_default
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.crm.rule=Host(`crm.micronuba.net`)"
      - "traefik.http.routers.crm.entrypoints=websecure"
      - "traefik.http.routers.crm.tls.certresolver=le"
      - "traefik.http.services.crm.loadbalancer.server.port=3000"

networks:
  micronuba_public:
    external: true
```

### P3 — Desplegar micronuba-infra en el VPS (sin tocar :80/:443 aún)

```bash
# En el VPS
git clone git@github.com:micronuba/micronuba-infra.git /root/micronuba-infra
cd /root/micronuba-infra

# Crear red pública ANTES de arrancar
docker network create micronuba_public || true

# Arrancar en puerto alternativo para verificar (NO en prod aún)
# Editar docker-compose.yml temporalmente: cambiar "8090:80" → verificar descubrimiento
docker compose up -d
```

### P4 — Aplicar cambios P1 y P2 en apps (sin cortar gateway-prod)

```bash
# PLAGIE — los nuevos containers se unen a micronuba_public
# gateway-prod sigue funcionando EN PARALELO
cd /root/PLAGIE-SaaS
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx-static saas-core-prod saas-core-staging

# CRM — crm-app se une a micronuba_public, crm-nginx sigue activo
cd /root/crm-comercial-micronuba
docker compose up -d crm-app-1
```

### P5 — Verificar en Traefik dashboard (en puerto alternativo)

Acceder al dashboard de Traefik en el puerto temporal y confirmar que:
- `plagie.cloud` → saas-core-prod aparece como router activo
- `staging.plagie.cloud` → saas-core-staging aparece
- `crm.micronuba.net` → crm-app aparece

---

## Corte (~30-60 segundos de downtime)

```bash
# PASO 1: Detener gateway-prod (cae el tráfico)
docker stop gateway-prod

# PASO 2: Detener crm-nginx (ya no hace falta)
docker stop crm-comercial-micronuba-nginx-1

# PASO 3: Rearrancar micronuba-infra en :80/:443
cd /root/micronuba-infra
# Cambiar docker-compose.prod.yml para que use puertos 80/443
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# PASO 4: Verificar
curl -I https://plagie.cloud/health
curl -I https://staging.plagie.cloud/health
curl -I https://crm.micronuba.net
```

> Traefik solicita nuevos certs TLS via ACME al arrancar.  
> El proceso toma ~10-30 segundos por dominio.  
> Los certs anteriores siguen siendo válidos en el browser hasta que Traefik entrega los nuevos.

---

## Post-corte

```bash
# Eliminar containers obsoletos cuando todo esté estable
docker rm gateway-prod
docker rm crm-comercial-micronuba-nginx-1

# Los certs viejos de certbot ya no son necesarios (Traefik gestiona los suyos)
# Conservar el directorio /root/PLAGIE-SaaS/docker/certbot como backup por 30 días
```

---

## Rollback (si algo falla)

```bash
# Detener Traefik
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Reactivar gateway-prod
docker start gateway-prod

# Reactivar crm-nginx
docker start crm-comercial-micronuba-nginx-1
```

El rollback tarda ~10 segundos. Los containers de app nunca se detienen.
