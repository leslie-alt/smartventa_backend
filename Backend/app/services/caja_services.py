from fastapi import HTTPException
from app.core.database import supabase


def listar_cajas(sucursal_id: str, solo_activas: bool = True) -> dict:
    """Lista las cajas de la sucursal (hasta 5 de venta + 1 verificador, RF-04.3)."""
    query = supabase.table("cajas").select("*").eq("sucursal_id", sucursal_id)
    if solo_activas:
        query = query.eq("activa", True)
    respuesta = query.order("nombre").execute()
    items = respuesta.data or []
    return {"total": len(items), "items": items}


def obtener_caja(caja_id: str, sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("cajas")
        .select("*")
        .eq("id", caja_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Caja no encontrada en esta sucursal")
    return respuesta.data
    