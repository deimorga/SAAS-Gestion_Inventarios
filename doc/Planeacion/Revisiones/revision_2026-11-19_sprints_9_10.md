# Revisión de código — Integración de Sprints 9 y 10 (2026-11-19)

**Rama revisada:** `feat/plan-de-sedes` (`3632294`), que incluye `feat/platform-sedes` y
`feature/sprint-9-gestion-usuarios`. Diff contra `main` (`065ca62`): 92 ficheros.
**Revisó:** Deiby Moreno (revisión asistida por Claude, esfuerzo alto)
**Responsable de las correcciones:** Cristian Anacona
**Estado:** ✅ **Cerrada.** R-01 a R-10 y A-1 a A-3 corregidos (PRs #1–#7), revisados por Deiby y
desplegados: staging y **producción en `c441522`** el 2026-11-24 (prod a las 21:34 UTC, sin migraciones, corte de ~16 s).
Suite en staging: 530 ok, 2 skip; mypy limpio.

**Seguimiento abierto (menor, para Cristian):** al **reactivar** a un usuario que se desactivó estando pendiente
(R-03), queda `active` con la contraseña aleatoria del alta, que nadie conoce; solo podría entrar con «olvidé mi
contraseña», y si su email estaba mal escrito, quien lo reciba también. Debería volver a `pending` (p. ej. si
`last_login_at` es nulo) y pedir reenviar la activación.

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

> **Estado: ✅ Corregido** · rama `fix/R-01-02-reservas` · commit: `8dd526a`
> **Cambio:** el bucle pasa a `expire_due_reservations()` (`services/reservation.py`). Cada reserva se
> expira en su propia sesión y transacción; si una falla, se hace rollback solo de ella, se registra con
> `logger.exception` (id de reserva y tenant) y se sigue con las demás. `main.py` ya no usa
> `except Exception: pass`: registra el fallo general. La función acepta `tenant_ids` para que los tests
> solo toquen sus datos.
> **Tests:** `tests/test_review_reservas.py::test_r01_una_reserva_que_falla_no_detiene_la_expiracion_de_las_demas`,
> `…::test_r01_un_tenant_que_falla_al_prepararse_no_detiene_a_los_demas`.
> Tras una revisión independiente, el aislamiento también cubre el paso previo por tenant (fijar su contexto y
> listar sus reservas vencidas): un fallo ahí se registra y se sigue con el siguiente tenant.

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

> **Estado: ✅ Corregido** · rama `fix/R-01-02-reservas` · commit: `8dd526a`
> **Cambio:** `_item_allocations` (rama sin asignaciones) solo considera filas con `reserved_qty > 0`,
> la que más tiene primero, y si una no alcanza reparte la cantidad entre varias. Si entre todas no
> suman lo reservado, `409` con el motivo («Saldo reservado insuficiente…») en vez de dejar
> `reserved_qty` negativo. Vale para cancelar, confirmar y expirar.
> **Tests:** `tests/test_review_reservas.py::test_r02_cancelar_una_reserva_antigua_libera_el_saldo_que_de_verdad_la_tiene`,
> `…::test_r02_confirmar_una_reserva_antigua_despacha_del_saldo_reservado`,
> `…::test_r02_una_reserva_antigua_vencida_expira`,
> `…::test_r02_lo_reservado_repartido_en_varias_filas_se_libera_de_todas`,
> `…::test_r02_si_no_alcanza_lo_reservado_responde_409_con_motivo`,
> `…::test_r02_una_reserva_antigua_no_se_lleva_lo_apartado_por_una_nueva`.
> Tras una revisión independiente: `reserved_qty` de una fila suma **todas** las reservas, también las nuevas
> (con asignaciones). El reparto de la antigua descuenta de cada fila lo que explican las asignaciones de
> reservas ACTIVE y solo reparte el remanente; si no, con una reserva antigua y una nueva en la misma zona
> liberaba la fila de la nueva, dejaba la suya apartada para siempre y bloqueaba la cancelación de la nueva.
> **Sigue pendiente antes de prod:** contar en producción las reservas ACTIVE creadas antes de la 015.

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

> **Estado: ✅ Corregido** · rama `fix/R-03-04-usuarios` · commit: `20f7e92`
> **Cambio:** `update_user` (`services/user_management.py`) y `update_super_admin`
> (`services/super_admins.py`) desactivan también a un pendiente: `is_active=False`,
> `must_change_password=False` (pasa a "desactivado"), auditan `DEACTIVATE`, cierran sus sesiones y
> borran de Redis sus enlaces de activación con la nueva `revoke_activation_tokens(user_id, redis)`
> (`services/activation.py`). Los tokens se guardan como `activation:<token>` → user_id, sin índice por
> usuario, así que se recorren con `SCAN` y se borran los que apuntan a él. Aunque quedara algún token,
> `activate_account` ya lo rechaza con **410** porque el usuario dejó de estar pendiente; tampoco se le
> puede reenviar la activación (409). Si se reactiva, entra con «olvidé mi contraseña».
> **Correcciones a esta revisión:** (1) el test espera **410**, no 400: es lo que responde
> `activate_account` a un token que no sirve (`user.is_active or not user.must_change_password`).
> (2) El hueco de `update_super_admin` se corrigió en el mismo cambio, con su test.
> Tras una revisión independiente se afinó: (1) `revoke_activation_tokens` solo se llama al desactivar a un
> **pendiente** (recorre todo el keyspace de Redis; no hacía falta en cada desactivación); (2) `activate_account`
> lee al usuario con `FOR UPDATE`: si un admin lo está desactivando en ese instante, la activación espera y lee
> el estado nuevo (sin el bloqueo activaba a un usuario recién desactivado). `update_super_admin` ya bloqueaba
> su fila. Reactivar a un ex-pendiente lo deja activo **sin contraseña**: entra por «olvidé mi contraseña»
> (no se le manda ningún email al reactivarlo).
> **Tests:** `tests/test_review_usuarios.py::test_r03_tenant_admin_desactiva_un_pendiente_y_su_enlace_deja_de_servir`,
> `…::test_r03_super_admin_desactiva_un_pendiente_de_un_tenant`,
> `…::test_r03_desactivar_un_super_admin_pendiente_invalida_su_enlace`,
> `…::test_r03_desactivar_a_un_pendiente_no_toca_el_enlace_de_otro_y_borra_todos_los_suyos`,
> `…::test_r03_solo_se_recorre_redis_al_desactivar_a_un_pendiente`,
> `…::test_r03_un_pendiente_desactivado_y_reactivado_entra_por_olvide_mi_contrasena`,
> `…::test_r03_activar_y_desactivar_a_la_vez_deja_al_usuario_desactivado`.

- **Qué pasa:** pendiente = `is_active=false` y `must_change_password=true`. La rama
  `request.is_active is False and user.is_active` nunca se ejecuta y responde 200 sin cambios ni
  auditoría. `update_super_admin` (`super_admins.py:132`) tiene el mismo hueco.
- **Escenario:** se crea un usuario con el email equivocado y se desactiva → sigue "pendiente" → quien
  reciba el email lo activa en las siguientes 48 h y obtiene una cuenta activa.
- **Corrección:** al desactivar a un pendiente, `must_change_password=False` (pasa a "desactivado"),
  invalidar su token de activación y auditar `DEACTIVATE`. Esto **sustituye** la decisión "desactivar a
  un pendiente no hace nada".
- **Test:** crear → desactivar → `POST /v1/auth/activate` con el token original → ~~400~~ **410**
  (ver la corrección arriba).

### R-04 — Cambio de rol sin cerrar sesiones

> **Estado: ✅ Corregido** · rama `fix/R-03-04-usuarios` · commit: `20f7e92`
> **Cambio:** `update_user` llama a `revoke_all_sessions(user.id, redis)` siempre que cambie el rol,
> tanto desde el tenant_admin (`PATCH /v1/users/{id}`) como desde el super_admin
> (`PATCH /admin/tenants/{id}/users/{uid}`). Cambiar solo el nombre no cierra la sesión.
> `update_super_admin` no cambia roles, así que no aplica.
> **Tests:** `tests/test_review_usuarios.py::test_r04_bajar_de_rol_a_un_tenant_admin_cierra_su_sesion`,
> `…::test_r04_cambiar_el_rol_desde_el_tenant_admin_tambien_cierra_la_sesion`,
> `…::test_r04_cambiar_solo_el_nombre_no_cierra_la_sesion`,
> `…::test_r04_el_refresh_token_anterior_tampoco_sirve_tras_cambiar_el_rol`.

- **Qué pasa:** `get_current_auth` toma el `role` del JWT y `update_user` cambia el rol sin
  `revoke_all_sessions` (sí lo hace al desactivar).
- **Escenario:** se baja un `tenant_admin` a `viewer` → durante 30 min sigue creando usuarios y
  cambiando roles.
- **Corrección:** `revoke_all_sessions(user.id, redis)` siempre que cambie el rol.
- **Test:** cambiar rol → el access token anterior da 401.

### R-05 — Stock histórico sin lote

> **Estado: ✅ Corregido** · rama `fix/R-05-09-inventario` · commit: `21cd13f`
> **Cambio:** `process_adjustment` y `process_transfer` (`services/inventory.py`) buscan primero el saldo
> existente y solo exigen `lot_number` (`require_lot`) cuando no hay saldo que corregir o mover. Un saldo
> histórico sin lote de un producto con `track_lots=true` se puede poner en 0, ajustar y trasladar (el
> traslado lo deja sin lote en el destino, igual que en el origen). Un saldo **nuevo** sin lote sigue
> rechazándose con 422, como en las entradas.
> **Tests:** `tests/test_review_inventario.py::test_r05_poner_en_cero_un_saldo_historico_sin_lote`,
> `…::test_r05_trasladar_un_saldo_historico_sin_lote`,
> `…::test_r05_sin_lote_y_sin_saldo_existente_sigue_exigiendo_lote`,
> `…::test_r05_con_lote_indicado_el_ajuste_funciona_como_siempre`.

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

> **Estado: ✅ Corregido** · rama `fix/R-05-09-inventario` · commit: `21cd13f`
> **Cambio:** dos capas. (1) `process_issue` y `process_transfer` suman lo ya pedido de cada saldo por los
> ítems anteriores antes de validar contra `available_qty`, y responden 409 antes de tocar nada.
> (2) `_apply_balance_change` rechaza con 409 cualquier descuento que deje `available_qty < 0`, así que
> también protege al reempaque (que tenía el mismo patrón) y a cualquier llamador futuro. La red de
> seguridad solo frena los **descuentos**: una entrada sobre un saldo que un ajuste dejó por debajo de lo
> reservado sigue pasando, y los ajustes (`allow_negative=True`) no cambian.
> **Tests:** `tests/test_review_inventario.py::test_r09_dos_items_del_mismo_saldo_no_consumen_lo_reservado`,
> `…::test_r09_lo_justo_para_el_disponible_si_se_despacha`,
> `…::test_r09_items_de_saldos_distintos_no_se_suman_entre_si`,
> `…::test_r09_dos_items_del_mismo_saldo_en_un_traslado_tampoco_consumen_lo_reservado`,
> `…::test_r09_un_reempaque_tampoco_consume_lo_reservado`.

- `process_issue` valida cada ítem contra `available_qty` por separado, sin restar los anteriores del
  mismo saldo, y `_apply_balance_change` solo impide stock físico negativo.
- **Corrección:** sumar lo pedido por saldo antes de validar, o rechazar en `_apply_balance_change` si
  `new_available < 0`.

### R-10 — Enlace de reseteo en desarrollo

> **Estado: ✅ Corregido** · rama `fix/R-10-reset-url` · commit: `cd3d62e`
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

### A-3 — Una API key de solo lectura podía escribir (hallazgo adicional)

> **Estado: ✅ Corregido** · rama `fix/api-key-scopes` · commit: `07a6551`
> No estaba en esta revisión; apareció al probar los Sprints 9 y 10 y es anterior a ellos.
> **Qué pasaba:** `require_roles` traducía los scopes de una API key a roles y le daba el más alto.
> `READ_INVENTORY`/`READ_CATALOG` daban `inventory_manager`, así que una key de solo lectura creaba almacenes,
> registraba entradas y productos. Además `WRITE_CATALOG` abría las escrituras de inventario y
> `MANAGE_RESERVATIONS` las entradas.
> **Cambio (`api/deps.py`):** los scopes de lectura dan solo `viewer`; las escrituras exigen a la API key el
> scope de `doc/integracion/api_scopes.md`: catálogo `WRITE_CATALOG`; movimientos, conteos, bulk y snapshots
> `WRITE_INVENTORY`; almacenes y bins `MANAGE_WAREHOUSES` o `WRITE_INVENTORY`; reservas y cuotas por canal
> `MANAGE_RESERVATIONS` o `WRITE_INVENTORY`; lotes `WRITE_CATALOG` o `WRITE_INVENTORY`. `ADMIN` conserva el
> acceso total. Los usuarios con JWT no cambian. La key de una sede de Appits (todos los scopes) no pierde nada.
> **Tests:** `tests/test_api_key_scopes.py` (6).

---

## Cómo entregar las correcciones

- Una rama por grupo, desde `staging`: `fix/R-01-02-reservas`, `fix/R-03-04-usuarios`,
  `fix/R-06-07-08-plataforma`, `fix/R-05-09-inventario`, `fix/R-10-reset-url`. Un PR hacia `staging` cada una.
- Cada hallazgo con su test, que debe fallar sin la corrección.
- Con Claude: "Lee `doc/Planeacion/Revisiones/revision_2026-11-19_sprints_9_10.md` y corrige R-0x. Primero
  escribe el test que reproduce el escenario."

---

## Hallazgos adicionales (revisión independiente de las correcciones)

No estaban en esta revisión: los encontró una segunda revisión de las ramas de corrección. Son anteriores a
los Sprints 9 y 10.

### A-1 — Una reserva se podía liberar o despachar dos veces

> **Estado: ✅ Corregido** · rama `fix/reservas-webhooks-concurrencia` (sobre `fix/R-01-02-reservas`) · commit: `e047f8c`
> **Qué pasaba:** confirmar, cancelar y expirar leían el estado de la reserva sin bloquear la fila. Prod corre
> 4 workers, cada uno con su bucle de expiración: dos podían expirar la misma reserva, o una cancelación por
> API cruzarse con la expiración, y liberarla dos veces (`available_qty` inflado, posible sobreventa). Una
> confirmación podía despachar una reserva que otro proceso acababa de cancelar.
> **Cambio:** `_get_reservation_or_404(..., lock=True)` lee con `FOR UPDATE`; confirmar y cancelar la usan, y
> `expire_reservation` bloquea la reserva, vuelve a comprobar que siga ACTIVE y devuelve si la expiró (el
> bucle solo cuenta las que sí).
> **Tests:** `tests/test_concurrencia_bucles.py::test_cancelar_una_reserva_que_otro_proceso_esta_cerrando_no_la_libera_dos_veces`,
> `…::test_confirmar_una_reserva_que_otro_proceso_esta_cerrando_no_despacha`,
> `…::test_expirar_una_reserva_que_otro_proceso_esta_cerrando_no_la_libera_dos_veces`.

### A-2 — Webhooks reenviados duplicados y errores tragados

> **Estado: ✅ Corregido** · rama `fix/reservas-webhooks-concurrencia` · commit: `e047f8c`
> **Qué pasaba:** el despacho (`main.py`) usaba una sola sesión para todos los tenants, con commit al final y
> `except Exception: pass`. Un error tardío deshacía el estado de entregas ya enviadas por HTTP y el siguiente
> ciclo las reenviaba; los 4 workers, además, podían enviar la misma entrega a la vez.
> **Cambio:** la lógica pasa a `dispatch_pending_webhooks()` (`services/webhook.py`): cada entrega en su
> propia transacción, reclamada con `FOR UPDATE SKIP LOCKED`; un error se registra con `logger.exception` y se
> sigue. `main.py` solo llama a la función y registra un fallo general. La entrega sigue siendo «al menos una
> vez»: si el commit falla después del POST, se reintenta.
> **Test:** `tests/test_concurrencia_bucles.py::test_un_fallo_en_una_entrega_no_hace_reenviar_las_que_ya_salieron`.
