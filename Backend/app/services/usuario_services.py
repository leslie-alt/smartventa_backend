from datetime import datetime, timezone
from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto
from app.services.auth_services import generar_hash_contrasena

PERMISOS = [
    "perm_inventario_entrada", "perm_inventario_ajuste", "perm_kardex",
    "perm_corte_caja", "perm_modificar_precios", "perm_cancelar_tickets",
    "perm_clientes", "perm_descuentos", "perm_reportes", "perm_exportar",
    "perm_promociones", "perm_administrar", "perm_movimientos_caja",
    "perm_devoluciones", "perm_auditoria",
]

CAMPOS_USUARIO = "id, nombre_completo, nombre_usuario, activo, ultimo_login, creado_en, rol_id, " + ", ".join(PERMISOS)
CAMPOS_ROL_ANIDADO = "roles(nombre, " + ", ".join(PERMISOS) + ")"


def _combinar_permisos(fila: dict) -> dict:
    """Recibe una fila con campos perm_* del usuario + roles(...) anidado,
    y regresa la fila limpia con los permisos EFECTIVOS (override si existe, si no, el del rol)."""
    rol = fila.pop("roles", None) or {}
    rol_nombre = rol.get("nombre")

    for p in PERMISOS:
        valor_usuario = fila.get(p)
        fila[p] = valor_usuario if valor_usuario is not None else rol.get(p, False)

    fila["rol_nombre"] = rol_nombre
    return fila


def listar_usuarios(sucursal_id: str) -> dict:
    """Lista todos los usuarios de la sucursal con su rol y permisos efectivos."""
    respuesta = (
        supabase.table("usuarios")
        .select(f"{CAMPOS_USUARIO}, {CAMPOS_ROL_ANIDADO}")
        .eq("sucursal_id", sucursal_id)
        .order("nombre_completo")
        .execute()
    )

    items = [_combinar_permisos(u) for u in respuesta.data]
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
        .select(f"{CAMPOS_USUARIO}, {CAMPOS_ROL_ANIDADO}")
        .eq("id", usuario_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Usuario")

    return _combinar_permisos(respuesta.data)


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