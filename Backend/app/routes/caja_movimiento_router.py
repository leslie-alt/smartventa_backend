from fastapi import APIRouter, Depends
from app.core.deps import verificar_permiso
from app.models.caja_movimiento_model import MovimientoCajaCreate, MovimientoCajaOut
from app.services import caja_movimiento_services

router = APIRouter()

@router.post("/", response_model=MovimientoCajaOut)
def registrar_movimiento(
    datos: MovimientoCajaCreate,
    usuario: dict = Depends(verificar_permiso("perm_corte_caja")),
):
    """Registra entrada/salida manual de efectivo en caja (RF-10.1). Requiere turno abierto."""
    if not usuario.get("turno_id") or not usuario.get("caja_id"):
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="No hay turno abierto en esta caja")

    return caja_movimiento_services.registrar_movimiento(
        turno_id=usuario["turno_id"], caja_id=usuario["caja_id"],
        sucursal_id=usuario["sucursal_id"], usuario_id=usuario["usuario_id"],
        tipo_movimiento=datos.tipo_movimiento.value, monto=float(datos.monto), notas=datos.notas,
    )