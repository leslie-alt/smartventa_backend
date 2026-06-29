from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.venta_model import VentaCreate, VentaOut
from app.services import venta_services
from app.models.venta_model import TicketPendienteGuardar, TicketCobrarCreate

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


@router.post("/pendiente")
def crear_ticket_pendiente(datos: TicketPendienteGuardar, usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.guardar_ticket_pendiente(
        venta_id=None, datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"], caja_id=usuario["caja_id"],
        turno_id=usuario["turno_id"], usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )

@router.put("/pendiente/{venta_id}")
def actualizar_ticket_pendiente(venta_id: UUID, datos: TicketPendienteGuardar, usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.guardar_ticket_pendiente(
        venta_id=str(venta_id), datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"], caja_id=usuario["caja_id"],
        turno_id=usuario["turno_id"], usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )

@router.get("/pendientes")
def listar_tickets_pendientes(usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.listar_tickets_pendientes(caja_id=usuario["caja_id"], sucursal_id=usuario["sucursal_id"])

@router.delete("/pendiente/{venta_id}")
def eliminar_ticket_pendiente(venta_id: UUID, usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.eliminar_ticket_pendiente(
        venta_id=str(venta_id), sucursal_id=usuario["sucursal_id"],
        caja_id=usuario["caja_id"], usuario_id=usuario["usuario_id"],
    )

@router.post("/pendiente/{venta_id}/cobrar")
def cobrar_ticket_pendiente(venta_id: UUID, datos: TicketCobrarCreate, usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.cobrar_ticket_pendiente(
        venta_id=str(venta_id), datos=datos.model_dump(mode="json"),
        sucursal_id=usuario["sucursal_id"], caja_id=usuario["caja_id"],
        turno_id=usuario["turno_id"], usuario_id=usuario["usuario_id"],
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