from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.core.config import config
from app.core.exceptions import ErrorSesionInvalida, ErrorNoAutorizado

esquema_bearer = HTTPBearer()

def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials = Depends(esquema_bearer),
) -> dict:
    """
    Decodifica el JWT y retorna el payload completo.
    Se inyecta como dependencia en cualquier endpoint protegido.
    """
    try:
        payload = jwt.decode(
            credenciales.credentials,
            config.jwt_secret,
            algorithms=[config.jwt_algoritmo]
        )
        if not payload.get("usuario_id") or not payload.get("sucursal_id"):
            raise ErrorSesionInvalida()
        return payload
    except JWTError:
        raise ErrorSesionInvalida()


def verificar_permiso(permiso: str):
    """
    Fábrica de dependencias para verificar un permiso específico.
    Uso: usuario = Depends(verificar_permiso("perm_administrar"))
    """
    def _verificar(
        usuario: dict = Depends(obtener_usuario_actual)
    ) -> dict:
        if not usuario.get(permiso, False):
            raise ErrorNoAutorizado(f"ejecutar esta acción (requiere {permiso})")
        return usuario
    return _verificar