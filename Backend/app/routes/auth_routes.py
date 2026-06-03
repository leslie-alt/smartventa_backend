from fastapi import APIRouter, Depends
from supabase import Client

from app.core.database import supabase
from app.models.auth_model import LoginEntrada, TokenSalida
from app.services.auth_services import login, generar_hash_contrasena
from app.core.exceptions import ErrorConflicto

router = APIRouter()


@router.post("/login", response_model=TokenSalida)
def iniciar_sesion(datos: LoginEntrada):
    """
    Inicia sesión con usuario y contraseña.
    Retorna JWT con permisos embebidos válido por 8 horas.
    """
    return login(datos.nombre_usuario, datos.contrasena, supabase)

