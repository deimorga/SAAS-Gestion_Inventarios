# Conectar tu proyecto al gateway local de MicroNuba

Este documento explica cómo conectar cualquier proyecto al gateway centralizado
`micronuba-infra` para desarrollo local. Seguirlo no modifica tu proyecto —
solo agrega un archivo de overlay que usás cuando querés trabajar con el gateway.

---

## ¿Qué es el gateway?

`micronuba-infra` levanta un **Traefik** en el puerto `:8090` de tu máquina.
Todos los proyectos pueden enrutarse a través de él usando dominios `.local`
en lugar de acceder directamente por puerto.

```
curl http://api.tu-proyecto.local:8090   →  Traefik  →  tu-container:puerto
```

Ventajas frente al acceso directo por puerto:
- Mismo patrón de URLs que producción (sin puertos, con subdominios)
- Un solo punto de entrada para todos los proyectos
- Fácil de encender/apagar por proyecto sin tocar los otros

---

## Prerequisitos

### 1. Clonar y levantar el gateway

```bash
git clone git@github.com:micronuba/micronuba-infra.git ~/Proyectos/micronuba-infra
cd ~/Proyectos/micronuba-infra

# Primera vez: construir el socket-proxy
docker compose build

# Levantar
docker compose up -d
```

Verificar que está sano:
```bash
docker compose ps
# NAME                     STATUS
# micronuba-socket-proxy   Up (healthy)
# micronuba-traefik        Up (healthy)
```

Dashboard disponible en: **http://localhost:8888**

### 2. macOS — variable de socket

Crear `~/Proyectos/micronuba-infra/.env` con:

```env
DOCKER_SOCKET=/Users/<tu-usuario>/.docker/run/docker.sock
```

Reemplazar `<tu-usuario>` con el resultado de `whoami`.

> En Linux/WSL2 esto no hace falta (el socket está en `/var/run/docker.sock` por defecto).

---

## Paso 1 — Agregar el dominio a `/etc/hosts`

Elegí el subdominio que va a usar tu proyecto y agregalo:

```bash
# macOS / Linux
sudo sh -c 'echo "127.0.0.1  api.tu-proyecto.local" >> /etc/hosts'

# Si tenés frontend además de API:
sudo sh -c 'echo "127.0.0.1  api.tu-proyecto.local tu-proyecto.local" >> /etc/hosts'
```

> **Dominios ya configurados en el equipo:**
> `api.inventarios.local`, `api.talleres.local`, `talleres.local`,
> `crm.micronuba.local`, `plagie.micronuba.local`, `portal.micronuba.local`

---

## Paso 2 — Crear `docker-compose.local.yml`

En la raíz de tu proyecto, creá el archivo `docker-compose.local.yml`.
Este archivo es un *overlay* — se combina con tu compose existente y solo
sobreescribe lo que necesita cambiar.

### Plantilla base

```yaml
# Overlay para desarrollo local con micronuba-infra.
# Uso: docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d
#
# Requiere:
#   - micronuba-infra corriendo (Traefik en :8090, red micronuba_public activa)
#   - /etc/hosts: 127.0.0.1  api.tu-proyecto.local

services:
  nombre-del-servicio:                          # ← nombre en tu docker-compose
    networks:
      - micronuba_public
      - tu-red-interna                          # ← red(es) que ya usa el servicio
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.mi-proyecto-local.rule=Host(`api.tu-proyecto.local`)"
      - "traefik.http.routers.mi-proyecto-local.entrypoints=web"
      - "traefik.http.services.mi-proyecto-local.loadbalancer.server.port=8000"
      - "traefik.docker.network=micronuba_public"

networks:
  micronuba_public:
    external: true
```

### Valores a reemplazar

| Placeholder | Qué poner |
|-------------|-----------|
| `nombre-del-servicio` | El nombre del servicio en tu `docker-compose.dev.yml` (ej. `api`, `backend_api`, `app`) |
| `tu-red-interna` | Las redes que ese servicio ya usa en tu compose (mantenerlas todas) |
| `mi-proyecto-local` | Un nombre único para el router de Traefik, sin espacios (ej. `talleres-api-local`) |
| `api.tu-proyecto.local` | El dominio que elegiste en el paso anterior |
| `8000` | El puerto interno que expone tu container (el que está en tu `Dockerfile` o `EXPOSE`) |

### Ejemplo real — API Python con `app-net` y `data-net`

```yaml
services:
  api:
    networks:
      - micronuba_public
      - app-net
      - data-net
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.inventarios-api-local.rule=Host(`api.inventarios.local`)"
      - "traefik.http.routers.inventarios-api-local.entrypoints=web"
      - "traefik.http.services.inventarios-api-local.loadbalancer.server.port=8000"
      - "traefik.docker.network=micronuba_public"

networks:
  micronuba_public:
    external: true
```

### Si tu proyecto tiene un router/gateway propio

Si tu `docker-compose.dev.yml` levanta su propio Traefik, nginx, o cualquier
proxy en un puerto local, deshabilitalo en el overlay para evitar conflictos:

```yaml
services:
  traefik_router:        # o gateway, nginx-proxy, etc.
    profiles: ["disabled"]

  api:
    networks:
      - micronuba_public
      - ...
    labels:
      - ...
```

---

## Paso 3 — Levantar con el overlay

```bash
# Bajar primero si ya estaba levantado (para que tome los nuevos labels y redes)
docker compose -f docker-compose.dev.yml down

# Levantar con el overlay
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d
```

> Si tu proyecto no tiene `docker-compose.dev.yml` y usa el `docker-compose.yml` base:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
> ```

---

## Verificación

### Confirmar que el container está en la red del gateway

```bash
docker network inspect micronuba_public --format '{{range .Containers}}{{.Name}} {{end}}'
# Debe aparecer tu container
```

### Confirmar que Traefik lo descubrió

Abrí el dashboard: **http://localhost:8888**

En **HTTP → Routers** debe aparecer `mi-proyecto-local` con estado verde.

### Probar el endpoint

```bash
curl http://api.tu-proyecto.local:8090/health
# o cualquier endpoint que tenga tu API
```

---

## Modo standalone (sin gateway)

El overlay no modifica tu compose base. Para volver a trabajar sin el gateway:

```bash
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d
# Acceso directo: http://localhost:<puerto>
```

---

## Solución de problemas

### El router no aparece en el dashboard

```bash
# 1. Verificar que el container está en micronuba_public
docker network inspect micronuba_public --format '{{range .Containers}}{{.Name}} {{end}}'

# Si no aparece: el overlay no se aplicó correctamente
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml ps

# 2. Verificar los labels del container
docker inspect <nombre-container> | grep -A1 traefik
```

### "no such network: micronuba_public"

El gateway no está levantado. Iniciarlo primero:
```bash
cd ~/Proyectos/micronuba-infra && docker compose up -d
```

### El dominio no resuelve

```bash
grep tu-proyecto /etc/hosts
# Si no aparece: volver al Paso 1
```

### El container aparece en la red pero da 502 Bad Gateway

El container está registrado en Traefik pero no responde en el puerto configurado.
Verificar que el puerto en el label `loadbalancer.server.port` coincide con el que
usa internamente tu aplicación (no el puerto del host — el del container).

```bash
docker logs <nombre-container> | tail -20
```
