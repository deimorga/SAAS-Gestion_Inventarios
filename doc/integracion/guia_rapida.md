# Guía Rápida de Integración — MicroNuba Inventory API

**Versión:** 1.1 · **Fecha:** 2026-07-01  
**Audiencia:** Desarrolladores externos que consumen la API desde sistemas de terceros (ej. Gestión de Talleres).

---

## Tabla de contenidos

0. [Credenciales que recibes de MicroNuba](#0-credenciales-que-recibes-de-micronuba)
1. [Prerrequisitos](#1-prerrequisitos)
2. [Autenticarse y obtener JWT](#2-autenticarse-y-obtener-jwt)
3. [Crear una API Key](#3-crear-una-api-key)
4. [Verificar que la key funciona](#4-verificar-que-la-key-funciona)
5. [Flujo E2E 1 — Entrada de mercancía](#5-flujo-e2e-1--entrada-de-mercancía)
6. [Flujo E2E 2 — Salida por consumo en taller](#6-flujo-e2e-2--salida-por-consumo-en-taller)
7. [Flujo E2E 3 — Consulta de saldo de stock](#7-flujo-e2e-3--consulta-de-saldo-de-stock)
8. [Refrescar el token](#8-refrescar-el-token)
9. [Errores comunes](#9-errores-comunes)

---

## 0. Credenciales que recibes de MicroNuba

Cuando tu cuenta es activada, el equipo de MicroNuba te entrega estos tres datos:

| Dato | Ejemplo | Para qué sirve |
|---|---|---|
| **API URL** | `https://staging.inventarios.micronuba.net` | URL base de todas las llamadas |
| **Tenant ID** | `e8826b95-4fe0-43d8-a1b9-02e54a5b26a9` | Identifica tu cuenta en el sistema |
| **API Key** | `mk_live_xxxx.mk_secret_yyyy` | Header `X-API-Key` en cada request |

> **Importante:** La API Key solo se muestra una vez al momento de ser generada. Guárdala de inmediato en tu gestor de secretos (variables de entorno, AWS Secrets Manager, etc.). Si la pierdes, debes contactar a MicroNuba para revocarla y emitir una nueva.

### Verificación rápida (30 segundos)

```bash
curl -s https://staging.inventarios.micronuba.net/health \
  -H "X-API-Key: mk_live_xxxx.mk_secret_yyyy"
# → {"status": "ok"}
```

Si el health check responde `200 OK`, tu integración está lista para empezar.

---

## 1. Prerrequisitos

### URLs base

| Entorno     | URL base                                              |
|-------------|-------------------------------------------------------|
| Desarrollo  | `http://localhost:8002`                               |
| Staging     | `https://staging.inventarios.micronuba.net`           |
| Producción  | `https://api.inventarios.micronuba.net`               |

> La documentación interactiva (Swagger UI) está disponible en `{base_url}/docs` (desactivada en producción).

### Prefijos de ruta

| Tipo de endpoint          | Prefijo    |
|---------------------------|------------|
| API pública (tenant)      | `/v1/`     |
| Administración SaaS       | `/admin/`  |

### Cabeceras requeridas

Todas las peticiones deben incluir:

```
Content-Type: application/json
```

Y **una** de las siguientes cabeceras de autenticación:

| Método      | Cabecera                                        | Cuándo usarlo                          |
|-------------|------------------------------------------------|----------------------------------------|
| JWT Bearer  | `Authorization: Bearer <access_token>`         | Sesiones interactivas, setup inicial   |
| API Key     | `X-API-Key: <key_id>.<key_secret>`             | Integraciones M2M, scripts, servicios  |

### Visión general del flujo de autenticación

```
1. POST /v1/auth/login  →  access_token (JWT, 30 min) + refresh_token (7 días)
2. POST /v1/api-keys    →  key_id + key_secret  ← guardar en sitio seguro, solo se muestran una vez
3. Todas las llamadas   →  X-API-Key: {key_id}.{key_secret}
```

---

## 2. Autenticarse y obtener JWT

```bash
curl -s -X POST http://localhost:8002/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@mi-taller.com",
    "password": "Mi$Passw0rd"
  }'
# → Response 200
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTc4OTAtYWJjZC1lZjEyMzQ1Njc4OTAiLCJ0ZW5hbnQiOiJiMWMyZDNlNGY1YTYiLCJyb2xlIjoidGVuYW50X2FkbWluIiwiZXhwIjoxNzQ3MjM0NTY3fQ.sig",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNCIsImV4cCI6MTc0Nzc1NjM2N30.ref",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "admin@mi-taller.com",
    "full_name": "Juan García",
    "role": "tenant_admin",
    "tenant_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891"
  }
}
```

| Campo           | Descripción                                                          |
|-----------------|----------------------------------------------------------------------|
| `access_token`  | JWT para usar en `Authorization: Bearer`. Expira en 30 minutos.     |
| `refresh_token` | Token de rotación para renovar el JWT. Válido 7 días.               |
| `expires_in`    | Vida del `access_token` en segundos (`1800` = 30 min).              |
| `user.role`     | `tenant_admin`, `inventory_manager` o `viewer`.                     |

---

## 3. Crear una API Key

Use el JWT obtenido en el paso anterior. El `key_secret` **solo se muestra en esta respuesta**; no existe forma de recuperarlo después.

```bash
curl -s -X POST http://localhost:8002/v1/api-keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTc4OTAtYWJjZC1lZjEyMzQ1Njc4OTAiLCJ0ZW5hbnQiOiJiMWMyZDNlNGY1YTYiLCJyb2xlIjoidGVuYW50X2FkbWluIiwiZXhwIjoxNzQ3MjM0NTY3fQ.sig" \
  -d '{
    "name": "Integración Sistema Gestión Talleres",
    "scopes": ["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"],
    "ip_whitelist": null,
    "expires_at": "2027-01-01T00:00:00Z"
  }'
# → Response 201
```

```json
{
  "id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
  "key_id": "mnk_a1b2c3d4e5f6",
  "key_secret": "sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v",
  "name": "Integración Sistema Gestión Talleres",
  "scopes": ["READ_INVENTORY", "WRITE_INVENTORY", "READ_CATALOG"],
  "ip_whitelist": null,
  "is_active": true,
  "expires_at": "2027-01-01T00:00:00Z",
  "created_at": "2026-05-14T10:00:00Z"
}
```

> **IMPORTANTE:** Guarde `key_id` y `key_secret` en su gestor de secretos ahora mismo. El `key_secret` no vuelve a mostrarse. Si lo pierde, debe revocar la key y crear una nueva.

La cabecera de uso a partir de este momento es:

```
X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v
```

### Scopes disponibles

| Scope                 | Qué permite                                               |
|-----------------------|-----------------------------------------------------------|
| `READ_INVENTORY`      | Consultar saldos, ledger y balances de stock              |
| `WRITE_INVENTORY`     | Registrar entradas, salidas, transferencias y ajustes     |
| `READ_CATALOG`        | Consultar productos, categorías y unidades de medida      |
| `WRITE_CATALOG`       | Crear y editar productos y categorías                     |
| `MANAGE_WAREHOUSES`   | Crear y administrar almacenes, zonas y bins               |
| `MANAGE_RESERVATIONS` | Crear, confirmar y liberar reservas de stock              |
| `ADMIN`               | Acceso completo incluyendo gestión de usuarios y API Keys |

---

## 4. Verificar que la key funciona

```bash
curl -s http://localhost:8002/v1/warehouses \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

```json
{
  "data": [
    {
      "id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "code": "ALM-PRINCIPAL",
      "name": "Almacén Principal Taller",
      "is_virtual": false,
      "is_active": true
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 1,
    "total_items": 1,
    "total_pages": 1
  }
}
```

Si recibe `200`, su integración está lista. Si recibe `401`, revise que el header `X-API-Key` tenga el formato exacto `{key_id}.{key_secret}` (punto como separador).

---

## 5. Flujo E2E 1 — Entrada de mercancía

**Caso de uso Talleres:** El proveedor entrega repuestos (filtros, correas) contra la Orden de Compra OC-2026-00145. El sistema de gestión de talleres debe registrar esa recepción en el inventario.

### 5.1 Obtener el almacén destino

```bash
curl -s http://localhost:8002/v1/warehouses \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

Anote el `id` del almacén donde se recibirá la mercancía, p.ej. `b1c2d3e4-f5a6-7890-bcde-f01234567891`.

### 5.2 Obtener la zona de recepción

```bash
curl -s http://localhost:8002/v1/warehouses/b1c2d3e4-f5a6-7890-bcde-f01234567891/zones \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

```json
[
  {
    "id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
    "code": "RECEIVING",
    "name": "Zona de Recepción",
    "zone_type": "RECEIVING",
    "is_active": true
  },
  {
    "id": "d3e4f5a6-b7c8-9012-defa-123456789013",
    "code": "DISPATCH",
    "name": "Zona de Despacho",
    "zone_type": "DISPATCH",
    "is_active": true
  }
]
```

Anote el `id` de la zona `RECEIVING`, p.ej. `c2d3e4f5-a6b7-8901-cdef-012345678902`.

### 5.3 Buscar el producto (o crearlo si no existe)

**Buscar por SKU:**

```bash
curl -s "http://localhost:8002/v1/products?search=FILTRO-ACEITE-001&page=1" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

**Si el producto no existe, crearlo** (requiere scope `WRITE_CATALOG`):

```bash
curl -s -X POST http://localhost:8002/v1/products \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v" \
  -d '{
    "sku": "FILTRO-ACEITE-001",
    "name": "Filtro de aceite motor 2.0L",
    "description": "Compatible con motores Chevrolet 2.0L y 2.4L — modelos 2015–2024.",
    "base_uom": "UND",
    "reorder_point": 5,
    "track_lots": false,
    "track_serials": false,
    "track_expiry": false,
    "low_stock_alert_enabled": true,
    "metadata": {"marca": "Bosch", "referencia_oem": "1457429618"}
  }'
# → Response 201
```

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "sku": "FILTRO-ACEITE-001",
  "name": "Filtro de aceite motor 2.0L",
  "base_uom": "UND",
  "current_cpp": "0.00",
  "reorder_point": "5.00",
  "is_active": true
}
```

Anote el `id` del producto, p.ej. `a1b2c3d4-e5f6-7890-abcd-ef1234567890`.

### 5.4 Registrar la entrada de mercancía

```bash
curl -s -X POST http://localhost:8002/v1/transactions/receipts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v" \
  -d '{
    "reference_type": "PURCHASE_ORDER",
    "reference_id": "OC-2026-00145",
    "reason_code": "COMPRA",
    "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
    "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
    "items": [
      {
        "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "quantity": 20,
        "unit_cost": 15500.00
      }
    ]
  }'
# → Response 201
```

```json
{
  "transaction_id": "e4f5a6b7-c8d9-0123-efab-234567890124",
  "transaction_type": "RECEIPT",
  "timestamp": "2026-05-14T10:15:30Z",
  "status": "COMPLETED",
  "items_processed": 1
}
```

### 5.5 Verificar que el stock aumentó

```bash
curl -s "http://localhost:8002/v1/stock/balances?product_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890&warehouse_id=b1c2d3e4-f5a6-7890-bcde-f01234567891" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

```json
{
  "data": [
    {
      "id": "f5a6b7c8-d9e0-1234-fabc-345678901235",
      "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
      "lot_number": null,
      "physical_qty": "20.00",
      "reserved_qty": "0.00",
      "available_qty": "20.00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 1,
    "total_pages": 1
  }
}
```

---

## 6. Flujo E2E 2 — Salida por consumo en taller

**Caso de uso Talleres:** El mecánico usa 2 filtros de aceite para atender la Orden de Trabajo OT-2026-00892. El sistema de talleres debe descontar esas unidades del inventario.

### 6.1 Verificar stock disponible antes de descontar

```bash
curl -s "http://localhost:8002/v1/stock/balances?product_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890&warehouse_id=b1c2d3e4-f5a6-7890-bcde-f01234567891" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200 — confirmar que available_qty >= 2 antes de continuar
```

### 6.2 Registrar la salida

```bash
curl -s -X POST http://localhost:8002/v1/transactions/issues \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v" \
  -d '{
    "reference_type": "SALES_ORDER",
    "reference_id": "OT-2026-00892",
    "reason_code": "CONSUMO_TALLER",
    "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
    "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
    "items": [
      {
        "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "quantity": 2
      }
    ]
  }'
# → Response 201
```

```json
{
  "transaction_id": "a6b7c8d9-e0f1-2345-abcd-456789012346",
  "transaction_type": "ISSUE",
  "timestamp": "2026-05-14T11:30:00Z",
  "status": "COMPLETED",
  "items_processed": 1
}
```

> `unit_cost` es opcional en salidas. El sistema aplica automáticamente el CPP (Costo Promedio Ponderado) vigente del producto.

### 6.3 Verificar el ledger de movimientos

```bash
curl -s "http://localhost:8002/v1/ledger?product_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

```json
{
  "data": [
    {
      "id": "b7c8d9e0-f1a2-3456-bcde-567890123457",
      "transaction_id": "a6b7c8d9-e0f1-2345-abcd-456789012346",
      "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
      "movement_type": "ISSUE",
      "qty_change": "-2.00",
      "unit_cost": "15500.00",
      "reference_type": "SALES_ORDER",
      "reference_id": "OT-2026-00892",
      "reason_code": "CONSUMO_TALLER",
      "created_at": "2026-05-14T11:30:00Z"
    },
    {
      "id": "c8d9e0f1-a2b3-4567-cdef-678901234568",
      "transaction_id": "e4f5a6b7-c8d9-0123-efab-234567890124",
      "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "movement_type": "RECEIPT",
      "qty_change": "20.00",
      "unit_cost": "15500.00",
      "reference_type": "PURCHASE_ORDER",
      "reference_id": "OC-2026-00145",
      "reason_code": "COMPRA",
      "created_at": "2026-05-14T10:15:30Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 2,
    "total_pages": 1
  }
}
```

El ledger es inmutable (append-only): cada movimiento queda registrado permanentemente con su `reference_id` para trazabilidad.

---

## 7. Flujo E2E 3 — Consulta de saldo de stock

### Consulta con filtros

```bash
curl -s "http://localhost:8002/v1/stock/balances?product_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890&warehouse_id=b1c2d3e4-f5a6-7890-bcde-f01234567891&page=1&page_size=50" \
  -H "X-API-Key: mnk_a1b2c3d4e5f6.sk_7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v"
# → Response 200
```

```json
{
  "data": [
    {
      "id": "f5a6b7c8-d9e0-1234-fabc-345678901235",
      "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
      "lot_number": null,
      "physical_qty": "18.00",
      "reserved_qty": "0.00",
      "available_qty": "18.00"
    }
  ]
}
```

### Interpretación de los campos de cantidad

| Campo          | Significado                                                                       |
|----------------|-----------------------------------------------------------------------------------|
| `physical_qty` | Unidades físicamente presentes en el almacén (incluyendo las reservadas).         |
| `reserved_qty` | Unidades comprometidas por reservas activas; no disponibles para nuevas salidas.  |
| `available_qty`| Stock que puede despacharse: `physical_qty − reserved_qty`.                       |

> Use siempre `available_qty` para decidir si puede procesar una salida. Nunca use `physical_qty` directamente: puede incluir stock ya reservado para otras órdenes.

### Filtros disponibles en `/v1/stock/balances`

| Parámetro      | Tipo   | Descripción                                   |
|----------------|--------|-----------------------------------------------|
| `product_id`   | UUID   | Filtrar por producto                          |
| `warehouse_id` | UUID   | Filtrar por almacén                           |
| `zone_id`      | UUID   | Filtrar por zona específica dentro del almacén|
| `page`         | int    | Página (defecto: 1)                           |
| `page_size`    | int    | Registros por página (máx. 200, defecto: 50)  |

---

## 8. Refrescar el token

El `access_token` expira en 30 minutos. Renuévelo con el `refresh_token` antes de que expire. El refresh token se rota en cada llamada.

```bash
curl -s -X POST http://localhost:8002/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNCIsImV4cCI6MTc0Nzc1NjM2N30.ref"
  }'
# → Response 200
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNC1lNWY2LTc4OTAtYWJjZC1lZjEyMzQ1Njc4OTAiLCJleHAiOjE3NDcyMzgxNjd9.new",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMWIyYzNkNCIsImV4cCI6MTc0ODM0NjM2N30.rot",
  "token_type": "bearer",
  "expires_in": 1800
}
```

> El `refresh_token` devuelto reemplaza al anterior. Actualice su almacén de tokens con ambos valores.  
> Las integraciones de servicio (M2M) deben usar API Keys en lugar de JWT para evitar gestionar la rotación de tokens.

---

## 9. Errores comunes

| Código HTTP | Código de error    | Causa más frecuente                                                       | Acción recomendada                                              |
|-------------|--------------------|---------------------------------------------------------------------------|-----------------------------------------------------------------|
| `401`       | No autenticado     | Token JWT expirado, API Key inválida o cabecera ausente                   | Refrescar el JWT (sección 8) o verificar el formato de la key  |
| `403`       | Permisos insuficientes | La API Key no tiene el scope requerido para esa operación             | Crear una nueva key con los scopes correctos (sección 3)        |
| `409`       | Conflicto          | Stock insuficiente para la salida, o código duplicado (SKU, almacén)      | Consultar `available_qty` antes de la salida (sección 7)        |
| `422`       | Error de validación| Campo requerido faltante, formato de UUID incorrecto, cantidad ≤ 0        | Revisar el detalle en `detail[].msg` de la respuesta            |
| `429`       | Rate limit         | Demasiadas peticiones en la ventana de tiempo                             | Aplicar backoff exponencial y reintentar tras el período indicado|

Para el catálogo completo de errores y sus códigos internos, consulte [`error_catalog.md`](error_catalog.md).
