from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CajaOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    nombre: str
    es_verificador: bool
    activa: bool
    creado_en: datetime


class CajaList(BaseModel):
    total: int
    items: list[CajaOut]