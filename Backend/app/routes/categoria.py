from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.models.categoria_model import CategoriaCreate, CategoriaUpdate, CategoriaOut, CategoriaList
from app.services import categoria_services

router = APIRouter()


@router.get("/", response_model=CategoriaList)
def listar_categorias(
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Lista todas las categorías activas de la sucursal."""
    items = categoria_services.obtener_categorias(usuario["sucursal_id"])
    return {"total": len(items), "items": items}


@router.get("/{categoria_id}", response_model=CategoriaOut)
def obtener_categoria(
    categoria_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Retorna una categoría por ID."""
    return categoria_services.obtener_categoria_por_id(
        categoria_id=str(categoria_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.post("/", response_model=CategoriaOut)
def crear_categoria(
    datos: CategoriaCreate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Crea una nueva categoría. Requiere permiso administrar."""
    return categoria_services.crear_categoria(
        nombre=datos.nombre,
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.put("/{categoria_id}", response_model=CategoriaOut)
def actualizar_categoria(
    categoria_id: UUID,
    datos: CategoriaUpdate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Actualiza una categoría. Requiere permiso administrar."""
    return categoria_services.actualizar_categoria(
        categoria_id=str(categoria_id),
        datos=datos.model_dump(exclude_none=True, mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.delete("/{categoria_id}")
def eliminar_categoria(
    categoria_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """
    Desactiva una categoría (soft delete).
    Falla si tiene productos activos asignados.
    """
    return categoria_services.eliminar_categoria(
        categoria_id=str(categoria_id),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )