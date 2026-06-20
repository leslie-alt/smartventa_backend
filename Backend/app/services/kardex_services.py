from datetime import date
from uuid import UUID

from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado


def buscar_productos_kardex(
    sucursal_id: str,
    termino: str,
) -> list[dict]:
    """
    Buscador de productos en la pantalla de kardex (RF-03.5).
    Busca por código de barras o descripción.
    """
    if not termino or len(termino.strip()) < 2:
        return []

    respuesta = (
        supabase.table("productos")
        .select("id, codigo_barras, descripcion, inventario(cantidad_actual)")
        .eq("sucursal_id", sucursal_id)
        .or_(f"codigo_barras.ilike.%{termino}%,descripcion.ilike.%{termino}%")
        .order("descripcion")
        .limit(20)
        .execute()
    )

    resultados = []
    for p in respuesta.data:
        inv = p.pop("inventario", None)
        resultados.append({
            "id": p["id"],
            "codigo_barras": p["codigo_barras"],
            "descripcion": p["descripcion"],
            "cantidad_actual": inv[0]["cantidad_actual"] if inv else 0,
        })

    return resultados


def consultar_kardex(
    
    producto_id: str,
    sucursal_id: str,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    tipo_movimiento: str | None = None,
    caja_id: str | None = None,
    usuario_id: str | None = None,
) -> dict:
    """
    Consulta el kardex de un producto con filtros opcionales (RF-03.5).
    Retorna encabezado + lista cronológica de movimientos.
    """
    # 1. Encabezado: datos del producto + inventario
    producto = (
        supabase.table("productos")
        .select(
            "id, codigo_barras, descripcion, costo_unitario, precio_venta, "
            "inventario_minimo, ruta_imagen, "
            "categorias(nombre), inventario(cantidad_actual)"
        )
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not producto.data:
        raise ErrorNoEncontrado("Producto")

    p = producto.data
    inv = p.pop("inventario", None)
    cat = p.pop("categorias", None)
    existencia_actual = inv[0]["cantidad_actual"] if inv else 0

    encabezado = {
        "producto_id": p["id"],
        "codigo_barras": p["codigo_barras"],
        "descripcion": p["descripcion"],
        "categoria_nombre": cat["nombre"] if cat else None,
        "existencia_actual": existencia_actual,
        "inventario_minimo": p["inventario_minimo"],
        "costo_unitario": p["costo_unitario"],
        "precio_venta": p["precio_venta"],
        "ruta_imagen": p["ruta_imagen"],
        "stock_bajo": existencia_actual <= p["inventario_minimo"],
    }


    # 2. Movimientos con filtros
    query = (
        supabase.table("kardex")
        .select(
            "id, fecha_hora, tipo_movimiento, cantidad_entrada, cantidad_salida, "
            "existencia_resultante, costo_unitario, referencia_id, tipo_referencia, "
            "notas, caja_id, usuario_id, "
            "usuarios(nombre_completo), "
            "cajas(nombre)"
        )
        .eq("producto_id", producto_id)
        .eq("sucursal_id", sucursal_id)
    )

    if fecha_desde:
        query = query.gte("fecha_hora", str(fecha_desde))
    if fecha_hasta:
        query = query.lte("fecha_hora", f"{fecha_hasta} 23:59:59")
    if tipo_movimiento:
        query = query.eq("tipo_movimiento", tipo_movimiento)
    if caja_id:
        query = query.eq("caja_id", caja_id)
    if usuario_id:
        query = query.eq("usuario_id", usuario_id)

    respuesta = query.order("fecha_hora", desc=True).execute()

    movimientos = []
    for m in respuesta.data:
        usuario_data = m.pop("usuarios", None)
        caja_data = m.pop("cajas", None)
        movimientos.append({
            **m,
            "usuario_nombre": usuario_data["nombre_completo"] if usuario_data else "—",
            "caja_nombre": caja_data["nombre"] if caja_data else None,
        })

    return {
        "encabezado": encabezado,
        "total_movimientos": len(movimientos),
        "movimientos": movimientos,
    }