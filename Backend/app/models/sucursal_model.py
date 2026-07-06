from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SucursalOut(BaseModel):
    id: UUID
    nombre: str
    direccion: str | None = None
    telefono: str | None = None
    activa: bool
    creado_en: datetime | None = None

    class Config:
        from_attributes = True


class SucursalUpdate(BaseModel):
    nombre: str | None = None
    direccion: str | None = None
    telefono: str | None = None