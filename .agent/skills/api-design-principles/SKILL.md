---
name: api-design-principles
description: Domina los principios de diseño de APIs REST y GraphQL para construir interfaces intuitivas, escalables y mantenibles que encanten a los desarrolladores. Úsala al diseñar nuevas APIs, revisar especificaciones o establecer estándares de diseño de APIs.
---

# Principios de Diseño de APIs

Domina los principios de diseño de APIs REST y GraphQL para construir interfaces intuitivas, escalables y mantenibles que deleiten a los desarrolladores y resistan el paso del tiempo.

## Cuándo usar esta habilidad

- Al diseñar nuevas APIs REST o GraphQL.
- Al refactorizar APIs existentes para mejorar su usabilidad.
- Al establecer estándares de diseño de APIs para tu equipo.
- Al revisar especificaciones de APIs antes de su implementación.
- Al migrar entre paradigmas de API (de REST a GraphQL, etc.).
- Al crear documentación de API amigable para desarrolladores.
- Al optimizar APIs para casos de uso específicos (móviles, integraciones de terceros).

## Conceptos Core

### 1. Principios de Diseño RESTful

**Arquitectura Orientada a Recursos**

- Los recursos son sustantivos (usuarios, pedidos, productos), no verbos.
- Usa métodos HTTP para las acciones (GET, POST, PUT, PATCH, DELETE).
- Las URLs representan jerarquías de recursos.
- Convenciones de nomenclatura consistentes.

**Semántica de los Métodos HTTP:**

- `GET`: Recuperar recursos (idempotente, seguro).
- `POST`: Crear nuevos recursos.
- `PUT`: Reemplazar el recurso completo (idempotente).
- `PATCH`: Actualizaciones parciales del recurso.
- `DELETE`: Eliminar recursos (idempotente).

### 2. Principios de Diseño GraphQL

**Desarrollo Schema-First**

- Los tipos definen tu modelo de dominio.
- Queries para leer datos.
- Mutations para modificar datos.
- Subscriptions para actualizaciones en tiempo real.

**Estructura de Query:**

- Los clientes solicitan exactamente lo que necesitan.
- Un solo endpoint, múltiples operaciones.
- Esquema fuertemente tipado.
- Introspección integrada.

### 3. Estrategias de Versionado de APIs

**Versionado por URL:**

```
/api/v1/users
/api/v2/users
```

**Versionado por Header:**

```
Accept: application/vnd.api+json; version=1
```

**Versionado por Parámetro de Query:**

```
/api/users?version=1
```

## Patrones de Diseño de API REST

### Patrón 1: Diseño de Colección de Recursos

```python
# Bien: Endpoints orientados a recursos
GET    /api/users              # Listar usuarios (con paginación)
POST   /api/users              # Crear usuario
GET    /api/users/{id}         # Obtener un usuario específico
PUT    /api/users/{id}         # Reemplazar usuario
PATCH  /api/users/{id}         # Actualizar campos del usuario
DELETE /api/users/{id}         # Eliminar usuario

# Recursos anidados
GET    /api/users/{id}/orders  # Obtener pedidos del usuario
POST   /api/users/{id}/orders  # Crear pedido para el usuario

# Mal: Endpoints orientados a acciones (evitar)
POST   /api/createUser
POST   /api/getUserById
POST   /api/deleteUser
```

### Patrón 2: Paginación y Filtrado

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Número de página")
    page_size: int = Field(20, ge=1, le=100, description="Elementos por página")

class FilterParams(BaseModel):
    status: Optional[str] = None
    created_after: Optional[str] = None
    search: Optional[str] = None

class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int
    pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

# Ejemplo de endpoint en FastAPI
from fastapi import FastAPI, Query, Depends

app = FastAPI()

@app.get("/api/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    # Aplicar filtros
    query = build_query(status=status, search=search)

    # Contar total
    total = await count_users(query)

    # Obtener página
    offset = (page - 1) * page_size
    users = await fetch_users(query, limit=page_size, offset=offset)

    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )
```

### Patrón 3: Manejo de Errores y Códigos de Estado

```python
from fastapi import HTTPException, status
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None
    timestamp: str
    path: str

# Códigos de estado consistentes
STATUS_CODES = {
    "success": 200,
    "created": 201,
    "no_content": 204,
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "unprocessable": 422,
    "internal_error": 500
}

def raise_not_found(resource: str, id: str):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "NotFound",
            "message": f"{resource} no encontrado",
            "details": {"id": id}
        }
    )
```

## Buenas Prácticas

### APIs REST

1. **Nomenclatura Consistente**: Usa sustantivos en plural para las colecciones (`/users`, no `/user`).
2. **Sin Estado (Stateless)**: Cada solicitud contiene toda la información necesaria.
3. **Usa Correctamente los Códigos de Estado HTTP**: 2xx éxito, 4xx errores de cliente, 5xx errores de servidor.
4. **Versiona tu API**: Planifica los cambios disruptivos desde el primer día.
5. **Paginación**: Siempre pagina las colecciones grandes.
6. **Limitación de Tasa (Rate Limiting)**: Protege tu API con límites de solicitudes.
7. **Documentación**: Usa OpenAPI/Swagger para documentación interactiva.

### APIs GraphQL

1. **Schema First**: Diseña el esquema antes de escribir los resolvers.
2. **Evita el Problema N+1**: Usa DataLoaders para la obtención eficiente de datos.
3. **Validación de Entradas**: Valida a nivel de esquema y de resolver.
4. **Manejo de Errores**: Devuelve errores estructurados en los payloads de las mutations.
5. **Paginación**: Usa paginación basada en cursores (especificación Relay).
6. **Depreciación**: Usa la directiva `@deprecated` para migraciones graduales.
7. **Monitoreo**: Realiza un seguimiento de la complejidad de la consulta y el tiempo de ejecución.
