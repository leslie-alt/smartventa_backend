# caja_model.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CajaOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    nombre: str
    es_verificador: bool
    activa: bool
    impresora_tipo: Optional[str] = None
    impresora_valor: Optional[str] = None
    impresora_puerto: Optional[int] = None
    creado_en: datetime


class CajaList(BaseModel):
    total: int
    items: list[CajaOut]


class CajaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    es_verificador: bool = False
    impresora_tipo: Optional[str] = None
    impresora_valor: Optional[str] = None
    impresora_puerto: Optional[int] = None