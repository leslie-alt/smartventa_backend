from fastapi import HTTPException
from app.core.database import supabase


def listar_clientes(
    sucursal_id: str,
    busqueda: str | None = None,
    es_mayorista: bool | None = None,
    orden: str = "nombre_asc",
    pagina: int = 1,
    por_pagina: int = 20,
) -> dict:
    """Lista clientes de la sucursal con filtros opcionales (RF-07.1)."""
    query = (
        supabase.table("clientes")
        .select("*", count="exact")
        .eq("sucursal_id", sucursal_id)
    )

    if busqueda:
        query = query.or_(
            f"nombre.ilike.%{busqueda}%,"
            f"correo.ilike.%{busqueda}%,"
            f"telefono.ilike.%{busqueda}%"
        )

    if es_mayorista is not None:
        query = query.eq("es_mayorista", es_mayorista)

    # Ordenamiento
    if orden == "nombre_desc":
        query = query.order("nombre", desc=True)
    elif orden == "reciente":
        query = query.order("creado_en", desc=True)
    elif orden == "antiguo":
        query = query.order("creado_en", desc=False)
    else:
        query = query.order("nombre", desc=False)

    desde = (pagina - 1) * por_pagina
    query = query.range(desde, desde + por_pagina - 1)

    respuesta = query.execute()
    return {
        "total": respuesta.count or 0,
        "items": respuesta.data or [],
    }


def obtener_cliente(cliente_id: str, sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("clientes")
        .select("*")
        .eq("id", cliente_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return respuesta.data


def crear_cliente(sucursal_id: str, datos: dict) -> dict:
    """Crea un cliente nuevo (RF-07.1). Requiere perm_clientes."""
    try:
        respuesta = (
            supabase.table("clientes")
            .insert({
                "sucursal_id": sucursal_id,
                "nombre":       datos["nombre"],
                "telefono":     datos.get("telefono"),
                "correo":       datos.get("correo"),
                "es_mayorista": datos.get("es_mayorista", False),
                "activo":       True,
                "notas": datos.get("notas"),
            })
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo crear el cliente.")

    if not respuesta.data:
        raise HTTPException(status_code=500, detail="No se pudo crear el cliente.")
    return respuesta.data[0]


def actualizar_cliente(cliente_id: str, sucursal_id: str, datos: dict) -> dict:
    """Actualiza un cliente (RF-07.1). Requiere perm_clientes."""
    obtener_cliente(cliente_id, sucursal_id)  # valida existencia

    cambios = {k: v for k, v in datos.items() if v is not None}
    if not cambios:
        return obtener_cliente(cliente_id, sucursal_id)

    try:
        supabase.table("clientes").update(cambios).eq("id", cliente_id).eq("sucursal_id", sucursal_id).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo actualizar el cliente.")

    return obtener_cliente(cliente_id, sucursal_id)


def eliminar_cliente(cliente_id: str, sucursal_id: str) -> dict:
    obtener_cliente(cliente_id, sucursal_id)

    try:
        supabase.table("clientes").delete().eq("id", cliente_id).eq("sucursal_id", sucursal_id).execute()
    except Exception as exc:
        if "foreign key" in str(exc).lower() or "23503" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="No se puede eliminar este cliente porque tiene ventas registradas.",
            )
        raise HTTPException(status_code=500, detail="No se pudo eliminar el cliente.")

    return {"mensaje": "Cliente eliminado correctamente."}

