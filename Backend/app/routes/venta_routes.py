from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.venta_model import VentaCreate, VentaOut
from app.services import venta_services

router = APIRouter()


@router.post("/", response_model=VentaOut)
def crear_venta(
    datos: VentaCreate,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Registra una venta completa: artículos, pagos, descuento de inventario,
    kardex y auditoría en una sola operación atómica (RPC).
    Soporta forzar_mayoreo por línea (requiere perm_descuentos).

    caja_id y turno_id vienen en el body (no en el JWT) y se validan contra
    la base de datos para confirmar que el turno está abierto y pertenece
    a este usuario en esta sucursal (RNF-03.4).
    """
    return venta_services.crear_venta(
        datos=datos.model_dump(mode="json", exclude={"caja_id", "turno_id"}, exclude_none=True),
        sucursal_id=usuario["sucursal_id"],
        caja_id=str(datos.caja_id),
        turno_id=str(datos.turno_id),
        usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )


@router.get("/{venta_id}", response_model=VentaOut)
def obtener_venta(
    venta_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Obtiene una venta para reimprimir el ticket o revisar el detalle."""
    return venta_services.obtener_venta(
        venta_id=str(venta_id),
        sucursal_id=usuario["sucursal_id"],
    )