from uuid import UUID
from supabase import Client
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto
from app.core.database import supabase
import pandas as pd
from io import BytesIO
import json
from datetime import date


# =============================================================
# HELPERS INTERNOS
# =============================================================

def _serializar_para_json(obj: dict | None) -> dict | None:
    """Convierte UUIDs, fechas y otros tipos no serializables a strings."""
    if obj is None:
        return None
    return json.loads(json.dumps(obj, default=str))


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
        "valores_anteriores": _serializar_para_json(valores_anteriores),
        "valores_nuevos": _serializar_para_json(valores_nuevos),
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


def _obtener_o_crear_categoria(nombre: str, sucursal_id: str) -> str | None:
    """
    Busca una categoría por nombre en la sucursal.
    Si no existe, la crea y retorna su ID.
    Retorna None si el nombre está vacío.
    """
    if not nombre or not nombre.strip():
        return None

    nombre = nombre.strip()

    # Buscar existente
    existente = (
        supabase.table("categorias")
        .select("id")
        .eq("sucursal_id", sucursal_id)
        .eq("nombre", nombre)
        .execute()
    )
    if existente.data:
        return existente.data[0]["id"]

    # Crear nueva
    nueva = (
        supabase.table("categorias")
        .insert({"nombre": nombre, "sucursal_id": sucursal_id, "activo": True})
        .execute()
    )
    return nueva.data[0]["id"]


# =============================================================
# CRUD PRODUCTOS
# =============================================================

def obtener_productos(sucursal_id: str, solo_activos: bool = True) -> list[dict]:
    """
    Retorna todos los productos de la sucursal con su existencia actual
    y el nombre de su categoría.
    Incluye stock_bajo = True cuando cantidad_actual <= inventario_minimo (RF-01.6).
    """
    query = (
        supabase.table("productos")
        .select("*, inventario(cantidad_actual), categorias(nombre)")
        .eq("sucursal_id", sucursal_id)
    )
    if solo_activos:
        query = query.eq("activo", True)

    respuesta = query.order("descripcion").execute()
    productos = []

    for p in respuesta.data:
        inv = p.pop("inventario", None)
        cat = p.pop("categorias", None)
        cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
        p["cantidad_actual"] = cantidad_actual
        p["categoria_nombre"] = cat["nombre"] if cat else None
        p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]
        productos.append(p)

    return productos


def obtener_producto_por_id(producto_id: str, sucursal_id: str) -> dict:
    """Retorna un producto por ID verificando que pertenezca a la sucursal."""
    respuesta = (
        supabase.table("productos")
        .select("*, inventario(cantidad_actual), categorias(nombre)")
        .eq("id", producto_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Producto")

    p = respuesta.data
    inv = p.pop("inventario", None)
    cat = p.pop("categorias", None)
    cantidad_actual = inv[0]["cantidad_actual"] if inv else 0
    p["cantidad_actual"] = cantidad_actual
    p["categoria_nombre"] = cat["nombre"] if cat else None
    p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]
    return p


def buscar_productos(
    sucursal_id: str,
    termino: str | None = None,
    categoria: str | None = None,
    solo_con_stock: bool = False,
) -> list[dict]:
    """
    Búsqueda por código de barras, descripción o categoría (RF-01.3).
    Usado en POS y verificador de precios (RF-01.4).

    solo_con_stock=True oculta productos agotados — pensado para el
    catálogo del POS (RF-01.6 ya alerta sobre stock bajo, pero aquí
    directamente no se ofrecen productos sin existencia para vender).
    El verificador de precios debe seguir usando solo_con_stock=False
    para poder confirmar precio aunque esté agotado.
    """
    query = (
        supabase.table("productos")
        .select(
            "*, inventario(cantidad_actual), categorias(nombre), "
            "promociones(cantidad_minima, tipo_beneficio, valor_beneficio, activa, fecha_inicio)"
        )
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
    )

    if termino:
        query = query.or_(
            f"codigo_barras.ilike.%{termino}%,descripcion.ilike.%{termino}%"
        )
    if categoria:
        query = query.eq("categoria_id", categoria)

    respuesta = query.order("descripcion").range(0, 199).execute()
    productos = []
    hoy = date.today()

    for p in respuesta.data:
        inv = p.pop("inventario", None)
        cat = p.pop("categorias", None)
        cantidad_actual = inv[0]["cantidad_actual"] if inv else 0

        if solo_con_stock and cantidad_actual <= 0:
            continue

        p["cantidad_actual"] = cantidad_actual
        p["categoria_nombre"] = cat["nombre"] if cat else None
        p["stock_bajo"] = cantidad_actual <= p["inventario_minimo"]

        # Extraer promoción activa y vigente (RF-09.2: respeta fecha_inicio).
        # Se alinea con _promocion_aplicable() de ventas para que el precio
        # mostrado en el POS coincida con el que calcula el backend al cobrar.
        promos = p.pop("promociones", None) or []
        promo_activa = next(
            (pr for pr in promos
             if pr.get("activa")
             and (not pr.get("fecha_inicio")
                  or date.fromisoformat(str(pr["fecha_inicio"])) <= hoy)),
            None,
        )
        if promo_activa:
            es_precio_especial = promo_activa["tipo_beneficio"] == "precio_especial"
            p["precio_promo"] = float(promo_activa["valor_beneficio"]) if es_precio_especial else None
            p["porcentaje_promo"] = float(promo_activa["valor_beneficio"]) if not es_precio_especial else None
            p["cantidad_minima_promo"] = promo_activa["cantidad_minima"]
        else:
            p["precio_promo"] = None
            p["porcentaje_promo"] = None
            p["cantidad_minima_promo"] = None

        productos.append(p)

    return productos


def crear_producto(datos: dict, sucursal_id: str, usuario_id: str) -> dict:
    """
    Crea un producto. El trigger `crear_inventario_producto` se encarga
    de crear automáticamente el registro de inventario en 0.
    Si se especifica stock_inicial, se actualiza el inventario y se
    registra la entrada en kardex.
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

    # Extraer stock_inicial — no es columna de la tabla productos
    stock_inicial = datos.pop("stock_inicial", 0) or 0

    nuevo = {**datos, "sucursal_id": sucursal_id}
    respuesta = supabase.table("productos").insert(_serializar_para_json(nuevo)).execute()
    producto = respuesta.data[0]

    cantidad_actual = 0

    # Si se especificó stock inicial, actualizar inventario + kardex
    if stock_inicial > 0:
        supabase.table("inventario").update({
            "cantidad_actual": stock_inicial,
        }).eq("producto_id", producto["id"]).eq("sucursal_id", sucursal_id).execute()

        supabase.table("kardex").insert({
            "producto_id": producto["id"],
            "sucursal_id": sucursal_id,
            "usuario_id": usuario_id,
            "tipo_movimiento": "entrada_mercancia",
            "tipo_referencia": "entrada",
            "cantidad_entrada": stock_inicial,
            "cantidad_salida": 0,
            "existencia_resultante": stock_inicial,
            "costo_unitario": float(producto["costo_unitario"]),
            "notas": "Stock inicial al crear el producto",
        }).execute()

        cantidad_actual = stock_inicial

    # Auditoría
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="crear_producto",
        registro_id=producto["id"],
        valores_anteriores=None,
        valores_nuevos={**producto, "stock_inicial": stock_inicial},
    )

    producto["cantidad_actual"] = cantidad_actual
    producto["stock_bajo"] = cantidad_actual <= producto["inventario_minimo"]
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
        .update(_serializar_para_json(datos))
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
# EXPORTAR / IMPORTAR
# =============================================================

def exportar_productos_excel(sucursal_id: str, solo_plantilla: bool = False) -> bytes:
    """
    Exporta el catálogo en formato Excel (RF-01.5).
    Si solo_plantilla=True, exporta solo los encabezados (plantilla vacía).
    """
    if solo_plantilla:
        productos = []
    else:
        productos = obtener_productos(sucursal_id, solo_activos=False)

    # Construir filas con el nombre de la categoría (no el UUID)
    filas = [{
        "codigo_barras": p.get("codigo_barras"),
        "descripcion": p.get("descripcion"),
        "categoria": p.get("categoria_nombre"),
        "precio_venta": p.get("precio_venta"),
        "precio_mayoreo": p.get("precio_mayoreo"),
        "costo_unitario": p.get("costo_unitario"),
        "inventario_minimo": p.get("inventario_minimo"),
        "cantidad_actual": p.get("cantidad_actual"),
    } for p in productos]

    columnas = [
        "codigo_barras", "descripcion", "categoria",
        "precio_venta", "precio_mayoreo", "costo_unitario",
        "inventario_minimo", "cantidad_actual",
    ]
    df = pd.DataFrame(filas, columns=columnas)
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
    Importa productos desde Excel o CSV (RF-01.5) — versión optimizada.
    
    Optimizaciones:
        - Precarga de productos y categorías existentes (2 consultas iniciales)
        - Inserts en batches de 500 filas
        - Updates en batches de 500 filas
        - Categorías nuevas se crean en batch antes de procesar productos
    
    Columnas requeridas: Descripción, Precio Venta, Precio Mayoreo, Costo Unitario.
    Columnas opcionales: Código de Barras, Categoría, Inventario Mínimo.
    """
    BATCH_SIZE = 500

    # 1. Leer archivo
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
            "insertados": 0,
            "actualizados": 0,
            "omitidos": 0,
            "errores": [{
                "fila": 0,
                "motivo": f"Faltan columnas requeridas: {columnas_requeridas - set(df.columns)}",
            }],
        }

    # 2. Precarga: productos existentes en la sucursal {codigo_barras: id}
    productos_existentes = {}
    respuesta_prods = (
        supabase.table("productos")
        .select("id, codigo_barras")
        .eq("sucursal_id", sucursal_id)
        .execute()
    )
    for p in respuesta_prods.data:
        if p["codigo_barras"]:
            productos_existentes[p["codigo_barras"]] = p["id"]

    # 3. Precarga: categorías existentes en la sucursal {nombre_lowercase: id}
    categorias_existentes = {}
    respuesta_cats = (
        supabase.table("categorias")
        .select("id, nombre")
        .eq("sucursal_id", sucursal_id)
        .execute()
    )
    for c in respuesta_cats.data:
        categorias_existentes[c["nombre"].strip().lower()] = c["id"]

    # 4. Primera pasada: identificar categorías nuevas que hay que crear
    nombres_categorias_nuevas = set()
    for _, fila in df.iterrows():
        nombre_cat = str(fila.get("Categoría", "")).strip()
        if nombre_cat and nombre_cat.lower() not in categorias_existentes:
            nombres_categorias_nuevas.add(nombre_cat)

    # Crear categorías nuevas en batch
    if nombres_categorias_nuevas:
        nuevas_cats = [
            {"nombre": n, "sucursal_id": sucursal_id, "activo": True}
            for n in nombres_categorias_nuevas
        ]
        resultado = supabase.table("categorias").insert(nuevas_cats).execute()
        for c in resultado.data:
            categorias_existentes[c["nombre"].strip().lower()] = c["id"]

    # 5. Segunda pasada: clasificar filas en insertar / actualizar / error
    insertar_lote: list[dict] = []
    actualizar_lote: list[dict] = []  # cada item: {"id": ..., "datos": {...}}
    omitidos = 0
    errores: list[dict] = []

    for i, fila in df.iterrows():
        numero_fila = int(i) + 2

        try:
            codigo = str(fila.get("Código de Barras", "")).strip() or None
            if codigo and codigo.lower() == "nan":
                codigo = None

            descripcion = str(fila["Descripción"]).strip()
            if not descripcion or descripcion.lower() == "nan":
                omitidos += 1
                errores.append({"fila": numero_fila, "motivo": "Descripción vacía."})
                continue

            # Resolver categoría (ya están precargadas)
            nombre_cat = str(fila.get("Categoría", "")).strip()
            categoria_id = (
                categorias_existentes.get(nombre_cat.lower())
                if nombre_cat else None
            )

            datos_producto = {
                "descripcion": descripcion,
                "categoria_id": categoria_id,
                "precio_venta": float(fila["Precio Venta"]),
                "precio_mayoreo": float(fila["Precio Mayoreo"]),
                "costo_unitario": float(fila["Costo Unitario"]),
                "inventario_minimo": int(fila.get("Inventario Mínimo", 0) or 0),
            }

            # ¿Existe por código de barras?
            if codigo and codigo in productos_existentes:
                actualizar_lote.append({
                    "id": productos_existentes[codigo],
                    "datos": datos_producto,
                })
            else:
                datos_producto["codigo_barras"] = codigo
                datos_producto["sucursal_id"] = sucursal_id
                insertar_lote.append(datos_producto)

        except Exception as e:
            omitidos += 1
            errores.append({"fila": numero_fila, "motivo": str(e)})

    # 6. Ejecutar INSERTS en batches
    insertados = 0
    for inicio in range(0, len(insertar_lote), BATCH_SIZE):
        batch = insertar_lote[inicio:inicio + BATCH_SIZE]
        try:
            resultado = supabase.table("productos").insert(batch).execute()
            insertados += len(resultado.data)
        except Exception as e:
            # Si el batch entero falla, registrar error genérico
            errores.append({
                "fila": 0,
                "motivo": f"Error al insertar lote (filas {inicio + 1}-{inicio + len(batch)}): {str(e)}",
            })
            omitidos += len(batch)

    # 7. Ejecutar UPDATES (uno por uno, Supabase no soporta update masivo con distintos valores)
    actualizados = 0
    for item in actualizar_lote:
        try:
            supabase.table("productos").update(item["datos"]).eq(
                "id", item["id"]
            ).execute()
            actualizados += 1
        except Exception as e:
            omitidos += 1
            errores.append({
                "fila": 0,
                "motivo": f"Error al actualizar producto {item['id']}: {str(e)}",
            })

    # 8. Auditoría del proceso completo
    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="importar_productos",
        registro_id=sucursal_id,
        valores_anteriores=None,
        valores_nuevos={
            "insertados": insertados,
            "actualizados": actualizados,
            "omitidos": omitidos,
            "total_filas": len(df),
        },
    )

    return {
        "total_filas": len(df),
        "insertados": insertados,
        "actualizados": actualizados,
        "omitidos": omitidos,
        "errores": errores[:100],  # Limitar a 100 errores para no saturar la UI
    }

def obtener_categorias(sucursal_id: str) -> list[dict]:
    """
    Retorna las categorías únicas usadas en productos de la sucursal,
    para el filtro de categoría en el catálogo.
    """
    respuesta = (
        supabase.table("categorias")
        .select("id, nombre, sucursal_id, activo, creado_en")
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
        .order("nombre")
        .execute()
    )
    return respuesta.data