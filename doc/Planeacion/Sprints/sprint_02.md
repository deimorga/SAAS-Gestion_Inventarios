# Sprint 2 — Almacenes y Motor Transaccional

**Fecha Inicio:** 2026-04-29
**Fecha Fin:** 2026-04-28
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Implementar la topología física de almacenes y el motor transaccional de inventario (entradas, salidas, transferencias, ajustes y devoluciones), con cálculo de Costo Promedio Ponderado (CPP) y registro inmutable en ledger. Sobre la base segura del Sprint 1, este sprint construye la capacidad operativa central del sistema.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|
| T-201 | RF-013 | Almacenes Multi-Sede: CRUD warehouses + zonas automáticas | ✅ Completado | Auto-zonas RECEIVING/DISPATCH/QUARANTINE |
| T-202 | RF-016 | Entrada de Mercancía + CPP (POST /v1/transactions/receipts) | ✅ Completado | Cálculo CPP ponderado, ledger append-only |
| T-203 | RF-017 | Salida de Mercancía (POST /v1/transactions/issues) | ✅ Completado | Validación stock, OCC con versión |
| T-204 | RF-018 | Transferencias Inter-Almacén (POST /v1/transactions/transfers) | ✅ Completado | Transacción atómica: salida + entrada |
| T-205 | RF-019 | Ajustes por Auditoría (POST /v1/transactions/adjustments) | ✅ Completado | Delta positivo/negativo vs qty actual |
| T-206 | RF-020 | Devoluciones/RMA (cubierto por receipts con RETURN_IN) | ✅ Completado | reference_type=RETURN_IN |
| T-207 | RF-022 | Bajas/Scrap (cubierto por issues con SCRAP_LOSS) | ✅ Completado | reason_code=SCRAP_LOSS |
| T-208 | RF-020* | Stock Balances query (GET /v1/stock/balances) | ✅ Completado | Filtros por product/warehouse/zone |
| T-209 | RF-021 | Ledger histórico (GET /v1/ledger) | ✅ Completado | Append-only, paginado |

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Umbral | Estado |
|----------|--------|--------|
| Cobertura global ≥80% | **93%** (84 tests, 1724 líneas) | ✅ |
| 0 errores `ruff` | `All checks passed!` | ✅ |
| 0 errores `mypy` | `Success: no issues found in 56 source files` | ✅ |
| Aislamiento RLS validado en nuevas tablas | warehouses, zones, stock_balances, inventory_ledger | ✅ |
| Motor transaccional ACID: OCC + ledger inmutable | 3 reintentos max en concurrencia | ✅ |
| CPP actualizado correctamente en receipts | Fórmula ponderada sobre stock total | ✅ |
| Sin secretos en código | Passwords via env vars | ✅ |

---

## 📊 Resultado

- **Tests:** 84 / 84 pasando (36 nuevos en Sprint 2)
- **Cobertura:** 93% global
- **Items completados:** 9 / 9
- **Errores ruff:** 0
- **Errores mypy:** 0

### Tablas nuevas
- `warehouses` — Almacenes físicos y virtuales con RLS
- `zones` — Zonas/bins dentro de almacenes con RLS
- `transactions` — Cabecera de cada transacción del motor
- `stock_balances` — Saldos por producto/zona/lote con OCC (version)
- `inventory_ledger` — Registro append-only de cada movimiento
