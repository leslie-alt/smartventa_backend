from datetime import datetime, timezone
from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto
from app.services.auth_services import generar_hash_contrasena

PERMISOS = [
    "perm_inventario_entrada", "perm_inventario_ajuste", "perm_kardex",
    "perm_corte_caja", "perm_modificar_precios", "perm_cancelar_tickets",
    "perm_clientes", "perm_descuentos", "perm_reportes", "perm_exportar",
    "perm_promociones", "perm_administrar", "perm_movimientos_caja",
    "perm_devoluciones", "perm_auditoria", "perm_dueno",
]

CAMPOS_USUARIO = "id, nombre_completo, nombre_usuario, activo, ultimo_login, creado_en, rol_id"
CAMPOS_ROL_ANIDADO = "roles(nombre, " + ", ".join(PERMISOS) + ")"


def _aplanar_permisos_del_rol(fila: dict) -> dict:
    rol = fila.pop("roles", None) or {}
    for p in PERMISOS:
        fila[p] = bool(rol.get(p, False))
    fila["rol_nombre"] = rol.get("nombre")
    return fila


def _nombre_rol_disponible(nombre_usuario: str, sucursal_id: str) -> str:
    """
    Genera un nombre de rol único basado en nombre_usuario. Cada usuario
    tiene su propio rol exclusivo (nombrado igual a su nombre_usuario);
    si ya existe uno con ese nombre (por ejemplo, al reemplazar permisos
    en una edición, el rol anterior queda huérfano con el mismo nombre
    base), se agrega un sufijo incremental para no chocar.
    """
    base = nombre_usuario.strip()
    candidato = base
    sufijo = 2
    while True:
        existente = (
            supabase.table("roles")
            .select("id")
            .eq("sucursal_id", sucursal_id)
            .eq("nombre", candidato)
            .execute()
        )
        if not existente.data:
            return candidato
        candidato = f"{base}-{sufijo}"
        sufijo += 1


def _crear_rol_para_usuario(nombre_usuario: str, sucursal_id: str, permisos: dict) -> str:
    """Crea un rol exclusivo con los permisos dados y retorna su id."""
    nombre_rol = _nombre_rol_disponible(nombre_usuario, sucursal_id)
    datos_rol = {"nombre": nombre_rol, "sucursal_id": sucursal_id}
    for p in PERMISOS:
        datos_rol[p] = bool(permisos.get(p, False))

    respuesta = supabase.table("roles").insert(datos_rol).execute()
    return respuesta.data[0]["id"]


def listar_usuarios(sucursal_id: str) -> dict:
    respuesta = (
        supabase.table("usuarios")
        .select(f"{CAMPOS_USUARIO}, {CAMPOS_ROL_ANIDADO}")
        .eq("sucursal_id", sucursal_id)
        .order("nombre_completo")
        .execute()
    )
    items = [_aplanar_permisos_del_rol(u) for u in respuesta.data]
    return {"total": len(items), "items": items}


def crear_usuario(datos: dict, sucursal_id: str) -> dict:
    """
    Crea un usuario y, junto con él, un rol exclusivo nombrado igual a su
    nombre_usuario con los permisos indicados en el formulario (RF-08.4:
    cada empleado tiene su propio conjunto de permisos).
    """
    existente = (
        supabase.table("usuarios")
        .select("id")
        .eq("nombre_usuario", datos["nombre_usuario"])
        .execute()
    )
    if existente.data:
        raise ErrorConflicto("Ya existe un usuario con ese nombre de usuario.")

    permisos = {p: datos.pop(p, False) for p in PERMISOS}
    rol_id = _crear_rol_para_usuario(datos["nombre_usuario"], sucursal_id, permisos)

    contrasena_hash = generar_hash_contrasena(datos["contrasena"])

    respuesta = (
        supabase.table("usuarios")
        .insert({
            "sucursal_id": sucursal_id,
            "rol_id": rol_id,
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
    return _aplanar_permisos_del_rol(respuesta.data)


def actualizar_usuario(
    usuario_id: str, datos: dict, sucursal_id: str, generar_nuevo_token: bool = False,
) -> dict:
    """
    Si el body trae algún perm_*, se actualiza EL MISMO rol que ya tiene
    asignado el usuario (un rol = un usuario, siempre) — no se crea uno
    nuevo ni se dejan huérfanos en la tabla roles.

    Si generar_nuevo_token=True (el usuario en sesión se edita a sí
    mismo), se genera un JWT con los permisos actualizados y se agrega
    como 'nuevo_token' en la respuesta, para refrescar la sesión sin
    necesidad de volver a iniciar sesión.
    """
    permisos_enviados = {p: datos.pop(p) for p in PERMISOS if datos.get(p) is not None}
    cambios = {k: v for k, v in datos.items() if v is not None}

    if permisos_enviados:
        actual = obtener_usuario(usuario_id, sucursal_id)
        permisos_finales = {p: actual[p] for p in PERMISOS}
        permisos_finales.update(permisos_enviados)

        supabase.table("roles").update(permisos_finales).eq("id", str(actual["rol_id"])).execute()

    if cambios:
        supabase.table("usuarios").update(cambios).eq("id", usuario_id).eq("sucursal_id", sucursal_id).execute()

    resultado = obtener_usuario(usuario_id, sucursal_id)
    if generar_nuevo_token:
        from app.services.auth_services import generar_token
        payload = {
            "usuario_id": usuario_id,
            "nombre_usuario": resultado["nombre_usuario"],
            "nombre_completo": resultado["nombre_completo"],
            "sucursal_id": sucursal_id,
            "rol_id": str(resultado["rol_id"]),
        }
        for p in PERMISOS:
            payload[p] = bool(resultado.get(p, False))
        resultado["nuevo_token"] = generar_token(payload)

    return resultado


def cambiar_estado_usuario(usuario_id: str, activo: bool, sucursal_id: str) -> dict:
    """El rol asociado no se toca al desactivar — queda disponible."""
    supabase.table("usuarios").update({"activo": activo}).eq("id", usuario_id).eq("sucursal_id", sucursal_id).execute()
    return obtener_usuario(usuario_id, sucursal_id)