"""Modelos Pydantic para el módulo de Auditoría (RF-13)."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class RegistroAuditoria(BaseModel):
    """Registro individual e inmutable del historial de auditoría (RF-13.2)."""

    id: UUID
    usuario_id: UUID
    usuario_nombre: Optional[str] = None
    sucursal_id: UUID
    caja_id: Optional[UUID] = None
    fecha_hora: datetime
    modulo: str
    accion: str
    registro_id: Optional[UUID] = None
    valores_anteriores: Optional[dict[str, Any]] = None
    valores_nuevos: Optional[dict[str, Any]] = None


class FiltrosAuditoria(BaseModel):
    """Filtros opcionales para consultar el historial (RF-13.3)."""

    usuario_id: Optional[UUID] = None
    caja_id: Optional[UUID] = None
    modulo: Optional[str] = None
    accion: Optional[str] = None
    registro_id: Optional[UUID] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None


class RespuestaAuditoriaPaginada(BaseModel):
    """Respuesta paginada del listado de auditoría."""

    items: list[RegistroAuditoria]
    total: int
    pagina: int
    tamano_pagina: int
    total_paginas: int