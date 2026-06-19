from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Literal


class PromocionCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)  # ← AGREGAR
    producto_id: UUID
    cantidad_minima: int = Field(gt=0)
    tipo_beneficio: Literal["precio_especial", "porcentaje_descuento"]
    valor_beneficio: Decimal = Field(gt=0, decimal_places=2)
    fecha_inicio: date

    @field_validator("valor_beneficio")
    @classmethod
    def validar_porcentaje(cls, v, info):
        if info.data.get("tipo_beneficio") == "porcentaje_descuento" and v >= 100:
            raise ValueError("El porcentaje de descuento debe ser menor a 100")
        return v


class PromocionUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100) 
    cantidad_minima: int | None = Field(default=None, gt=0)
    tipo_beneficio: Literal["precio_especial", "porcentaje_descuento"] | None = None
    valor_beneficio: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    fecha_inicio: date | None = None
    activa: bool | None = None
    


class PromocionOut(BaseModel):
    id: UUID
    nombre: str | None
    producto_id: UUID
    cantidad_minima: int
    tipo_beneficio: str
    valor_beneficio: Decimal
    fecha_inicio: date
    activa: bool
    creado_en: datetime
    modificado_en: datetime

    class Config:
        from_attributes = True


class PromocionConProducto(PromocionOut):
    """PromocionOut con datos básicos del producto — para listar en el frontend."""
    producto_descripcion: str
    producto_codigo_barras: str | None


class PromocionList(BaseModel):
    total: int
    items: list[PromocionConProducto]