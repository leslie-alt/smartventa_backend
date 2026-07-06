from fastapi import HTTPException
from app.core.database import supabase


def obtener_sucursal(sucursal_id: str) -> dict:
    """Devuelve los datos de la sucursal actual (para la pantalla de Configuración)."""
    respuesta = (
        supabase.table("sucursales")
        .select("*")
        .eq("id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return respuesta.data


def actualizar_sucursal(sucursal_id: str, datos: dict) -> dict:
    """Actualiza nombre, dirección y/o teléfono de la sucursal (solo admin)."""
    # Quita campos vacíos para no sobrescribir con None
    cambios = {k: v for k, v in datos.items() if v is not None}

    if not cambios:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar.")

    respuesta = (
        supabase.table("sucursales")
        .update(cambios)
        .eq("id", sucursal_id)
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return respuesta.data[0]