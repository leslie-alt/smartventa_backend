from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto


def _registrar_auditoria(
    usuario_id: str,
    sucursal_id: str,
    accion: str,
    registro_id: str,
    valores_anteriores: dict | None,
    valores_nuevos: dict | None,
):
    supabase.table("auditoria").insert({
        "usuario_id": usuario_id,
        "sucursal_id": sucursal_id,
        "modulo": "promociones",
        "accion": accion,
        "registro_id": registro_id,
        "valores_anteriores": valores_anteriores,
        "valores_nuevos": valores_nuevos,
    }).execute()


def _verificar_producto_en_sucursal(producto_id: str, sucursal_id: str) -> dict:
    """Verifica que el producto exista y pertenezca a la sucursal."""
    respuesta = (
        supabase.table("productos")
        .select("id, descripcion, codigo_barras, activo")
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Producto")
    if not respuesta.data["activo"]:
        raise ErrorConflicto("No se puede crear una promoción para un producto inactivo.")
    return respuesta.data


def _enriquecer_promocion(promocion: dict) -> dict:
    """Agrega descripción y código del producto a la promoción."""
    producto = (
        supabase.table("productos")
        .select("descripcion, codigo_barras")
        .eq("id", promocion["producto_id"])
        .single()
        .execute()
    )
    if producto.data:
        promocion["producto_descripcion"] = producto.data["descripcion"]
        promocion["producto_codigo_barras"] = producto.data.get("codigo_barras")
    return promocion


def obtener_promociones(sucursal_id: str, solo_activas: bool = True) -> list[dict]:
    """
    Retorna todas las promociones de la sucursal.
    Se obtiene la sucursal a través de producto_id → productos.sucursal_id.
    """
    # Primero obtenemos los IDs de productos de la sucursal
    productos = (
        supabase.table("productos")
        .select("id")
        .eq("sucursal_id", sucursal_id)
        .execute()
    )
    if not productos.data:
        return []

    ids_productos = [p["id"] for p in productos.data]

    query = (
        supabase.table("promociones")
        .select("*, productos(descripcion, codigo_barras)")
        .in_("producto_id", ids_productos)
    )
    if solo_activas:
        query = query.eq("activa", True)

    respuesta = query.order("creado_en", desc=True).execute()

    promociones = []
    for p in respuesta.data:
        producto_data = p.pop("productos", None)
        p["producto_descripcion"] = producto_data["descripcion"] if producto_data else ""
        p["producto_codigo_barras"] = producto_data.get("codigo_barras") if producto_data else None
        promociones.append(p)

    return promociones


def obtener_promocion_por_id(promocion_id: str, sucursal_id: str) -> dict:
    """Retorna una promoción verificando que el producto pertenezca a la sucursal."""
    respuesta = (
        supabase.table("promociones")
        .select("*, productos(descripcion, codigo_barras, sucursal_id)")
        .eq("id", promocion_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Promoción")

    promocion = respuesta.data
    producto_data = promocion.pop("productos", None)

    # Verificar que el producto pertenezca a la sucursal del usuario
    if not producto_data or producto_data.get("sucursal_id") != sucursal_id:
        raise ErrorNoEncontrado("Promoción")

    promocion["producto_descripcion"] = producto_data["descripcion"]
    promocion["producto_codigo_barras"] = producto_data.get("codigo_barras")
    return promocion


def obtener_promocion_activa_por_producto(producto_id: str) -> dict | None:
    """
    Retorna la promoción activa de un producto si existe.
    Usado en el cálculo de precios al momento de la venta (RF-09, RF-05.5).
    """
    respuesta = (
        supabase.table("promociones")
        .select("*")
        .eq("producto_id", producto_id)
        .eq("activa", True)
        .single()
        .execute()
    )
    return respuesta.data if respuesta.data else None


def crear_promocion(datos: dict, sucursal_id: str, usuario_id: str) -> dict:
    """
    Crea una promoción para un producto de la sucursal.
    Un producto solo puede tener una promoción activa a la vez (RF-09.4).
    """
    producto_id = str(datos["producto_id"])

    # Verificar que el producto pertenezca a la sucursal
    _verificar_producto_en_sucursal(producto_id, sucursal_id)

    # Verificar que no tenga ya una promoción activa
    activa_existente = obtener_promocion_activa_por_producto(producto_id)
    if activa_existente:
        raise ErrorConflicto(
            "Este producto ya tiene una promoción activa. "
            "Desactívala antes de crear una nueva."
        )

    nueva = {
        **datos,
        "producto_id": producto_id,
        "activa": True,
    }
    # Convertir tipos no serializables
    if "valor_beneficio" in nueva:
        nueva["valor_beneficio"] = float(nueva["valor_beneficio"])
    if "fecha_inicio" in nueva:
        nueva["fecha_inicio"] = str(nueva["fecha_inicio"])

    respuesta = supabase.table("promociones").insert(nueva).execute()
    promocion = respuesta.data[0]

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="crear_promocion",
        registro_id=promocion["id"],
        valores_anteriores=None,
        valores_nuevos=promocion,
    )

    return _enriquecer_promocion(promocion)


def actualizar_promocion(
    promocion_id: str,
    datos: dict,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """Actualiza los datos de una promoción existente."""
    anterior = obtener_promocion_por_id(promocion_id, sucursal_id)

    if "valor_beneficio" in datos:
        datos["valor_beneficio"] = float(datos["valor_beneficio"])
    if "fecha_inicio" in datos:
        datos["fecha_inicio"] = str(datos["fecha_inicio"])

    respuesta = (
        supabase.table("promociones")
        .update(datos)
        .eq("id", promocion_id)
        .execute()
    )
    actualizado = respuesta.data[0]

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="actualizar_promocion",
        registro_id=promocion_id,
        valores_anteriores=anterior,
        valores_nuevos=actualizado,
    )

    return _enriquecer_promocion(actualizado)


def eliminar_promocion(
    promocion_id: str,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Elimina (desactiva) una promoción manualmente (RF-09.3).
    Las promociones no tienen fecha de fin; se desactivan así.
    """
    anterior = obtener_promocion_por_id(promocion_id, sucursal_id)

    supabase.table("promociones").update(
        {"activa": False}
    ).eq("id", promocion_id).execute()

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="eliminar_promocion",
        registro_id=promocion_id,
        valores_anteriores=anterior,
        valores_nuevos={"activa": False},
    )

    return {"mensaje": "Promoción desactivada correctamente."}