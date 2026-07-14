from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class ClienteCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    telefono: Optional[str] = Field(default=None, max_length=20)
    correo: Optional[str] = Field(default=None, max_length=120)
    es_mayorista: bool = False
    notas: Optional[str] = None


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    telefono: Optional[str] = None
    correo: Optional[str] = None
    es_mayorista: Optional[bool] = None
    activo: Optional[bool] = None
    notas: Optional[str] = None


class ClienteOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    nombre: str
    telefono: Optional[str] = None
    correo: Optional[str] = None
    es_mayorista: bool
    activo: bool
    creado_en: datetime
    modificado_en: Optional[datetime] = None


class ClienteList(BaseModel):
    total: int
    items: list[ClienteOut]