# Product Backlog — MicroNuba Inventory SaaS

> **Última actualización:** 2026-04-28  
> **Product Owner:** Usuario  
> **Scrum Master:** Orquestador de Proyecto

---

## Criterios de Priorización

| Prioridad | Significado | Criterio |
|-----------|-------------|----------|
| **P0 — Must** | Bloqueante para MVP | Sin esto no hay SaaS funcional |
| **P1 — Should** | Segundo corte | Necesario para operación real pero no para demo |
| **P2 — Could** | Tercer corte | Funcionalidad avanzada, diferenciación competitiva |

## Estimación

| Tamaño | Descripción |
|--------|-------------|
| **S** | 1-2 días — CRUD simple, validaciones directas |
| **M** | 3-5 días — Lógica de negocio compleja, múltiples validaciones |
| **L** | 5-8 días — Motor transaccional, procesos asíncronos, integraciones |
| **XL** | 8-13 días — Sistemas completos con múltiples dependencias |

---

## Backlog Priorizado

| # | ID | Módulo | Descripción | Prioridad | Tamaño | Sprint | Estado | Dependencias |
|---|---|--------|-------------|-----------|--------|--------|--------|-------------|
| 1 | RF-001 | Gobierno | Aislamiento Multi-Tenant (RLS) | P0 | L | Sprint 1 | ✅ Completado | — |
| 2 | RF-002 | Gobierno | API Keys con Scopes granulares | P0 | M | Sprint 1 | ✅ Completado | RF-001 |
| 3 | RF-003 | Gobierno | Rate Limiting por suscripción | P0 | M | Sprint 1 | ✅ Completado | RF-001 |
| 4 | RF-004 | Gobierno | Audit Trail inmutable | P0 | M | Sprint 1 | ✅ Completado | RF-001 |
| 5 | RF-005 | Gobierno | Motor de Políticas de Negocio | P0 | S | Sprint 1 | ✅ Completado | RF-001 |
| 6 | RF-006 | Catálogo | Gestión Maestra de SKUs | P0 | M | Sprint 1 | ✅ Completado | RF-001 |
| 7 | RF-007 | Catálogo | Categorías Jerárquicas | P0 | M | Sprint 1 | ✅ Completado | RF-006 |
| 8 | RF-008 | Catálogo | Motor de Conversión UOM | P0 | M | Sprint 1 | ✅ Completado | RF-006 |
| 9 | RF-013 | Sedes | Almacenes Multi-Sede | P0 | M | Sprint 2 | ✅ Completado | RF-001 |
| 10 | RF-016 | Motor | Entrada de Mercancía + CPP | P0 | L | Sprint 2 | ✅ Completado | RF-006, RF-013 |
| 11 | RF-017 | Motor | Salida de Mercancía | P0 | L | Sprint 2 | ✅ Completado | RF-006, RF-013, RF-005 |
| 12 | RF-018 | Motor | Transferencias Inter-Almacén | P0 | L | Sprint 2 | ✅ Completado | RF-013, RF-016, RF-017 |
| 13 | RF-019 | Motor | Ajustes por Auditoría | P1 | M | Sprint 2 | ✅ Completado | RF-016 |
| 14 | RF-020 | Motor | Devoluciones (RMA) | P1 | M | Sprint 2 | ✅ Completado | RF-016 |
| 15 | RF-022 | Motor | Bajas (Scrap & Loss) | P1 | S | Sprint 2 | ✅ Completado | RF-017 |
| 16 | RF-029 | Reportes | Kardex Histórico | P1 | M | Sprint 3 | ✅ Completado | RF-016..RF-018 |
| 17 | RF-030 | Reportes | Balance Snapshots (Valoración Contable) | P1 | M | Sprint 3 | ✅ Completado | RF-016 |
| 18 | RF-031 | Reportes | Alertas de Stock Bajo | P1 | M | Sprint 3 | ✅ Completado | RF-006, RF-017 |
| 19 | RF-032 | Reportes | Valoración de Inventario | P1 | M | Sprint 3 | ✅ Completado | RF-016, RF-030 |
| 20 | RF-025 | Reservas | Soft Reservations + TTL | P1 | L | Sprint 3 | ✅ Completado | RF-017 |
| 21 | RF-026 | Reservas | Hard Commitment | P1 | M | Sprint 3 | ✅ Completado | RF-025 |
| 22 | RF-027 | Reservas | Auto-Expiration (worker) | P1 | M | Sprint 3 | ✅ Completado | RF-025 |
| 23 | DOC-001 | Docs | Documentación API (OpenAPI enriquecido + export estático) | P1 | S | Sprint 3 | ✅ Completado | RF-001..RF-022 |
| 24 | RF-033 | Integración | Webhooks (Push) | P2 | L | Sprint 4 | ✅ Completado | RF-001 |
| 25 | RF-034 | Integración | Bulk Engine (masivas) | P2 | L | Sprint 4 | ✅ Completado | RF-016, RF-006 |
| 26 | RF-035 | Integración | Inventario Cíclico | P2 | L | Sprint 4 | ✅ Completado | RF-019 |
| 27 | RF-009 | Catálogo | Kits/Combos (BOM) | P2 | L | Sprint 5 | ✅ Completado | RF-006, RF-017 |
| 28 | RF-010 | Catálogo | Trazabilidad Lotes/Seriales | P2 | L | Sprint 5 | ✅ Completado | RF-006, RF-016 |
| 29 | RF-011 | Catálogo | Directorio de Proveedores | P1 | M | Sprint 5 | ✅ Completado | RF-006 |
| 30 | RF-012 | Catálogo | Costos de Reposición | P1 | M | Sprint 5 | ✅ Completado | RF-016 |
| 31 | RF-014 | Sedes | Zonificación (Bins/Slots) | P2 | M | Sprint 5 | ✅ Completado | RF-013 |
| 32 | RF-015 | Sedes | Bloqueos de Ubicación | P2 | M | Sprint 5 | ✅ Completado | RF-014 |
| 33 | RF-021 | Motor | Re-empaque | P2 | M | Sprint 5 | ✅ Completado | RF-016, RF-017 |
| 34 | RF-023 | Motor | Control de Vencimiento | P2 | M | Sprint 5 | ✅ Completado | RF-010 |
| 35 | RF-024 | Motor | Validación de Seriales | P2 | M | Sprint 5 | ✅ Completado | RF-010 |
| 36 | RF-028 | Reservas | Allocation por Canal | P2 | M | Sprint 5 | ✅ Completado | RF-025 |

---

## Resumen de Velocidad Estimada

| Sprint | RF Incluidos | Tamaño Total | Módulos |
|--------|-------------|--------------|---------|
| Sprint 1 | RF-001..RF-008 | XL (9 tareas) | Gobierno + Catálogo Base | ✅ Completado (48 tests, 90% cov) |
| Sprint 2 | RF-013, RF-016..RF-020, RF-022 | XL (9 tareas) | Almacenes + Motor Transaccional | ✅ Completado (84 tests, 93% cov) |
| Sprint 3 | RF-025..RF-027, RF-029..RF-032, DOC-001 | L (8 tareas) | Reportes + Reservas + Docs API | ✅ Completado (111 tests, 92% cov) |
| Sprint 4 | RF-033..RF-035 | L (6 tareas) | Webhooks + Bulk Engine + Inventario Cíclico | ✅ Completado (154 tests, 91% cov) |
| Sprint 5 | RF-009..RF-012, RF-014..RF-015, RF-021, RF-023..RF-024, RF-028 | XL (10 tareas) | Trazabilidad Avanzada | ✅ Completado (208 tests, 92% cov) |
