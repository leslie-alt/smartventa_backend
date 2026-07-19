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
    """Crea una caja nueva (RF-04.3: máx 5 de venta + 1 verificador por sucursal)."""
    # Validar límites antes de insertar
    existentes = (
        supabase.table("cajas")
        .select("id, es_verificador")
        .eq("sucursal_id", sucursal_id)
        .eq("activa", True)
        .execute()
    ).data or []

    verificadores = [c for c in existentes if c["es_verificador"]]
    venta = [c for c in existentes if not c["es_verificador"]]

    if datos["es_verificador"] and len(verificadores) >= 1:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una estación verificadora en esta sucursal.",
        )
    if not datos["es_verificador"] and len(venta) >= 5:
        raise HTTPException(
            status_code=409,
            detail="Se alcanzó el límite de 5 cajas de venta por sucursal.",
        )

    try:
        respuesta = (
            supabase.table("cajas")
            .insert({
                "sucursal_id": sucursal_id,
                "nombre": datos["nombre"],
                "es_verificador": datos["es_verificador"],
                "activa": True,
            })
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo crear la caja.")

    return respuesta.data[0]