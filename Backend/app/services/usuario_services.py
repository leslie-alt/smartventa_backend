from datetime import datetime, timezone
from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto
from app.services.auth_services import generar_hash_contrasena


def listar_usuarios(sucursal_id: str) -> dict:
    """Lista todos los usuarios de la sucursal con su rol."""
    respuesta = (
        supabase.table("usuarios")
        .select("id, nombre_completo, nombre_usuario, activo, ultimo_login, creado_en, rol_id, roles(nombre)")
        .eq("sucursal_id", sucursal_id)
        .order("nombre_completo")
        .execute()
    )

    items = []
    for u in respuesta.data:
        rol = u.pop("roles", None)
        items.append({**u, "rol_nombre": rol["nombre"] if rol else None})

    return {"total": len(items), "items": items}


def crear_usuario(datos: dict, sucursal_id: str) -> dict:
    """Crea un nuevo usuario con contraseña hasheada."""
    existente = (
        supabase.table("usuarios")
        .select("id")
        .eq("nombre_usuario", datos["nombre_usuario"])
        .execute()
    )
    if existente.data:
        raise ErrorConflicto("Ya existe un usuario con ese nombre de usuario.")

    contrasena_hash = generar_hash_contrasena(datos["contrasena"])

    respuesta = (
        supabase.table("usuarios")
        .insert({
            "sucursal_id": sucursal_id,
            "rol_id": str(datos["rol_id"]),
            "nombre_completo": datos["nombre_completo"],
            "nombre_usuario": datos["nombre_usuario"],
            "contrasena_hash": contrasena_hash,
            "activo": True,
        })
        .execute()
    )
    return respuesta.data[0]


def obtener_usuario(usuario_id: str, sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("usuarios")
        .select("id, nombre_completo, nombre_usuario, activo, ultimo_login, creado_en, rol_id, roles(nombre)")
        .eq("id", usuario_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Usuario")

    rol = respuesta.data.pop("roles", None)
    return {**respuesta.data, "rol_nombre": rol["nombre"] if rol else None}


def actualizar_usuario(usuario_id: str, datos: dict, sucursal_id: str) -> dict:
    cambios = {k: v for k, v in datos.items() if v is not None}
    if not cambios:
        return obtener_usuario(usuario_id, sucursal_id)

    if "rol_id" in cambios:
        cambios["rol_id"] = str(cambios["rol_id"])

    supabase.table("usuarios").update(cambios).eq("id", usuario_id).eq("sucursal_id", sucursal_id).execute()
    return obtener_usuario(usuario_id, sucursal_id)


def cambiar_estado_usuario(usuario_id: str, activo: bool, sucursal_id: str) -> dict:
    supabase.table("usuarios").update({"activo": activo}).eq("id", usuario_id).eq("sucursal_id", sucursal_id).execute()
    return obtener_usuario(usuario_id, sucursal_id)