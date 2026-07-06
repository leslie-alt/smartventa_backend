from fastapi import APIRouter, Depends

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.sucursal_model import SucursalOut, SucursalUpdate
from app.services import sucursal_services
router = APIRouter()


@router.get("/actual", response_model=SucursalOut)
def obtener_sucursal_actual(
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Devuelve los datos de la sucursal del usuario logueado (pantalla de Configuración)."""
    return sucursal_services.obtener_sucursal(
        sucursal_id=usuario["sucursal_id"],
    )

@router.put("/actual", response_model=SucursalOut)
def actualizar_sucursal_actual(
    datos: SucursalUpdate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Actualiza los datos de la sucursal del usuario. Requiere perm_administrar."""
    return sucursal_services.actualizar_sucursal(
        sucursal_id=usuario["sucursal_id"],
        datos=datos.model_dump(exclude_none=True),
    )