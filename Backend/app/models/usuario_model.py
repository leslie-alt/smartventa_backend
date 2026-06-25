from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class UsuarioCreate(BaseModel):
    nombre_completo: str = Field(min_length=2, max_length=150)
    nombre_usuario: str = Field(min_length=3, max_length=60)
    contrasena: str = Field(min_length=6, max_length=72)
    rol_id: UUID


class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=150)
    nombre_usuario: str | None = Field(default=None, min_length=3, max_length=60)
    rol_id: UUID | None = None


class UsuarioOut(BaseModel):
    id: UUID
    nombre_completo: str
    nombre_usuario: str
    activo: bool
    ultimo_login: datetime | None
    creado_en: datetime
    rol_id: UUID
    rol_nombre: str | None = None

    class Config:
        from_attributes = True


class UsuarioList(BaseModel):
    total: int
    items: list[UsuarioOut]