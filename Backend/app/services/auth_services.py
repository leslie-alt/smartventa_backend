from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import jwt
from passlib.context import CryptContext
from supabase import Client

from app.core.config import config
from app.core.exceptions import ErrorSesionInvalida

# Contexto para verificar hashes bcrypt
contexto_hash = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verificar_contrasena(contrasena_plana: str, contrasena_hash: str) -> bool:
    """Compara la contraseña ingresada contra el hash almacenado."""
    return contexto_hash.verify(contrasena_plana, contrasena_hash)


def generar_hash_contrasena(contrasena: str) -> str:
    """Genera un hash bcrypt de la contraseña."""
    return contexto_hash.hash(contrasena)


def generar_token(payload: dict) -> str:
    """
    Firma el payload con el JWT_SECRET y agrega la fecha de expiración.
    """
    datos = payload.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=config.jwt_expiracion_minutos
    )
    datos["exp"] = expiracion
    return jwt.encode(datos, config.jwt_secret, algorithm=config.jwt_algoritmo)

def login(nombre_usuario: str, contrasena: str, db: Client) -> dict:
    PERMISOS = [
        "perm_inventario_entrada", "perm_inventario_ajuste", "perm_kardex",
        "perm_corte_caja", "perm_modificar_precios", "perm_cancelar_tickets",
        "perm_clientes", "perm_descuentos", "perm_reportes", "perm_exportar",
        "perm_promociones", "perm_administrar", "perm_movimientos_caja",
        "perm_devoluciones", "perm_auditoria",
    ]

    # 1. Buscar usuario (ahora incluyendo sus posibles overrides de permisos)
    try:
        respuesta = (
            db.table("usuarios")
            .select(
                "id, nombre_completo, nombre_usuario, contrasena_hash, activo, "
                "sucursal_id, rol_id, " + ", ".join(PERMISOS)
            )
            .eq("nombre_usuario", nombre_usuario)
            .eq("activo", True)
            .single()
            .execute()
        )
        usuario = respuesta.data
    except Exception:
        raise ErrorSesionInvalida()

    if not usuario:
        raise ErrorSesionInvalida()

    # 2. Verificar contraseña
    if not verificar_contrasena(contrasena, usuario["contrasena_hash"]):
        raise ErrorSesionInvalida()

    # 3. Buscar permisos del rol por separado
    try:
        respuesta_rol = (
            db.table("roles")
            .select(", ".join(PERMISOS))
            .eq("id", usuario["rol_id"])
            .single()
            .execute()
        )
        rol = respuesta_rol.data
    except Exception:
        raise ErrorSesionInvalida()

    if not rol:
        raise ErrorSesionInvalida()

    # 4. Construir payload del JWT — permiso efectivo: override del usuario, si no hay, el del rol
    payload = {
        "usuario_id": str(usuario["id"]),
        "nombre_usuario": usuario["nombre_usuario"],
        "nombre_completo": usuario["nombre_completo"],
        "sucursal_id": str(usuario["sucursal_id"]),
        "rol_id": str(usuario["rol_id"]),
    }
    for p in PERMISOS:
        payload[p] = usuario[p] if usuario[p] is not None else rol[p]

    # 5. Actualizar ultimo_login
    db.table("usuarios").update(
        {"ultimo_login": datetime.now(timezone.utc).isoformat()}
    ).eq("id", usuario["id"]).execute()

    # 6. Generar y retornar token
    token = generar_token(payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario_id": usuario["id"],
        "nombre_completo": usuario["nombre_completo"],
        "sucursal_id": usuario["sucursal_id"],
        "rol_id": usuario["rol_id"],
        "permisos": {k: v for k, v in payload.items() if k.startswith("perm_")},
    }

