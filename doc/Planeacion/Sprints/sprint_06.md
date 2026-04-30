# Sprint 6 — Admin Multi-tenant & Onboarding

**Fecha Inicio:** 2026-04-29  
**Fecha Fin Estimada:** 2026-05-09  
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Implementar el módulo de administración multi-tenant que permite a MicroNuba operar comercialmente: incorporar clientes nuevos, gestionar su ciclo de vida, controlar el acceso a la plataforma y mantener las credenciales de integración seguras y actualizadas. Este sprint convierte el MVP técnico en un producto SaaS operable.

---

## 📋 Items del Sprint

| ID | Fase | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|---|
| T-601 | F-1 | RF-036 / RF-037 | Migración 012 — must_change_password, created_by, last_used_at, RLS bypass, seed micronuba-internal | ✅ Completado | Ejecutar `alembic upgrade head` |
| T-602 | F-1 | RF-036 / RF-041 | Actualizar modelos User (must_change_password, created_by) y ApiKey (last_used_at) | ✅ Completado | |
| T-603 | F-1 | RF-036..RF-044 | Actualizar config.py — ADMIN_BOOTSTRAP_SECRET, RESEND_*, ACTIVATION_*, API_KEY_* | ✅ Completado | |
| T-604 | F-1 | RF-043 | Agregar resend==2.4.0 a requirements.txt | ✅ Completado | |
| T-605 | F-1 | RF-036 | Actualizar deps.py — require_super_admin, get_admin_db, token_scope en AuthContext | ✅ Completado | Sentinel __super_admin__ |
| T-606 | F-1 | RF-037 | Actualizar tenant service — api_key_rotation_grace_days en _DEFAULT_CONFIG | ✅ Completado | |
| T-607 | F-2 | RF-036 | Schemas admin_auth (AdminRegisterRequest, AdminLoginResponse) | ✅ Completado | `app/schemas/admin_auth.py` |
| T-608 | F-2 | RF-036 | Service admin_auth (register_super_admin, login_super_admin) | ✅ Completado | `app/services/admin_auth.py` |
| T-609 | F-2 | RF-036 | Endpoint POST /admin/auth/register + POST /admin/auth/login | ✅ Completado | `app/api/admin/endpoints/admin_auth.py` |
| T-610 | F-2 | RF-036 | Tests F-2: separación de superficies, bootstrap desactivado, rol incorrecto | ✅ Completado | 13 tests, 221 total, 0 ruff/mypy |
| T-611 | F-3 | RF-037 | Schemas admin_tenant (TenantCreate, TenantUpdate, TenantResponse, TenantListResponse) | ✅ Completado | `app/schemas/admin_tenant.py` |
| T-612 | F-3 | RF-037 | Service admin_tenant (create_tenant, list_tenants, get_tenant, update_tenant) | ✅ Completado | `app/services/admin_tenant.py` |
| T-613 | F-3 | RF-037 | Endpoints CRUD /admin/tenants + creación de tenant_admin inicial | ✅ Completado | `app/api/admin/endpoints/admin_tenants.py` |
| T-614 | F-3 | RF-037 | Tests F-3: creación, suspensión, colisión de slug, cambio de tier | ✅ Completado | 16 tests, 29 total F-2+F-3, 0 errores |
| T-615 | F-4 | RF-038 | Schemas activation (ActivateRequest, ResendActivationRequest) | ✅ Completado | `app/schemas/activation.py` |
| T-616 | F-4 | RF-038 | Service activation (generate_activation_token, validate_activation_token) | ✅ Completado | `app/services/activation.py` |
| T-617 | F-4 | RF-038 | Endpoint POST /auth/activate + POST /auth/resend-activation/{user_id} | ✅ Completado | `app/api/v1/endpoints/auth_activate.py` |
| T-618 | F-4 | RF-040 | Endpoint POST /auth/change-password | ✅ Completado | mismo archivo auth_activate.py |
| T-619 | F-4 | RF-038 / RF-040 | Tests F-4: token single-use, expiración 410, password débil, change-password | ✅ Completado | 11 tests, 248 total, 0 fallos |
| T-620 | F-5 | RF-039 | Schemas user_management (UserCreate, UserUpdate, UserResponse) | ✅ Completado | `app/schemas/user_management.py` |
| T-621 | F-5 | RF-039 | Service user_management (create_user, list_users, update_user) | ✅ Completado | `app/services/user_management.py` |
| T-622 | F-5 | RF-039 | Endpoints GET/POST/PATCH /v1/users | ✅ Completado | `app/api/v1/endpoints/users.py` |
| T-623 | F-5 | RF-039 | Tests F-5: RLS aislamiento, rol no permitido, email duplicado | ✅ Completado | 13 tests, 261 total, 0 fallos |
| T-624 | F-6 | RF-041 | Lógica staggering de fechas de expiración (ningún tenant comparte día) | ✅ Completado | `app/services/api_key_rotation.py::_staggered_expiry` |
| T-625 | F-6 | RF-041 | Service api_key rotation (rotate_api_key, immediate revocation) | ✅ Completado | `app/services/api_key_rotation.py` |
| T-626 | F-6 | RF-041 | Endpoint POST /v1/api-keys/{key_id}/rotate | ✅ Completado | `app/api/v1/endpoints/api_keys.py` |
| T-627 | F-6 | RF-044 | Endpoints admin: GET /admin/tenants/{id}/api-keys + DELETE .../{key_id} | ✅ Completado | `app/api/admin/endpoints/admin_tenants.py` |
| T-628 | F-6 | RF-041 / RF-044 | Tests F-6: rotación normal, inmediata, staggering, revocación admin | ✅ Completado | 13 tests, 274 total, 0 fallos |
| T-629 | F-7 | RF-043 | Crear app/tasks.py — inicialización Celery + registro de tasks | ✅ Completado | `app/tasks.py` — resuelve crash inv-worker/beat |
| T-630 | F-7 | RF-043 | Tasks: send_email (con retry x3 backoff) vía Resend SDK | ✅ Completado | 9 templates texto/HTML |
| T-631 | F-7 | RF-042 | Task: check_expiring_api_keys (Celery Beat, diaria) | ✅ Completado | Hitos T-30, T-7, T-1, T-0 |
| T-632 | F-7 | RF-041 | Task: revoke_grace_period_key (programada al rotar) | ✅ Completado | |
| T-633 | F-7 | RF-043 | Templates de email (9 templates texto/HTML básico) | ✅ Completado | En `app/tasks.py::_TEMPLATES` |
| T-634 | F-7 | RF-042 / RF-043 | Tests F-7: mock Resend, retry logic, beat scheduling | ✅ Completado | 10 tests, 284 total, 0 fallos |
| T-635 | F-8 | RF-036..RF-044 | Registrar todos los routers nuevos en api/v1/router.py y main.py | ✅ Completado | Integrado progresivamente por fase |
| T-636 | F-8 | RF-036 | Verificación DoD: ruff, mypy, pytest ≥90%, cobertura 100% en auth/admin | ✅ Completado | 284 tests, 93% cobertura, 0 ruff, 0 mypy |
| T-637 | F-8 | RF-036 | Verificar rollback migración 012 (alembic downgrade -1) | ✅ Completado | downgrade 012→011 exitoso, re-upgrade OK |

---

## 🗄️ Modelo de Datos

### Migración 012 — Admin Bootstrap

#### Columnas nuevas

| Tabla | Columna | Tipo | Default |
|-------|---------|------|---------|
| `users` | `must_change_password` | `Boolean NOT NULL` | `false` |
| `users` | `created_by` | `UUID nullable` | `null` |
| `api_keys` | `last_used_at` | `DateTime(tz) nullable` | `null` |

#### RLS — Políticas actualizadas

Tablas afectadas: `users`, `api_keys`, `audit_logs`

```sql
-- Antes (Sprints 1-5)
USING (tenant_id::text = current_setting('app.current_tenant', true))

-- Después (Sprint 6)
USING (
    current_setting('app.current_tenant', true) = '__super_admin__'
    OR tenant_id::text = current_setting('app.current_tenant', true)
)
```

#### Seed fijo (idempotente)

| Campo | Valor |
|-------|-------|
| `id` | `00000000-0000-0000-0000-000000000001` |
| `name` | `MicroNuba Internal` |
| `slug` | `micronuba-internal` |
| `tier` | `ENTERPRISE` |

---

## 🌐 Endpoints Nuevos

### Admin Auth — `/admin/auth`

| Método | Endpoint | RF | Auth |
|--------|----------|----|------|
| `POST` | `/admin/auth/register` | RF-036 | Header `X-Bootstrap-Secret` |
| `POST` | `/admin/auth/login` | RF-036 | Pública |

### Admin Tenants — `/admin/tenants`

| Método | Endpoint | RF | Auth |
|--------|----------|----|------|
| `POST` | `/admin/tenants` | RF-037 | JWT `super_admin` |
| `GET` | `/admin/tenants` | RF-037 | JWT `super_admin` |
| `GET` | `/admin/tenants/{id}` | RF-037 | JWT `super_admin` |
| `PATCH` | `/admin/tenants/{id}` | RF-037 | JWT `super_admin` |
| `GET` | `/admin/tenants/{id}/api-keys` | RF-044 | JWT `super_admin` |
| `DELETE` | `/admin/tenants/{id}/api-keys/{key_id}` | RF-044 | JWT `super_admin` |

### Auth Cliente — `/auth`

| Método | Endpoint | RF | Auth |
|--------|----------|----|------|
| `POST` | `/auth/activate` | RF-038 | Sin auth |
| `POST` | `/auth/resend-activation/{user_id}` | RF-038 | JWT `tenant_admin` |
| `POST` | `/auth/change-password` | RF-040 | JWT `scope=full` |

### Usuarios — `/v1/users`

| Método | Endpoint | RF | Auth |
|--------|----------|----|------|
| `GET` | `/v1/users` | RF-039 | JWT `tenant_admin` |
| `POST` | `/v1/users` | RF-039 | JWT `tenant_admin` |
| `PATCH` | `/v1/users/{user_id}` | RF-039 | JWT `tenant_admin` |

### API Keys — extensión de `/v1/api-keys`

| Método | Endpoint | RF | Auth |
|--------|----------|----|------|
| `POST` | `/v1/api-keys/{key_id}/rotate` | RF-041 | JWT `tenant_admin` |

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Umbral | Estado |
|----------|--------|--------|
| Cobertura global | ≥ 90% | ✅ 93% |
| Cobertura módulos auth + admin | 100% | ✅ admin_auth 98%, admin_tenant 100%, activation 96% |
| 0 errores `ruff` | `All checks passed!` | ✅ |
| 0 errores `mypy` | `Success: no issues found` | ✅ |
| Tests nuevos | ≥ 60 | ✅ 76 tests nuevos (208→284) |
| RLS: tenant_A no lee datos de tenant_B | Test explícito en `tests/security/` | ✅ test_list_users_rls_isolation, test_rotate_cross_tenant_forbidden |
| RLS: super_admin lee datos de todos los tenants | Test explícito | ✅ test_admin_list_tenant_api_keys |
| Rollback migración 012 exitoso | `alembic downgrade -1` sin errores | ✅ downgrade 012→011 + re-upgrade OK |
| Separación de superficies verificada | `POST /auth/login` rechaza super_admin | ✅ test_super_admin_rejected_at_client_login |
| Activación single-use verificada | Token usado → 401 en segundo uso | ✅ test_activate_token_single_use |
| Email mock funcional en tests | Mock Resend, 0 llamadas reales | ✅ test_send_email_no_real_calls |
| Convención DOC-001 aplicada | Todos los endpoints nuevos documentados | ✅ |

---

## 📊 Métricas Objetivo

| Métrica | Sprint 5 | Sprint 6 (objetivo) |
|---------|----------|---------------------|
| Tests totales | 208 | **284** ✅ |
| Cobertura | 92% | **93%** ✅ |
| Ruff errors | 0 | **0** ✅ |
| Mypy errors | 0 | **0** ✅ |
| Endpoints totales | ~76 | **~92** ✅ |
| Migraciones | 008–011 | **012** ✅ |
| Tareas Celery | 0 activas | **3** (send_email, check_expiring, revoke_grace) ✅ |

---

## 🔗 Trazabilidad

| RF | HU | Tasks del Sprint |
|----|-----|-----------------|
| RF-036 | HU-ADM-001 | T-601, T-602, T-603, T-605, T-607, T-608, T-609, T-610, T-635, T-636, T-637 |
| RF-037 | HU-ADM-001, HU-ADM-002 | T-601, T-606, T-611, T-612, T-613, T-614 |
| RF-038 | HU-ADM-003 | T-615, T-616, T-617, T-619 |
| RF-039 | HU-ADM-004 | T-620, T-621, T-622, T-623 |
| RF-040 | HU-ADM-004 | T-618, T-619 |
| RF-041 | HU-ADM-005 | T-604, T-624, T-625, T-626, T-628, T-632 |
| RF-042 | HU-ADM-006 | T-631, T-634 |
| RF-043 | HU-ADM-001..006 | T-604, T-629, T-630, T-633, T-634 |
| RF-044 | HU-ADM-005 | T-627, T-628 |

---

## 📌 Decisiones de Diseño Registradas

| # | Decisión | Alternativa descartada | Razón |
|---|----------|----------------------|-------|
| D-01 | Superficie `/admin/auth/*` separada de `/auth/*` | Un solo endpoint con flag de rol | Seguridad: no revelar existencia del admin ni permitir ataques de fuerza bruta cruzados |
| D-02 | RLS bypass vía sentinel `__super_admin__` en `app.current_tenant` | Privilegio `BYPASSRLS` al usuario de BD | No requiere permisos especiales en PostgreSQL; controlado desde la aplicación |
| D-03 | Activación por token en Redis (48h, single-use) en lugar de contraseña temporal en email | Contraseña temporal en texto plano | Mayor seguridad: la contraseña nunca viaja por email |
| D-04 | `tenant_admin` solo puede crear `api_consumer` | Permitir creación de cualquier rol | El cliente no debe poder escalar privilegios sin intervención de MicroNuba |
| D-05 | Período de gracia de API Key configurable por tenant (7-90d) con default 30d | Fijo globalmente | Los clientes enterprise necesitan más tiempo de transición |
| D-06 | Staggering de fechas de expiración (±14 días máx) | Sin staggering | Facilita la operación del equipo de soporte: no hay concentración de renovaciones en un mismo día |
| D-07 | Notificaciones como Celery tasks fire-and-forget | Llamada síncrona a Resend en el request | Un fallo de Resend no debe bloquear la respuesta HTTP principal |
| D-08 | `app/tasks.py` como punto de entrada de Celery | Archivo disperso por módulos | Resuelve el crash de `inv-worker` e `inv-beat` (dependency Sprint 5 pendiente) |
