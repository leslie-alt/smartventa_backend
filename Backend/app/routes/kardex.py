from fastapi import APIRouter, Depends
from datetime import date
from uuid import UUID

from app.core.deps import verificar_permiso
from app.models.kardex_model import KardexConsulta, ProductoBusquedaKardex
from app.services import kardex_services

router = APIRouter()


@router.get("/productos/buscar", response_model=list[ProductoBusquedaKardex])
def buscar_productos(
    termino: str,
    usuario: dict = Depends(verificar_permiso("perm_kardex")),
):
    """
    Buscador de productos en la pantalla de kardex.
    Busca por código de barras o descripción.
    Requiere permiso perm_kardex (RF-03.6).
    """
    return kardex_services.buscar_productos_kardex(
        sucursal_id=usuario["sucursal_id"],
        termino=termino,
    )


@router.get("/{producto_id}", response_model=KardexConsulta)
def consultar_kardex(
    producto_id: UUID,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    tipo_movimiento: str | None = None,
    caja_id: UUID | None = None,
    usuario_id: UUID | None = None,
    usuario: dict = Depends(verificar_permiso("perm_kardex")),
):
    """
    Consulta el kardex completo de un producto (RF-03).
    Retorna encabezado + movimientos cronológicos.
    Permite filtrar por fecha, tipo de movimiento, caja y usuario (RF-03.5).
    Requiere permiso perm_kardex.
    """
    return kardex_services.consultar_kardex(
        producto_id=str(producto_id),
        sucursal_id=usuario["sucursal_id"],
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_movimiento=tipo_movimiento,
        caja_id=str(caja_id) if caja_id else None,
        usuario_id=str(usuario_id) if usuario_id else None,
    )