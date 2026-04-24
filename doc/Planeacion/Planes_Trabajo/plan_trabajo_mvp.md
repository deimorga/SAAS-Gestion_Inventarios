# Plan de Trabajo — MicroNuba Inventory SaaS

> **Versión:** 1.0  
> **Fecha:** 2026-04-24  
> **Metodología:** Scrum adaptado (sprints de 2 semanas)

---

## 1. Visión General del Plan

```mermaid
gantt
    title Roadmap MicroNuba Inventory
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Fase 1 - Definición
    Definición Funcional (35 RF)         :done, f1a, 2026-04-24, 1d
    Arquitectura y Specs Técnicas        :active, f1b, after f1a, 5d
    ERD Detallado + Migraciones Base     :f1c, after f1b, 3d

    section Fase 2 - Core MVP
    Sprint 1 - Gobierno + Catálogo       :s1, after f1c, 14d
    Sprint 2 - Almacenes + Motor         :s2, after s1, 14d
    Sprint 3 - Reportes + Reservas       :s3, after s2, 14d

    section Fase 3 - Avanzados
    Sprint 4 - Integración               :s4, after s3, 14d
    Sprint 5 - Trazabilidad Avanzada     :s5, after s4, 14d
```

---

## 2. Secuencia de Ejecución por Fase

### Fase 1: Definición (Actual — Semana 1)

| Paso | Actividad | Responsable | Entregable | Estado |
|------|-----------|-------------|------------|--------|
| 1.1 | Definición Funcional completa (35 RF, 18 HU) | `experto_requerimientos_historias` | `doc/Funcional/mejorado/` (8 archivos) | ✅ Completado |
| 1.2 | Definir arquitectura técnica y stack final | `arquitecto_soluciones` | `doc/Arquitectura/Arquitectura definida/` | ⏳ Próximo |
| 1.3 | ERD definitivo con migraciones Alembic base | `experto_base_datos_postgres` | Modelo en `doc/Tecnico/` + SQL en `infra/` | ⏳ Pendiente |
| 1.4 | Definiciones técnicas por módulo (contratos API) | `experto_backend_python` + `api-design-principles` | `doc/Tecnico/` | ⏳ Pendiente |

### Fase 2: Desarrollo Core MVP (Sprints 1–3)

Cada sprint sigue el **workflow de 11 pasos** del orquestador:

```
Paso 1 (Funcional) ✅ → Paso 2 (Arquitectura) → Paso 3 (Técnico) → 
Paso 5 (Backend) → Paso 7 (Tests) → Paso 7.5 (QA Gate) → 
Paso 8 (E2E) → Paso 9 (Staging)
```

> **Nota:** Paso 4 (UX/UI) y Paso 6 (Frontend) se omiten en el MVP API-First.

| Sprint | Duración | Objetivo | RF Incluidos | Módulos |
|--------|----------|----------|-------------|---------|
| Sprint 1 | 2 semanas | Base segura + catálogo operativo | RF-001 a RF-008 | Gobierno, Catálogo |
| Sprint 2 | 2 semanas | Motor transaccional funcionando | RF-013, RF-016 a RF-020, RF-022 | Sedes, Motor |
| Sprint 3 | 2 semanas | Reportes + reservas completas | RF-025 a RF-027, RF-029 a RF-032 | Reservas, Reportes |

### Fase 3: Módulos Avanzados (Sprints 4–5)

| Sprint | Duración | Objetivo | RF Incluidos | Módulos |
|--------|----------|----------|-------------|---------|
| Sprint 4 | 2 semanas | Conectividad con ecosistema externo | RF-033 a RF-035 | Integración |
| Sprint 5 | 2 semanas | Trazabilidad y funciones avanzadas | RF-009 a RF-012, RF-014, RF-015, RF-021, RF-023, RF-024, RF-028 | Catálogo+, Sedes+, Motor+ |

---

## 3. Criterios de Éxito por Sprint

Cada sprint DEBE cumplir antes de avanzar al siguiente:

| Criterio | Umbral | Verificación |
|----------|--------|-------------|
| Tests unitarios | ≥ 80% cobertura | `pytest --cov --cov-fail-under=80` |
| Tests Auth/RLS | 100% cobertura | Reporte de cobertura en módulos `auth/` y `core/` |
| Tipado estático | 0 errores | `mypy app/ --ignore-missing-imports` |
| Linting | 0 errores | `ruff check app/` |
| Verificador de Calidad | Veredicto `APROBADO` | `verificador_calidad` ejecutado |
| Criterios Gherkin | 100% cubiertos | Matriz RF → Test Case en `doc/Planeacion/Sprints/` |

---

## 4. Riesgos Identificados

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| R1 | Complejidad del motor transaccional atómico (ACID + CPP) | Alta | Alto | Spike técnico antes de Sprint 2. Tests exhaustivos |
| R2 | Performance de RLS en queries con muchos tenants | Media | Alto | Indexar `tenant_id` en todas las tablas. Benchmark temprano |
| R3 | Concurrencia en reservas (race conditions) | Media | Alto | Optimistic locking (`version` en STOCK_BALANCE) |
| R4 | Volumen de datos en Kardex histórico | Media | Medio | Paginación obligatoria. Particionamiento si crece |
| R5 | Complejidad de transferencias de dos fases | Media | Medio | Estado `IN_TRANSIT` bien definido. Tests de borde |

---

## 5. Dependencias Externas

| Dependencia | Tipo | Impacto si Falla |
|-------------|------|-----------------|
| PostgreSQL 15+ (con RLS) | Infraestructura | Bloqueante total |
| Redis (rate limiting, caché, worker) | Infraestructura | Degrada rate limiting y workers |
| Docker + Traefik | DevOps | Bloquea entorno de desarrollo |
| Celery (procesamiento asíncrono) | Framework | Bloquea bulk engine y auto-expiration |
