from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import obtener_usuario_actual
from app.models.caja_model import CajaOut, CajaList
from app.services import caja_services

router = APIRouter()


@router.get("/", response_model=CajaList)
def listar_cajas(
    solo_activas: bool = True,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Lista las cajas de la sucursal del usuario, para poblar el selector del POS."""
    return caja_services.listar_cajas(
        sucursal_id=usuario["sucursal_id"],
        solo_activas=solo_activas,
    )


@router.get("/{caja_id}", response_model=CajaOut)
def obtener_caja(
    caja_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    return caja_services.obtener_caja(
        caja_id=str(caja_id),
        sucursal_id=usuario["sucursal_id"],
    )