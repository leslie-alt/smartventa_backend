from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MetodoPago(str, Enum):
    """Métodos de pago aceptados por línea (RF-06.1). 'mixto' no es un método
    individual: se determina a nivel ticket cuando hay más de un pago."""
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    CHEQUE = "cheque"
    TRANSFERENCIA = "transferencia"


class MotivoMayoreo(str, Enum):
    MONTO = "monto"
    CLIENTE = "cliente"
    NINGUNO = "ninguno"


class EstadoVenta(str, Enum):
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class VentaArticuloCreate(BaseModel):
    """Línea de producto enviada por el frontend al cobrar."""
    producto_id: UUID
    cantidad: int = Field(gt=0, description="Cantidad vendida, debe ser mayor a cero")


class PagoCreate(BaseModel):
    """Detalle de un método de pago aplicado al ticket (RF-06.4)."""
    metodo: MetodoPago
    monto: Decimal = Field(gt=0)
    recibido: Optional[Decimal] = Field(
        default=None, description="Monto entregado por el cliente, solo aplica a efectivo"
    )
    referencia: Optional[str] = Field(
        default=None, description="Folio de transferencia o número de cheque"
    )

    @field_validator("recibido")
    @classmethod
    def _validar_recibido_efectivo(cls, v, info):
        metodo = info.data.get("metodo")
        if metodo != MetodoPago.EFECTIVO and v is not None:
            raise ValueError("Solo el pago en efectivo puede llevar monto recibido")
        return v


class VentaCreate(BaseModel):
    """Payload para cerrar una venta desde el POS."""
    cliente_id: Optional[UUID] = None
    articulos: list[VentaArticuloCreate] = Field(min_length=1)
    pagos: list[PagoCreate] = Field(min_length=1)
    notas: Optional[str] = None


class VentaArticuloOut(BaseModel):
    id: UUID
    producto_id: UUID
    descripcion: Optional[str] = None
    cantidad: int
    precio_unitario: Decimal
    uso_precio_mayoreo: bool
    descuento: Decimal
    subtotal: Decimal


class PagoOut(BaseModel):
    id: UUID
    metodo: MetodoPago
    monto: Decimal
    cambio: Decimal
    referencia: Optional[str] = None


class VentaOut(BaseModel):
    id: UUID
    folio: int
    sucursal_id: UUID
    caja_id: UUID
    turno_id: UUID
    usuario_id: UUID
    cliente_id: Optional[UUID] = None
    total: Decimal
    aplico_mayoreo: bool
    motivo_mayoreo: MotivoMayoreo
    metodo_pago_principal: str
    notas: Optional[str] = None
    estado: EstadoVenta
    creado_en: datetime
    articulos: list[VentaArticuloOut] = []
    pagos: list[PagoOut] = []