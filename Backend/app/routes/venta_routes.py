from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import obtener_usuario_actual
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

    Requiere turno abierto: usuario["turno_id"] y usuario["caja_id"] deben
    venir poblados por el módulo de Turnos al iniciar sesión de caja.

    TODO: si el módulo de Turnos aún no expone turno_id/caja_id en el token,
    reemplazar temporalmente por un parámetro explícito en el body mientras
    se integra.
    """
    return venta_services.crear_venta(
        datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"],
        caja_id=usuario["caja_id"],
        turno_id=usuario["turno_id"],
        usuario_id=usuario["usuario_id"],
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

    