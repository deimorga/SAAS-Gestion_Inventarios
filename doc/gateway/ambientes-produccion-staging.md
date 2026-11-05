# Ambientes Producción y Staging — Inventarios SaaS

> Documento creado: 2026-06-25 · Última actualización: 2026-10-27
> Estado: **Producción operativa ✅** · **Staging operativo ✅**

> 🔒 **Este repositorio es público.** La IP y el acceso al servidor, sus directorios, los nombres
> de los ficheros de secretos y los datos de las cuentas viven en el repositorio privado
> `micronuba-infra`. Aquí se usan marcadores:
>
> | Marcador | Qué es |
> |---|---|
> | `<DIR_PROD>` | Directorio de despliegue de producción en el VPS |
> | `<DIR_STAGING>` | Directorio de despliegue de staging en el VPS |
> | `<VPS>` | Acceso SSH al servidor |
> | `<EMAIL_SUPER_ADMIN>` | Cuenta super_admin de cada ambiente |
>
> Saneado el 2026-10-27; ver [`ci-diagnostico-y-estrategia.md`](../Arquitectura/ci-diagnostico-y-estrategia.md).
> El historial de git conserva las versiones anteriores.

## Estado de ramas (2026-10-27)

`main`, `develop` y `staging` convergen en `afbe623`.

| Rama | Rol | Dónde corre |
|---|---|---|
| `main` | Producción | `<DIR_PROD>` |
| `develop` | Staging | `<DIR_STAGING>` |

> ⚠️ **Regla que originó el incidente del 401**: producción despliega desde `main`, y `main`
> DEBE recibir merge al cerrar cada sprint. Entre mayo y agosto de 2026 dejó de recibirlos, y
> producción corrió tres meses con un fallo que ya estaba arreglado en `develop`.

---

## Arquitectura de ambientes

```
Internet
  :80 / :443
    │
  Traefik v3 (repo micronuba-infra) ← compartido con toda la infra MicroNuba
    │                                  IP fija 172.22.0.254 en micronuba_public
    ├── api.inventarios.micronuba.net          → inv-api:8000            (prod)
    ├── admin.inventarios.micronuba.net        → inv-admin-portal:8080   (prod)
    ├── staging.inventarios.micronuba.net      → inv-api-staging:8000    (staging)
    ├── staging-admin.inventarios.micronuba.net→ inv-admin-portal-staging:8080 (staging)
    └── mail-staging.inventarios.micronuba.net → inv-mailpit-staging:8025 (staging)
```

---

## Dominios y DNS

Todos los registros están en **Cloudflare**, zona `micronuba.net`.

| Dominio | Tipo | Proxy CF | Certificado |
|---|---|---|---|
| `api.inventarios.micronuba.net` | A → VPS | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `admin.inventarios.micronuba.net` | A → VPS | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `staging.inventarios.micronuba.net` | A → VPS | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `staging-admin.inventarios.micronuba.net` | A → VPS | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |
| `mail-staging.inventarios.micronuba.net` | A → VPS | DNS-only ⚪ | Let's Encrypt HTTP-01 (`le`) |

> **Importante**: los registros deben seguir en DNS-only (nube gris), por dos motivos:
> - El challenge HTTP-01 de Let's Encrypt fallaría con el proxy de Cloudflare (🟠).
> - El límite de intentos de login cuenta por la IP del cliente que añade Traefik. Con el proxy,
>   todos los usuarios llegarían con IPs de Cloudflare y compartirían contador.
>
> Infra tiene anotado no pasar `api.inventarios` ni `admin.inventarios` a proxy sin avisar
> antes. Si algún día se hace, la solución es configurar en Traefik
> `forwardedHeaders.trustedIPs` con los rangos de Cloudflare.

---

## Ambiente de Staging

### Rama y directorio
- **Rama Git**: `develop`
- **Directorio VPS**: `<DIR_STAGING>`
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
| `micronuba_public` | bridge externo, compartido | `inv-api-staging`, `inv-worker-staging`, `inv-admin-portal-staging`, `inv-mailpit-staging` + Traefik + contenedores de otros proyectos |
| `inv_app_staging` | bridge `internal` | `inv-api-staging`, `inv-worker-staging`, `inv-beat-staging`, `inv-redis-staging`, `inv-admin-portal-staging`, `inv-mailpit-staging` |
| `inv_data_staging` | bridge `internal` | `inv-api-staging`, `inv-worker-staging`, `inv-postgres-staging`, `inv-redis-staging` |

### Variables de entorno (.env)

| Variable | Valor en staging |
|---|---|
| `APP_ENV` | `staging` |
| `ENABLE_SWAGGER` | `true` |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | *(generados con `openssl rand -hex 24`)* |
| `APP_DB_USER` / `APP_DB_PASSWORD` | Rol de la app sin superuser ni BYPASSRLS |
| `JWT_SECRET_KEY`, `STORAGE_SECRET` | *(generados con `openssl rand -hex 32`)* |
| `ADMIN_BOOTSTRAP_SECRET` | *(generado con `openssl rand -hex 20`)* |
| `RESEND_API_KEY` | `re_staging_placeholder` *(no se usa — email va a Mailpit)* |
| `RESEND_FROM_EMAIL` | `staging@micronuba.net` |
| `ACTIVATION_BASE_URL` | `https://staging-admin.inventarios.micronuba.net` |

Fijadas en `docker-compose.staging.yml`: `SMTP_HOST=inv-mailpit-staging`, `SMTP_PORT=1025` y
`TRUSTED_PROXY_HOSTS=172.22.0.254,inv-admin-portal-staging` (ver
[Seguridad](#consideraciones-de-seguridad)).

> Los secretos reales están en el `.env` del directorio de despliegue (permisos 600, nunca en
> git). La contraseña de la UI de Mailpit va en un fichero aparte, también fuera de git: ver el
> comentario del servicio `mailpit` en `docker-compose.staging.yml`.

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
| Mailpit (emails, con usuario y contraseña) | `https://mail-staging.inventarios.micronuba.net` |

---

## Ambiente de Producción

### Rama y directorio
- **Rama Git**: `main`
- **Directorio VPS**: `<DIR_PROD>`
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
| `micronuba_public` | bridge externo, compartido con Traefik y con contenedores de otros proyectos |
| `inv_app` | bridge `internal` |
| `inv_data` | bridge `internal` |

### Variables de entorno (.env)

| Variable | Valor en producción |
|---|---|
| `APP_ENV` | `production` |
| `ENABLE_SWAGGER` | `false` |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | *(generados con `openssl rand -hex 24`)* |
| `APP_DB_USER` / `APP_DB_PASSWORD` | Rol de la app sin superuser ni BYPASSRLS |
| `JWT_SECRET_KEY`, `STORAGE_SECRET` | *(generados con `openssl rand -hex 32`)* |
| `ADMIN_BOOTSTRAP_SECRET` | *(vaciar después del bootstrap inicial)* |
| `RESEND_API_KEY` | API key real de Resend |
| `RESEND_FROM_EMAIL` | `notification.inventory@micronuba.net` |
| `RESEND_FROM_NAME` | `MicroNuba` |
| `ACTIVATION_BASE_URL` | `https://admin.inventarios.micronuba.net` |

Fijada en `docker-compose.prod.yml`: `TRUSTED_PROXY_HOSTS=172.22.0.254,inv-admin-portal`.

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

El dominio `micronuba.net` tiene publicados los registros de Resend (DKIM `resend._domainkey`
y SPF/MX en `send.micronuba.net`). Que figure como *verified* solo se ve en el panel de Resend.

---

## Comandos de operación

> Producción tiene tenants usando el inventario: **no tumbarla**. Recrear solo los servicios
> que el cambio toca (`up -d --no-deps --force-recreate <servicio>`). `git pull` y `build` no
> afectan a lo que está corriendo.
>
> | Qué se recrea | Corte para los tenants |
> |---|---|
> | `worker`, `beat` | Ninguno (la cola espera en Redis) |
> | `api` | ~8 s (502 y luego 404 de Traefik mientras redescubre el contenedor) |
> | `api` + `admin-portal` | ~15 s |
>
> Medido el 2026-10-27. Hacerlo fuera del horario de oficina de Colombia y avisar a infra del
> commit y la hora para su bitácora.

### Arrancar staging (primera vez)
```bash
ssh <VPS>
cd <DIR_STAGING>

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

### Bootstrap primer super_admin
```bash
curl -X POST https://<api del ambiente>/admin/auth/register \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Secret: <ADMIN_BOOTSTRAP_SECRET>" \
  -d '{"email":"<EMAIL_SUPER_ADMIN>","password":"<contraseña_min_12_chars>","full_name":"<nombre>"}'
```

> Los dos ambientes tienen ya su super_admin (tenant `micronuba-internal`). Las credenciales se
> guardan fuera del repo. Política de contraseña: mínimo 12 caracteres.
>
> Para resetear una contraseña olvidada sin que pase por ningún log, generar el hash dentro de
> `inv-api` con `getpass` y `app.core.security.hash_password`, y hacer el `UPDATE` con `psql`
> como owner. No usar `H=$(docker exec -it ...)`: con `-it` dentro de `$(...)` el prompt queda
> capturado y nunca pide la contraseña.

### Actualización rutinaria de staging

> ⚠️ **Al cerrar el sprint**, adelantar `main` para que producción no se quede atrás:
> `git checkout main && git merge --ff-only origin/develop && git push origin main`
> (ver [Estado de ramas](#estado-de-ramas-2026-10-27) al inicio del documento).

```bash
cd <DIR_STAGING>
git pull origin develop
docker compose -f docker-compose.staging.yml build api admin-portal
docker compose -f docker-compose.staging.yml up -d --no-deps --force-recreate api
docker compose -f docker-compose.staging.yml exec api alembic upgrade head
docker compose -f docker-compose.staging.yml up -d --no-deps --force-recreate worker beat admin-portal
```

### Arrancar producción (primera vez)
```bash
ssh <VPS>
cd <DIR_PROD>

# Build
docker compose -f docker-compose.prod.yml build api admin-portal

# Infraestructura
docker compose -f docker-compose.prod.yml up -d postgres redis
# Esperar ~15s

# API + migraciones
docker compose -f docker-compose.prod.yml up -d api
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Bootstrap super_admin: ver "Bootstrap primer super_admin"

# IMPORTANTE: vaciar ADMIN_BOOTSTRAP_SECRET en .env tras el bootstrap

# Resto de servicios
docker compose -f docker-compose.prod.yml up -d worker beat admin-portal
```

### Actualización rutinaria de producción
```bash
cd <DIR_PROD>
git pull --ff-only origin main      # ANTES del up: el compose también cambia (p. ej. TRUSTED_PROXY_HOSTS)
docker compose -f docker-compose.prod.yml build api admin-portal
# Solo si hay migraciones nuevas:
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m alembic upgrade head
# Solo lo que el cambio toca (ver la tabla de cortes):
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate worker beat
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate api admin-portal
```

Después: `docker ps` (todo `healthy`), `alembic current`, `/health` por la URL pública, y
`docker inspect inv-api | grep TRUSTED_PROXY_HOSTS`.

### Ver estado de contenedores
```bash
# Staging
docker compose -f <DIR_STAGING>/docker-compose.staging.yml ps

# Producción
docker compose -f <DIR_PROD>/docker-compose.prod.yml ps
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

- Los certs se almacenan en el volumen de Traefik (`acme.json`)
- Traefik renueva automáticamente antes del vencimiento (~30 días antes)
- El primer cert puede tardar 1-5 minutos en emitirse tras el primer request HTTPS

> Si Traefik muestra cert de auto-firma temporalmente, esperar unos minutos y refrescar.
> Los errores `503 Service Busy` de Let's Encrypt son transitorios — Traefik reintenta solo.

---

## Consideraciones de seguridad

| Item | Estado |
|---|---|
| Redes `inv_app` / `inv_data` con `internal: true` | ✅ El beat no tiene salida a internet. El worker sí, por `micronuba_public`, porque envía email por Resend |
| Secrets distintos entre prod y staging | ✅ Generados con `openssl rand` independientes |
| `.env` con permisos `600` en VPS | ✅ Solo root puede leer |
| Rol de la app sin superuser ni BYPASSRLS | ✅ `assert_rls_enforced` aborta el arranque si no |
| `ADMIN_BOOTSTRAP_SECRET` vacío post-bootstrap | ⚠️ Sin verificar en producción |
| Swagger deshabilitado en prod | ✅ `ENABLE_SWAGGER=false` |
| Rate limit por tenant según su plan | ✅ STARTER 60 / PROFESSIONAL 1.000 / ENTERPRISE 10.000 req/min |
| Límite de intentos de login | ✅ 5 fallos por cuenta + IP y 20 por IP → 429 durante 15 min |
| `X-Forwarded-For` solo de proxies de confianza | ✅ `TRUSTED_PROXY_HOSTS`: Traefik (172.22.0.254) y el portal del ambiente |
| UI de Mailpit (staging) con usuario y contraseña | ✅ Responde 401 sin credenciales |
| HTTPS forzado (redirect 80→443) | ✅ Configurado en Traefik global |

> **`micronuba_public` es una red compartida** con contenedores de otros proyectos, que llegan a
> `inv-api:8000` sin pasar por Traefik. Por eso `X-Forwarded-For` solo se cree de los orígenes
> de `TRUSTED_PROXY_HOSTS`. Si cambia la IP fija de Traefik, hay que actualizar esa variable en
> los dos compose; si no, todo el tráfico parecería venir de una sola IP y el límite de login
> bloquearía a todos juntos. Infra tiene registrada esta dependencia.

---

## Estado actual de los ambientes (2026-10-27)

### Staging — ✅ Operativo

| Componente | Estado | Notas |
|---|---|---|
| Contenedores (7) | Todos `Up` | api, worker, beat y admin-portal con la imagen de `afbe623` |
| Commit | `afbe623` | rama `develop` |
| Migraciones (001→013) | ✅ Aplicadas | |
| Rol de la app | ✅ `inv_app` | Sin superuser ni BYPASSRLS — RLS activo de verdad |
| Suite de tests | ✅ 343 passed, 1 skipped | Ejecutada dentro del propio ambiente |
| Super_admin | ✅ Creado | |
| Email (Mailpit) | ✅ Funcional | Entrega verificada por la cola de Celery |

### Producción — ✅ Operativa

| Componente | Estado | Notas |
|---|---|---|
| Commit | `afbe623` | rama `main`, desplegado el 2026-10-27 a las 04:39 UTC |
| Migraciones (001→013) | ✅ Aplicadas | |
| Rol de la app | ✅ `inv_app` | Sin superuser ni BYPASSRLS |
| Contenedores | ✅ `Up` | api/admin-portal `healthy`; los cuatro con la imagen de `afbe623` |
| Super_admin | ✅ | Uno solo; contraseña cambiada el 2026-10-27 |
| Auth por API Key | ✅ Verificada | Appits la usa con la key de cada taller |
| Almacén por defecto | ✅ | Los tenants nuevos nacen con `PRINCIPAL`; los anteriores al 2026-08-28 se crearon a mano |
| Resend en producción | ⚠️ Sin verificar | Ningún email real comprobado de punta a punta |

### Despliegue: el orden importa

Crear el rol restringido **antes** de subir el código. Si no, `assert_rls_enforced` aborta el
arranque a propósito:

```bash
cd <DIR_PROD>
echo "APP_DB_USER=inv_app"                     >> .env
echo "APP_DB_PASSWORD=$(openssl rand -hex 24)" >> .env
APP_DB_PASSWORD=... ./infra/postgres/create_app_role.sh inv-postgres inv_app

git pull origin main
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --force-recreate api worker beat admin-portal
```

> Los servicios de compose son `api`, `worker`, `beat`, `admin-portal`. `inv-api` es el
> `container_name`, no el nombre del servicio.
