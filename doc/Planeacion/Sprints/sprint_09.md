# Sprint 9 — Gestión de Usuarios y Recuperación de Acceso

**Fecha Inicio:** por definir
**Fecha Fin Estimada:** por definir
**Responsable:** Cristian Anacona
**Revisión y despliegue:** Deiby Moreno
**Estado:** 📝 Planificado

**Definición funcional:** [RF_gestion_usuarios.md](../../Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md) (RF-046 a RF-052)
**Definición técnica:** [DT_gestion_usuarios.md](../../Definicion-Tecnica/09_gestion_usuarios/DT_gestion_usuarios.md)

---

## 🎯 Objetivo del Sprint

Que gestionar usuarios no requiera la API ni la base de datos: activar cuentas desde el enlace del
email, administrar los usuarios de cada tenant y los super_admins desde el portal, y recuperar una
contraseña olvidada por email.

**Contexto:** el 2026-11-05 se comprobó que el enlace de activación lleva a una página inexistente
(404). Por eso **AWP PERFORMANCE**, un cliente en producción, y AutolavadoDemo no tienen ningún
administrador activo. Ese mismo día, recuperar el acceso de un super_admin exigió entrar al servidor
por SSH. T-901 corrige lo primero y es lo más urgente del sprint.

---

## 🛡️ Lineamientos (obligatorios)

Definidos por Deiby Moreno. Detalle en la [definición funcional](../../Funcional/mejorado/09_gestion_usuarios/RF_gestion_usuarios.md#lineamientos-del-requerimiento-obligatorios).

- **L-1 — El super_admin actual es la cuenta raíz y está protegido.** Desde él se crean los demás
  usuarios. Nada puede borrarlo, desactivarlo, cambiarle el rol ni forzar su reseteo.
- **L-2** — La gestión de usuarios nace de esa cuenta raíz; no hay registro abierto.
- **L-3** — No se borra ningún usuario de forma física: se desactiva.
- **L-4** — Los tests nunca borran ni modifican datos que no crearon.
- **L-5** — Ningún administrador conoce ni fija la contraseña de otro usuario.

## 👥 Responsabilidades

| Quién | Qué |
|---|---|
| **Cristian Anacona** | Desarrollo y tests de T-901 a T-915 y T-917, en local, con Claude Code |
| **Deiby Moreno** | Revisión y merge de cada PR, validación en staging, despliegue a producción (T-916) |

**Forma de trabajo:** una rama `feature/T-9xx-…` desde `staging` y un Pull Request por tarea hacia
`staging`. Guía para desarrollar con Claude, qué no debe hacer y prompt de arranque: §13 de la
[definición técnica](../../Definicion-Tecnica/09_gestion_usuarios/DT_gestion_usuarios.md#13-guía-para-desarrollar-con-claude).

---

## 📋 Items del Sprint

Todos asignados a **Cristian Anacona**. Tamaño: S ≈ medio día · M ≈ 1–2 días · L ≈ 3+ días.

| ID | Área | Tarea | RF | Tamaño | Depende de | Estado |
|----|------|-------|----|--------|-----------|--------|
| T-901 | Portal | Página pública `/activate?token=` (activación de cuenta) | RF-046 | S | — | ⬜ Pendiente |
| T-902 | Backend | Política de contraseña única de 12 caracteres (`PASSWORD_MIN_LENGTH`) en activación, cambio, reseteo y registro | RF-052 | S | — | ⬜ Pendiente |
| T-903 | Backend | Migración 014: email en minúsculas + índice único `lower(email)`; login sin distinguir mayúsculas; columna `is_protected` que marca la cuenta raíz (L-1) | RF-052, RF-049 | M | — | ⬜ Pendiente |
| T-904 | Backend | Sesiones por usuario (`app/services/sessions.py`): índice de refresh tokens y `revoke_all_sessions` | RF-051 | M | — | ⬜ Pendiente |
| T-905 | Backend | `get_current_auth` rechaza access tokens anteriores a la revocación (`user_revoked_at`) | RF-051 | S | T-904 | ⬜ Pendiente |
| T-906 | Backend | `user_management`: `Actor`, `ensure_can_manage`, roles asignables, defecto `viewer`, email único global, filtros `status`/`q`, auditoría | RF-047, RF-048, RF-052 | L | T-903, T-904 | ⬜ Pendiente |
| T-907 | Backend | `/v1/users`: PATCH con `role` y restricciones; `POST /v1/users/{id}/password-reset` | RF-048 | M | T-906, T-910 | ⬜ Pendiente |
| T-908 | Backend | `/admin/tenants/{id}/users`: POST, PATCH y `password-reset` | RF-047 | M | T-906, T-910 | ⬜ Pendiente |
| T-909 | Backend | `/admin/super-admins` (GET, POST, PATCH, password-reset) con "al menos uno activo" atómico y `403` sobre la cuenta raíz | RF-049 | M | T-903, T-906, T-910 | ⬜ Pendiente |
| T-910 | Backend | `password_reset.py`: `forgot-password` (respuesta única, límites 3/h email y 10/h IP) y `reset-password`; plantilla `password_reset` | RF-050 | L | T-902, T-904 | ⬜ Pendiente |
| T-911 | Portal | Páginas públicas `/forgot-password` y `/reset-password`; enlace desde `/login`; reenvío de `X-Forwarded-For` | RF-050 | M | T-910 | ⬜ Pendiente |
| T-912 | Portal | Página `/tenants/{id}/users` (super_admin → `/admin`, tenant_admin → `/v1`) y botón en el detalle del tenant | RF-047, RF-048 | L | T-907, T-908 | ⬜ Pendiente |
| T-913 | Portal | Página `/super-admins` y enlace desde `/tenants` | RF-049 | M | T-909 | ⬜ Pendiente |
| T-914 | Tests | Tests de §11 de la DT (gestión, admin, super_admins, reseteo, revocación) | Todos | L | Cada tarea | ⬜ Pendiente |
| T-915 | Docs | Actualizar RF-039/RF-040 (módulo 08), `CLAUDE.md` y la guía de integración con los endpoints nuevos | — | S | Al cerrar | ⬜ Pendiente |
| T-916 | Despliegue | **(Deiby)** Staging → verificación con Mailpit → prod. Reenviar activación a los admins pendientes de AWP y AutolavadoDemo. Prueba real de Resend | — | M | Todo | ⬜ Pendiente |
| T-917 | Tests | `test_admin_auth.py`: que el fixture solo borre los super_admins `sa-test-*` que creó, nunca la cuenta raíz, y que los tests que exigen tabla vacía hagan `skip` | RF-052, L-4 | S | — | ⬜ Pendiente |

### Orden sugerido

1. **T-917** primero: hasta que esté hecha, correr la suite contra staging borra su super_admin.
2. **T-901** y **T-902**: desbloquean la activación de inmediato. T-901 se puede desplegar sola si
   hay prisa por activar a los administradores de AWP.
3. Base: **T-903**, **T-904** y **T-905**.
4. Lógica: **T-906** y **T-910**; después **T-907**, **T-908** y **T-909**.
5. Portal: **T-911**, **T-912** y **T-913**.
6. **T-914** va a la par de cada tarea, no al final. **T-915** y **T-916** cierran el sprint.

---

## ✅ Definición de Hecho (DoD)

- [ ] Todos los criterios de aceptación HU-USR-001 a HU-USR-006 cubiertos por tests.
- [ ] `ruff check app/ tests/` y `mypy app/` sin errores; suite completa en verde en local (Cristian) y contra staging (Deiby, tras T-917).
- [ ] Probado de punta a punta en staging con Mailpit: activación, olvido de contraseña, reseteo
      forzado, desactivación con sesión abierta.
- [ ] Ninguna respuesta pública permite averiguar si un email está registrado (RN-050-1).
- [ ] Ninguna contraseña, hash ni token aparece en logs ni en `audit_logs`.
- [ ] La cuenta raíz de staging sigue intacta tras la validación (mismo id, email, rol y estado) y
      ningún endpoint permite modificarla (L-1).
- [ ] Desplegado en prod por Deiby, con aviso a infra del commit y la hora.
- [ ] Las tres ramas (`main`, `staging`, `develop`) en el mismo commit al cerrar el sprint.

---

## ⚠️ Riesgos

| Riesgo | Mitigación |
|---|---|
| La migración 014 falla si aparecen emails duplicados | Comprobar en prod antes de desplegar (a 2026-11-05: 0 duplicados) |
| Resend en producción nunca se ha verificado de punta a punta | T-916 incluye una prueba real antes de cerrar |
| Correr la suite contra staging borra su super_admin | T-917 antes que nada |
| Un `GET` de Redis más por request (T-905) | Mismo coste que el tier del rate limit; medir en staging |
