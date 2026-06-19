from fastapi import APIRouter, Depends

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.inventario_model import (
    EntradaMercanciaIn, AjusteInventarioIn, InventarioList
)
from app.services import inventario_services

router = APIRouter()


@router.get("/", response_model=InventarioList)
def listar_inventario(
    termino: str | None = None,
    categoria_id: str | None = None,
    solo_stock_bajo: bool = False,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Listado de productos con existencia actual y alertas de stock bajo.
    Pantalla principal del módulo de inventario.
    Incluye filtros por código/descripción, categoría y stock bajo.
    """
    return inventario_services.listar_inventario(
        sucursal_id=usuario["sucursal_id"],
        termino=termino,
        categoria_id=categoria_id,
        solo_stock_bajo=solo_stock_bajo,
    )


@router.post("/entradas")
def registrar_entrada(
    datos: EntradaMercanciaIn,
    usuario: dict = Depends(verificar_permiso("perm_inventario_entrada")),
):
    """
    Registra una entrada de mercancía (RF-02.3).
    Incrementa el inventario y genera registro en kardex.
    Requiere permiso perm_inventario_entrada.
    """
    return inventario_services.registrar_entrada(
        datos=datos.model_dump(mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.post("/ajustes")
def ajustar_inventario(
    datos: AjusteInventarioIn,
    usuario: dict = Depends(verificar_permiso("perm_inventario_ajuste")),
):
    """
    Ajusta el inventario a una cantidad real contada (RF-02.4).
    Calcula diferencia automáticamente y genera movimiento en kardex solo si hay cambio.
    Requiere permiso perm_inventario_ajuste.
    """
    return inventario_services.ajustar_inventario(
        datos=datos.model_dump(mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )