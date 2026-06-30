from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TipoMovimientoCaja(str, Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"


class MovimientoCajaCreate(BaseModel):
    caja_id: UUID
    tipo_movimiento: TipoMovimientoCaja
    monto: Decimal = Field(gt=0)
    notas: Optional[str] = None

class MovimientoCajaOut(BaseModel):
    id: UUID
    turno_id: UUID
    caja_id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    tipo_movimiento: TipoMovimientoCaja
    monto: Decimal
    notas: Optional[str] = None
    registrado_en: datetime