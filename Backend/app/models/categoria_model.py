from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class CategoriaCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    activo: bool | None = None


class CategoriaOut(BaseModel):
    id: UUID
    sucursal_id: UUID | None
    nombre: str
    activo: bool
    creado_en: datetime
    total_productos: int = 0

    class Config:
        from_attributes = True


class CategoriaList(BaseModel):
    total: int
    items: list[CategoriaOut]