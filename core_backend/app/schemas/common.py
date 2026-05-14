from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    page: int = Field(..., description="Página actual (base 1).", examples=[1])
    page_size: int = Field(..., description="Número de elementos por página.", examples=[20])
    total_items: int = Field(..., description="Total de elementos que coinciden con el filtro.", examples=[157])
    total_pages: int = Field(..., description="Total de páginas disponibles.", examples=[8])


class PaginatedResponse(BaseModel):
    data: list = Field(..., description="Lista de elementos de la página actual.")
    pagination: PaginationMeta = Field(..., description="Metadata de paginación.")
