from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado


def listar_destinatarios(sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("destinatarios_reportes")
        .select("*")
        .eq("sucursal_id", sucursal_id)
        .order("creado_en")
        .execute()
    )
    items = respuesta.data or []
    return {"total": len(items), "items": items}


def crear_destinatario(datos: dict, sucursal_id: str) -> dict:
    nuevo = {**datos, "sucursal_id": sucursal_id}
    respuesta = supabase.table("destinatarios_reportes").insert(nuevo).execute()
    return respuesta.data[0]


def obtener_destinatario(destinatario_id: str, sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("destinatarios_reportes")
        .select("*")
        .eq("id", destinatario_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Destinatario")
    return respuesta.data


def actualizar_destinatario(destinatario_id: str, datos: dict, sucursal_id: str) -> dict:
    if not datos:
        return obtener_destinatario(destinatario_id, sucursal_id)

    supabase.table("destinatarios_reportes").update(datos).eq(
        "id", destinatario_id
    ).eq("sucursal_id", sucursal_id).execute()
    return obtener_destinatario(destinatario_id, sucursal_id)


def eliminar_destinatario(destinatario_id: str, sucursal_id: str) -> dict:
    supabase.table("destinatarios_reportes").delete().eq(
        "id", destinatario_id
    ).eq("sucursal_id", sucursal_id).execute()
    return {"mensaje": "Destinatario eliminado correctamente."}