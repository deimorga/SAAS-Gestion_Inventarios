# Guía de Scopes — MicroNuba Inventory API

> Reference last updated: 2026-05-14

Los **scopes** son permisos granulares que determinan qué operaciones puede realizar una API Key. Cada key se crea con uno o más scopes que no pueden modificarse después de la creación. La autenticación con API Key se realiza enviando el secreto en la cabecera `X-API-Key: <key_secret>`.

Las API Keys se crean vía `POST /v1/api-keys` usando un JWT de sesión con rol `tenant_admin` o `super_admin`. Una vez creada, la key puede usarse de forma independiente (sin JWT) en todos los endpoints para los que tenga los scopes requeridos.

---

## Los 7 Scopes disponibles

| Scope | Descripción | Operaciones que habilita |
|---|---|---|
| `READ_INVENTORY` | Consulta de inventario | Saldos de stock, ledger de movimientos, kardex, reportes de valoración, stock bajo, lotes por vencer |
| `WRITE_INVENTORY` | Escritura de inventario | Entradas, salidas, transferencias, ajustes, bajas, devoluciones, re-empaques, conteo cíclico |
| `READ_CATALOG` | Consulta de catálogo | Productos, categorías, UOM, kits/BOM, lotes, seriales, proveedores, costos de reposición |
| `WRITE_CATALOG` | Escritura de catálogo | Crear/editar productos, categorías, UOM, componentes de kit, lotes, proveedores |
| `MANAGE_WAREHOUSES` | Gestión de almacenes | Crear/editar almacenes, zonas, bins; bloquear/desbloquear ubicaciones |
| `MANAGE_RESERVATIONS` | Gestión de reservas | Crear, confirmar y cancelar reservas; gestionar cuotas por canal |
| `ADMIN` | Administración del tenant | Gestión de API Keys y usuarios del tenant (solo `tenant_admin`) |

---

## Endpoints por scope

### READ_INVENTORY

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/v1/stock/balances` | Saldos actuales por producto/zona/lote (`physical_qty`, `reserved_qty`, `available_qty`) |
| `GET` | `/v1/ledger` | Historial inmutable de movimientos (append-only) |
| `GET` | `/v1/reports/kardex` | Kardex histórico de un producto con balance acumulado por movimiento |
| `GET` | `/v1/reports/valuation` | Valoración contable del inventario por CPP |
| `GET` | `/v1/reports/valuation/snapshots` | Listar snapshots de cierre contable |
| `GET` | `/v1/reports/low-stock` | Alertas de productos en o por debajo del punto de reorden |
| `GET` | `/v1/reports/expiring` | Lotes con fecha de vencimiento próxima |
| `GET` | `/v1/warehouses` | Listar almacenes |
| `GET` | `/v1/warehouses/{warehouse_id}` | Detalle de un almacén con sus zonas |
| `GET` | `/v1/warehouses/{warehouse_id}/zones` | Listar zonas del almacén |
| `GET` | `/v1/warehouses/zones/{zone_id}` | Detalle de una zona |
| `GET` | `/v1/warehouses/{warehouse_id}/zones/{zone_id}/bins` | Listar bins de una zona |
| `GET` | `/v1/cycle-counts` | Listar sesiones de conteo cíclico |
| `GET` | `/v1/cycle-counts/{session_id}` | Detalle de una sesión de conteo con varianzas |

### WRITE_INVENTORY

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/v1/transactions/receipts` | Registrar entrada de mercancía (incrementa stock, recalcula CPP) |
| `POST` | `/v1/transactions/issues` | Registrar salida de mercancía (con pre-validación y OCC) |
| `POST` | `/v1/transactions/transfers` | Transferencia inter-almacén (genera TRANSFER_OUT + TRANSFER_IN) |
| `POST` | `/v1/transactions/adjustments` | Ajuste por conteo físico (fija el stock a una cantidad exacta) |
| `POST` | `/v1/transactions/repacks` | Re-empaque: convertir una presentación en otra de forma atómica |
| `POST` | `/v1/reports/valuation/snapshots` | Crear snapshot contable de cierre (responde 202, corre en background) |
| `POST` | `/v1/cycle-counts` | Iniciar sesión de conteo cíclico |
| `PATCH` | `/v1/cycle-counts/{session_id}/items/{item_id}` | Registrar cantidad contada para un ítem |
| `POST` | `/v1/cycle-counts/{session_id}/close` | Cerrar sesión y aplicar ajustes automáticos |
| `POST` | `/v1/warehouses` | Crear almacén (auto-crea zonas RECEIVING/DISPATCH/QUARANTINE) |
| `PATCH` | `/v1/warehouses/{warehouse_id}` | Actualizar almacén |
| `POST` | `/v1/warehouses/{warehouse_id}/zones` | Crear zona en un almacén |
| `PATCH` | `/v1/warehouses/zones/{zone_id}` | Actualizar zona |
| `POST` | `/v1/warehouses/{warehouse_id}/zones/{zone_id}/bins` | Crear bin en una zona |
| `PATCH` | `/v1/warehouses/bins/{bin_id}` | Actualizar bin |
| `DELETE` | `/v1/warehouses/bins/{bin_id}` | Desactivar bin (soft delete) |
| `POST` | `/v1/warehouses/bins/{bin_id}/locks` | Bloquear bin (impide movimientos de inventario) |
| `DELETE` | `/v1/warehouses/bins/{bin_id}/locks` | Desbloquear bin |
| `POST` | `/v1/batches/{batch_id}/serials` | Registrar seriales en un lote |
| `POST` | `/v1/channel-allocations` | Definir cuota de inventario por canal de venta |
| `PATCH` | `/v1/channel-allocations/{allocation_id}` | Actualizar cuota de canal |
| `DELETE` | `/v1/channel-allocations/{allocation_id}` | Eliminar cuota de canal |

### READ_CATALOG

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/v1/products` | Listar productos con filtros por categoría, estado y búsqueda por SKU/nombre |
| `GET` | `/v1/products/{product_id}` | Detalle de un producto (CPP actual, punto de reorden) |
| `GET` | `/v1/products/{product_id}/uom` | Conversiones de unidad de medida del producto |
| `GET` | `/v1/products/{product_id}/components` | Componentes del kit/BOM (productos con `is_kit=true`) |
| `GET` | `/v1/categories` | Árbol de categorías (jerarquía o lista plana) |
| `GET` | `/v1/categories/{cat_id}` | Detalle de una categoría |
| `GET` | `/v1/batches` | Listar lotes (filtrable por producto) |
| `GET` | `/v1/batches/{batch_id}` | Detalle de un lote con fechas de fabricación y vencimiento |
| `GET` | `/v1/batches/{batch_id}/serials` | Listar seriales del lote con su estado |
| `GET` | `/v1/serials/{serial_number}/status` | Consultar estado de un serial (AVAILABLE / RESERVED / CONSUMED) |
| `GET` | `/v1/suppliers` | Listar proveedores |
| `GET` | `/v1/suppliers/{supplier_id}` | Detalle de un proveedor |
| `GET` | `/v1/suppliers/{supplier_id}/products` | Productos del proveedor con costos de reposición, lead time y MOQ |
| `GET` | `/v1/channel-allocations` | Listar cuotas de inventario por canal |

### WRITE_CATALOG

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/v1/products` | Crear producto (nuevo SKU en el catálogo) |
| `PATCH` | `/v1/products/{product_id}` | Actualizar producto parcialmente |
| `DELETE` | `/v1/products/{product_id}` | Desactivar producto (soft delete, preserva historial) |
| `POST` | `/v1/products/{product_id}/uom` | Agregar conversión de unidad al producto |
| `DELETE` | `/v1/products/{product_id}/uom/{uom_id}` | Eliminar conversión de unidad |
| `POST` | `/v1/products/{product_id}/components` | Agregar componente al kit/BOM |
| `DELETE` | `/v1/products/{product_id}/components/{component_id}` | Eliminar componente del kit |
| `POST` | `/v1/categories` | Crear categoría (con soporte de jerarquía) |
| `PATCH` | `/v1/categories/{cat_id}` | Actualizar categoría (recalcula path automáticamente) |
| `DELETE` | `/v1/categories/{cat_id}` | Eliminar categoría |
| `POST` | `/v1/batches` | Crear lote para productos con `track_lots=true` |
| `POST` | `/v1/suppliers` | Registrar proveedor |
| `PATCH` | `/v1/suppliers/{supplier_id}` | Actualizar proveedor |
| `DELETE` | `/v1/suppliers/{supplier_id}` | Desactivar proveedor (soft delete) |
| `POST` | `/v1/suppliers/{supplier_id}/products` | Asociar producto al proveedor con costo de reposición |
| `PATCH` | `/v1/suppliers/{supplier_id}/products/{sp_id}` | Actualizar costo, lead time o MOQ del proveedor |
| `DELETE` | `/v1/suppliers/{supplier_id}/products/{sp_id}` | Eliminar asociación proveedor-producto |

### MANAGE_WAREHOUSES

> Este scope extiende los permisos de escritura de `WRITE_INVENTORY` para las operaciones estructurales de almacén. Los endpoints de consulta de almacenes requieren `READ_INVENTORY`.

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/v1/warehouses` | Crear almacén (auto-crea zonas RECEIVING/DISPATCH/QUARANTINE) |
| `PATCH` | `/v1/warehouses/{warehouse_id}` | Actualizar nombre, estado o configuración del almacén |
| `POST` | `/v1/warehouses/{warehouse_id}/zones` | Crear zona adicional (con soporte de jerarquía de zonas) |
| `PATCH` | `/v1/warehouses/zones/{zone_id}` | Actualizar nombre, tipo o estado de una zona |
| `POST` | `/v1/warehouses/{warehouse_id}/zones/{zone_id}/bins` | Crear bin/ubicación en una zona |
| `PATCH` | `/v1/warehouses/bins/{bin_id}` | Actualizar bin (capacidades, nombre, estado) |
| `DELETE` | `/v1/warehouses/bins/{bin_id}` | Desactivar bin (soft delete) |
| `POST` | `/v1/warehouses/bins/{bin_id}/locks` | Bloquear bin (impide movimientos de inventario) |
| `DELETE` | `/v1/warehouses/bins/{bin_id}/locks` | Desbloquear bin |

### MANAGE_RESERVATIONS

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/v1/reservations` | Crear reserva de stock (reduce `available_qty`, con TTL configurable) |
| `GET` | `/v1/reservations` | Listar reservas (filtrable por estado: ACTIVE, COMPLETED, CANCELLED, EXPIRED) |
| `GET` | `/v1/reservations/{reservation_id}` | Detalle de una reserva con sus ítems |
| `POST` | `/v1/reservations/{reservation_id}/confirm` | Confirmar reserva (convierte a salida real de inventario) |
| `POST` | `/v1/reservations/{reservation_id}/cancel` | Cancelar reserva (libera el stock reservado a `available_qty`) |
| `POST` | `/v1/channel-allocations` | Definir cuota de inventario por canal de venta (WEB, POS, B2B, etc.) |
| `GET` | `/v1/channel-allocations` | Listar cuotas por canal |
| `PATCH` | `/v1/channel-allocations/{allocation_id}` | Actualizar cuota de canal |
| `DELETE` | `/v1/channel-allocations/{allocation_id}` | Eliminar cuota de canal |

### ADMIN

> Requiere autenticación JWT con rol `tenant_admin`. Las API Keys con scope `ADMIN` pueden gestionar otras keys del mismo tenant.

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/v1/api-keys` | Listar API Keys del tenant (el secreto nunca se retorna) |
| `POST` | `/v1/api-keys` | Crear nueva API Key con scopes específicos |
| `DELETE` | `/v1/api-keys/{key_id}` | Revocar API Key permanentemente |
| `POST` | `/v1/api-keys/{key_uuid}/rotate` | Rotar key (genera nueva con los mismos atributos; la anterior expira en período de gracia) |
| `GET` | `/v1/users` | Listar usuarios del tenant con paginación |
| `POST` | `/v1/users` | Crear usuario en el tenant (solo roles no privilegiados) |
| `PATCH` | `/v1/users/{user_id}` | Actualizar nombre o estado de un usuario |

---

## Combinaciones mínimas por caso de uso

| Caso de uso | Scopes mínimos |
|---|---|
| Solo consultar saldos | `READ_INVENTORY`, `READ_CATALOG` |
| Sistema POS (ventas) | `READ_INVENTORY`, `WRITE_INVENTORY`, `READ_CATALOG` |
| Gestión de compras (entradas) | `READ_INVENTORY`, `WRITE_INVENTORY`, `READ_CATALOG` |
| E-commerce (reservas y canal) | `READ_INVENTORY`, `MANAGE_RESERVATIONS`, `READ_CATALOG` |
| Sistema de reportes | `READ_INVENTORY`, `READ_CATALOG` |
| Integración completa (ERP) | `READ_INVENTORY`, `WRITE_INVENTORY`, `READ_CATALOG`, `WRITE_CATALOG`, `MANAGE_RESERVATIONS` |
| Setup inicial (crear almacenes) | `MANAGE_WAREHOUSES` |
| Administración completa | `ADMIN` (+ scopes adicionales según necesidad) |

---

## Ejemplos de creación de API Key

### 1. Key mínima para sistema POS

Scopes: `READ_INVENTORY`, `WRITE_INVENTORY`, `READ_CATALOG`

```bash
curl -X POST https://api.micronuba.com/v1/api-keys \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integración POS - Sucursal Centro",
    "scopes": ["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"],
    "expires_in_days": 365
  }'
```

Respuesta (el campo `key_secret` solo se muestra en esta llamada):

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Integración POS - Sucursal Centro",
  "key_secret": "mnk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "scopes": ["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"],
  "expires_at": "2027-05-14T00:00:00Z",
  "is_active": true
}
```

### 2. Key de integración completa (ERP / sin ADMIN)

Scopes: `READ_INVENTORY`, `WRITE_INVENTORY`, `READ_CATALOG`, `WRITE_CATALOG`, `MANAGE_WAREHOUSES`, `MANAGE_RESERVATIONS`

```bash
curl -X POST https://api.micronuba.com/v1/api-keys \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ERP Integration - Producción",
    "scopes": [
      "READ_INVENTORY",
      "WRITE_INVENTORY",
      "READ_CATALOG",
      "WRITE_CATALOG",
      "MANAGE_WAREHOUSES",
      "MANAGE_RESERVATIONS"
    ],
    "expires_in_days": 180
  }'
```

### Uso de la key en requests posteriores

```bash
curl -X GET "https://api.micronuba.com/v1/stock/balances?warehouse_id=<uuid>" \
  -H "X-API-Key: mnk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## Notas importantes

- **Los scopes son inmutables tras la creación.** Si se necesitan permisos adicionales, se debe crear una nueva API Key y revocar la anterior con `DELETE /v1/api-keys/{key_id}`.
- **El secreto (`key_secret`) solo se expone una vez**, en la respuesta de creación. Almacenarlo de forma segura inmediatamente.
- **El scope `ADMIN` permite gestionar otras API Keys del tenant.** Usarlo con precaución y asignarlo solo a integraciones de administración interna.
- **Principio de mínimo privilegio:** solicitar únicamente los scopes que la integración necesita. Un sistema de reportes no necesita `WRITE_INVENTORY`.
- **Rotación de keys:** usar `POST /v1/api-keys/{key_uuid}/rotate` para rotar sin downtime. Con `immediate=false` (por defecto), la key antigua permanece activa durante el período de gracia configurado (default 30 días).
- **IP Whitelist (opcional):** al crear la key se puede especificar una lista de IPs permitidas para restringir el origen de las llamadas.
