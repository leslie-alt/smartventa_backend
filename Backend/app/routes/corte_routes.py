from fastapi import APIRouter, Depends, Query
from datetime import date
from uuid import UUID

from app.core.deps import verificar_permiso
from app.services import corte_services

from app.models.dashboard_dueno_model import DetalleVenta



router = APIRouter()


@router.get("/")
def consultar_corte(
    caja_id: UUID,
    fecha: str,
    usuario: dict = Depends(verificar_permiso("perm_corte_caja")),
):
    """
    Corte de caja de consulta: calcula al vuelo el corte de una caja
    en una fecha específica (AAAA-MM-DD). No cierra nada.
    Requiere permiso perm_corte_caja.
    """
    return corte_services.corte_por_caja_dia(
        caja_id=str(caja_id),
        sucursal_id=usuario["sucursal_id"],
        fecha=fecha,
    )



@router.get("/ventas-dia")
async def ventas_dia(
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
    fecha: date = Query(default_factory=date.today),
    sucursal_id: UUID | None = Query(None),
) -> dict:
    from app.services.dashboard_dueno_services import listar_ventas_dia
    return listar_ventas_dia(
        sucursal_id=str(sucursal_id) if sucursal_id else None,
        fecha=fecha.isoformat(),
    )


@router.get("/venta/{venta_id}/detalle", response_model=DetalleVenta)
async def venta_detalle(
    venta_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
) -> DetalleVenta:
    from app.services.dashboard_dueno_services import obtener_detalle_venta
    return obtener_detalle_venta(str(venta_id))

    

@router.get("/productos-faltantes")
async def productos_faltantes(
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
    sucursal_id: UUID | None = Query(None),
) -> dict:
    from app.services.dashboard_dueno_services import listar_productos_faltantes
    return listar_productos_faltantes(sucursal_id=str(sucursal_id) if sucursal_id else None)