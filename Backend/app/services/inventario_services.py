from datetime import datetime, timezone
from uuid import UUID

from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado


# =============================================================
# HELPERS
# =============================================================

def _registrar_auditoria(
    usuario_id: str,
    sucursal_id: str,
    accion: str,
    registro_id: str,
    valores_anteriores: dict | None,
    valores_nuevos: dict | None,
):
    """Inserta un registro inmutable en auditoría."""
    supabase.table("auditoria").insert({
        "usuario_id": usuario_id,
        "sucursal_id": sucursal_id,
        "modulo": "inventario",
        "accion": accion,
        "registro_id": registro_id,
        "valores_anteriores": valores_anteriores,
        "valores_nuevos": valores_nuevos,
    }).execute()


def _obtener_inventario(producto_id: str, sucursal_id: str) -> dict:
    """Obtiene el registro de inventario + costo del producto."""
    inv = (
        supabase.table("inventario")
        .select("id, cantidad_actual, productos(costo_unitario, activo)")
        .eq("producto_id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not inv.data:
        raise ErrorNoEncontrado("Inventario del producto")
    return inv.data


# =============================================================
# ENTRADAS DE MERCANCÍA (RF-02.3)
# =============================================================

def registrar_entrada(
    datos: dict,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Registra una entrada de mercancía (RF-02.3).
    Incrementa el inventario y deja registro en kardex.
    """
    producto_id = str(datos["producto_id"])
    cantidad = datos["cantidad"]
    notas = datos.get("notas")

    inv = _obtener_inventario(producto_id, sucursal_id)
    cantidad_anterior = inv["cantidad_actual"]
    costo_unitario = float(inv["productos"]["costo_unitario"])
    cantidad_nueva = cantidad_anterior + cantidad

    # Actualizar inventario
    supabase.table("inventario").update({
        "cantidad_actual": cantidad_nueva,
        "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
    }).eq("producto_id", producto_id).eq("sucursal_id", sucursal_id).execute()

    # Kardex
    supabase.table("kardex").insert({
        "producto_id": producto_id,
        "sucursal_id": sucursal_id,
        "usuario_id": usuario_id,
        "tipo_movimiento": "entrada_mercancia",
        "tipo_referencia": "entrada",
        "cantidad_entrada": cantidad,
        "cantidad_salida": 0,
        "existencia_resultante": cantidad_nueva,
        "costo_unitario": costo_unitario,
        "notas": notas,
    }).execute()

    # Auditoría
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="entrada_mercancia",
        registro_id=producto_id,
        valores_anteriores={"cantidad_actual": cantidad_anterior},
        valores_nuevos={"cantidad_actual": cantidad_nueva, "entrada": cantidad, "notas": notas},
    )

    return {
        "mensaje": f"Entrada de {cantidad} unidades registrada correctamente.",
        "cantidad_anterior": cantidad_anterior,
        "cantidad_nueva": cantidad_nueva,
    }


# =============================================================
# AJUSTES DE INVENTARIO (RF-02.4)
# =============================================================

def ajustar_inventario(
    datos: dict,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Ajusta el inventario a una cantidad real contada.
    Calcula la diferencia contra el stock actual y genera
    UN solo movimiento en kardex si hay diferencia (RF-02.4).
    """
    producto_id = str(datos["producto_id"])
    nueva_cantidad = datos["nueva_cantidad"]
    motivo = datos["motivo"]

    inv = _obtener_inventario(producto_id, sucursal_id)
    cantidad_anterior = inv["cantidad_actual"]
    costo_unitario = float(inv["productos"]["costo_unitario"])
    diferencia = nueva_cantidad - cantidad_anterior

    # Sin cambios
    if diferencia == 0:
        return {
            "mensaje": "Sin cambios. La cantidad ingresada es igual al stock actual.",
            "cantidad_actual": cantidad_anterior,
        }

    # Actualizar inventario
    supabase.table("inventario").update({
        "cantidad_actual": nueva_cantidad,
        "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
    }).eq("producto_id", producto_id).eq("sucursal_id", sucursal_id).execute()

    # Un solo movimiento en kardex según signo
    supabase.table("kardex").insert({
        "producto_id": producto_id,
        "sucursal_id": sucursal_id,
        "usuario_id": usuario_id,
        "tipo_movimiento": "ajuste_inventario",
        "tipo_referencia": "ajuste",
        "cantidad_entrada": diferencia if diferencia > 0 else 0,
        "cantidad_salida": abs(diferencia) if diferencia < 0 else 0,
        "existencia_resultante": nueva_cantidad,
        "costo_unitario": costo_unitario,
        "notas": motivo,
    }).execute()

    # Auditoría
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="ajuste_inventario",
        registro_id=producto_id,
        valores_anteriores={"cantidad_actual": cantidad_anterior},
        valores_nuevos={"cantidad_actual": nueva_cantidad, "motivo": motivo},
    )

    return {
        "mensaje": f"Inventario ajustado correctamente. "
                   f"{'Entrada' if diferencia > 0 else 'Salida'} de {abs(diferencia)} unidades.",
        "cantidad_anterior": cantidad_anterior,
        "cantidad_nueva": nueva_cantidad,
        "diferencia": diferencia,
        "tipo": "entrada" if diferencia > 0 else "salida",
    }


# =============================================================
# LISTADO DE INVENTARIO (pantalla principal)
# =============================================================

def listar_inventario(
    sucursal_id: str,
    termino: str | None = None,
    categoria_id: str | None = None,
    solo_stock_bajo: bool = False,
) -> dict:
    """
    Retorna el listado de productos con su existencia actual.
    Incluye filtros por código/descripción y categoría.
    Calcula el resumen para las tarjetas superiores (RF-01.6).
    """
    query = (
        supabase.table("productos")
        .select(
            "id, codigo_barras, descripcion, categoria_id, inventario_minimo, "
            "ruta_imagen, activo, "
            "categorias(nombre), "
            "inventario(cantidad_actual)"
        )
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
    )

    if termino:
        query = query.or_(
            f"codigo_barras.ilike.%{termino}%,descripcion.ilike.%{termino}%"
        )
    if categoria_id:
        query = query.eq("categoria_id", categoria_id)

    respuesta = query.order("descripcion").execute()

    items = []
    productos_stock_bajo = 0

    for p in respuesta.data:
        inv = p.pop("inventario", None)
        cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
        stock_bajo = cantidad_actual <= p["inventario_minimo"]

        if stock_bajo:
            productos_stock_bajo += 1

        # Filtro adicional: solo stock bajo
        if solo_stock_bajo and not stock_bajo:
            continue

        cat = p.pop("categorias", None)
        items.append({
            "producto_id": p["id"],
            "codigo_barras": p["codigo_barras"],
            "descripcion": p["descripcion"],
            "categoria_nombre": cat["nombre"] if cat else None,
            "cantidad_actual": cantidad_actual,
            "inventario_minimo": p["inventario_minimo"],
            "stock_bajo": stock_bajo,
            "ruta_imagen": p["ruta_imagen"],
            "activo": p["activo"],
        })

    return {
        "resumen": {
            "productos_activos": len(respuesta.data),
            "productos_stock_bajo": productos_stock_bajo,
        },
        "total": len(items),
        "items": items,
    }