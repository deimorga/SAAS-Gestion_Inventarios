# Sprint 0 — Definición Funcional y Arquitectura

**Fecha Inicio:** 2026-04-24  
**Fecha Fin:** 2026-04-30 (estimado)  
**Estado:** En Progreso

---

## Objetivo del Sprint

Completar toda la documentación funcional y arquitectónica necesaria para iniciar el desarrollo del MVP en Sprint 1. No se escribe código de producción en este sprint.

---

## Items del Sprint

| ID | Tarea | Skill Asignada | Estado | Notas |
|---|---|---|---|---|
| T-000 | Crear `DEFINICION_SAAS.md` (documento paraguas) | `experto_requerimientos_historias` | ✅ Completado | 12 secciones, ERD, glosario |
| T-001 | Formalizar RF-001..RF-005 (Gobierno) | `experto_requerimientos_historias` | ✅ Completado | 5 RF, 4 HU, 9 endpoints |
| T-002 | Formalizar RF-006..RF-012 (Catálogo) | `experto_requerimientos_historias` | ✅ Completado | 7 RF, 3 HU, 16 endpoints |
| T-003 | Formalizar RF-013..RF-015 (Sedes) | `experto_requerimientos_historias` | ✅ Completado | 3 RF, 3 HU, 10 endpoints |
| T-004 | Formalizar RF-016..RF-024 (Motor) | `experto_requerimientos_historias` | ✅ Completado | 9 RF, 3 HU, 10 endpoints |
| T-005 | Formalizar RF-025..RF-028 (Reservas) | `experto_requerimientos_historias` | ✅ Completado | 4 RF, 1 HU, 7 endpoints |
| T-006 | Formalizar RF-029..RF-032 (Reportes) | `experto_requerimientos_historias` | ✅ Completado | 4 RF, 2 HU, 6 endpoints |
| T-007 | Formalizar RF-033..RF-035 (Integración) | `experto_requerimientos_historias` | ✅ Completado | 3 RF, 2 HU, 11 endpoints |
| T-008 | Crear Product Backlog priorizado | `orquestador_proyecto` | ✅ Completado | 35 items, 5 sprints |
| T-009 | Crear Plan de Trabajo MVP | `orquestador_proyecto` | ✅ Completado | Roadmap + riesgos |
| T-010 | Definir Arquitectura Técnica | `arquitecto_soluciones` | ⏳ Pendiente | `ARQUITECTURA_FISICA.md` |
| T-011 | ERD Definitivo + Migraciones Base | `experto_base_datos_postgres` | ⏳ Pendiente | Modelo detallado |
| T-012 | Definiciones Técnicas por módulo | `experto_backend_python` | ⏳ Pendiente | Contratos API |
| T-013 | Configurar Docker Compose (dev) | `experto_devsecops` | ⏳ Pendiente | `docker-compose.dev.yml` |

---

## Resultado Parcial

- **Definición Funcional:** ✅ **8/8 documentos completados**
  - 35 Requerimientos Funcionales formalizados
  - 18 Historias de Usuario con criterios Gherkin
  - 69 Endpoints documentados
  - 7 ERDs por módulo
- **Planeación:** ✅ **3/3 artefactos creados**
  - Product Backlog, Plan de Trabajo, Sprint 0
- **Arquitectura:** ⏳ **0/3 pendiente**

---

## Próximos Pasos (en orden)

1. Definir `ARQUITECTURA_FISICA.md` y `ESPECIFICACIONES_INFRAESTRUCTURA.md`
2. Crear ERD definitivo con modelo de datos completo
3. Generar definiciones técnicas por módulo en `doc/Tecnico/`
4. Configurar `docker-compose.dev.yml` y scaffolding base de FastAPI
