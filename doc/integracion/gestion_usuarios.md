# Gestión de usuarios y recuperación de contraseña — guía de integración

> Última actualización: 2026-11-06 · Estado: **implementado (migración 016)**, pendiente de revisión y despliegue.
> Definición: [RF_gestion_usuarios.md](../Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md) (RF-046 a RF-052) y [DT_gestion_usuarios.md](../Definicion-Tecnica/09_gestion_usuarios/DT_gestion_usuarios.md).

Un `tenant_admin` gestiona a su equipo por API, y cualquier usuario activa su cuenta y recupera su
contraseña con un enlace enviado por email. El portal admin usa estos mismos endpoints.

---

## Estados de un usuario

El estado se deriva de dos campos y la respuesta lo trae ya calculado en `status`.

| `status` | `is_active` | `must_change_password` | Significado |
|---|---|---|---|
| `pending` | `false` | `true` | Creado; aún no fijó su contraseña con el enlace de activación |
| `active` | `true` | `false` | Puede iniciar sesión |
| `disabled` | `false` | `false` | Un administrador lo desactivó; no puede iniciar sesión |

---

## 1. Equipo del tenant — `/v1/users`

Requieren `tenant_admin` (JWT) o una API Key con scope `ADMIN`. Solo ven y tocan usuarios de su propio tenant.

| Método | Endpoint | Qué hace |
|---|---|---|
| `GET` | `/v1/users?status=&q=&page=&size=` | Lista. `status`: `active`, `pending` o `disabled`. `q` busca en email y nombre |
| `POST` | `/v1/users` | Crea un usuario **pendiente** y le envía el email de activación |
| `PATCH` | `/v1/users/{user_id}` | Cambia nombre, rol o estado |
| `POST` | `/v1/users/{user_id}/password-reset` | Fuerza el reseteo: envía el email y cierra sus sesiones |
| `POST` | `/v1/auth/resend-activation/{user_id}` | Reenvía la activación a un usuario pendiente |

```json
// POST /v1/users
{ "email": "ana@cliente.com", "full_name": "Ana Pérez", "role": "viewer" }

// 201
{
  "id": "…", "tenant_id": "…", "email": "ana@cliente.com", "full_name": "Ana Pérez",
  "role": "viewer", "is_active": false, "must_change_password": true, "status": "pending",
  "is_protected": false, "last_login_at": null, "created_at": "2026-11-06T15:00:00Z"
}
```

```json
// PATCH /v1/users/{user_id} — todos los campos son opcionales
{ "full_name": "Ana P. Gómez", "role": "inventory_manager", "is_active": false }
```

**Reglas**

- **Roles asignables:** `inventory_manager` y `viewer`. Sin `role`, se crea `viewer`. Un `tenant_admin`
  no crea ni asciende a otros `tenant_admin` (lo hace el super_admin). `api_consumer` ya no existe como rol.
- **Email único en toda la plataforma**, sin distinguir mayúsculas. Se guarda en minúsculas. El login
  también lo compara así. No se puede cambiar el email de un usuario existente.
- **No se puede tocar a otro `tenant_admin`**, ni desactivarse a uno mismo, ni cambiarse el propio rol.
- **Un usuario pendiente no se activa a mano:** se activa con su enlace (`PATCH … is_active: true` → `409`).
  Un desactivado sí se puede reactivar.
- **Desactivar cierra sus sesiones al momento:** su siguiente request recibe `401`. Las API Keys no se ven afectadas.
- **No hay borrado:** los usuarios se desactivan.
- **Reseteo y reenvío:** el reseteo solo aplica a usuarios `active`; el reenvío de activación, solo a `pending`.
  Nadie —ni un administrador— ve ni fija la contraseña de otro: solo se envían emails.
- **Cuenta protegida (`is_protected: true`):** la cuenta raíz del ambiente. No se puede desactivar, editar ni resetear: `403 Cuenta raíz protegida`.
- **Auditoría:** cada acción queda en `GET /v1/audit-logs` (`entity = users`): `CREATE`, `UPDATE` (con valores anterior y nuevo), `DEACTIVATE`, `REACTIVATE`, `RESEND_ACTIVATION`, `FORCE_PASSWORD_RESET`, `ACTIVATE` y `PASSWORD_RESET`. Si actuó una API Key, `performed_by.type` es `api_key`.

---

## 2. Activar la cuenta y recuperar la contraseña — endpoints públicos

No requieren autenticación: el token del email es la credencial. El portal ofrece las páginas
`/activate`, `/forgot-password` y `/reset-password`.

| Método | Endpoint | Qué hace |
|---|---|---|
| `POST` | `/v1/auth/activate` | Fija la contraseña con el token de activación (TTL 48 h, un solo uso) |
| `POST` | `/v1/auth/forgot-password` | Envía el enlace para restablecer la contraseña |
| `POST` | `/v1/auth/reset-password` | Fija la contraseña nueva con el token del email |

```json
// POST /v1/auth/activate           → 200 { "message": "Cuenta activada exitosamente", "email": "ana@cliente.com" }
{ "token": "…", "password": "una-contraseña-de-12-o-más" }

// POST /v1/auth/forgot-password    → 202, SIEMPRE el mismo cuerpo
{ "email": "ana@cliente.com" }
// { "message": "Si el email está registrado, recibirás un enlace en unos minutos." }

// POST /v1/auth/reset-password     → 200 { "message": "Contraseña actualizada. Ya puedes iniciar sesión." }
{ "token": "…", "new_password": "una-contraseña-de-12-o-más" }
```

**`forgot-password`**

- Responde **igual exista o no el email**, esté activo o no: no permite averiguar qué emails tienen cuenta.
- Usuario activo → recibe el enlace (TTL 60 min, un solo uso). Pendiente → se le reenvía la activación.
  Desactivado o de un tenant suspendido → no se envía nada.
- Pedir un enlace nuevo invalida el anterior.
- **Límite:** 3 solicitudes por email y hora, y 10 por IP y hora → `429` con `Retry-After`. Es el único caso que no responde `202`.
- Si llamas desde un servidor, reenvía la IP real del usuario en `X-Forwarded-For` para que el límite cuente por usuario.

**`reset-password`**

- Cierra **todas** las sesiones del usuario, borra sus intentos fallidos de login (si estaba bloqueado, entra de inmediato) y le envía un aviso de contraseña cambiada.
- El cambio voluntario (`POST /v1/auth/change-password`) **no** cierra las demás sesiones.

**Política de contraseña:** mínimo **12 caracteres**, igual en activación, cambio y reseteo. Las contraseñas
anteriores, de 8, siguen valiendo hasta que se cambien.

---

## 3. Errores

| HTTP | `detail` | Cuándo |
|---|---|---|
| `400` | `El enlace no es válido o caducó.` | Token de reseteo inexistente, usado, caducado o reemplazado |
| `401` | `Sesión cerrada. Vuelve a iniciar sesión.` | El access token es anterior a una revocación (usuario desactivado o contraseña restablecida) |
| `403` | `Cuenta raíz protegida` | Se intentó modificar o resetear la cuenta raíz |
| `403` | `No puedes gestionar a otro tenant_admin` / `No puedes desactivarte a ti mismo` / `No puedes cambiar tu propio rol` | Reglas del `tenant_admin` |
| `403` | `Un tenant_admin no puede crear usuarios con rol '…'` | Rol no asignable |
| `404` | `Usuario no encontrado` | Usuario inexistente o de otro tenant |
| `409` | `El email ya está registrado` | Email ya usado en **cualquier** tenant |
| `409` | `El usuario está pendiente de activación…` | Activar a mano un pendiente, o resetear a uno pendiente |
| `409` | `El usuario está desactivado` / `La cuenta está desactivada` | Resetear o reenviar activación a un desactivado |
| `410` | `Token de activación inválido o expirado` | Token de activación inexistente, usado, caducado, o el usuario ya no está pendiente |
| `422` | (validación) | Contraseña de menos de 12 caracteres, rol fuera de la lista, `status` inválido |
| `429` | `Demasiadas solicitudes. Inténtalo de nuevo más tarde.` | Límite de `forgot-password` |

---

## 4. Superficie de super_admin (la usa el portal)

Requieren JWT `super_admin`. Mismo contrato que `/v1/users`, sobre cualquier tenant.

| Método | Endpoint |
|---|---|
| `GET` · `POST` | `/admin/tenants/{tenant_id}/users` |
| `PATCH` | `/admin/tenants/{tenant_id}/users/{user_id}` |
| `POST` | `/admin/tenants/{tenant_id}/users/{user_id}/password-reset` |
| `POST` | `/admin/tenants/{tenant_id}/users/{user_id}/resend-activation` |
| `GET` · `POST` | `/admin/super-admins` |
| `PATCH` | `/admin/super-admins/{user_id}` |
| `POST` | `/admin/super-admins/{user_id}/password-reset` |

- El super_admin puede asignar además el rol `tenant_admin`, y **nunca** `super_admin` por la ruta de usuarios.
- Los super_admins **no aparecen** en la lista de usuarios de un tenant, ni siquiera en la del tenant interno.
- Siempre debe quedar al menos un super_admin activo (`409`), y ninguno puede desactivarse a sí mismo (`403`).
- Los super_admins creados desde el portal **no** son cuenta raíz. La raíz es la del bootstrap (`POST /admin/auth/register`, solo para el primero de cada ambiente).
