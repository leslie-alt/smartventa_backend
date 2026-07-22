from fastapi import APIRouter, Depends

from app.core.deps import verificar_permiso
from app.models.rol_model import RolList
from app.services import rol_services

router = APIRouter()


@router.get("/", response_model=RolList)
def listar_roles(
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Lista los roles y permisos de la sucursal. Solo lectura — los roles
    se gestionan directamente en la base de datos."""
    items = rol_services.listar_roles(usuario["sucursal_id"])
    return {"total": len(items), "items": items}