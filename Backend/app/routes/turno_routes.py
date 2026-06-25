from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.turno_model import TurnoAbrir, TurnoOut
from app.services import turno_services
from typing import Optional

router = APIRouter()


@router.post("/abrir", response_model=TurnoOut)
def abrir_turno(
    datos: TurnoAbrir,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Abre un turno con fondo inicial opcional (RF-10.1, RF-11.1)."""
    return turno_services.abrir_turno(
        caja_id=str(datos.caja_id),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
        fondo_inicial=float(datos.fondo_inicial),
        notas=datos.notas,
    )


@router.get("/mi-activo", response_model=Optional[TurnoOut])
def mi_turno_activo(usuario: dict = Depends(obtener_usuario_actual)):
    """Turno abierto del usuario logueado, para reconstruir sesión si se perdió."""
    return turno_services.obtener_turno_activo_de_usuario(
        usuario_id=usuario["usuario_id"],
        sucursal_id=usuario["sucursal_id"],
    )


@router.get("/{turno_id}/resumen")
def resumen_turno(
    turno_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Resumen de ventas y movimientos para la pantalla de cierre."""
    return turno_services.obtener_resumen_turno(
        turno_id=str(turno_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.get("/activo", response_model=Optional[TurnoOut])
def turno_activo(
    caja_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Regresa el turno abierto de una caja, o null si no hay ninguno."""
    return turno_services.obtener_turno_activo(
        caja_id=str(caja_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.post("/{turno_id}/cerrar", response_model=TurnoOut)
def cerrar_turno(
    turno_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_corte_caja")),
):
    """Cierra un turno abierto. Requiere permiso perm_corte_caja."""
    return turno_services.cerrar_turno(
        turno_id=str(turno_id),
        sucursal_id=usuario["sucursal_id"],
    )