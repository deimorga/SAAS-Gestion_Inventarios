# Revisión de código — Integración de Sprints 9 y 10 (2026-11-19)

**Rama revisada:** `feat/plan-de-sedes` (`3632294`), que incluye `feat/platform-sedes` y
`feature/sprint-9-gestion-usuarios`. Diff contra `main` (`065ca62`): 92 ficheros.
**Revisó:** Deiby Moreno (revisión asistida por Claude, esfuerzo alto)
**Responsable de las correcciones:** Cristian Anacona
**Estado:** desplegado en **staging** para pruebas. **Producción bloqueada** hasta cerrar los R marcados 🔴.

---

## Decisiones confirmadas por Deiby

- Límites por plan: STARTER 1.000 · PROFESSIONAL 3.000 · ENTERPRISE 10.000 req/min.
- Las cinco decisiones de `CLAUDE.md` del módulo 09 (migración 016 sin super_admins, `email` en
  `ActivationResponse`, pendiente-desactivar, rol propio del tenant_admin, refresh tokens previos).
  **Ojo:** R-03 corrige la tercera: desactivar a un pendiente debe tener efecto.

## Corregido al integrar

- `doc/integracion/plataforma_sedes.md` publicaba un `key_id` + `key_secret` completos (de la base
  local; no existían en staging ni en prod). Sustituidos por marcadores. **Regla:** en la
  documentación, nunca credenciales reales aunque sean de desarrollo: el repositorio es público.

---

## Hallazgos

🔴 = bloquea producción · 🟡 = corregir en el próximo sprint · ⚪ = menor

| ID | Prioridad | Fichero | Hallazgo |
|---|---|---|---|
| R-01 | 🔴 | `core_backend/app/main.py:55` | Una reserva que falla al liberarse detiene la expiración de reservas de **todos** los tenants, para siempre y en silencio |
| R-02 | 🔴 | `core_backend/app/services/reservation.py:162` | Reservas anteriores a la migración 015 pueden no poder cancelarse, confirmarse ni expirar (409), o liberar stock del saldo equivocado |
| R-03 | 🔴 | `core_backend/app/services/user_management.py:262` | Desactivar a un usuario pendiente no hace nada y su enlace de activación sigue sirviendo |
| R-04 | 🔴 | `core_backend/app/services/user_management.py:258` | Tras un cambio de rol, el usuario conserva los permisos anteriores hasta 30 min |
| R-05 | 🟡 | `core_backend/app/services/inventory.py:505` (y `:441`) | El stock histórico sin lote de un producto `track_lots` ya no se puede ajustar ni trasladar |
| R-06 | 🔴 | `core_backend/app/services/platform.py:60` | La key de plataforma (Appits) puede leer y dar de baja sedes que no creó, incluidas las creadas desde el panel |
| R-07 | 🟡 | `core_backend/app/services/platform.py:101` | Si el aprovisionamiento falla a medias, queda un tenant a medio construir que un reintento no arregla |
| R-08 | ⚪ | `core_backend/app/services/admin_tenant.py:47` | Dos altas simultáneas con el mismo email o `external_id` dan 500 en vez de 409 |
| R-09 | 🟡 | `core_backend/app/services/inventory.py:398` | Una salida con varios ítems del mismo saldo puede consumir stock reservado (fallo **anterior** a estos sprints) |
| R-10 | ⚪ | `core_backend/app/services/password_reset.py:50` | En desarrollo, el enlace de reseteo apunta al API (404): `ACTIVATION_BASE_URL` por defecto no es el portal |

### R-01 — La expiración de reservas se bloquea entera

- **Qué pasa:** el bucle llama a `expire_reservation` → `_release`, que puede lanzar `409` ("reserved_qty
  no puede ser negativo") o `404`. Una sola sesión cubre a todos los tenants, solo hace commit al final,
  y el error se traga con `except Exception: pass`: todo se deshace y la misma reserva vuelve a fallar
  cada minuto.
- **Escenario:** una reserva ACTIVE cuyo saldo tiene menos `reserved_qty` que su asignación (p. ej. una
  reserva antigua, ver R-02) vence → ninguna reserva de ningún tenant vuelve a pasar a EXPIRED y el
  stock reservado queda bloqueado.
- **Corrección:** cada reserva en su propia transacción o savepoint; registrar el fallo (`logger.exception`)
  y seguir con las demás. Nunca `except Exception: pass`.
- **Test:** dos reservas vencidas, una que falla al liberar → la otra sí expira y queda un log.

### R-02 — Reservas anteriores a la 015

- **Qué pasa:** el fallback de `_item_allocations` elige un saldo con
  `ORDER BY (bin_id IS NOT NULL), (lot_number IS NOT NULL), reserved_qty DESC`, y prefiere una fila sin
  lote aunque tenga `reserved_qty = 0`. El código anterior reservaba contra la fila que devolviera
  `fetchone()`, que podía tener lote.
- **Escenario:** producto con saldo sin lote (reservado 0) y saldo con lote (reservado 5) en la misma
  zona; reserva antigua de 5 → cancelar/confirmar elige la fila sin lote → 0 − 5 < 0 → 409. La reserva
  no se puede cancelar, confirmar ni expirar.
- **Corrección:** ordenar primero por `reserved_qty DESC` y exigir `reserved_qty >= cantidad`, o repartir
  la liberación entre las filas que de verdad tienen reservado.
- **Antes de prod:** contar en producción las reservas ACTIVE creadas antes de la 015.

### R-03 — Desactivar a un pendiente

- **Qué pasa:** pendiente = `is_active=false` y `must_change_password=true`. La rama
  `request.is_active is False and user.is_active` nunca se ejecuta y responde 200 sin cambios ni
  auditoría. `update_super_admin` (`super_admins.py:132`) tiene el mismo hueco.
- **Escenario:** se crea un usuario con el email equivocado y se desactiva → sigue "pendiente" → quien
  reciba el email lo activa en las siguientes 48 h y obtiene una cuenta activa.
- **Corrección:** al desactivar a un pendiente, `must_change_password=False` (pasa a "desactivado"),
  invalidar su token de activación y auditar `DEACTIVATE`. Esto **sustituye** la decisión "desactivar a
  un pendiente no hace nada".
- **Test:** crear → desactivar → `POST /v1/auth/activate` con el token original → 400.

### R-04 — Cambio de rol sin cerrar sesiones

- **Qué pasa:** `get_current_auth` toma el `role` del JWT y `update_user` cambia el rol sin
  `revoke_all_sessions` (sí lo hace al desactivar).
- **Escenario:** se baja un `tenant_admin` a `viewer` → durante 30 min sigue creando usuarios y
  cambiando roles.
- **Corrección:** `revoke_all_sessions(user.id, redis)` siempre que cambie el rol.
- **Test:** cambiar rol → el access token anterior da 401.

### R-05 — Stock histórico sin lote

- **Qué pasa:** `require_lot` en `process_adjustment` (y `process_transfer`, línea 441) devuelve 422 si
  el ítem no trae `lot_number`, aunque el propio código de reservas asume que existen saldos históricos
  sin lote.
- **Escenario:** portal → Stock → "Poner en 0" sobre una fila con lote "—" de un producto
  `track_lots=true` → 422. Ese stock no se puede corregir.
- **Corrección:** sin lote, permitir ajustes y traslados sobre un saldo sin lote **existente**; exigir lote
  solo cuando se cree un saldo nuevo, como en las entradas.

### R-06 — Alcance de la key de plataforma

- **Qué pasa:** `_get_platform_tenant` solo comprueba `external_provider IS NOT NULL`. Las sedes del panel
  llevan `external_provider='panel'` y `POST /admin/tenants` acepta cualquier proveedor. La documentación
  dice que la key solo gestiona los tenants que ella aprovisionó.
- **Escenario:** sede creada desde el panel → Appits llama a `DELETE /v1/platform/tenants/{id}` → la sede
  queda suspendida y sus API keys revocadas.
- **Corrección:** limitar `/v1/platform/*` a los proveedores de esa key (como mínimo,
  `external_provider != 'panel'`), o guardar qué key aprovisionó cada tenant y filtrar por ella.
- **Test:** sede del panel → `GET`/`DELETE` por plataforma → 404.

### R-07 — Aprovisionamiento a medias

- **Qué pasa:** `create_tenant` hace commit del tenant y del admin antes de crear almacén y key. Si un
  paso posterior falla, nada se deshace, y el reintento con el mismo `external_id` da 409 sin key.
- **Corrección:** deshacer (desactivar o borrar) el tenant si falla un paso posterior, o que el reintento
  complete el tenant existente y devuelva su key nueva.

### R-08 — 500 en altas simultáneas

- Capturar `IntegrityError` en el commit de `create_tenant` y devolver 409, como ya hace `create_user`.

### R-09 — Salida que consume stock reservado (anterior)

- `process_issue` valida cada ítem contra `available_qty` por separado, sin restar los anteriores del
  mismo saldo, y `_apply_balance_change` solo impide stock físico negativo.
- **Corrección:** sumar lo pedido por saldo antes de validar, o rechazar en `_apply_balance_change` si
  `new_available < 0`.

### R-10 — Enlace de reseteo en desarrollo

> **Estado: ✅ Corregido** · rama `fix/R-10-reset-url` · commit: _pendiente_
> **Cambio:** el valor por defecto de `ACTIVATION_BASE_URL` pasa del API (`http://api.inventarios.local:8090`)
> al portal de desarrollo (`http://localhost:8081`, el puerto de `docker-compose.dev.yml`) en
> `core/config.py`, `.env.example`, `CLAUDE.md` y `DT_admin_multitenant.md`. Se eligió cambiar el valor por
> defecto y no separar un `PORTAL_BASE_URL`: el activo y el de reseteo ya apuntan los dos al portal, así que
> una segunda variable solo duplicaría la configuración. Staging y prod no cambian: sus compose ya definen
> `ACTIVATION_BASE_URL` con la URL del portal.
> **Ojo local:** un `.env` ya creado conserva el valor viejo; hay que actualizarlo a mano.
> **Tests:** `tests/test_review_enlaces.py::test_r10_el_valor_por_defecto_es_el_portal_no_el_api`,
> `…::test_r10_los_enlaces_de_activacion_y_de_reseteo_apuntan_al_portal`
> (más `…::test_r10_el_ambiente_sigue_mandando_si_define_su_propia_url`, que protege que cada ambiente
> siga pudiendo fijar la suya).

- `reset_url` usa `ACTIVATION_BASE_URL`, cuyo valor por defecto (`config.py`, `.env.example`) es el API.
  Cambiar el valor por defecto al portal (`http://localhost:8081`) o separar `PORTAL_BASE_URL`.

---

## Cómo entregar las correcciones

- Una rama por grupo, desde `staging`: `fix/R-01-02-reservas`, `fix/R-03-04-usuarios`,
  `fix/R-06-07-08-plataforma`, `fix/R-05-09-inventario`, `fix/R-10-reset-url`. Un PR hacia `staging` cada una.
- Cada hallazgo con su test, que debe fallar sin la corrección.
- Con Claude: "Lee `doc/Planeacion/Revisiones/revision_2026-11-19_sprints_9_10.md` y corrige R-0x. Primero
  escribe el test que reproduce el escenario."
