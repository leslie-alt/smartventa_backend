from pydantic import BaseModel
from uuid import UUID


class LoginEntrada(BaseModel):
    nombre_usuario: str
    contrasena: str


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: UUID
    nombre_completo: str
    sucursal_id: UUID
    rol_id: UUID
    permisos: dict