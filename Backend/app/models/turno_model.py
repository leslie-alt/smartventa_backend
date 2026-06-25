from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


from pydantic import BaseModel, Field
from decimal import Decimal




class EstadoTurno(str, Enum):
    ABIERTO = "abierto"
    CERRADO = "cerrado"


class TurnoAbrir(BaseModel):
    """Payload para abrir un turno. El usuario se toma del token."""
    caja_id: UUID
    fondo_inicial: Decimal = Field(default=Decimal("0"), ge=0)
    notas: Optional[str] = None

class TurnoOut(BaseModel):
    id: UUID
    caja_id: UUID
    usuario_id: UUID
    inicio: datetime
    cierre: Optional[datetime] = None
    estado: EstadoTurno
    creado_en: datetime

