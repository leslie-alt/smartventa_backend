from fastapi import HTTPException, status

class ErrorNoEncontrado(HTTPException):
    """El recurso solicitado no existe en la base de datos."""
    def __init__(self, recurso: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{recurso} no encontrado."
        )

class ErrorNoAutorizado(HTTPException):
    """El usuario no tiene permiso para ejecutar esta acción."""
    def __init__(self, accion: str = "realizar esta acción"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes permiso para {accion}."
        )

class ErrorSesionInvalida(HTTPException):
    """El token JWT es inválido o expiró."""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada. Inicia sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

class ErrorConflicto(HTTPException):
    """Violación de unicidad u otra restricción de negocio."""
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detalle
        )

class ErrorValidacion(HTTPException):
    """Los datos enviados no cumplen las reglas de negocio."""
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detalle
        )