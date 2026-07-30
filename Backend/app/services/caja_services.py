# caja_services.py
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


def crear_caja(sucursal_id: str, datos: dict) -> dict:
    """Crea una caja nueva."""
    try:
        respuesta = (
            supabase.table("cajas")
            .insert({
                "sucursal_id": sucursal_id,
                "nombre": datos["nombre"],
                "es_verificador": datos["es_verificador"],
                "activa": True,
                "impresora_tipo": datos.get("impresora_tipo"),
                "impresora_valor": datos.get("impresora_valor"),
                "impresora_puerto": datos.get("impresora_puerto"),
            })
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo crear la caja.")

    return respuesta.data[0]

def actualizar_caja(caja_id: str, sucursal_id: str, datos: dict) -> dict:
    """Actualiza una caja existente, incluyendo su configuración de impresora."""
    actual = (
        supabase.table("cajas")
        .select("id, es_verificador, activa")
        .eq("id", caja_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not actual.data:
        raise HTTPException(status_code=404, detail="Caja no encontrada en esta sucursal")

    try:
        respuesta = (
            supabase.table("cajas")
            .update({
                "nombre": datos["nombre"],
                "es_verificador": datos["es_verificador"],
                "activa": datos["activa"],
                "impresora_tipo": datos.get("impresora_tipo"),
                "impresora_valor": datos.get("impresora_valor"),
                "impresora_puerto": datos.get("impresora_puerto"),
            })
            .eq("id", caja_id)
            .eq("sucursal_id", sucursal_id)
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la caja.")

    return respuesta.data[0]