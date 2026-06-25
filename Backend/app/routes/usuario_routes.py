from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.usuario_model import UsuarioCreate, UsuarioUpdate, UsuarioOut, UsuarioList
from app.services import usuario_services

router = APIRouter()


@router.get("/", response_model=UsuarioList)
def listar_usuarios(usuario: dict = Depends(verificar_permiso("perm_administrar"))):
    """Lista todos los usuarios de la sucursal. Requiere perm_administrar."""
    return usuario_services.listar_usuarios(sucursal_id=usuario["sucursal_id"])


@router.post("/", response_model=UsuarioOut)
def crear_usuario(
    datos: UsuarioCreate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Crea un nuevo usuario. Requiere perm_administrar."""
    return usuario_services.crear_usuario(
        datos=datos.model_dump(),
        sucursal_id=usuario["sucursal_id"],
    )


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obtener_usuario(
    usuario_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    return usuario_services.obtener_usuario(
        usuario_id=str(usuario_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: UUID,
    datos: UsuarioUpdate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    return usuario_services.actualizar_usuario(
        usuario_id=str(usuario_id),
        datos=datos.model_dump(exclude_none=True),
        sucursal_id=usuario["sucursal_id"],
    )


@router.patch("/{usuario_id}/estado", response_model=UsuarioOut)
def cambiar_estado(
    usuario_id: UUID,
    activo: bool,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Activa o desactiva un usuario."""
    return usuario_services.cambiar_estado_usuario(
        usuario_id=str(usuario_id),
        activo=activo,
        sucursal_id=usuario["sucursal_id"],
    )