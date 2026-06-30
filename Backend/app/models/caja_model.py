from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field



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

class CajaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    es_verificador: bool = False