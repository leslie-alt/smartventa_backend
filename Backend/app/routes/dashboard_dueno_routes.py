"""Endpoints del dashboard de la dueña (RF-14.1, RF-14.2, RF-14.3).
Exclusivamente de consulta — no expone ninguna operación de escritura."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.deps import verificar_permiso
from app.models.dashboard_dueno_model import ResumenDueno, DetalleVenta
from app.services.dashboard_dueno_services import (
    obtener_resumen_dueno,
    listar_ventas_dia,
    obtener_detalle_venta,
    listar_productos_faltantes,
)

router = APIRouter(prefix="/dashboard-dueno", tags=["Dashboard Dueña"])


@router.get("/resumen", response_model=ResumenDueno)
async def resumen_dueno(
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
    fecha: date = Query(default_factory=date.today, description="Día a consultar, por defecto hoy"),
) -> ResumenDueno:
    """Devuelve dinero en caja en vivo, ventas, entradas/salidas y
    devoluciones del día, consolidado y desglosado por sucursal."""
    return obtener_resumen_dueno(fecha=fecha.isoformat())


@router.get("/ventas-dia")
async def ventas_dia(
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
    fecha: date = Query(default_factory=date.today),
    sucursal_id: UUID | None = Query(None),
) -> dict:
    """Lista todas las ventas completadas del día, con nombre de
    sucursal, para la pantalla 'Ventas del día'."""
    return listar_ventas_dia(
        sucursal_id=str(sucursal_id) if sucursal_id else None,
        fecha=fecha.isoformat(),
    )


@router.get("/venta/{venta_id}/detalle", response_model=DetalleVenta)
async def venta_detalle(
    venta_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
) -> DetalleVenta:
    """Desglose de artículos de una venta específica, para el panel
    flotante de la pantalla 'Ventas del día'."""
    return obtener_detalle_venta(str(venta_id))


@router.get("/productos-faltantes")
async def productos_faltantes(
    usuario: dict = Depends(verificar_permiso("perm_dueno")),
    sucursal_id: UUID | None = Query(None),
) -> dict:
    """Lista COMPLETA (sin límite) de productos en o bajo su mínimo."""
    return listar_productos_faltantes(sucursal_id=str(sucursal_id) if sucursal_id else None)