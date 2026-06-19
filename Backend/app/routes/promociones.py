from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.promocion_model import (
    PromocionCreate, PromocionUpdate,
    PromocionOut, PromocionList, PromocionConProducto
)
from app.services import promocion_services

router = APIRouter()


@router.get("/", response_model=PromocionList)
def listar_promociones(
    solo_activas: bool = True,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Lista todas las promociones de la sucursal."""
    items = promocion_services.obtener_promociones(
        sucursal_id=usuario["sucursal_id"],
        solo_activas=solo_activas,
    )
    return {"total": len(items), "items": items}


@router.get("/{promocion_id}", response_model=PromocionConProducto)
def obtener_promocion(
    promocion_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Retorna una promoción por ID."""
    return promocion_services.obtener_promocion_por_id(
        promocion_id=str(promocion_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.post("/", response_model=PromocionConProducto)
def crear_promocion(
    datos: PromocionCreate,
    usuario: dict = Depends(verificar_permiso("perm_promociones")),
):
    """
    Crea una promoción para un producto.
    Un producto solo puede tener una promoción activa a la vez.
    Requiere permiso perm_promociones.
    """
    return promocion_services.crear_promocion(
        datos=datos.model_dump(mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.put("/{promocion_id}", response_model=PromocionConProducto)
def actualizar_promocion(
    promocion_id: UUID,
    datos: PromocionUpdate,
    usuario: dict = Depends(verificar_permiso("perm_promociones")),
):
    """Actualiza una promoción. Requiere permiso perm_promociones."""
    return promocion_services.actualizar_promocion(
        promocion_id=str(promocion_id),
        datos=datos.model_dump(exclude_none=True, mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.delete("/{promocion_id}")
def eliminar_promocion(
    promocion_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_promociones")),
):
    """
    Desactiva una promoción manualmente (RF-09.3).
    Las promociones no tienen fecha de fin.
    Requiere permiso perm_promociones.
    """
    return promocion_services.eliminar_promocion(
        promocion_id=str(promocion_id),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )