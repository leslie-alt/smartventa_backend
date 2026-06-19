from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# =============================================================
# ENTRADAS DE MERCANCÍA
# =============================================================

class EntradaMercanciaIn(BaseModel):
    producto_id: UUID
    cantidad: int = Field(gt=0, description="Cantidad de unidades que entran")
    notas: str | None = Field(default=None, max_length=255)


# =============================================================
# AJUSTES DE INVENTARIO
# =============================================================

class AjusteInventarioIn(BaseModel):
    producto_id: UUID
    nueva_cantidad: int = Field(ge=0, description="Cantidad real contada en físico")
    motivo: str = Field(min_length=3, max_length=255, description="Merma, corrección, daño, diferencia física")


# =============================================================
# LISTADO DE INVENTARIO
# =============================================================

class InventarioItem(BaseModel):
    """Fila del listado de inventario — pantalla principal."""
    producto_id: UUID
    codigo_barras: str | None
    descripcion: str
    categoria_nombre: str | None
    cantidad_actual: int
    inventario_minimo: int
    stock_bajo: bool
    ruta_imagen: str | None
    activo: bool

    class Config:
        from_attributes = True


class InventarioResumen(BaseModel):
    """Tarjetas superiores de la pantalla de inventario."""
    productos_activos: int
    productos_stock_bajo: int


class InventarioList(BaseModel):
    resumen: InventarioResumen
    total: int
    items: list[InventarioItem]