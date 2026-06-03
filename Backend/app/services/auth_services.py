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
    # 1. Buscar usuario SIN join
    respuesta = (
        db.table("usuarios")
        .select("id, nombre_completo, nombre_usuario, contrasena_hash, activo, sucursal_id, rol_id")
        .eq("nombre_usuario", nombre_usuario)
        .eq("activo", True)
        .single()
        .execute()
    )

    usuario = respuesta.data
    if not usuario:
        raise ErrorSesionInvalida()

    # 2. Verificar contraseña
    if not verificar_contrasena(contrasena, usuario["contrasena_hash"]):
        raise ErrorSesionInvalida()

    # 3. Buscar permisos del rol por separado
    respuesta_rol = (
        db.table("roles")
        .select(
            "perm_inventario_entrada, perm_inventario_ajuste, perm_kardex, "
            "perm_corte_caja, perm_modificar_precios, perm_cancelar_tickets, "
            "perm_clientes, perm_descuentos, perm_reportes, perm_exportar, "
            "perm_promociones, perm_administrar"
        )
        .eq("id", usuario["rol_id"])
        .single()
        .execute()
    )

    rol = respuesta_rol.data
    if not rol:
        raise ErrorSesionInvalida()

    # --- resto del código igual ---