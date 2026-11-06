# Definición Técnica — Módulo 09: Gestión de Usuarios y Recuperación de Acceso

**Versión:** 1.0
**Estado:** ✅ Implementado en local — pendiente de revisión y despliegue (T-916)
**Fecha:** 2026-11-05
**RF Cubiertos:** RF-046 a RF-052 — [RF_gestion_usuarios.md](../../Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md)
**Responsable de desarrollo:** Cristian Anacona
**Revisión:** Deiby Moreno
**Sprint:** Sprint 9 — [sprint_09.md](../../Planeacion/Sprints/sprint_09.md)

---

> [!IMPORTANT]
> Antes de empezar, leer en `CLAUDE.md` las **"Reglas que no se pueden saltar"** de RLS: nunca
> `set_config` a mano; `get_db()` (sentinel de super_admin) solo para localizar usuarios antes de
> conocer su tenant, y esos endpoints **nunca** devuelven datos de un tenant. Los endpoints públicos
> de este módulo (`forgot-password`, `reset-password`, `activate`) caen en ese caso.

> [!WARNING]
> **No correr la suite contra staging hasta completar T-917** (ver sprint). Hoy
> `tests/test_admin_auth.py` borra todos los super_admins de la base de datos que toque.

> [!CAUTION]
> **Lineamiento L-1 — cuenta raíz protegida.** El super_admin actual de cada ambiente
> (staging y producción) es la cuenta desde la que se crean todos los demás usuarios. **Ningún
> código, migración, script ni test puede borrarla, desactivarla, cambiarle el rol o el nombre, ni
> forzar su reseteo.** Se identifica con `users.is_protected = true` (migración 016). Ver los
> lineamientos L-1 a L-5 en la [definición funcional](../../Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md#lineamientos-del-requerimiento-obligatorios).

---

## 1. Estado de partida (código real a 2026-11-05)

| Pieza | Dónde | Situación |
|---|---|---|
| CRUD de usuarios por tenant_admin | `app/api/v1/endpoints/users.py`, `app/services/user_management.py`, `app/schemas/user_management.py` | Listar, crear y editar (`full_name`, `is_active`). Sin `role` en el PATCH, sin auditoría, rol por defecto `api_consumer` |
| Admin de usuarios | `app/api/admin/endpoints/admin_users.py` | Listar y reenviar activación. Patrón `_tenant_session(tenant_id)` con RLS del tenant: **reutilizarlo** |
| Activación / cambio de contraseña | `app/api/v1/endpoints/auth_activate.py`, `app/services/activation.py` | `activate_account` ya pone `is_active=True` y `must_change_password=False`. Mínimo 8 caracteres |
| Email de activación | `activation.activation_url()` → `<ACTIVATION_BASE_URL>/activate?token=…` | El portal no tiene `/activate`: **404** |
| Sesiones | `auth.issue_tokens`, `admin_auth._issue_admin_tokens` | `refresh:<token> → user_id` en Redis. Sin índice por usuario |
| JWT | `deps.get_current_auth` | No comprueba si el usuario sigue activo |
| Plantillas de email | `app/tasks.py` (`_TEMPLATES`) | Existen `account_activation`, `activation_resent`, `password_changed`. Falta `password_reset` |
| Auditoría | `app/services/audit.log_action` | Nadie la llama desde la gestión de usuarios |
| Portal | `web_frontend/app/main.py`, `web_frontend/app/api.py` | Sin páginas de usuarios. Un `tenant_admin` puede iniciar sesión (cascada en `api.admin_login`) |
| Migraciones | `alembic/versions/` | Última: `013_product_sale_price.py` |

---

## 2. Resumen de Endpoints

### 2.1 Superficie Admin — `/admin/*` (solo `super_admin`)

| Método | Endpoint | Cambio | Fichero |
|---|---|---|---|
| `GET` | `/admin/tenants/{tenant_id}/users?status=&q=&page=&size=` | Añadir filtros | `admin_users.py` |
| `POST` | `/admin/tenants/{tenant_id}/users` | Nuevo | `admin_users.py` |
| `PATCH` | `/admin/tenants/{tenant_id}/users/{user_id}` | Nuevo | `admin_users.py` |
| `POST` | `/admin/tenants/{tenant_id}/users/{user_id}/password-reset` | Nuevo | `admin_users.py` |
| `GET` | `/admin/super-admins` | Nuevo | `admin_super_admins.py` (nuevo) |
| `POST` | `/admin/super-admins` | Nuevo | `admin_super_admins.py` |
| `PATCH` | `/admin/super-admins/{user_id}` | Nuevo | `admin_super_admins.py` |
| `POST` | `/admin/super-admins/{user_id}/password-reset` | Nuevo | `admin_super_admins.py` |

### 2.2 Superficie Cliente — `/v1/*`

| Método | Endpoint | Auth | Cambio |
|---|---|---|---|
| `GET` | `/v1/users?status=&q=&page=&size=` | tenant_admin | Añadir filtros |
| `POST` | `/v1/users` | tenant_admin | Roles `inventory_manager`/`viewer`, defecto `viewer`, email global |
| `PATCH` | `/v1/users/{user_id}` | tenant_admin | Añadir `role`; prohibir autodesactivarse y tocar a otro tenant_admin |
| `POST` | `/v1/users/{user_id}/password-reset` | tenant_admin | Nuevo |
| `POST` | `/v1/auth/activate` | público | Política 12 caracteres; auditoría |
| `POST` | `/v1/auth/forgot-password` | público | Nuevo |
| `POST` | `/v1/auth/reset-password` | público | Nuevo |

---

## 3. Servicios — dónde vive la lógica

Toda la lógica nueva va en servicios; los endpoints solo validan y delegan (patrón del proyecto).

| Servicio | Funciones |
|---|---|
| `app/services/user_management.py` | `list_users(..., status, q)`, `create_user(..., actor)`, `update_user(..., actor)`, `request_password_reset_for(user, actor)` |
| `app/services/password_reset.py` (nuevo) | `request_reset(email, ip, db, redis)`, `issue_reset_token(user, redis)`, `reset_password(token, new_password, db, redis)` |
| `app/services/sessions.py` (nuevo) | `register_session(user_id, refresh_token, redis)`, `unregister_session(...)`, `revoke_all_sessions(user_id, redis)`, `is_revoked(user_id, iat, redis)` |
| `app/services/super_admins.py` (nuevo) | `list_super_admins`, `create_super_admin`, `update_super_admin`, con las reglas RN-049-1/2 |

Usa un único objeto "actor" para auditoría y permisos:

```python
@dataclass
class Actor:
    user_id: str
    role: str            # "super_admin" | "tenant_admin"
    ip: str | None       # login_throttle.client_ip(request): ya resuelve proxies de confianza
```

### 3.1 Reglas de permisos (un solo sitio)

Centralizar en `user_management.py` una función que decida qué rol puede asignar quién, y no
repartir `if` por los endpoints:

```python
ASSIGNABLE_ROLES = {
    "super_admin": {"tenant_admin", "inventory_manager", "viewer"},   # RN-047-1
    "tenant_admin": {"inventory_manager", "viewer"},                  # RN-048-1
}

def ensure_can_manage(actor: Actor, target: User, *, deactivating: bool = False) -> None:
    if target.is_protected:
        raise HTTPException(403, "Cuenta raíz protegida")                            # L-1, RN-049-5
    if actor.role == "tenant_admin":
        if target.role == "tenant_admin" and target.id != actor.user_id:
            raise HTTPException(403, "No puedes gestionar a otro tenant_admin")      # RN-048-2
        if deactivating and target.id == actor.user_id:
            raise HTTPException(403, "No puedes desactivarte a ti mismo")            # RN-048-3
    if target.role == "super_admin":
        raise HTTPException(404, "Usuario no encontrado")  # RN-049-4: no se gestionan por aquí
```

- `ensure_can_manage` se llama en **todas** las escrituras sobre usuarios de un tenant (PATCH,
  password-reset, resend-activation), antes de tocar nada.
- `super_admins.py` tiene su propia comprobación, con el **mismo primer paso**: si
  `target.is_protected`, `403` "Cuenta raíz protegida". Después: no desactivarse a sí mismo y no
  dejar 0 activos.
- La comprobación de `is_protected` va **en el servicio**, no solo en el portal: ocultar el botón
  no protege nada si el endpoint acepta la petición.

---

## 4. Contratos API

Formato de error: el del handler global (`detail`, `error_code`, `timestamp`, `request_id`).

### 4.1 POST `/admin/tenants/{tenant_id}/users` y POST `/v1/users`

```json
// Request
{ "email": "ana@cliente.com", "full_name": "Ana Pérez", "role": "viewer" }
```

- `email`: `EmailStr`, se normaliza con `.strip().lower()` antes de validar unicidad.
- `role`: en `/admin` uno de `tenant_admin|inventory_manager|viewer`; en `/v1` `inventory_manager|viewer`, por defecto `viewer`.

**Response `201`** — `UserResponse` (schema existente) + campo calculado `status`:

```json
{
  "id": "…", "tenant_id": "…", "email": "ana@cliente.com", "full_name": "Ana Pérez",
  "role": "viewer", "is_active": false, "must_change_password": true,
  "status": "pending", "last_login_at": null, "created_at": "2026-11-05T15:00:00Z"
}
```

`status` = `pending` si `not is_active and must_change_password`; `active` si `is_active`; `disabled` en otro caso.

| Error | Cuándo |
|---|---|
| `403` | Rol no asignable por el actor |
| `409` | Email ya registrado **en cualquier tenant** |
| `422` | Validación |

> **Unicidad global con RLS:** la sesión del endpoint tiene RLS del tenant y no ve usuarios de otros.
> La comprobación de email debe hacerse con una sesión de sistema (`set_system_context`) que **solo**
> responde sí/no (`SELECT 1 … WHERE lower(email)=:e`), sin devolver datos. La garantía final es el
> índice único de la migración 016: capturar `IntegrityError` y devolver `409`.

### 4.2 PATCH `/admin/tenants/{tenant_id}/users/{user_id}` y PATCH `/v1/users/{user_id}`

```json
{ "full_name": "Ana P. Gómez", "role": "inventory_manager", "is_active": false }
```

Todos opcionales. `is_active=false` → `revoke_all_sessions` (RF-051). Pasar a `is_active=true` a un
usuario **pendiente** no está permitido (`409`: debe activarse con su enlace).

| Error | Cuándo |
|---|---|
| `403` | `ensure_can_manage` o rol no asignable |
| `404` | Usuario de otro tenant (RLS) o super_admin |
| `409` | Activar a mano un usuario pendiente |

### 4.3 POST `…/users/{user_id}/password-reset` (admin, v1 y super-admins)

Sin body. Solo para usuarios `active`. Revoca sesiones y envía el email `password_reset`.

- **Response `202`:** `{ "message": "Email de reseteo enviado" }`
- **Errores:** `403`, `404`, `409` (pendiente o desactivado).

### 4.4 POST `/v1/auth/forgot-password` (público)

```json
{ "email": "ana@cliente.com" }
```

**Response `202` siempre** (RN-050-1), con el mismo cuerpo y un tiempo de respuesta similar:

```json
{ "message": "Si el email está registrado, recibirás un enlace en unos minutos." }
```

Lógica interna (`password_reset.request_reset`):

1. Contadores `pwd_forgot:email:<email>` (máx 3/h) y `pwd_forgot:ip:<ip>` (máx 10/h). Al superarlos:
   `429` con `Retry-After`. **Este es el único caso que no responde 202** (RN-050-5).
2. Buscar el usuario por email con sesión de sistema (`get_db`).
3. Si activo y su tenant activo → `issue_reset_token` + `send_email.delay(..., "password_reset", …)`.
4. Si pendiente → reenviar activación (`resend_activation`). Si desactivado o inexistente → nada.
5. El envío del email va a la cola de Celery: la respuesta no espera a que salga.

### 4.5 POST `/v1/auth/reset-password` (público)

```json
{ "token": "…", "new_password": "…" }
```

- `new_password`: `min_length=12` (RN-052-4).
- Proceso: `GET pwd_reset:<token>` → `user_id`; comprobar que es el token de `pwd_reset_user:<user_id>`;
  fijar hash; borrar ambas claves; `revoke_all_sessions`; borrar `login_fail:acct:<email>:*` (SCAN por
  patrón del email); auditar; encolar `password_changed`.
- **Response `200`:** `{ "message": "Contraseña actualizada. Ya puedes iniciar sesión." }`
- **Errores:** `400` token inválido/usado/caducado · `422` política.

### 4.6 `/admin/super-admins`

- `GET` → lista de super_admins (`UserResponse` + `status`), sin paginar (son pocos).
- `POST` `{ email, full_name }` → crea en el tenant `00000000-0000-0000-0000-000000000001`,
  `role=super_admin`, pendiente, email de activación. `201`. `409` email duplicado.
- `PATCH /{user_id}` `{ full_name?, is_active? }` → `403` si `user_id == actor`, `409` si deja 0 activos.
  Desactivar revoca sesiones.
- `POST /{user_id}/password-reset` → como 4.3.

La comprobación "queda al menos uno" debe ser atómica frente a dos desactivaciones simultáneas:
`SELECT … FOR UPDATE` sobre los super_admins activos dentro de la misma transacción.

---

## 5. Sesiones y revocación (RF-051)

### 5.1 Índice de sesiones por usuario

En **todos** los sitios donde se emite o rota un refresh token:

| Sitio | Acción |
|---|---|
| `auth.issue_tokens` | `SADD user_sessions:<uid> <refresh>` + `EXPIRE` = vida del refresh |
| `admin_auth._issue_admin_tokens` | Igual |
| `auth.refresh_session` (rota el token) | `SREM` el viejo, `SADD` el nuevo |
| `auth.logout` | `SREM` |

`revoke_all_sessions(uid)`: `SMEMBERS user_sessions:<uid>` → `DEL refresh:<t>` de cada uno →
`DEL user_sessions:<uid>` → `SET user_revoked_at:<uid> <now> EX <vida del access token>`.

### 5.2 Rechazo de access tokens

En `deps.get_current_auth`, rama JWT, después de decodificar:

```python
revoked_at = await redis.get(f"user_revoked_at:{user_id}")
if revoked_at and payload["iat"] <= int(revoked_at):
    raise HTTPException(401, "Sesión cerrada. Vuelve a iniciar sesión.")
```

Coste: un `GET` de Redis por request, igual que el del tier. Las API Keys no pasan por aquí (RN-051-3).

> Caso borde: un login en el mismo segundo de la revocación tendría `iat == revoked_at` y sería
> rechazado. Es aceptable; si molesta en tests, comparar con milisegundos.

---

## 6. Migración 016 — email único global y cuenta raíz protegida

> [!NOTE]
> **Implementada como `016_users_email_global_cuenta_raiz.py`** (`down_revision = "015"`): en esta rama la 014 es
> `tenant_external_ref` y la 015, `lot_location_traceability`. Una diferencia con el borrador de abajo: **no aborta si la
> base no tiene ningún super_admin** (una base nueva, como la de CI), porque el bootstrap creará el primero ya protegido.
> Solo aborta si existen super_admins y ninguno está activo. También levanta `FORCE ROW LEVEL SECURITY` de `users`
> mientras corre, como la 015, para que funcione con un rol dueño que no sea superusuario.

`alembic/versions/016_users_email_global_cuenta_raiz.py`:

```python
def upgrade():
    bind = op.get_bind()
    # 1. Abortar con un mensaje claro si hay duplicados (en prod no los hay a 2026-11-05)
    dup = bind.execute(sa.text(
        "SELECT lower(email) FROM users GROUP BY 1 HAVING count(*) > 1"
    )).fetchall()
    if dup:
        raise RuntimeError(f"Emails duplicados, resolver a mano antes de migrar: {dup}")
    # 2. Normalizar
    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))")
    # 3. Índice
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    # 4. Cuenta raíz protegida (L-1)
    op.add_column("users", sa.Column("is_protected", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.execute("UPDATE users SET is_protected = true WHERE role = 'super_admin' AND is_active")
    protegidas = bind.execute(sa.text("SELECT count(*) FROM users WHERE is_protected")).scalar()
    if protegidas == 0:
        raise RuntimeError("No hay ningún super_admin activo que proteger: revisar antes de migrar")

def downgrade():
    op.drop_column("users", "is_protected")
    op.drop_index("uq_users_email_lower", table_name="users")
```

- A 2026-11-05 hay **exactamente un** super_admin activo en cada ambiente, que es la cuenta raíz. La
  migración solo lo marca: **no** modifica su email, contraseña, nombre ni estado.
- Añadir `is_protected: Mapped[bool]` al modelo `app/models/user.py` y exponerlo en `UserResponse`,
  para que el portal muestre la etiqueta "Raíz".
- El bootstrap (`register_super_admin`, solo funciona si no hay ningún super_admin) crea la cuenta
  con `is_protected=True`: el primer super_admin de un ambiente nuevo es su cuenta raíz.

- Corre con `MIGRATION_DATABASE_URL`, como todas. Ese rol es el superusuario de PostgreSQL, y los
  superusuarios ignoran RLS aunque `users` lo tenga en FORCE: la consulta de duplicados ve todos los
  tenants. **No** correr esta migración con el rol de la app (`inv_app`): vería 0 filas y el chequeo
  no serviría.
- Login (`authenticate_user`, `login_admin_surface`): comparar con `func.lower(User.email) == email.lower()`.

---

## 7. Política de contraseña

Una sola constante, `PASSWORD_MIN_LENGTH = 12` en `app/core/security.py`, usada por los schemas de
activación, cambio, reseteo y registro de super_admin (hoy cada uno tiene su número).

---

## 8. Emails

Nueva plantilla en `_TEMPLATES` de `app/tasks.py`:

| Plantilla | Contexto | Enlace |
|---|---|---|
| `password_reset` | `full_name`, `reset_url`, `ttl_minutes` | `<ACTIVATION_BASE_URL>/reset-password?token=…` |

Reutilizar `ACTIVATION_BASE_URL` (ya apunta al portal en cada ambiente). Añadir
`reset_url(token)` junto a `activation_url(token)`.

En staging los emails llegan a Mailpit (`https://mail-staging.inventarios.micronuba.net`): ahí se
prueban todos los enlaces de punta a punta.

---

## 9. Auditoría (RN-052-5)

`log_action` con `entity="users"` en el tenant del usuario afectado (super_admins: tenant interno).

| Acción | `action` | `old_values` / `new_values` |
|---|---|---|
| Alta | `CREATE` | — / `{email, role}` |
| Edición | `UPDATE` | campos cambiados |
| Desactivar / reactivar | `DEACTIVATE` / `REACTIVATE` | — |
| Reenvío de activación | `RESEND_ACTIVATION` | — |
| Reseteo forzado | `FORCE_PASSWORD_RESET` | — |
| Reseteo completado | `PASSWORD_RESET` | — (nunca la contraseña ni el token) |
| Activación | `ACTIVATE` | — |

`performed_by = {"type": "user", "id": actor.user_id, "role": actor.role}`, `ip_address = actor.ip`.
Para `PASSWORD_RESET` y `ACTIVATE`, el actor es el propio usuario.

---

## 10. Portal (`web_frontend/`)

### 10.1 Páginas públicas

| Página | Llama a | Notas |
|---|---|---|
| `/activate?token=` | `POST /v1/auth/activate` | Dos campos + validación de 12 caracteres en cliente. Éxito → `/login?email=` |
| `/forgot-password` | `POST /v1/auth/forgot-password` | Siempre el mismo mensaje. Enlace desde `/login` |
| `/reset-password?token=` | `POST /v1/auth/reset-password` | Igual que `/activate` |

Estas páginas **no** deben exigir sesión: hoy las páginas del portal redirigen a `/login` si no hay
token; revisar ese guard. Reenviar `X-Forwarded-For` con la IP del navegador, como hace ya
`api.admin_login` (ver `page_login`), para que los límites de RN-050-5 cuenten por usuario y no
por el contenedor del portal.

### 10.2 `/tenants/{tenant_id}/users`

- Botón "Gestionar Usuarios" en el detalle del tenant, junto a Productos, Stock y Almacenes.
- Tabla + filtros + diálogos de crear / editar / confirmar desactivación (con el aviso de RN-047-3 si
  es el último tenant_admin activo).
- **Según el rol de la sesión** (`app.storage.user["role"]`), `web_frontend/app/api.py` llama a
  `/admin/tenants/{id}/users/*` (super_admin) o a `/v1/users/*` (tenant_admin). Un tenant_admin no
  puede abrir `/tenants/{otro_id}/users`: redirigir a su tenant.
- Mostrar el `detail` del API en los errores (como en la página de almacenes), no un código pelado.

### 10.3 `/super-admins`

Solo `super_admin`. Enlace en la cabecera de `/tenants`. Misma estructura que la tabla de usuarios.

---

## 11. Tests

Todos en `core_backend/tests/`. Cada test crea y borra **solo** sus datos.

| Fichero | Casos mínimos |
|---|---|
| `test_user_management.py` (ampliar) | Defecto `viewer`; `403` crear `tenant_admin` desde v1; `403` autodesactivarse; `403` tocar a otro tenant_admin; `409` email de otro tenant; `409` activar a mano un pendiente; PATCH de rol con auditoría `old/new` |
| `test_admin_users.py` (nuevo) | CRUD admin; `404` usuario de otro tenant; super_admin no aparece en la lista de un tenant |
| `test_super_admins.py` (nuevo) | Crear → pendiente en tenant interno y `is_protected=false`; `403` autodesactivarse; `409` dejar 0 activos; **`403` desactivar, editar o forzar reseteo de una cuenta protegida, y la cuenta queda intacta**; el dueño de una cuenta protegida sí puede usar `forgot-password` |
| `test_user_management.py` / `test_admin_users.py` | Un `tenant_admin` con `is_protected=true` (creado por el test) tampoco se puede tocar: la protección vale para cualquier rol |
| `test_password_reset.py` (nuevo) | `202` idéntico para email existente e inexistente; pendiente → reenvía activación; token de un solo uso; el segundo token invalida el primero; `429` al 4º en una hora; reseteo borra contadores de login; contraseña < 12 → `422` |
| `test_session_revocation.py` (nuevo) | Desactivar → el access token vigente da `401` en el siguiente request; refresh revocado; cambio voluntario (RF-040) **no** revoca; API Key sigue funcionando |
| `test_migration_016` o en `test_user_management.py` | Login con email en mayúsculas funciona |
| `test_admin_auth.py` (T-917) | El fixture solo borra super_admins con email `sa-test-*` creados por el propio test, **nunca** filas con `is_protected=true`; los tests que exigen tabla vacía (bootstrap) hacen `skip` si existe algún super_admin que no crearon |

Las cuentas que los tests marcan como protegidas usan emails `sa-test-*` / `test-*` y se borran en el
teardown con `DELETE … WHERE id = :id` (el id que crearon), nunca por rol ni por `is_protected`.

Validación del desarrollador: `ruff check app/ tests/`, `mypy app/` y la suite completa **en local**.
La ejecución contra staging la hace Deiby al revisar el PR, con la receta de `CLAUDE.md` y solo
después de T-917.

---

## 12. Despliegue (lo hace Deiby Moreno)

1. Staging primero (rama `develop`). Comprobar con Mailpit: activación, olvido de contraseña y reseteo forzado.
2. **Migración 016:** en prod, antes de desplegar, confirmar 0 duplicados con la consulta de la §6.
3. Prod: `alembic upgrade head` y recrear `api`, `admin-portal` y `worker` (plantilla de email nueva).
   Corte esperado ~15 s del API (ver `doc/gateway/ambientes-produccion-staging.md`). Fuera del
   horario de oficina de Colombia, y avisar a infra del commit y la hora.
4. Tras desplegar: reenviar la activación a los `tenant_admin` pendientes de AWP PERFORMANCE y
   AutolavadoDemo desde la página nueva, y confirmar que el enlace funciona.
5. **Resend en producción no está verificado de punta a punta.** Hacer una prueba real (p. ej.
   "olvidé mi contraseña" con una cuenta propia) antes de dar el módulo por cerrado.

---

## 13. Guía para desarrollar con Claude

Cristian desarrolla este módulo con Claude Code. Claude carga `CLAUDE.md` automáticamente, y ahí
están los lineamientos de este módulo (sección *Trabajo en curso: Módulo 09*). Esta guía completa lo
que no cabe allí.

### 13.1 Cómo trabajar

- **Una tarea del sprint por sesión o por PR** (T-901, T-902…), en el orden de
  [sprint_09.md](../../Planeacion/Sprints/sprint_09.md). Empezar siempre por T-917.
- **Rama de trabajo:** `feature/T-9xx-descripcion` creada desde `staging`, con Pull Request hacia
  `staging`. Deiby revisa, hace el merge y despliega. Nadie más empuja a `main`.
- **Tests primero:** para cada regla de negocio, escribir el test que la prueba, verlo fallar y
  luego implementar. Los criterios de aceptación de las HU-USR del RF son la lista mínima.
- **Antes de abrir el PR:** `ruff check app/ tests/`, `mypy app/` y la suite completa en local, con
  la base de datos del `docker-compose.dev.yml`.

### 13.2 Lo que Claude NO debe hacer

| Prohibido | Por qué |
|---|---|
| Tocar la cuenta raíz (`is_protected=true`) en código, migraciones, scripts o tests | L-1 |
| Correr tests o scripts contra staging o producción | Escriben en sus bases de datos reales; el 2026-10-26 un test borró el super_admin de staging. Se prueba en local; staging lo valida Deiby |
| Conectarse al VPS, desplegar o reiniciar contenedores | Despliega solo Deiby, con aviso a infra (hay tenants reales en producción) |
| `DELETE` de usuarios reales, o `DELETE`/`UPDATE` filtrando por rol | L-3 y L-4 |
| `set_config('app.current_tenant', …)` a mano | Usar `set_tenant_context` / `set_system_context` (`CLAUDE.md`) |
| Devolver datos de un tenant desde endpoints con `get_db()` | `get_db()` salta RLS; solo sirve para localizar el usuario |
| Guardar o registrar contraseñas, hashes o tokens en logs o `audit_logs` | DoD del sprint |
| Cambiar los permisos de los roles | Fuera de alcance: no se rediseñan los roles |

### 13.3 Prompt de arranque sugerido

Para cada tarea, abrir Claude Code en la raíz del repo y empezar con algo como:

```text
Vamos a desarrollar la tarea T-9xx del Sprint 9.
Lee doc/Planeacion/Sprints/sprint_09.md, la definición funcional
doc/Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md y la técnica
doc/Definicion-Tecnica/09_gestion_usuarios/DT_gestion_usuarios.md.
Respeta los lineamientos L-1 a L-5 y la sección 13.2 de la DT.
Primero dime qué ficheros vas a tocar y qué tests vas a escribir; no escribas
código hasta que lo confirme. Trabaja en la rama feature/T-9xx-… desde staging.
```

### 13.4 Si algo no está definido

Si una decisión no está en el RF ni en la DT, **no la inventes**: anótala en el PR como pregunta para
Deiby. Si es bloqueante, se decide y se añade aquí antes de seguir.
