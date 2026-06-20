from pydantic import BaseModel
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


class KardexMovimiento(BaseModel):
    """Una fila del kardex de un producto (RF-03.3)."""
    id: UUID
    fecha_hora: datetime
    tipo_movimiento: str
    cantidad_entrada: int
    cantidad_salida: int
    existencia_resultante: int
    costo_unitario: Decimal
    referencia_id: UUID | None
    tipo_referencia: str | None
    usuario_id: UUID
    usuario_nombre: str
    caja_id: UUID | None
    caja_nombre: str | None
    notas: str | None

    class Config:
        from_attributes = True


class KardexEncabezado(BaseModel):
    """Encabezado de la consulta de kardex (RF-03.2)."""
    producto_id: UUID
    codigo_barras: str | None
    descripcion: str
    categoria_nombre: str | None
    existencia_actual: int
    inventario_minimo: int
    costo_unitario: Decimal
    precio_venta: Decimal
    ruta_imagen: str | None
    stock_bajo: bool


class KardexConsulta(BaseModel):
    """Respuesta completa: encabezado + lista de movimientos."""
    encabezado: KardexEncabezado
    total_movimientos: int
    movimientos: list[KardexMovimiento]


class ProductoBusquedaKardex(BaseModel):
    """Resultado del buscador de productos en pantalla de kardex."""
    id: UUID
    codigo_barras: str | None
    descripcion: str
    cantidad_actual: int