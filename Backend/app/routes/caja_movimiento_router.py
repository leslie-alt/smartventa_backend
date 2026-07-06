#caja_movimiento_router.py

from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import verificar_permiso
from app.models.caja_movimiento_model import MovimientoCajaCreate, MovimientoCajaOut
from app.services import caja_movimiento_services, turno_services

router = APIRouter()

@router.post("/", response_model=MovimientoCajaOut)
def registrar_movimiento(
    datos: MovimientoCajaCreate,
    usuario: dict = Depends(verificar_permiso("perm_movimientos_caja")),
):
    """Registra entrada/salida manual de efectivo en caja (RF-10.1)."""
    turno = turno_services.obtener_turno_activo(
        caja_id=str(datos.caja_id),
        sucursal_id=usuario["sucursal_id"],
    )
    if not turno:
        raise HTTPException(status_code=409, detail="No hay turno abierto en esta caja.")

    return caja_movimiento_services.registrar_movimiento(
        turno_id=turno["id"], caja_id=str(datos.caja_id),
        sucursal_id=usuario["sucursal_id"], usuario_id=usuario["usuario_id"],
        tipo_movimiento=datos.tipo_movimiento.value, monto=float(datos.monto), notas=datos.notas,
    )