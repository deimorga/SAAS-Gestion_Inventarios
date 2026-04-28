# Sprint 1 — Gobierno, Seguridad y Catálogo Base

**Fecha Inicio:** 2026-04-24  
**Fecha Fin:** 2026-04-28  
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Implementar la base fundamental de seguridad, aislamiento (Multi-Tenant/RLS) y autenticación del sistema, junto con la gestión maestra inicial del catálogo de productos. El éxito de este sprint establece el andamiaje transaccional seguro sobre el cual operarán los siguientes módulos.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|
| T-101 | RF-001 | Implementar RLS en PostgreSQL + middleware de tenant | ✅ Completado | Migraciones 001/002, ENABLE+FORCE RLS, políticas por tabla |
| T-102 | RF-001/002 | Implementar Auth: JWT HS256, login, refresh, logout | ✅ Completado | Refresh tokens en Redis con rotación, 100% cobertura |
| T-103 | RF-002 | Implementar RBAC + API Keys con scopes | ✅ Completado | API Keys con SHA-256, 5 roles, dependency injection |
| T-104 | RF-003 | Implementar Rate Limiting dinámico por tier en Redis | ✅ Completado | INCR/TTL en Redis, tiers STARTER/PROFESSIONAL/ENTERPRISE |
| T-105 | RF-004 | Implementar Audit Trail inmutable | ✅ Completado | AuditLog JSONB, log_action() en todos los endpoints mutables |
| T-106 | RF-005 | Implementar Motor de Políticas del Tenant (JSONB) | ✅ Completado | Config JSONB con merge por patch, defaults por tier |
| T-107 | RF-006 | Implementar CRUD Productos (SKU, metadata JSONB) | ✅ Completado | Soft-delete, UOM sub-resource, búsqueda ILIKE |
| T-108 | RF-007 | Implementar Categorías Jerárquicas | ✅ Completado | Materialized path, árbol recursivo, filtro por descendientes |
| T-109 | RF-008 | Implementar Motor de Conversión UOM | ✅ Completado | Conversiones múltiples por producto, validación gt=0 |

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Resultado | Estado |
|---|---|---|
| Cobertura global ≥80% | **90%** (48 tests, greenlet+thread concurrency) | ✅ |
| Cobertura Auth+RLS 100% | `auth.py` 100%, `auth endpoint` 100%, RLS 7/7 tests | ✅ |
| Aislamiento multi-tenant validado | 7 tests de aislamiento RLS (DB directa + HTTP) | ✅ |
| 0 errores `ruff` | `All checks passed!` | ✅ |
| 0 errores `mypy` | `Success: no issues found in 45 source files` | ✅ |
| Sin secretos en código | Passwords via env vars, JWT_SECRET por settings | ✅ |
| Passwords encriptadas | bcrypt vía passlib (bcrypt==4.0.1) | ✅ |

---

## 📊 Resultado

- **Tests:** 48 / 48 pasando
- **Cobertura:** 90% global
- **Items completados:** 9 / 9
- **Errores ruff:** 0
- **Errores mypy:** 0

### Notas técnicas destacadas
- Puerto DB: 5433 (evita colisión con otros proyectos Docker)
- Puerto Redis: 6380 (mismo motivo)
- JWT: HS256 en lugar de RS256 (simplificación consciente para dev)
- Test RLS directo usa `inventory_app` (usuario sin BYPASSRLS), creado en runtime de tests
- `event_loop` session-scoped para compatibilidad con pytest-asyncio 0.23.6
