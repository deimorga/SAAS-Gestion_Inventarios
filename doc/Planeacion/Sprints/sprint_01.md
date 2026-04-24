# Sprint 1 — Gobierno, Seguridad y Catálogo Base

**Fecha Inicio:** 2026-04-24  
**Fecha Fin:** TBD  
**Estado:** 🏃 En Progreso

---

## 🎯 Objetivo del Sprint

Implementar la base fundamental de seguridad, aislamiento (Multi-Tenant/RLS) y autenticación del sistema, junto con la gestión maestra inicial del catálogo de productos. El éxito de este sprint establecerá el andamiaje transaccional seguro sobre el cual operarán los siguientes módulos.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Skill Asignada | Estado | Notas |
|---|---|---|---|---|---|
| T-101 | RF-001 | Implementar RLS en PostgreSQL + middleware de tenant | `experto_base_datos_postgres` / `experto_backend_python` | Pendiente | Bloqueante P0 |
| T-102 | RF-001/002 | Implementar Auth: JWT RS256, login, refresh, logout | `experto_backend_python` | Pendiente | Depende de base de datos |
| T-103 | RF-002 | Implementar RBAC + API Keys con scopes | `experto_backend_python` | Pendiente | Requiere modelo de usuarios |
| T-104 | RF-003 | Implementar Rate Limiting dinámico por tier en Redis | `experto_backend_python` | Pendiente | Depende de T-102 |
| T-105 | RF-004 | Implementar Audit Trail inmutable | `experto_backend_python` | Pendiente | Aplicar a todos los endpoints |
| T-106 | RF-005 | Implementar Motor de Políticas del Tenant (JSONB) | `experto_backend_python` | Pendiente | Configuraciones de operación |
| T-107 | RF-006 | Implementar CRUD Productos (SKU, metadata JSONB) | `experto_backend_python` | Pendiente | Base del motor de catálogo |
| T-108 | RF-007 | Implementar Categorías Jerárquicas | `experto_backend_python` | Pendiente | Ltree o Parent-ID |
| T-109 | RF-008 | Implementar Motor de Conversión UOM | `experto_backend_python` | Pendiente | Base vs. Alternativa |

---

## 🚦 Criterios de Aceptación (DoD)

Para que el sprint sea considerado exitoso, se deberá cumplir de forma innegociable con el Checklist Universal y Backend establecido en las reglas:

1. **Cobertura de Pruebas:** Mínimo 80% global. 100% de cobertura obligatoria en las rutas de Auth y en la asignación de RLS.
2. **Seguridad Multi-Tenant:** Aislamiento total validado en la base de datos (Tests de Aislamiento de Tenant).
3. **Calidad de Código:** Cero errores en `mypy` y `ruff`.
4. **DevSecOps:** Cero secretos en código, contraseñas encriptadas con algoritmos seguros.

---

## 📊 Resultado

- **Velocidad:** (Por calcular) Puntos
- **Items completados:** 0 / 9
