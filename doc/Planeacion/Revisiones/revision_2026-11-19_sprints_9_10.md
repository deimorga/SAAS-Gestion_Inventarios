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

> **Estado: ✅ Corregido** · rama `fix/R-06-07-08-plataforma` · commit: `98b7b53`
> **Cambio:** opción mínima de la revisión. `_get_platform_tenant` (`services/platform.py`) excluye
> `external_provider = 'panel'`, así que `GET`/`DELETE /v1/platform/tenants/{id}` responden 404 a una
> sede del panel; `GET …/by-external/panel/{id}` también da 404; y `POST /v1/platform/tenants` rechaza
> `external_provider: "panel"` con 422 (si no, la plataforma podría crear tenants que luego no ve). No
> se guarda qué key aprovisionó cada tenant: hoy hay una sola plataforma (Appits). Si llega otra, ese
> es el siguiente paso. `doc/integracion/plataforma_sedes.md` actualizado.
> **Tests:** `tests/test_review_plataforma.py::test_r06_plataforma_no_ve_ni_da_de_baja_una_sede_del_panel`,
> `…::test_r06_plataforma_no_puede_crear_tenants_como_panel`.

- **Qué pasa:** `_get_platform_tenant` solo comprueba `external_provider IS NOT NULL`. Las sedes del panel
  llevan `external_provider='panel'` y `POST /admin/tenants` acepta cualquier proveedor. La documentación
  dice que la key solo gestiona los tenants que ella aprovisionó.
- **Escenario:** sede creada desde el panel → Appits llama a `DELETE /v1/platform/tenants/{id}` → la sede
  queda suspendida y sus API keys revocadas.
- **Corrección:** limitar `/v1/platform/*` a los proveedores de esa key (como mínimo,
  `external_provider != 'panel'`), o guardar qué key aprovisionó cada tenant y filtrar por ella.
- **Test:** sede del panel → `GET`/`DELETE` por plataforma → 404.

### R-07 — Aprovisionamiento a medias

> **Estado: ✅ Corregido** · rama `fix/R-06-07-08-plataforma` · commit: `98b7b53`
> **Cambio:** `provision_tenant` es todo o nada. Tras crear tenant y admin, el resto (almacén, key,
> auditoría) va en `_complete_provisioning`; si falla, `_undo_provisioning` borra el tenant recién
> creado por id (todas las FK hacia `tenants` son `ON DELETE CASCADE`: se va su admin, almacén, zonas y
> key) y responde 500 «no se creó nada; se puede reintentar» (un `HTTPException` propio conserva su
> código). El reintento con el mismo `external_id` crea la sede completa y devuelve su key. El email de
> activación del admin sale solo cuando la sede está completa (`create_tenant(notify_admin=False)` +
> `notify_tenant_admin`); antes se mandaba un enlace que quedaba muerto.
> Tras una revisión independiente se afinó: el aviso al admin (Redis/Celery) se registra pero ya no tumba
> una sede completa, que perdería su key (solo se devuelve una vez); y `_undo_provisioning` informa si
> pudo borrar: si no, el 500 trae el `tenant_id` y dice que no se pudo deshacer, en vez de prometer «no se
> creó nada».
> **Tests:** `tests/test_review_plataforma.py::test_r07_si_falla_un_paso_no_queda_nada_y_el_reintento_completa`
> (dos casos: `falla_la_key`, `falla_el_almacen`),
> `…::test_r07_si_falla_el_ultimo_paso_se_deshace_aunque_ya_haya_key_y_almacen`,
> `…::test_r07_si_no_se_puede_deshacer_el_500_no_dice_que_no_se_creo_nada`,
> `…::test_r07_si_falla_solo_el_aviso_al_admin_la_sede_se_devuelve_completa`.

- **Qué pasa:** `create_tenant` hace commit del tenant y del admin antes de crear almacén y key. Si un
  paso posterior falla, nada se deshace, y el reintento con el mismo `external_id` da 409 sin key.
- **Corrección:** deshacer (desactivar o borrar) el tenant si falla un paso posterior, o que el reintento
  complete el tenant existente y devuelva su key nueva.

### R-08 — 500 en altas simultáneas

> **Estado: ✅ Corregido** · rama `fix/R-06-07-08-plataforma` · commit: `98b7b53`
> **Cambio:** `create_tenant` (`services/admin_tenant.py`) captura `IntegrityError` en el commit, hace
> rollback y responde 409 con el motivo según el índice (`uq_tenants_external_ref`, `idx_tenants_slug`,
> `uq_users_email_lower`). Si choca el `external_id`, el `detail` es el mismo que el de un reintento,
> con el `tenant_id` del que ganó, que es lo que la plataforma usa para recuperar la sede.
> Tras la revisión independiente: PostgreSQL reporta el primer índice único que choca, y un reintento
> **idéntico** (mismo nombre → mismo slug) choca antes por `idx_tenants_slug` que por el `external_id`.
> Ahora, en cualquier choque, si el `external_id` ya existe se responde el 409 con `tenant_id`; si solo
> chocó un slug calculado por el sistema, el 409 dice que otra alta con el mismo nombre estaba en curso.
> **Tests:** `tests/test_review_plataforma.py::test_r08_dos_altas_simultaneas_con_el_mismo_external_id_dan_201_y_409`
> y `…::test_r08_el_mismo_alta_enviada_dos_veces_a_la_vez_responde_409_con_el_tenant_existente`.
> La carrera es determinista: una barrera en `commit` retiene las dos altas hasta que ambas pasaron
> las comprobaciones previas. Antes del cambio una de las dos lanzaba `IntegrityError` (500).

- Capturar `IntegrityError` en el commit de `create_tenant` y devolver 409, como ya hace `create_user`.

### R-09 — Salida que consume stock reservado (anterior)

- `process_issue` valida cada ítem contra `available_qty` por separado, sin restar los anteriores del
  mismo saldo, y `_apply_balance_change` solo impide stock físico negativo.
- **Corrección:** sumar lo pedido por saldo antes de validar, o rechazar en `_apply_balance_change` si
  `new_available < 0`.

### R-10 — Enlace de reseteo en desarrollo

- `reset_url` usa `ACTIVATION_BASE_URL`, cuyo valor por defecto (`config.py`, `.env.example`) es el API.
  Cambiar el valor por defecto al portal (`http://localhost:8081`) o separar `PORTAL_BASE_URL`.

---

## Cómo entregar las correcciones

- Una rama por grupo, desde `staging`: `fix/R-01-02-reservas`, `fix/R-03-04-usuarios`,
  `fix/R-06-07-08-plataforma`, `fix/R-05-09-inventario`, `fix/R-10-reset-url`. Un PR hacia `staging` cada una.
- Cada hallazgo con su test, que debe fallar sin la corrección.
- Con Claude: "Lee `doc/Planeacion/Revisiones/revision_2026-11-19_sprints_9_10.md` y corrige R-0x. Primero
  escribe el test que reproduce el escenario."
