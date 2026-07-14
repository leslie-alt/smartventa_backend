from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.cliente_model import ClienteCreate, ClienteUpdate, ClienteOut, ClienteList
from app.services import cliente_services

router = APIRouter()


@router.get("/", response_model=ClienteList)
def listar_clientes(
    busqueda: Optional[str] = None,
    es_mayorista: Optional[bool] = None,
    orden: str = "nombre_asc",
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=20, ge=1, le=100),
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Lista clientes de la sucursal."""
    return cliente_services.listar_clientes(
        sucursal_id=usuario["sucursal_id"],
        busqueda=busqueda,
        es_mayorista=es_mayorista,
        orden=orden,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.post("/", response_model=ClienteOut)
def crear_cliente(
    datos: ClienteCreate,
    usuario: dict = Depends(verificar_permiso("perm_clientes")),
):
    """Crea un cliente nuevo (RF-07.1)."""
    return cliente_services.crear_cliente(
        sucursal_id=usuario["sucursal_id"],
        datos=datos.model_dump(exclude_none=True),
    )


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener_cliente(
    cliente_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    return cliente_services.obtener_cliente(
        cliente_id=str(cliente_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.put("/{cliente_id}", response_model=ClienteOut)
def actualizar_cliente(
    cliente_id: UUID,
    datos: ClienteUpdate,
    usuario: dict = Depends(verificar_permiso("perm_clientes")),
):
    """Actualiza un cliente (RF-07.1)."""
    return cliente_services.actualizar_cliente(
        cliente_id=str(cliente_id),
        sucursal_id=usuario["sucursal_id"],
        datos=datos.model_dump(exclude_none=True),
    )


@router.delete("/{cliente_id}")
def eliminar_cliente(
    cliente_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_clientes")),
):
    """Elimina un cliente (RF-07.1)."""
    return cliente_services.eliminar_cliente(
        cliente_id=str(cliente_id),
        sucursal_id=usuario["sucursal_id"],
    )

