from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Literal






class ProductoCreate(BaseModel):
    codigo_barras: str | None = Field(default=None, max_length=50)
    descripcion: str = Field(min_length=2, max_length=255)
    categoria_id: UUID | None = None
    precio_venta: Decimal = Field(gt=0, decimal_places=2)
    precio_mayoreo: Decimal = Field(gt=0, decimal_places=2)
    costo_unitario: Decimal = Field(ge=0, decimal_places=2)
    inventario_minimo: int = Field(default=0, ge=0)
    stock_inicial: int = Field(default=0, ge=0)
    ruta_imagen: str | None = Field(default=None)
    @field_validator("precio_mayoreo")
    @classmethod
    def mayoreo_menor_que_venta(cls, v, info):
        if info.data.get("precio_venta") and v >= info.data["precio_venta"]:
            raise ValueError("El precio de mayoreo debe ser menor al precio de venta")
        return v


class ProductoUpdate(BaseModel):
    codigo_barras: str | None = Field(default=None, max_length=50)
    descripcion: str | None = Field(default=None, min_length=2, max_length=255)
    categoria_id: UUID | None = None
    precio_venta: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    precio_mayoreo: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    costo_unitario: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    inventario_minimo: int | None = Field(default=None, ge=0)
    ruta_imagen: str | None = Field(default=None)


class ProductoOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    codigo_barras: str | None
    descripcion: str
    categoria_id: UUID | None
    precio_venta: Decimal
    precio_mayoreo: Decimal
    costo_unitario: Decimal
    inventario_minimo: int
    ruta_imagen: str | None
    activo: bool
    creado_en: datetime
    modificado_en: datetime

    class Config:
        from_attributes = True


class ProductoList(BaseModel):
    total: int
    items: list[ProductoOut]


class ProductoConStock(ProductoOut):
    """ProductoOut con existencia actual — para verificador de precios y búsquedas."""
    cantidad_actual: int
    stock_bajo: bool  # True si cantidad_actual <= inventario_minimo
    categoria_nombre: str | None = None
    # ── Campos de promoción activa (RF-09) — poblados solo en la búsqueda del POS.
    #    Son None cuando el producto no tiene promoción vigente. ──
    precio_promo: float | None = None
    porcentaje_promo: float | None = None
    cantidad_minima_promo: int | None = None

#

# =============================================================
# IMPORTACIÓN / EXPORTACIÓN
# =============================================================

class ErrorImportacion(BaseModel):
    """Detalle de una fila que falló durante la importación."""
    fila: int
    motivo: str


class ResultadoImportacion(BaseModel):
    """Resumen del proceso de importación."""
    total_filas: int
    insertados: int
    actualizados: int
    omitidos: int
    errores: list[ErrorImportacion]