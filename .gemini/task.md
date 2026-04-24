# Task List — SaaS Gestión de Inventarios (MicroNuba Inventory)

> **Última actualización:** 2026-04-24 (sesión 2)  
> **Fase actual:** Fase 1 — Arquitectura completada → Listo para desarrollo  
> **Próximo paso:** Definir arquitectura técnica y stack final

---

## 🏗️ Fase 0: Gobernanza y Configuración Inicial

- [x] Adaptar documentos de gobernanza al nuevo proyecto (reglas, DoD, estructura, contexto) <!-- id: 0 | RF: N/A -->
- [ ] Definir stack tecnológico y arquitectura de contenedores <!-- id: 1 | RF: N/A | Bloqueado por: Fase 1 -->
- [ ] Configurar entorno de desarrollo con Docker (`docker-compose.dev.yml`) <!-- id: 2 | RF: N/A | Bloqueado por: id:1 -->
- [ ] Definir identidad visual y sistema de diseño (Tokens de diseño) <!-- id: 3 | RF: N/A | Prioridad: Baja (sin frontend MVP) -->

---

## 📋 Fase 1: Definición Funcional y Arquitectura

### Definición Funcional ✅ COMPLETADA

- [x] Crear documento paraguas `DEFINICION_SAAS.md` (visión, modelo multi-tenant, capacidades, glosario, ERD general, priorización) <!-- id: 7 | RF: N/A | Completado: 2026-04-24 -->
- [x] Formalizar RF-001 a RF-005: Módulo 01 — Gobierno y Seguridad (multi-tenancy, API Keys, rate limiting, auditoría, políticas) <!-- id: 4a | RF: RF-001..RF-005 | HU: 4 | Endpoints: 9 | Completado: 2026-04-24 -->
- [x] Formalizar RF-006 a RF-012: Módulo 02 — Catálogo de Productos (SKUs, categorías, UOM, kits, trazabilidad, proveedores, costos) <!-- id: 4b | RF: RF-006..RF-012 | HU: 3 | Endpoints: 16 | Completado: 2026-04-24 -->
- [x] Formalizar RF-013 a RF-015: Módulo 03 — Sedes y Almacenes (multi-sede, zonificación, bloqueos) <!-- id: 4c | RF: RF-013..RF-015 | HU: 3 | Endpoints: 10 | Completado: 2026-04-24 -->
- [x] Formalizar RF-016 a RF-024: Módulo 04 — Motor Transaccional (entradas, salidas, transferencias, ajustes, devoluciones, bajas, re-empaque, vencimientos, seriales) <!-- id: 4d | RF: RF-016..RF-024 | HU: 3 | Endpoints: 10 | Completado: 2026-04-24 -->
- [x] Formalizar RF-025 a RF-028: Módulo 05 — Reservas y Demanda (soft reservation, hard commitment, auto-expiration, allocation) <!-- id: 4e | RF: RF-025..RF-028 | HU: 1 | Endpoints: 7 | Completado: 2026-04-24 -->
- [x] Formalizar RF-029 a RF-032: Módulo 06 — Reportes y Valoración (kardex, snapshots, alertas reorden, valoración contable) <!-- id: 4f | RF: RF-029..RF-032 | HU: 2 | Endpoints: 6 | Completado: 2026-04-24 -->
- [x] Formalizar RF-033 a RF-035: Módulo 07 — Integración y Masivas (webhooks, bulk engine, inventario cíclico) <!-- id: 4g | RF: RF-033..RF-035 | HU: 2 | Endpoints: 11 | Completado: 2026-04-24 -->

### Arquitectura y Especificaciones Técnicas ✅ COMPLETADA

- [x] Diseñar modelo de datos Multi-tenant definitivo (ERD con 20 entidades, convenciones, RLS, índices) <!-- id: 5 | RF: Todos | Completado: 2026-04-24 -->
- [x] Definir arquitectura física e infraestructura (`ARQUITECTURA_FISICA.md`, `ESPECIFICACIONES_INFRAESTRUCTURA.md`, `MODELO_DATOS.md`) <!-- id: 6 | RF: N/A | Completado: 2026-04-24 -->
- [ ] Crear definiciones técnicas por módulo en `doc/Tecnico/` (endpoints detallados, contratos request/response, validaciones) <!-- id: 6b | RF: Todos -->

---

## 🛠️ Fase 2: Desarrollo del Core (MVP — Sprint 1 a 3)

### Sprint 1: Gobierno + Catálogo Base
- [ ] Implementar Auth: JWT RS256, login, refresh, logout <!-- id: 8a | RF: RF-001, RF-002 -->
- [ ] Implementar RBAC + API Keys con scopes <!-- id: 8b | RF: RF-002 -->
- [ ] Implementar RLS en PostgreSQL + middleware de tenant <!-- id: 8c | RF: RF-001 -->
- [ ] Implementar Rate Limiting dinámico por tier <!-- id: 8d | RF: RF-003 -->
- [ ] Implementar Audit Trail <!-- id: 8e | RF: RF-004 -->
- [ ] Implementar Motor de Políticas del Tenant <!-- id: 8f | RF: RF-005 -->
- [ ] Implementar CRUD Productos (SKU, metadata JSONB) <!-- id: 10a | RF: RF-006 -->
- [ ] Implementar Categorías Jerárquicas <!-- id: 10b | RF: RF-007 -->
- [ ] Implementar Motor de UOM <!-- id: 10c | RF: RF-008 -->

### Sprint 2: Almacenes + Motor Transaccional
- [ ] Implementar CRUD Almacenes multi-sede <!-- id: 9a | RF: RF-013 -->
- [ ] Implementar Entrada de Mercancía + Recálculo CPP <!-- id: 11a | RF: RF-016 -->
- [ ] Implementar Salida de Mercancía + validación de disponibilidad <!-- id: 11b | RF: RF-017 -->
- [ ] Implementar Transferencias de dos fases <!-- id: 11c | RF: RF-018 -->
- [ ] Implementar Ajustes de Inventario <!-- id: 11d | RF: RF-019 -->
- [ ] Implementar Devoluciones (RMA) <!-- id: 11e | RF: RF-020 -->
- [ ] Implementar Bajas (Scrap) <!-- id: 11f | RF: RF-022 -->

### Sprint 3: Reportes + Reservas
- [ ] Implementar Kardex Histórico <!-- id: 13 | RF: RF-029 -->
- [ ] Implementar Balance Snapshots <!-- id: 18 | RF: RF-030 -->
- [ ] Implementar Alertas de Stock Bajo <!-- id: 15 | RF: RF-031 -->
- [ ] Implementar Valoración Contable (CPP) <!-- id: 19 | RF: RF-032 -->
- [ ] Implementar Soft Reservations + TTL <!-- id: 16a | RF: RF-025, RF-027 -->
- [ ] Implementar Hard Commitment <!-- id: 16b | RF: RF-026 -->

---

## 📊 Fase 3: Módulos Avanzados (Sprint 4 a 5)

### Sprint 4: Integración
- [ ] Implementar Sistema de Webhooks <!-- id: 14 | RF: RF-033 -->
- [ ] Implementar Bulk Engine (procesamiento masivo) <!-- id: 17 | RF: RF-034 -->
- [ ] Implementar Inventario Cíclico (Reconciliación) <!-- id: 17b | RF: RF-035 -->

### Sprint 5: Trazabilidad Avanzada
- [ ] Implementar Kits/Combos (BOM) <!-- id: 10d | RF: RF-009 -->
- [ ] Implementar Trazabilidad por Lotes/Seriales <!-- id: 10e | RF: RF-010 -->
- [ ] Implementar Control de Vencimiento <!-- id: 11g | RF: RF-023 -->
- [ ] Implementar Validación de Seriales <!-- id: 11h | RF: RF-024 -->
- [ ] Implementar Re-empaque <!-- id: 11i | RF: RF-021 -->
- [ ] Implementar Directorio de Proveedores <!-- id: 10f | RF: RF-011 -->
- [ ] Implementar Gestión de Costos de Reposición <!-- id: 10g | RF: RF-012 -->
- [ ] Implementar Zonificación (Bins/Slots) <!-- id: 9b | RF: RF-014 -->
- [ ] Implementar Bloqueos de Ubicación <!-- id: 9c | RF: RF-015 -->
- [ ] Implementar Allocation por Canal <!-- id: 16c | RF: RF-028 -->

---

## 📈 Fase 4: Frontend y Dashboard (Fuera del MVP API)

- [ ] Implementar Dashboard multi-tenant con branding dinámico <!-- id: 20 | Depende de: Fase 2+3 -->
- [ ] Implementar vistas de inventario por sede/almacén <!-- id: 21 -->
- [ ] Implementar interfaz de movimientos <!-- id: 22 -->
- [ ] Implementar reportes visuales <!-- id: 23 -->

---

## 🧪 Fase 5: Pruebas y Despliegue

- [ ] Pruebas unitarias e integración (Backend ≥80%, Auth/RLS 100%) <!-- id: 24 | Se ejecuta por Sprint -->
- [ ] Pruebas E2E y funcionales <!-- id: 25 -->
- [ ] Configurar Pipeline CI/CD <!-- id: 26 -->
- [ ] Despliegue en Staging <!-- id: 27 -->
