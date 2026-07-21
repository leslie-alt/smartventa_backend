# respaldo_services.py
from datetime import datetime, timezone
from io import BytesIO
import json

import pandas as pd
from app.core.database import supabase


# Tablas que se incluyen en el respaldo, en el orden en que se exportan.
# No incluye usuarios, roles ni auditoria por seguridad / alcance.
_TABLAS_RESPALDO = [
    "categorias",
    "productos",
    "promociones",
    "inventario",
    "kardex",
    "clientes",
    "cajas",
    "turnos",
    "movimientos_caja",
    "ventas",
    "venta_articulos",
    "pagos",
]

# Columna usada para filtrar por sucursal en cada tabla. None = la tabla
# no tiene sucursal_id propia y se filtra indirectamente (ver _obtener_tabla).
_COLUMNA_SUCURSAL = {
    "categorias": "sucursal_id",
    "productos": "sucursal_id",
    "promociones": None,       # se relaciona vía producto_id -> productos.sucursal_id
    "inventario": "sucursal_id",
    "kardex": "sucursal_id",
    "clientes": "sucursal_id",
    "cajas": "sucursal_id",
    "turnos": None,            # se relaciona vía caja_id -> cajas.sucursal_id
    "movimientos_caja": "sucursal_id",
    "ventas": "sucursal_id",
    "venta_articulos": None,   # se relaciona vía venta_id -> ventas.sucursal_id
    "pagos": None,             # se relaciona vía venta_id -> ventas.sucursal_id
}

# Cache de IDs de la corrida actual, para resolver relaciones sin sucursal_id directa.
_cache_ids: dict[str, list[str]] = {}
def _en_lotes(items: list, tam: int = 100):
    """Parte una lista en trozos de tamaño `tam` para no exceder el
    límite de longitud de URL al usar .in_() con muchos IDs."""
    for i in range(0, len(items), tam):
        yield items[i:i + tam]


def _seleccionar_por_ids(tabla: str, columna: str, ids: list[str]) -> list[dict]:
    """Trae filas de `tabla` donde `columna` esté en `ids`, en lotes."""
    resultados: list[dict] = []
    for lote in _en_lotes(ids):
        respuesta = supabase.table(tabla).select("*").in_(columna, lote).execute()
        resultados.extend(respuesta.data or [])
    return resultados
def _seleccionar_todo(tabla: str, columna: str, valor: str, tam_pagina: int = 1000) -> list[dict]:
    """Trae TODAS las filas que cumplan columna=valor, paginando de tam_pagina
    en tam_pagina, porque Supabase limita cada consulta a 1000 filas por
    defecto aunque no se pida explícitamente."""
    resultados: list[dict] = []
    inicio = 0
    while True:
        fin = inicio + tam_pagina - 1
        respuesta = (
            supabase.table(tabla)
            .select("*")
            .eq(columna, valor)
            .range(inicio, fin)
            .execute()
        )
        lote = respuesta.data or []
        resultados.extend(lote)
        if len(lote) < tam_pagina:
            break
        inicio += tam_pagina
    return resultados
def _obtener_tabla(nombre: str, sucursal_id: str) -> list[dict]:
    """
    Trae todas las filas de una tabla para la sucursal dada.
    Si la tabla no tiene sucursal_id directa, filtra usando los IDs
    ya recolectados de sus tablas "padre" en este mismo respaldo.
    """
    columna = _COLUMNA_SUCURSAL[nombre]

    if columna:
        return _seleccionar_todo(nombre, columna, sucursal_id)

    # Casos especiales sin sucursal_id directa — en lotes para evitar
    # URLs demasiado largas cuando hay muchos IDs.
    if nombre == "promociones":
        productos = _cache_ids.get("productos", [])
        if not productos:
            return []
        return _seleccionar_por_ids("promociones", "producto_id", productos)

    if nombre == "turnos":
        cajas = _cache_ids.get("cajas", [])
        if not cajas:
            return []
        return _seleccionar_por_ids("turnos", "caja_id", cajas)

    if nombre in ("venta_articulos", "pagos"):
        ventas = _cache_ids.get("ventas", [])
        if not ventas:
            return []
        return _seleccionar_por_ids(nombre, "venta_id", ventas)

    return []

def _recolectar_datos(sucursal_id: str) -> dict[str, list[dict]]:
    """Recorre todas las tablas del respaldo, respetando dependencias."""
    global _cache_ids
    _cache_ids = {}
    datos: dict[str, list[dict]] = {}

    for tabla in _TABLAS_RESPALDO:
        filas = _obtener_tabla(tabla, sucursal_id)
        datos[tabla] = filas
        _cache_ids[tabla] = [f["id"] for f in filas if "id" in f]

    return datos


def _serializar(obj):
    """Convierte tipos no serializables (UUID, Decimal, datetime) a texto."""
    return json.loads(json.dumps(obj, default=str))


def generar_respaldo_json(sucursal_id: str) -> bytes:
    """Genera el respaldo completo como bytes de un archivo .json."""
    datos = _recolectar_datos(sucursal_id)
    paquete = {
        "metadata": {
            "sucursal_id": sucursal_id,
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "tablas": list(datos.keys()),
        },
        "datos": datos,
    }
    contenido = json.dumps(_serializar(paquete), indent=2, ensure_ascii=False)
    return contenido.encode("utf-8")


def generar_respaldo_excel(sucursal_id: str) -> bytes:
    """Genera el respaldo completo como bytes de un archivo .xlsx, una hoja por tabla."""
    datos = _recolectar_datos(sucursal_id)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for tabla, filas in datos.items():
            df = pd.DataFrame(_serializar(filas)) if filas else pd.DataFrame()
            nombre_hoja = tabla[:31]  # límite de Excel para nombres de hoja
            df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    return buffer.getvalue()