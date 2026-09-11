# Aprovisionar sedes desde Appits — `/v1/platform/*`

> Última actualización: 2026-09-11 · Estado: **implementado en `feat/platform-sedes`**, pendiente de merge y despliegue.

Cuando un taller crea una sede en Appits (Gestión-Talleres), esa sede debe existir en
Inventarios como **tenant propio**: catálogo, stock y API key completamente separados del
taller principal. El aislamiento lo garantiza RLS en PostgreSQL, no una regla de aplicación.

Antes eran tres pasos a mano en el panel de MicroNuba (crear tenant → crear almacén →
emitir API key y pegarla en Appits). Ahora es **una llamada** desde Appits.

---

## Respuesta a las seis preguntas

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿Crear tenant por API? | Existía solo en `/admin/*` con JWT humano de super_admin. **Nuevo**: `POST /v1/platform/tenants` con API key de plataforma. |
| 2 | ¿Emitir la API key del tenant nuevo sin loguearse como su admin? | Sí: la misma llamada la devuelve. No hay que entrar como nadie. |
| 3 | ¿Almacén físico con zonas automáticas? | Sí: la misma llamada lo crea. `is_virtual=false` ⇒ zonas `RECEIVING`, `DISPATCH`, `QUARANTINE`. |
| 4 | ¿Un solo endpoint que devuelva `{tenant_id, api_key, warehouse_id}`? | **`POST /v1/platform/tenants`** — ver abajo. |
| 5 | ¿Cómo se marca que el tenant es de Appits y de qué taller? | Columnas nuevas en `tenants` (migración 014): `external_provider` (`"appits"`), `external_id` (id de la sede en Appits), `parent_tenant_id` (tenant del taller principal), `tax_id` (NIT). |
| 6 | ¿Borrar/desactivar por API? | `DELETE /v1/platform/tenants/{id}` — baja lógica + revoca sus keys. Nunca borra inventario. |

---

## Credencial: API key de plataforma

Appits **no** usa el JWT de super_admin (es humano, caduca a los 30 min). Usa una **API key
del tenant interno de MicroNuba con scope `PLATFORM`**, de larga duración, distinta de las
keys de cada taller.

**Qué puede hacer esa key:** crear, consultar y dar de baja tenants que ella misma aprovisionó.
**Qué NO puede hacer:** leer ni escribir datos de ningún tenant (productos, stock, nada).
`PLATFORM` no otorga ningún rol efectivo — `GET /v1/products` con ella responde `403`.

**Cómo se emite (una vez, un super_admin, desde el panel o por API):**

```bash
POST /admin/tenants/00000000-0000-0000-0000-000000000001/api-keys
Authorization: Bearer <JWT super_admin>

{"name": "Appits Platform", "scopes": ["PLATFORM"]}

# → 201 — guardar key_secret cifrado en Appits (config de plataforma, no de un taller)
```

En el portal: MicroNuba Internal → Nueva API Key → scope `PLATFORM` (solo aparece en ese tenant).
Emitirla en cualquier otro tenant responde `403`, incluso siendo super_admin.

---

## 1. Crear la sede — `POST /v1/platform/tenants`

Crea, en orden: el tenant con su usuario `tenant_admin` (recibe email de activación), el
almacén físico con sus tres zonas, y la API key de la sede. Si el almacén falla, la llamada
falla (500) en lugar de devolver un tenant a medias.

```http
POST /v1/platform/tenants
Authorization: Bearer <key_secret PLATFORM>
Content-Type: application/json
```

**Body**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| `name` | string | ✅ | Nombre de la sede |
| `tax_id` | string | | NIT |
| `admin_email` | email | ✅ | **Debe ser distinto al de cualquier otro tenant** — el login de Inventarios busca por correo, sin tenant. Recibe el email de activación. |
| `admin_full_name` | string | ✅ | |
| `external_id` | string | ✅ | Id de la sede en Appits (`shop_id`). Único por proveedor. |
| `external_provider` | string | | Default `"appits"` |
| `parent_tenant_id` | uuid | | Tenant de Inventarios del taller principal. Solo referencia; debe existir (si no, `404`). |
| `subscription_tier` | string | | `STARTER` (default) · `PROFESSIONAL` · `ENTERPRISE` |
| `warehouse.code` | string | | Default `"PRINCIPAL"`. Letras, dígitos, `-`, `_` |
| `warehouse.name` | string | | Default `"Bodega Principal"` |
| `warehouse.location_address` | string | | Dirección de la sede |
| `api_key_name` | string | | Default `"Appits"` |
| `api_key_scopes` | string[] | | Default: todos los de operación. **Nunca** `ADMIN` ni `PLATFORM` (→ `422`). |

**Ejemplo real**

```json
{
  "name": "Taller Demo - Sede Norte",
  "tax_id": "900123456-7",
  "admin_email": "sede.norte@tallerdemo.com",
  "admin_full_name": "Administrador Sede Norte",
  "external_id": "shop_42",
  "parent_tenant_id": "bd944e9b-2eb6-40d1-87b0-a91d94f04c64",
  "warehouse": {"code": "PRINCIPAL", "name": "Bodega Sede Norte"},
  "api_key_name": "Appits - Sede Norte"
}
```

**Response `201`**

```json
{
  "tenant_id": "1ccc6ae7-7fd4-49dd-9e69-09c0fdbdfa8c",
  "slug": "taller-demo-sede-norte",
  "name": "Taller Demo - Sede Norte",
  "external_provider": "appits",
  "external_id": "shop_42",
  "parent_tenant_id": "bd944e9b-2eb6-40d1-87b0-a91d94f04c64",
  "admin_user_id": "9c0c7c6e-f318-41d1-9239-4cff0bc718e3",
  "admin_email": "sede.norte@tallerdemo.com",
  "warehouse": {
    "id": "df4b1fa5-8103-4b3b-a7b3-8054d7e80017",
    "code": "PRINCIPAL",
    "name": "Bodega Sede Norte",
    "zones": [
      {"id": "6b9d46c2-…", "code": "PRINCIPAL-DISPATCH",   "zone_type": "DISPATCH"},
      {"id": "00331bf6-…", "code": "PRINCIPAL-QUARANTINE", "zone_type": "QUARANTINE"},
      {"id": "bf25f40d-…", "code": "PRINCIPAL-RECEIVING",  "zone_type": "RECEIVING"}
    ]
  },
  "api_key": {
    "id": "80731f3b-43e1-4960-9ef8-02e8af067b24",
    "key_id": "mk_live_yiIE5tLb96giTa0t8Lk8NCsS",
    "key_secret": "mk_secret_bAAXUWtBihChplKsJ-JN9uI_yHkQnsfPcQDAaJ-GzE4F1eXQ",
    "scopes": ["READ_CATALOG", "WRITE_CATALOG", "READ_INVENTORY", "WRITE_INVENTORY", "MANAGE_WAREHOUSES", "MANAGE_RESERVATIONS"],
    "expires_at": null
  }
}
```

**Qué guarda Appits de esto:** `tenant_id` → `X-Tenant-ID` de la sede · `api_key.key_secret` →
`shop_config.inventory_api_token_enc` de la sede · `warehouse.id` y la zona `RECEIVING` → destino
por defecto de las entradas de stock. **`key_secret` no se vuelve a mostrar.**

**Errores**

| Código | Cuándo | Qué hacer |
|---|---|---|
| `403` | La credencial no es una key `PLATFORM` del tenant interno | Revisar la key de plataforma |
| `404` | `parent_tenant_id` no existe | Verificar el tenant del taller principal |
| `409` | Ya hay un tenant con ese `external_id` — el `detail` incluye `tenant_id=…` | Es un reintento: usar el tenant existente (ver §2). **No** se crea duplicado. |
| `409` | `admin_email` ya registrado en otro tenant | Usar un correo distinto para la sede |
| `422` | Scopes `ADMIN`/`PLATFORM` en `api_key_scopes`, o datos inválidos | Corregir el body |

---

## 2. Consultar una sede

```http
GET /v1/platform/tenants/{tenant_id}
GET /v1/platform/tenants/by-external/appits/{external_id}
Authorization: Bearer <key_secret PLATFORM>
```

La segunda forma sirve tras un `409` en el alta, o para saber si una sede ya está conectada.

**Response `200`**

```json
{
  "tenant_id": "1ccc6ae7-7fd4-49dd-9e69-09c0fdbdfa8c",
  "slug": "taller-demo-sede-norte",
  "name": "Taller Demo - Sede Norte",
  "is_active": true,
  "tax_id": "900123456-7",
  "external_provider": "appits",
  "external_id": "shop_42",
  "parent_tenant_id": "bd944e9b-2eb6-40d1-87b0-a91d94f04c64",
  "warehouses": [
    {"id": "df4b1fa5-…", "code": "PRINCIPAL", "name": "Bodega Sede Norte", "zones": [ … ]}
  ],
  "created_at": "2026-09-11T18:20:31.412Z"
}
```

`404` si el tenant no existe **o no fue creado por una plataforma**: los tenants dados de alta
a mano en el panel (los talleres principales de hoy) no son visibles ni gestionables desde aquí.
No devuelve la API key: si se perdió, se emite otra desde el panel.

---

## 3. Dar de baja una sede — `DELETE /v1/platform/tenants/{tenant_id}`

Baja **lógica**: `is_active=false` (sus usuarios no pueden entrar) y **todas sus API keys quedan
revocadas**, así la key guardada en Appits deja de funcionar de inmediato (`401`).

```http
DELETE /v1/platform/tenants/1ccc6ae7-7fd4-49dd-9e69-09c0fdbdfa8c
Authorization: Bearer <key_secret PLATFORM>
```

**Response `200`**

```json
{"tenant_id": "1ccc6ae7-7fd4-49dd-9e69-09c0fdbdfa8c", "is_active": false, "api_keys_revoked": 1}
```

El inventario **no se borra**. Si la sede se eliminó por error, un super_admin la reactiva desde
el panel y emite una key nueva. El `external_id` sigue ocupado: volver a crear la misma sede
responde `409`, a propósito.

---

## Endpoints que ya existían y siguen igual

Para operar la sede una vez creada, Appits usa exactamente lo mismo que usa hoy con cada
taller — con la key y el `tenant_id` de la sede:

| Método | Endpoint | Scope |
|---|---|---|
| `GET` | `/v1/warehouses`, `/v1/warehouses/{id}/zones` | `READ_INVENTORY` |
| `POST` | `/v1/warehouses` (almacén extra; `is_virtual=false` ⇒ zonas automáticas) | `MANAGE_WAREHOUSES` |
| `GET/POST` | `/v1/products`, `/v1/categories` | `READ_CATALOG` / `WRITE_CATALOG` |
| `GET` | `/v1/stock/balances` | `READ_INVENTORY` |
| `POST` | `/v1/stock/receipts`, `/v1/stock/adjustments` | `WRITE_INVENTORY` |
| `*` | `/v1/reservations` | `MANAGE_RESERVATIONS` |

Ver [guia_rapida.md](guia_rapida.md) y [api_scopes.md](api_scopes.md).

---

## Flujo completo en Appits

```
Usuario crea sede en Appits
  │
  ├─ POST /v1/platform/tenants  (key PLATFORM)
  │     201 → guardar tenant_id, key_secret (cifrado), warehouse.id, zona RECEIVING
  │     409 → GET /v1/platform/tenants/by-external/appits/{shop_id} → usar ese tenant_id
  │            (la key no se recupera; si hace falta, emitir una nueva desde el panel)
  │
  └─ La sede opera con SU key + X-Tenant-ID = tenant_id, igual que un taller

Usuario borra la sede en Appits
  └─ DELETE /v1/platform/tenants/{tenant_id}  (key PLATFORM)
        200 → borrar la key de shop_config
```

---

## Detalles de implementación (lado Inventarios)

- **Migración `014`** — `tenants.external_provider`, `external_id`, `parent_tenant_id` (FK a
  `tenants`, `ON DELETE SET NULL`), `tax_id`. Índice único parcial `(external_provider, external_id)`:
  es lo que hace idempotente el alta.
- **Scope `PLATFORM`** — `app/schemas/api_key.py`. No está en `_API_KEY_SCOPE_ROLES` a propósito.
  `create_api_key` rechaza emitirlo fuera del tenant interno (`403`).
- **Guard `require_platform`** — `app/api/deps.py`: API key + scope `PLATFORM` + tenant interno.
- **`app/services/platform.py`** — reutiliza `create_tenant` (que ya aprovisiona el almacén
  `PRINCIPAL` desde el 2026-08-27), `create_api_key` y `warehouse.list_zones`. El alta del tenant va
  con contexto de sistema; todo lo que toca datos del tenant nuevo va con **su** contexto RLS.
- **Auditoría** — `audit_logs` del tenant nuevo: `CREATE` con `new_values.via="platform"`, y
  `UPDATE` en la baja con `api_keys_revoked`. `performed_by = {"type": "api_key", "id": <key PLATFORM>}`.
- **Tests** — `tests/test_platform.py` (12): alta completa, aislamiento con la key de la sede,
  409 por `external_id`, 404 por padre, 422 por scopes prohibidos, consulta por id y por externo,
  404 para tenants manuales, baja + revocación, y los cuatro límites de la credencial.
