from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from supabase import Client

from app.core.config import obtener_configuracion
from app.core.database import obtener_db
from app.core.exceptions import ErrorSesionInvalida, ErrorNoAutorizado

# Esquema Bearer para extraer el token del header Authorization
esquema_bearer = HTTPBearer()

def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_bearer),
    config = Depends(obtener_configuracion)
) -> dict:
    """
    Decodifica el JWT y retorna el payload completo.
    Se inyecta como dependencia en cualquier endpoint protegido.
    
    El payload contiene:
        - usuario_id, nombre_usuario, sucursal_id, rol_id
        - Todos los permisos booleanos del rol
    """
    try:
        payload = jwt.decode(
            credenciales.credentials,
            config.jwt_secret,
            algorithms=[config.jwt_algoritmo]
        )
        
        # Verificar que el token tenga los campos mínimos
        if not payload.get("usuario_id") or not payload.get("sucursal_id"):
            raise ErrorSesionInvalida()
            
        return payload
    
    except JWTError:
        raise ErrorSesionInvalida()


def verificar_permiso(permiso: str):
    """
    Fábrica de dependencias para verificar un permiso específico.
    
    Uso en un endpoint:
        usuario = Depends(verificar_permiso("perm_administrar"))
    
    Si el usuario no tiene el permiso lanza HTTP 403.
    """
    def _verificar(
        usuario: dict = Depends(obtener_usuario_actual)
    ) -> dict:
        if not usuario.get(permiso, False):
            raise ErrorNoAutorizado(f"ejecutar esta acción (requiere {permiso})")
        return usuario
    
    return _verificar