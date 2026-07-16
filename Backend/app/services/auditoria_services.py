"""Servicio de consulta del módulo de Auditoría (RF-13).

Este módulo es EXCLUSIVAMENTE de lectura: los registros se insertan desde
los RPC combinados de cada módulo (ventas, inventario, cortes, clientes,
etc.), nunca desde aquí, ya que RF-13.4 establece que la auditoría no
puede editarse ni eliminarse bajo ninguna circunstancia.
"""

import math
from uuid import UUID

from app.core.database import supabase
from app.models.auditoria_model import (
    FiltrosAuditoria,
    RegistroAuditoria,
    RespuestaAuditoriaPaginada,
)

TAMANO_PAGINA_DEFECTO = 25


async def listar_auditoria(
    sucursal_id: UUID,
    filtros: FiltrosAuditoria,
    pagina: int = 1,
    tamano_pagina: int = TAMANO_PAGINA_DEFECTO,
) -> RespuestaAuditoriaPaginada:
    """Consulta el historial de auditoría de la sucursal del usuario en
    sesión, aplicando filtros opcionales y paginación (1 sola llamada a
    Supabase, incluyendo el conteo total)."""


    consulta = (
        supabase.table("auditoria")
        .select("*, usuarios(nombre_completo), cajas(nombre)", count="exact")
        .eq("sucursal_id", str(sucursal_id))
    )
    if filtros.usuario_id:
        consulta = consulta.eq("usuario_id", str(filtros.usuario_id))
    if filtros.caja_id:
        consulta = consulta.eq("caja_id", str(filtros.caja_id))
    if filtros.modulo:
        consulta = consulta.eq("modulo", filtros.modulo)
    if filtros.accion:
        consulta = consulta.eq("accion", filtros.accion)
    if filtros.registro_id:
        consulta = consulta.eq("registro_id", str(filtros.registro_id))
    if filtros.fecha_inicio:
        consulta = consulta.gte("fecha_hora", filtros.fecha_inicio.isoformat())
    if filtros.fecha_fin:
        consulta = consulta.lte("fecha_hora", filtros.fecha_fin.isoformat())

    inicio = (pagina - 1) * tamano_pagina
    fin = inicio + tamano_pagina - 1

    resultado = (
        consulta.order("fecha_hora", desc=True).range(inicio, fin).execute()
    )

    total = resultado.count or 0
    items: list[RegistroAuditoria] = []
    for registro in resultado.data:
        usuario = registro.pop("usuarios", None)
        caja = registro.pop("cajas", None)
        registro["usuario_nombre"] = usuario.get("nombre_completo") if usuario else None
        registro["caja_nombre"] = caja.get("nombre") if caja else None
        items.append(RegistroAuditoria(**registro))

    return RespuestaAuditoriaPaginada(
        items=items,
        total=total,
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        total_paginas=math.ceil(total / tamano_pagina) if total else 0,
    )