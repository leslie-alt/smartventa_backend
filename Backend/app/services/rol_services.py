from app.core.database import supabase


def listar_roles(sucursal_id: str) -> list[dict]:
    """Lista los roles configurados para la sucursal (solo lectura)."""
    respuesta = (
        supabase.table("roles")
        .select("*")
        .eq("sucursal_id", sucursal_id)
        .order("nombre")
        .execute()
    )
    return respuesta.data or []