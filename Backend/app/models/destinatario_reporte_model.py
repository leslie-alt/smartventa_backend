from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Literal


class DestinatarioCreate(BaseModel):
    correo: EmailStr
    nombre: str | None = Field(default=None, max_length=150)
    recibe_corte: bool = True
    recibe_ventas: bool = True
    recibe_diario: bool = True
    recibe_semanal: bool = False


class DestinatarioUpdate(BaseModel):
    correo: EmailStr | None = None
    nombre: str | None = Field(default=None, max_length=150)
    recibe_corte: bool | None = None
    recibe_ventas: bool | None = None
    recibe_diario: bool | None = None
    recibe_semanal: bool | None = None
    activo: bool | None = None


class DestinatarioOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    correo: str
    nombre: str | None = None
    recibe_corte: bool
    recibe_ventas: bool
    recibe_diario: bool
    recibe_semanal: bool
    activo: bool
    creado_en: datetime

    class Config:
        from_attributes = True


class DestinatarioList(BaseModel):
    total: int
    items: list[DestinatarioOut]


class ResultadoEnvio(BaseModel):
    enviados: int
    errores: list[dict]