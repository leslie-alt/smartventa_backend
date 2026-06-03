from uuid import UUID
from supabase import Client
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto
from app.core.database import supabase
import pandas as pd
from io import BytesIO


# =============================================================
# HELPERS INTERNOS
# =============================================================

def _registrar_auditoria(
    usuario_id: str,
    sucursal_id: str,
    accion: str,
    registro_id: str,
    valores_anteriores: dict | None,
    valores_nuevos: dict | None,
):
    """Inserta un registro inmutable en la tabla auditoria."""
    supabase.table("auditoria").insert({
        "usuario_id": usuario_id,
        "sucursal_id": sucursal_id,
        "modulo": "productos",
        "accion": accion,
        "registro_id": registro_id,
        "valores_anteriores": valores_anteriores,
        "valores_nuevos": valores_nuevos,
    }).execute()


def _registrar_kardex_cambio_precio(
    producto_id: str,
    sucursal_id: str,
    usuario_id: str,
    costo_anterior: float,
    costo_nuevo: float,
    existencia_actual: int,
    notas: str | None = None,
):
    """
    Registra en kardex cuando cambia el precio/costo de un producto (RF-03.4).
    tipo_movimiento = 'cambio_precio'
    """
    supabase.table("kardex").insert({
        "producto_id": producto_id,
        "sucursal_id": sucursal_id,
        "usuario_id": usuario_id,
        "tipo_movimiento": "cambio_precio",
        "tipo_referencia": None,
        "cantidad_entrada": 0,
        "cantidad_salida": 0,
        "existencia_resultante": existencia_actual,
        "costo_unitario": costo_nuevo,
        "notas": notas or f"Cambio de costo: ${costo_anterior} → ${costo_nuevo}",
    }).execute()


def _obtener_existencia(producto_id: str, sucursal_id: str) -> int:
    """Retorna la existencia actual del producto en la sucursal."""
    resp = (
        supabase.table("inventario")
        .select("cantidad_actual")
        .eq("producto_id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    return resp.data["cantidad_actual"] if resp.data else 0


# =============================================================
# CRUD PRODUCTOS
# =============================================================

def obtener_productos(sucursal_id: str, solo_activos: bool = True) -> list[dict]:
    """
    Retorna todos los productos de la sucursal con su existencia actual.
    Incluye stock_bajo = True cuando cantidad_actual <= inventario_minimo (RF-01.6).
    """
    query = (
        supabase.table("productos")
        .select("*, inventario(cantidad_actual)")
        .eq("sucursal_id", sucursal_id)
    )
    if solo_activos:
        query = query.eq("activo", True)

    respuesta = query.order("descripcion").execute()
    productos = []

    for p in respuesta.data:
        inv = p.pop("inventario", None)
        cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
        p["cantidad_actual"] = cantidad_actual
        # RF-01.6: alerta si stock <= mínimo
        p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]
        productos.append(p)

    return productos


def obtener_producto_por_id(producto_id: str, sucursal_id: str) -> dict:
    """Retorna un producto por ID verificando que pertenezca a la sucursal."""
    respuesta = (
        supabase.table("productos")
        .select("*, inventario(cantidad_actual)")
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Producto")

    p = respuesta.data
    inv = p.pop("inventario", None)
    cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
    p["cantidad_actual"] = cantidad_actual
    p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]
    return p


def buscar_productos(
    sucursal_id: str,
    termino: str | None = None,
    categoria: str | None = None,
) -> list[dict]:
    """
    Búsqueda por código de barras, descripción o categoría (RF-01.3).
    Retorna productos activos con existencia actual.
    """
    query = (
        supabase.table("productos")
        .select("*, inventario(cantidad_actual)")
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
    )

    if termino:
        # Busca en código de barras o descripción
        query = query.or_(
            f"codigo_barras.ilike.%{termino}%,descripcion.ilike.%{termino}%"
        )
    if categoria:
        query = query.eq("categoria", categoria)

    respuesta = query.order("descripcion").execute()
    productos = []

    for p in respuesta.data:
        inv = p.pop("inventario", None)
        cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
        p["cantidad_actual"] = cantidad_actual
        p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]
        productos.append(p)

    return productos


def crear_producto(datos: dict, sucursal_id: str, usuario_id: str) -> dict:
    """
    Crea un producto y su registro de inventario inicial en 0.
    Genera registro en auditoría.
    """
    # Verificar código de barras único en la sucursal
    if datos.get("codigo_barras"):
        existente = (
            supabase.table("productos")
            .select("id")
            .eq("sucursal_id", sucursal_id)
            .eq("codigo_barras", datos["codigo_barras"])
            .execute()
        )
        if existente.data:
            raise ErrorConflicto("Ya existe un producto con ese código de barras en esta sucursal.")

    nuevo = {**datos, "sucursal_id": sucursal_id}
    respuesta = supabase.table("productos").insert(nuevo).execute()
    producto = respuesta.data[0]

    # Crear registro de inventario en 0
    supabase.table("inventario").insert({
        "producto_id": producto["id"],
        "sucursal_id": sucursal_id,
        "cantidad_actual": 0,
    }).execute()

    # Auditoría
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="crear_producto",
        registro_id=producto["id"],
        valores_anteriores=None,
        valores_nuevos=producto,
    )

    producto["cantidad_actual"] = 0
    producto["stock_bajo"] = 0 <= producto["inventario_minimo"]
    return producto


def actualizar_producto(
    producto_id: str,
    datos: dict,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Actualiza un producto. Si cambia costo_unitario genera registro en kardex.
    Si cambia precio genera registro en auditoría (RF-03.4, RF-13.3).
    """
    # Obtener estado actual
    anterior = obtener_producto_por_id(producto_id, sucursal_id)

    # Verificar código de barras único si se está cambiando
    if datos.get("codigo_barras") and datos["codigo_barras"] != anterior["codigo_barras"]:
        existente = (
            supabase.table("productos")
            .select("id")
            .eq("sucursal_id", sucursal_id)
            .eq("codigo_barras", datos["codigo_barras"])
            .neq("id", producto_id)
            .execute()
        )
        if existente.data:
            raise ErrorConflicto("Ya existe un producto con ese código de barras en esta sucursal.")

    respuesta = (
        supabase.table("productos")
        .update(datos)
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .execute()
    )
    actualizado = respuesta.data[0]

    # Kardex si cambió el costo unitario
    if "costo_unitario" in datos and datos["costo_unitario"] != anterior["costo_unitario"]:
        existencia = _obtener_existencia(producto_id, sucursal_id)
        _registrar_kardex_cambio_precio(
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            usuario_id=usuario_id,
            costo_anterior=float(anterior["costo_unitario"]),
            costo_nuevo=float(datos["costo_unitario"]),
            existencia_actual=existencia,
        )

    # Auditoría
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="actualizar_producto",
        registro_id=producto_id,
        valores_anteriores=anterior,
        valores_nuevos=actualizado,
    )

    actualizado["cantidad_actual"] = anterior["cantidad_actual"]
    actualizado["stock_bajo"] = anterior["cantidad_actual"] <= actualizado["inventario_minimo"]
    return actualizado


def cambiar_visibilidad(
    producto_id: str,
    sucursal_id: str,
    usuario_id: str,
    activo: bool,
) -> dict:
    """
    Activa o desactiva la visibilidad del producto (botón ojo).
    
    NOTA: Actualmente esto hace soft delete (activo=False oculta el producto
    de ventas y búsquedas). Si en el futuro se quiere separar
    "oculto en POS" de "eliminado", agregar columna 'visible_en_pos'
    a la tabla productos y cambiar la lógica aquí.
    """
    anterior = obtener_producto_por_id(producto_id, sucursal_id)

    respuesta = (
        supabase.table("productos")
        .update({"activo": activo})
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .execute()
    )
    actualizado = respuesta.data[0]

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="desactivar_producto" if not activo else "activar_producto",
        registro_id=producto_id,
        valores_anteriores={"activo": anterior["activo"]},
        valores_nuevos={"activo": activo},
    )

    return {"mensaje": f"Producto {'activado' if activo else 'desactivado'} correctamente."}


# =============================================================
# CATEGORÍAS
# =============================================================

def obtener_categorias(sucursal_id: str) -> list[dict]:
    """
    Retorna las categorías únicas del catálogo de productos de la sucursal.
    No tienen tabla propia; se extraen dinámicamente de productos.categoria.
    """
    respuesta = (
        supabase.table("productos")
        .select("categoria")
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
        .execute()
    )

    conteo: dict[str, int] = {}
    for p in respuesta.data:
        cat = p["categoria"] or "Sin categoría"
        conteo[cat] = conteo.get(cat, 0) + 1

    return [{"nombre": k, "total_productos": v} for k, v in sorted(conteo.items())]


# =============================================================
# EXPORTAR / IMPORTAR
# =============================================================

def exportar_productos_excel(sucursal_id: str) -> bytes:
    """
    Exporta el catálogo completo en formato Excel (RF-01.5).
    No incluye ruta_imagen (se agrega manualmente después de importar).
    """
    productos = obtener_productos(sucursal_id, solo_activos=False)

    columnas = [
        "codigo_barras", "descripcion", "categoria",
        "precio_venta", "precio_mayoreo", "costo_unitario",
        "inventario_minimo", "cantidad_actual",
    ]
    df = pd.DataFrame(productos)[columnas]
    df.columns = [
        "Código de Barras", "Descripción", "Categoría",
        "Precio Venta", "Precio Mayoreo", "Costo Unitario",
        "Inventario Mínimo", "Stock Actual",
    ]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Productos")
    return buffer.getvalue()


def importar_productos_excel(
    contenido: bytes,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Importa productos desde Excel o CSV (RF-01.5).
    Columnas requeridas: Código de Barras, Descripción, Categoría,
    Precio Venta, Precio Mayoreo, Costo Unitario, Inventario Mínimo.
    La imagen se agrega manualmente después.
    """
    try:
        df = pd.read_excel(BytesIO(contenido))
    except Exception:
        df = pd.read_csv(BytesIO(contenido))

    columnas_requeridas = {
        "Descripción", "Precio Venta", "Precio Mayoreo", "Costo Unitario"
    }
    if not columnas_requeridas.issubset(df.columns):
        return {
            "total_filas": 0,
            "importados": 0,
            "omitidos": 0,
            "errores": [f"Faltan columnas requeridas: {columnas_requeridas - set(df.columns)}"],
        }

    importados = 0
    omitidos = 0
    errores = []

    for i, fila in df.iterrows():
        try:
            codigo = str(fila.get("Código de Barras", "")).strip() or None

            # Omitir si ya existe ese código en la sucursal
            if codigo:
                existente = (
                    supabase.table("productos")
                    .select("id")
                    .eq("sucursal_id", sucursal_id)
                    .eq("codigo_barras", codigo)
                    .execute()
                )
                if existente.data:
                    omitidos += 1
                    errores.append(f"Fila {i+2}: código '{codigo}' ya existe, omitido.")
                    continue

            producto = {
                "sucursal_id": sucursal_id,
                "codigo_barras": codigo,
                "descripcion": str(fila["Descripción"]).strip(),
                "categoria": str(fila.get("Categoría", "")).strip() or None,
                "precio_venta": float(fila["Precio Venta"]),
                "precio_mayoreo": float(fila["Precio Mayoreo"]),
                "costo_unitario": float(fila["Costo Unitario"]),
                "inventario_minimo": int(fila.get("Inventario Mínimo", 0)),
            }

            resp = supabase.table("productos").insert(producto).execute()
            producto_id = resp.data[0]["id"]

            # Inventario inicial en 0
            supabase.table("inventario").insert({
                "producto_id": producto_id,
                "sucursal_id": sucursal_id,
                "cantidad_actual": 0,
            }).execute()

            importados += 1

        except Exception as e:
            omitidos += 1
            errores.append(f"Fila {i+2}: {str(e)}")

    # Auditoría del proceso completo
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="importar_productos",
        registro_id=sucursal_id,
        valores_anteriores=None,
        valores_nuevos={"importados": importados, "omitidos": omitidos},
    )

    return {
        "total_filas": len(df),
        "importados": importados,
        "omitidos": omitidos,
        "errores": errores,
    }