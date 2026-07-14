"""Endpoints del módulo de Auditoría (RF-13).

Módulo exclusivamente de consulta: no expone creación, edición ni
eliminación, ya que RF-13.4 prohíbe modificar o borrar registros de
auditoría bajo cualquier circunstancia.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.deps import verificar_permiso
from app.models.auditoria_model import FiltrosAuditoria, RespuestaAuditoriaPaginada
from app.services.auditoria_services import listar_auditoria

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("/", response_model=RespuestaAuditoriaPaginada)
async def obtener_auditoria(
    usuario_actual: dict = Depends(verificar_permiso("perm_auditoria")),
    usuario_id: Optional[UUID] = Query(None, description="Filtrar por usuario responsable"),
    caja_id: Optional[UUID] = Query(None, description="Filtrar por caja"),
    modulo: Optional[str] = Query(None, description="Filtrar por módulo afectado"),
    accion: Optional[str] = Query(None, description="Filtrar por tipo de acción"),
    registro_id: Optional[UUID] = Query(None, description="Filtrar por el registro afectado"),
    fecha_inicio: Optional[datetime] = Query(None),
    fecha_fin: Optional[datetime] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano_pagina: int = Query(25, ge=1, le=100),
) -> RespuestaAuditoriaPaginada:
    """Lista el historial de auditoría de la sucursal del usuario en
    sesión. El id de sucursal se obtiene siempre del token, nunca del
    cliente (regla de negocio: no hardcodear sucursal)."""

    filtros = FiltrosAuditoria(
        usuario_id=usuario_id,
        caja_id=caja_id,
        modulo=modulo,
        accion=accion,
        registro_id=registro_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    return await listar_auditoria(
        sucursal_id=usuario_actual["sucursal_id"],
        filtros=filtros,
        pagina=pagina,
        tamano_pagina=tamano_pagina,
    )