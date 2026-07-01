# Sprint 8 — Portal de Administración Operativa

**Fecha Inicio:** 2026-06-25  
**Fecha Fin Real:** 2026-07-01  
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Habilitar al equipo de MicroNuba para operar la plataforma sin necesidad de consumir la API directamente. Sprint centrado en dos frentes: (1) extender el portal NiceGUI para gestión completa de productos y stock por tenant, y (2) cerrar el ciclo de provisionamiento de clientes con la capacidad de crear API Keys desde el portal.

**Contexto:** El equipo de Talleres ya está integrado y necesita credenciales. El super_admin no debería tener que hacer curls para crear una API Key. Este sprint cierra esa brecha operativa.

---

## 📋 Items del Sprint

| ID | Área | Tarea | Estado | Notas |
|----|------|-------|--------|-------|
| T-801 | Backend | `POST /admin/tenants/{id}/api-keys` — crear API Key desde admin | ✅ Completado | Con `log_action` en audit trail (`CREATE_BY_ADMIN`) |
| T-802 | Backend | `GET/POST/PATCH/DELETE /admin/tenants/{id}/products` — CRUD productos | ✅ Completado | `admin_products.py`, usa RLS del tenant específico |
| T-803 | Backend | `GET /admin/tenants/{id}/categories` | ✅ Completado | Solo lectura, para poblar selectores |
| T-804 | Backend | `GET/POST /admin/tenants/{id}/stock/receipts` — entrada de stock | ✅ Completado | `admin_stock.py` |
| T-805 | Backend | `POST /admin/tenants/{id}/stock/adjustments` — ajuste de stock | ✅ Completado | Campo `new_qty` (cantidad real final) |
| T-806 | Backend | `GET /admin/tenants/{id}/warehouses` y `/zones` | ✅ Completado | Solo lectura, para poblar formularios |
| T-807 | Backend | Migración 013 — `sale_price` (Numeric 18,4, nullable) en `products` | ✅ Completado | No destructiva, retrocompatible |
| T-808 | Portal | Página `/tenants/{id}/products` — CRUD con agrupación por categoría | ✅ Completado | Dialogs crear/editar/desactivar; precio de venta opcional |
| T-809 | Portal | Página `/tenants/{id}/stock` — saldos + dialogs entrada/ajuste/reset | ✅ Completado | Edición inline por fila, agrupación por categoría |
| T-810 | Portal | "+ Nueva API Key" en detalle de tenant — dialog con scope checkboxes | ✅ Completado | Diálogo revela secret una sola vez |
| T-811 | Portal | Clipboard compatible Safari HTTP (`_copy_js` con execCommand fallback) | ✅ Completado | Fix para entorno local sin HTTPS |
| T-812 | Portal | Token refresh automático (401 → refresh → retry) | ✅ Completado | Redirect a `/login` si refresh también falla |
| T-813 | Portal | Edit/Suspend dialogs inline en lista de tenants | ✅ Completado | Staging branch traía esta funcionalidad |
| T-814 | Infra | `docker-compose.staging.yml` — compose completo para VPS staging | ✅ Completado | Con Traefik labels, TLS, redes |
| T-815 | Infra | `docker-compose.prod.yml` — compose completo para producción | ✅ Completado | Configuración lista para Resend en prod |
| T-816 | Infra | `.env.staging.example`, `.env.prod.example` | ✅ Completado | Templates de variables por ambiente |
| T-817 | Infra | `core_backend/Dockerfile.prod` — imagen optimizada para producción | ✅ Completado | Multi-stage, sin dependencias de dev |
| T-818 | Docs | `doc/integracion/guia_rapida.md` v1.1 — sección credenciales + staging URL | ✅ Completado | Dominio micronuba.net |
| T-819 | Docs | `doc/gateway/ambientes-produccion-staging.md` — estado ambientes y runbook | ✅ Completado | Estado staging verificado |
| T-820 | Merge | Unificación staging ↔ develop — merge/unify-staging-develop | ✅ Completado | Ambas ramas idénticas en commit `0559ce0` |

---

## 🔧 Cambios Técnicos

### Nuevos endpoints (`/admin/*`)

```
POST   /admin/tenants/{id}/api-keys              → Crear API Key (secreto visible solo en respuesta)
GET    /admin/tenants/{id}/products              → Listar productos del tenant
POST   /admin/tenants/{id}/products              → Crear producto
PATCH  /admin/tenants/{id}/products/{pid}        → Actualizar producto
DELETE /admin/tenants/{id}/products/{pid}        → Desactivar producto
GET    /admin/tenants/{id}/categories            → Listar categorías
GET    /admin/tenants/{id}/stock                 → Saldos de stock
POST   /admin/tenants/{id}/stock/receipts        → Entrada de mercancía
POST   /admin/tenants/{id}/stock/adjustments     → Ajuste de stock
GET    /admin/tenants/{id}/warehouses            → Listar almacenes
GET    /admin/tenants/{id}/warehouses/{wid}/zones → Listar zonas
```

### Archivos nuevos

| Archivo | Descripción |
|---------|-------------|
| `core_backend/app/api/admin/endpoints/admin_products.py` | Endpoints CRUD productos + categorías por tenant |
| `core_backend/app/api/admin/endpoints/admin_stock.py` | Endpoints stock (saldos, receipts, adjustments, warehouses) |
| `core_backend/alembic/versions/013_product_sale_price.py` | Migración: columna `sale_price` en tabla `products` |
| `docker-compose.staging.yml` | Stack completo para ambiente staging en VPS |
| `docker-compose.prod.yml` | Stack completo para producción |
| `.env.staging.example` | Template variables de entorno para staging |
| `.env.prod.example` | Template variables de entorno para producción |
| `core_backend/Dockerfile.prod` | Imagen Docker optimizada para producción |
| `web_frontend/.gitignore` | Excluye `.nicegui/` (estado runtime de NiceGUI) |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `core_backend/app/api/admin/endpoints/admin_tenants.py` | `POST /{id}/api-keys` con `log_action`; `GET /{id}/api-keys`; `DELETE /{id}/api-keys/{key_id}` |
| `web_frontend/app/api.py` | Funciones `create_tenant_api_key`, `list_products`, `create_product`, `update_product`, `delete_product`, `list_categories`, `list_stock`, `stock_receipt`, `stock_adjustment`, `list_warehouses`, `list_zones`; token refresh (`_authed_request` con 401 retry) |
| `web_frontend/app/main.py` | Páginas `/tenants/{id}/products` y `/tenants/{id}/stock`; diálogo "+ Nueva API Key" con reveal de secreto; `_copy_js()` para clipboard Safari; edit/suspend dialogs en lista; token refresh integrado |

### Fix crítico — campo `data` en PaginatedResponse

El API retorna `{ "data": [...], "pagination": {...} }` (no `"items"`). El portal usaba `keys_data.get("items", [])` en tres lugares — corregido a `"data"` en este sprint.

---

## 🎯 Criterios de Entrega (DoD)

| Criterio | Estado |
|----------|--------|
| Endpoint `POST /admin/tenants/{id}/api-keys` funcional y documentado en Swagger | ✅ |
| Portal: "+ Nueva API Key" disponible en detalle de tenant, secret visible una vez | ✅ |
| Portal: página `/products` con CRUD funcional (crear, editar, desactivar) | ✅ |
| Portal: página `/stock` con saldos, entrada y ajuste funcionales | ✅ |
| Migración 013 aplicada en staging | ✅ |
| Clipboard funcional en Safari HTTP local | ✅ |
| Ramas `develop` y `staging` idénticas en GitHub | ✅ |
| Documentación funcional (RF-044, RF-045) actualizada | ✅ |

---

## 📌 Decisiones de Diseño

| # | Decisión | Alternativa descartada | Razón |
|---|----------|----------------------|-------|
| D-01 | Portal usa `_authed_request` con 401 retry para token refresh | Re-login manual | Experiencia de uso sostenida sin interrupciones |
| D-02 | `sale_price` como campo nullable en Product | Tabla separada de precios | Simplicidad; el sistema no gestiona ventas, solo referencia el precio |
| D-03 | Clipboard con `execCommand` fallback para Safari | Solo Clipboard API | Entorno local sin HTTPS bloquea `navigator.clipboard` en Safari |
| D-04 | Secret de API Key visible solo en diálogo de creación | Segunda vista de secret | El secret no se almacena en texto plano — solo disponible en la respuesta de creación |
| D-05 | Endpoints admin de productos/stock usan RLS del tenant específico | RLS `__super_admin__` bypass | Garantiza que el admin opera exactamente igual que el tenant, sin riesgo de cross-tenant |

---

## 🔗 Trazabilidad

| RF | Implementación |
|----|---------------|
| RF-044 (extendido) | `POST /admin/tenants/{id}/api-keys` + portal "+ Nueva API Key" |
| RF-045 (nuevo) | `admin_products.py`, `admin_stock.py`, páginas `/products` y `/stock` en portal |
| RN-006-6 (nuevo) | Campo `sale_price` en Product (Migración 013) |
