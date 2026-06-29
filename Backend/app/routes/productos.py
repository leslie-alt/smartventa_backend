from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import Response
from uuid import UUID

from app.core.deps import obtener_usuario_actual, verificar_permiso
from app.core.exceptions import ErrorNoAutorizado
from app.models.producto_model import (
    ProductoCreate, ProductoUpdate, ProductoConStock,
    ResultadoImportacion
)
from app.models.categoria_model import CategoriaList
from app.services import producto_services

router = APIRouter()


# =============================================================
# PRODUCTOS
# =============================================================

@router.get("/", response_model=list[ProductoConStock])
def listar_productos(
    solo_activos: bool = True,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Lista todos los productos de la sucursal con stock actual."""
    return producto_services.obtener_productos(
        sucursal_id=usuario["sucursal_id"],
        solo_activos=solo_activos,
    )


@router.get("/buscar", response_model=list[ProductoConStock])
def buscar_productos(
    termino: str | None = None,
    categoria: str | None = None,
    solo_con_stock: bool = False,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Búsqueda por código de barras o descripción, con filtro opcional por categoría.
    Usado en POS y verificador de precios (RF-01.3, RF-01.4).
    """
    return producto_services.buscar_productos(
        sucursal_id=usuario["sucursal_id"],
        termino=termino,
        categoria=categoria,
        solo_con_stock=solo_con_stock,
    )

@router.get("/exportar/excel")
def exportar_excel(
    solo_plantilla: bool = False,
    usuario: dict = Depends(verificar_permiso("perm_exportar")),
):
    """Exporta el catálogo completo en Excel, o plantilla vacía (RF-01.5)."""
    contenido = producto_services.exportar_productos_excel(
        sucursal_id=usuario["sucursal_id"],
        solo_plantilla=solo_plantilla,
    )
    nombre = "plantilla_productos.xlsx" if solo_plantilla else "productos.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@router.post("/importar/excel", response_model=ResultadoImportacion)
def importar_excel(
    archivo: UploadFile = File(...),
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Importa productos desde Excel o CSV (RF-01.5)."""
    contenido = archivo.file.read()
    return producto_services.importar_productos_excel(
        contenido=contenido,
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.get("/categorias/lista", response_model=CategoriaList)
def listar_categorias(
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Retorna las categorías únicas del catálogo."""
    items = producto_services.obtener_categorias(usuario["sucursal_id"])
    return {"total": len(items), "items": items}


@router.get("/{producto_id}", response_model=ProductoConStock)
def obtener_producto(
    producto_id: UUID,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """Retorna un producto por ID."""
    return producto_services.obtener_producto_por_id(
        producto_id=str(producto_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.post("/", response_model=ProductoConStock)
def crear_producto(
    datos: ProductoCreate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Crea un nuevo producto. Requiere permiso administrar."""
    return producto_services.crear_producto(
        datos=datos.model_dump(exclude_none=True, mode="json"),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.put("/{producto_id}", response_model=ProductoConStock)
def actualizar_producto(
    producto_id: UUID,
    datos: ProductoUpdate,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Actualiza un producto.
    Modificar precios requiere perm_modificar_precios.
    Modificar otros campos requiere perm_administrar.
    """
    campos = datos.model_dump(exclude_none=True, mode="json")

    campos_precio = {"precio_venta", "precio_mayoreo", "costo_unitario"}
    modifica_precio = bool(campos.keys() & campos_precio)
    modifica_otros  = bool(campos.keys() - campos_precio)

    if modifica_precio and not usuario.get("perm_modificar_precios") and not usuario.get("perm_administrar"):
        raise ErrorNoAutorizado("modificar precios de productos")

    if modifica_otros and not usuario.get("perm_administrar"):
        raise ErrorNoAutorizado("modificar datos del producto")

    return producto_services.actualizar_producto(
        producto_id=str(producto_id),
        datos=campos,
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
    )


@router.patch("/{producto_id}/visibilidad")
def cambiar_visibilidad(
    producto_id: UUID,
    activo: bool,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """
    Activa o desactiva la visibilidad del producto.

    NOTA: activo=False oculta el producto del POS y búsquedas.
    Si en el futuro se requiere separar 'oculto en POS' de 'eliminado',
    agregar columna 'visible_en_pos' a la tabla productos.
    """
    return producto_services.cambiar_visibilidad(
        producto_id=str(producto_id),
        sucursal_id=usuario["sucursal_id"],
        usuario_id=usuario["usuario_id"],
        activo=activo,
    )