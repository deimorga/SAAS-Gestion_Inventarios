# Catálogo de Errores — MicroNuba Inventory API

> Referencia actualizada: 2026-05-14

Este catálogo documenta todos los códigos de error que puede retornar la API de MicroNuba Inventory, incluyendo el mensaje exacto del campo `detail`, la causa que lo produce y la acción recomendada para el cliente. Los mensajes en español son los que aparecen literalmente en las respuestas de la API.

---

## Formato de respuesta de error

La API retorna errores en dos formas distintas según el origen:

**1. Errores de negocio / autenticación (HTTPException)**

```json
{
  "detail": "Mensaje de error legible en español"
}
```

**2. Errores de validación de esquema (Pydantic / FastAPI)**

```json
{
  "detail": [
    {
      "loc": ["body", "nombre_del_campo"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

> **Nota:** cuando `detail` es un arreglo, el error proviene de la validación automática del cuerpo o los parámetros de la solicitud. Cuando es una cadena, es un error lanzado explícitamente por la lógica de negocio.

---

## Tabla de errores por módulo

---

### 1. Autenticación y sesiones

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `INVALID_CREDENTIALS` | 401 | `Credenciales inválidas` | Email o contraseña incorrectos al hacer login | Verificar email y contraseña; no reintentar más de 5 veces |
| `ACCOUNT_SUSPENDED` | 403 | `Cuenta suspendida. Contacte soporte.` | El tenant al que pertenece el usuario está suspendido | Contactar soporte para rehabilitar el tenant |
| `ACCESS_DENIED` | 403 | `Acceso denegado` | El rol del usuario no tiene permiso para la operación solicitada | Revisar los permisos del rol asignado |
| `INVALID_REFRESH_TOKEN` | 401 | `Refresh token inválido o expirado` | Se envió un refresh token vencido o manipulado | Solicitar al usuario que vuelva a iniciar sesión |
| `NOT_AUTHENTICATED` | 401 | `No autenticado` | JWT ausente, malformado o expirado en el header `Authorization` | Incluir un Bearer token válido o renovarlo con el refresh token |
| `API_KEY_EXPIRED` | 401 | `API Key expirada` | La API Key usada superó su fecha de expiración | Rotar la API Key o generar una nueva |
| `INSUFFICIENT_PERMISSIONS` | 403 | `Permisos insuficientes` | El scope de la API Key no cubre la operación solicitada | Crear una API Key con los scopes necesarios |

---

### 2. API Keys

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `API_KEY_NOT_FOUND` | 404 | `API Key no encontrada` | Se intentó revocar, consultar o modificar una API Key con un ID inexistente | Verificar que el ID de API Key sea correcto |
| `ACCESS_DENIED_TENANT` | 403 | `Acceso denegado` | Se intentó operar sobre una API Key que pertenece a otro tenant | Usar credenciales del tenant propietario de la key |

---

### 3. Inventario — Movimientos

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `WAREHOUSE_NOT_FOUND_OR_INACTIVE` | 404 | `Almacén no encontrado o inactivo` | El ID de almacén referenciado en el movimiento no existe o está desactivado | Verificar el ID o activar el almacén antes de operar |
| `ZONE_NOT_FOUND_OR_INACTIVE` | 404 | `Zona no encontrada o inactiva` | La zona referenciada en el movimiento no existe o está desactivada | Verificar el ID de zona o activarla |
| `PRODUCT_NOT_FOUND_OR_INACTIVE` | 404 | `Producto {id} no encontrado o inactivo` | El producto referenciado no existe en el tenant o está desactivado | Verificar el UUID del producto; puede incluir el ID dinámico en el mensaje |
| `INSUFFICIENT_STOCK` | 409 | `Stock insuficiente: disponible {X}, solicitado {Y}` | Se intentó mover más unidades de las disponibles; el mensaje incluye el disponible real y el solicitado | Consultar el saldo actual antes de operar y ajustar la cantidad |
| `CONCURRENCY_CONFLICT_BALANCE` | 409 | `Conflicto de concurrencia al actualizar el saldo. Reintente la operación.` | Dos transacciones simultáneas tocaron el mismo saldo (OCC) | Reintentar la operación con backoff exponencial |

---

### 4. Almacenes y Zonas

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `WAREHOUSE_CODE_DUPLICATE` | 409 | `Ya existe un almacén con el código '{code}'` | Se intentó crear o actualizar un almacén con un código ya registrado en el tenant | Elegir un código único para el almacén |
| `WAREHOUSE_NOT_FOUND` | 404 | `Almacén no encontrado` | El ID de almacén no existe en el tenant | Verificar el UUID del almacén |
| `WAREHOUSE_HAS_INVENTORY` | 409 | `No se puede desactivar un almacén con inventario físico > 0` | Se intentó desactivar un almacén que aún tiene stock registrado | Transferir o dar salida al inventario antes de desactivar |
| `WAREHOUSE_INACTIVE` | 409 | `El almacén está inactivo` | Se intentó operar sobre un almacén desactivado | Reactivar el almacén o usar uno activo |
| `ZONE_CODE_DUPLICATE` | 409 | `Ya existe una zona con el código '{code}'` | Se intentó crear una zona con un código ya existente dentro del almacén | Elegir un código de zona único dentro del almacén |
| `PARENT_ZONE_NOT_FOUND` | 404 | `Zona padre no encontrada` | El `parent_zone_id` referenciado no existe en el almacén | Verificar el UUID de la zona padre |
| `ZONE_NOT_FOUND` | 404 | `Zona no encontrada` | El ID de zona no existe en el tenant | Verificar el UUID de la zona |

---

### 5. Catálogo de Productos

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `PRODUCT_NOT_FOUND` | 404 | `Producto no encontrado` | El producto referenciado no existe en el catálogo del tenant | Verificar el UUID del producto |
| `KIT_SELF_REFERENCE` | 422 | `Un kit no puede ser componente de sí mismo` | Se intentó agregar un producto como componente de su propio kit | Elegir un componente diferente |
| `NESTED_KIT_NOT_ALLOWED` | 422 | `No se permiten kits anidados: el componente es un kit` | Se intentó agregar un kit como componente de otro kit | Usar solo productos simples como componentes |
| `KIT_COMPONENT_DUPLICATE` | 409 | `El componente ya existe en este kit` | El producto ya fue agregado previamente como componente del mismo kit | No duplicar; actualizar la cantidad si se desea cambiar |
| `KIT_COMPONENT_NOT_FOUND` | 404 | `Componente no encontrado en este kit` | Se intentó eliminar o actualizar un componente que no existe en el kit | Verificar el UUID del componente dentro del kit |
| `BATCH_PRODUCT_NOT_FOUND` | 404 | `Producto no encontrado` | El producto referenciado en la operación de lote no existe | Verificar el UUID del producto |
| `BATCH_LOTS_NOT_ENABLED` | 422 | `El producto no tiene trazabilidad de lotes habilitada (\`track_lots=false\`)` | Se intentó crear un lote en un producto sin `track_lots=true` | Habilitar `track_lots` en el producto primero |
| `BATCH_NUMBER_DUPLICATE` | 409 | `El número de lote '{batch}' ya existe para este producto` | Se intentó crear un lote con un número ya registrado para ese producto | Usar un número de lote diferente o verificar si ya existe |
| `BATCH_NOT_FOUND` | 404 | `Lote no encontrado` | El ID de lote no existe en el tenant | Verificar el UUID del lote |
| `SERIALS_NOT_ENABLED` | 422 | `El producto no tiene trazabilidad de seriales habilitada (\`track_serials=false\`)` | Se intentó operar con seriales en un producto sin `track_serials=true` | Habilitar `track_serials` en el producto antes de registrar seriales |

---

### 6. Reservas

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `BALANCE_NOT_FOUND_FOR_PRODUCT_ZONE` | 404 | `No hay saldo para producto {id} en zona {id}` | Se intentó reservar un producto que nunca tuvo movimientos en esa zona | Verificar que el producto tenga saldo en la zona indicada |
| `INSUFFICIENT_AVAILABLE_STOCK` | 409 | `Stock disponible insuficiente para la operación` | El stock disponible (total − reservado) es menor al solicitado | Reducir la cantidad o liberar reservas existentes |
| `CONCURRENCY_CONFLICT_STOCK` | 409 | `Conflicto de concurrencia al actualizar stock. Intente nuevamente.` | Dos operaciones simultáneas colisionaron sobre el mismo saldo | Reintentar con backoff exponencial |
| `INSUFFICIENT_STOCK_RESERVATION` | 409 | `Stock insuficiente para producto {id} en zona {id}` | Al confirmar la reserva, el saldo físico real es menor al reservado | Revisar movimientos recientes antes de confirmar |
| `RESERVATION_NOT_FOUND` | 404 | `Reserva no encontrada` | El ID de reserva no existe en el tenant | Verificar el UUID de la reserva |
| `RESERVATION_CANNOT_CONFIRM` | 409 | `La reserva está en estado '{status}', no se puede confirmar` | Se intentó confirmar una reserva que no está en estado `pending` | Solo se pueden confirmar reservas en estado `pending` |
| `RESERVATION_EMPTY` | 409 | `La reserva no tiene ítems` | Se intentó confirmar una reserva sin líneas de detalle | Agregar al menos un ítem antes de confirmar |
| `RESERVATION_CANNOT_CANCEL` | 409 | `La reserva está en estado '{status}', no se puede cancelar` | Se intentó cancelar una reserva ya confirmada o cancelada | Solo se pueden cancelar reservas en estado `pending` |

---

### 7. Webhooks y Bulk Engine

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `WEBHOOK_NOT_FOUND` | 404 | `Webhook endpoint no encontrado` | El ID de webhook no existe en el tenant | Verificar el UUID del webhook |
| `BULK_VALIDATION_ERROR` | 422 | *(arreglo de errores por fila)* | Una o más filas del payload bulk contienen datos inválidos; el detalle incluye la posición y el campo | Corregir los registros señalados y reenviar solo las filas con error |
| `BULK_PARTIAL_FAILURE` | 207 | *(respuesta mixta)* | Algunas filas del bulk se procesaron y otras fallaron; el cuerpo indica el resultado por fila | Revisar las filas fallidas en el campo `errors` de la respuesta y reintentar solo esas |

---

### 8. Admin y Tenants

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `ADMIN_BOOTSTRAP_DISABLED` | 503 | `Bootstrap de admin deshabilitado` | Se intentó usar el endpoint de bootstrap sin la variable de entorno habilitada | Verificar la configuración del entorno o contactar al operador |
| `SUPER_ADMIN_ALREADY_EXISTS` | 409 | `Ya existe un super_admin registrado` | Se intentó crear un segundo super_admin cuando ya existe uno | Solo existe un super_admin; gestionar acceso desde el portal admin |
| `EMAIL_ALREADY_REGISTERED` | 409 | `Email ya registrado` | Se intentó crear un usuario o admin con un email que ya existe en el sistema | Usar un email diferente o recuperar acceso con el existente |
| `TENANT_NOT_FOUND` | 404 | `Tenant no encontrado` | El ID de tenant referenciado no existe | Verificar el UUID del tenant |

---

### 9. Errores del sistema

| error_code | HTTP | detail (mensaje) | Cuándo ocurre | Acción sugerida |
|---|---|---|---|---|
| `VALIDATION_ERROR` | 422 | *(arreglo Pydantic)* | Falta un campo requerido, el tipo de dato es incorrecto, el valor está fuera de rango o no cumple el patrón esperado | Revisar el esquema del endpoint en la documentación OpenAPI y corregir el cuerpo/parámetros |
| `FIELD_REQUIRED` | 422 | `[{"loc": ["body", "campo"], "msg": "field required", "type": "value_error.missing"}]` | Se omitió un campo obligatorio en el body | Incluir todos los campos requeridos según el esquema |
| `FIELD_TYPE_ERROR` | 422 | `[{"loc": [...], "msg": "value is not a valid ...", "type": "type_error..."}]` | El tipo del valor enviado no coincide con el esperado (ej: string en lugar de number) | Enviar el tipo correcto según la documentación |
| `FIELD_VALUE_ERROR` | 422 | `[{"loc": [...], "msg": "ensure this value is ...", "type": "value_error..."}]` | El valor enviado no cumple las restricciones (mínimo, máximo, patrón regex, enum) | Ajustar el valor dentro del rango o patrón permitido |
| `RATE_LIMIT_EXCEEDED` | 429 | `Rate limit exceeded` | Se superó el límite de peticiones por ventana de tiempo (Redis rate limiter) | Esperar antes de reintentar; implementar backoff en el cliente |
| `NOT_FOUND` | 404 | `Not Found` | La ruta solicitada no existe en la API | Verificar el path y método en la documentación OpenAPI |
| `METHOD_NOT_ALLOWED` | 405 | `Method Not Allowed` | Se usó un método HTTP no soportado para la ruta (ej: PUT en lugar de PATCH) | Verificar el método HTTP correcto para el endpoint |
| `INTERNAL_SERVER_ERROR` | 500 | `Internal Server Error` | Error inesperado en el servidor; puede ser un bug o fallo de infraestructura | Reintentar una vez; si persiste, reportar con el `request_id` si está disponible |

---

## Cómo identificar errores programáticamente

Dado que la API no incluye un campo `error_code` dedicado en la respuesta, la identificación debe hacerse combinando el **código HTTP** y el contenido del campo `detail`:

```python
import httpx

response = httpx.post("/v1/auth/login", json={"email": "...", "password": "..."})

if response.status_code == 401:
    detail = response.json().get("detail", "")
    if "Credenciales inválidas" in detail:
        # INVALID_CREDENTIALS — mostrar mensaje de login incorrecto
        ...
    elif "Refresh token" in detail:
        # INVALID_REFRESH_TOKEN — redirigir al login
        ...
    elif "No autenticado" in detail:
        # NOT_AUTHENTICATED — renovar token
        ...

elif response.status_code == 409:
    detail = response.json().get("detail", "")
    if "Stock insuficiente" in detail:
        # INSUFFICIENT_STOCK — parsear disponible y solicitado del mensaje
        ...
    elif "Conflicto de concurrencia" in detail:
        # CONCURRENCY_CONFLICT — reintentar con backoff
        ...

elif response.status_code == 422:
    detail = response.json().get("detail")
    if isinstance(detail, list):
        # VALIDATION_ERROR — iterar sobre la lista de errores por campo
        for error in detail:
            field = " → ".join(str(p) for p in error["loc"])
            print(f"Campo '{field}': {error['msg']}")
```

> **Recomendación:** Para errores con mensajes dinámicos (ej: `Stock insuficiente: disponible 5, solicitado 10`), usar `in` o expresiones regulares para detectar la subcadena clave, y luego extraer los valores numéricos si se necesitan para lógica de negocio.
