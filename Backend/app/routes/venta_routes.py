from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID

from app.core.deps import obtener_usuario_actual,verificar_permiso
from app.models.venta_model import (
    VentaCreate, VentaOut, TicketPendienteGuardar, TicketCobrarCreate,
    DevolucionCreate, DevolucionArticulo
)
from app.services import venta_services, turno_services
from pydantic import BaseModel, Field

router = APIRouter()


def _resolver_turno(caja_id: str, sucursal_id: str) -> str:
    """Obtiene el turno activo de la caja o lanza 409 si no hay ninguno."""
    turno = turno_services.obtener_turno_activo(
        caja_id=caja_id, sucursal_id=sucursal_id
    )
    if not turno:
        raise HTTPException(status_code=409, detail="No hay turno abierto en esta caja.")
    return turno["id"]


@router.post("/", response_model=VentaOut)
def crear_venta(datos: VentaCreate, usuario: dict = Depends(obtener_usuario_actual)):
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.crear_venta(
        datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )


@router.post("/pendiente")
def crear_ticket_pendiente(datos: TicketPendienteGuardar, usuario: dict = Depends(obtener_usuario_actual)):
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.guardar_ticket_pendiente(
        venta_id=None, datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )


@router.put("/pendiente/{venta_id}")
def actualizar_ticket_pendiente(venta_id: UUID, datos: TicketPendienteGuardar, usuario: dict = Depends(obtener_usuario_actual)):
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.guardar_ticket_pendiente(
        venta_id=str(venta_id), datos=datos.model_dump(mode="json", exclude_none=True),
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
        tiene_perm_descuentos=usuario.get("perm_descuentos", False),
    )


@router.get("/pendientes")
def listar_tickets_pendientes(
    caja_id: UUID = Query(...),
    usuario: dict = Depends(obtener_usuario_actual),
):
    return venta_services.listar_tickets_pendientes(
        caja_id=str(caja_id), sucursal_id=usuario["sucursal_id"]
    )


@router.delete("/pendiente/{venta_id}")
def eliminar_ticket_pendiente(
    venta_id: UUID,
    caja_id: UUID = Query(...),
    usuario: dict = Depends(obtener_usuario_actual),
):
    return venta_services.eliminar_ticket_pendiente(
        venta_id=str(venta_id), sucursal_id=usuario["sucursal_id"],
        caja_id=str(caja_id), usuario_id=usuario["usuario_id"],
    )


@router.post("/pendiente/{venta_id}/cobrar")
def cobrar_ticket_pendiente(venta_id: UUID, datos: TicketCobrarCreate, usuario: dict = Depends(obtener_usuario_actual)):
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.cobrar_ticket_pendiente(
        venta_id=str(venta_id), datos=datos.model_dump(mode="json"),
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
    )

@router.post("/{venta_id}/devolucion")
def registrar_devolucion(
    venta_id: UUID,
    datos: DevolucionCreate,
    usuario: dict = Depends(verificar_permiso("perm_devoluciones")),
):
    """Registra una devolución (RF-04.6). Requiere permiso perm_devoluciones."""
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.registrar_devolucion(
        venta_id=str(venta_id),
        articulos=[a.model_dump(mode="json") for a in datos.articulos],
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
    )

@router.get("/{venta_id}", response_model=VentaOut)
def obtener_venta(venta_id: UUID, usuario: dict = Depends(obtener_usuario_actual)):
    return venta_services.obtener_venta(
        venta_id=str(venta_id), sucursal_id=usuario["sucursal_id"],
    )

@router.get("/historial/dia")
def listar_ventas_dia(
    fecha_inicio: str | None = Query(None),
    fecha_fin: str | None = Query(None),
    estado: str | None = Query(None),
    metodo: str | None = Query(None),
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Listado de ventas del día (RF-04 / 'Ventas del día y Devoluciones')."""
    return venta_services.listar_ventas_dia(
        sucursal_id=usuario["sucursal_id"],
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        estado=estado, metodo=metodo,
    )


@router.get("/historial/{venta_id}/detalle")
def obtener_venta_detalle(venta_id: UUID, usuario: dict = Depends(obtener_usuario_actual)):
    """Detalle completo de una venta para la vista de devolución."""
    return venta_services.obtener_venta_detalle(
        venta_id=str(venta_id), sucursal_id=usuario["sucursal_id"],
    )

from pydantic import BaseModel, Field

class DevolucionArticulo(BaseModel):
    venta_articulo_id: UUID
    cantidad: int = Field(gt=0)

class DevolucionCreate(BaseModel):
    caja_id: UUID
    articulos: list[DevolucionArticulo] = Field(min_length=1)


@router.post("/{venta_id}/devolucion")
def registrar_devolucion(
    venta_id: UUID,
    datos: DevolucionCreate,
    usuario: dict = Depends(verificar_permiso("perm_devoluciones")),
):
    """Registra una devolución (RF-04.6). Requiere permiso perm_devoluciones."""
    caja_id = str(datos.caja_id)
    turno_id = _resolver_turno(caja_id, usuario["sucursal_id"])
    return venta_services.registrar_devolucion(
        venta_id=str(venta_id),
        articulos=[a.model_dump(mode="json") for a in datos.articulos],
        sucursal_id=usuario["sucursal_id"], caja_id=caja_id,
        turno_id=turno_id, usuario_id=usuario["usuario_id"],
    )


@router.get("/cliente/{cliente_id}")
def ventas_por_cliente(
    cliente_id: UUID,
    limite: int = Query(default=10, ge=1, le=50),
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Últimas ventas de un cliente para su perfil."""
    return venta_services.listar_ventas_cliente(
        cliente_id=str(cliente_id),
        sucursal_id=usuario["sucursal_id"],
        limite=limite,
    )