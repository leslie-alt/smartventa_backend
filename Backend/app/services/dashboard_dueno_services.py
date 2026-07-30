"""Servicio del dashboard de la dueña. Único módulo donde el sucursal_id
NO sale forzosamente del token (RF-14.2). El consolidado se construye
fusionando en Python los resultados por sucursal, para no gastar una
llamada extra a Supabase calculando el total aparte (RNF-02, minimizar
llamadas)."""

from collections import defaultdict

from app.core.database import supabase
from app.models.dashboard_dueno_model import ResumenDueno, ResumenSucursal

CAMPOS_SUMABLES = [
    "dinero_actual", "ventas_bruto", "descuentos_total", "ventas_neto",
    "ventas_cantidad", "ganancia", "entradas", "salidas",
    "devoluciones_total", "devoluciones_cantidad", "canceladas_cantidad",
    "alertas_inventario_cantidad", "venta_semana_pasada",
]


def _llamar_rpc_resumen(sucursal_id: str, fecha: str) -> dict:
    resultado = supabase.rpc(
        "calcular_resumen_dueno",
        {"p_sucursal_id": sucursal_id, "p_fecha": fecha},
    ).execute()
    return resultado.data or {}


def _fusionar_metodos_pago(lista_de_listas: list[list[dict]]) -> list[dict]:
    totales: dict[str, float] = defaultdict(float)
    for lista in lista_de_listas:
        for m in lista:
            totales[m["metodo"]] += m["total"]
    return [{"metodo": k, "total": v} for k, v in totales.items()]


def _fusionar_ventas_por_hora(lista_de_listas: list[list[dict]]) -> list[dict]:
    totales: dict[int, dict] = defaultdict(lambda: {"total": 0.0, "cantidad": 0})
    for lista in lista_de_listas:
        for h in lista:
            totales[h["hora"]]["total"] += h["total"]
            totales[h["hora"]]["cantidad"] += h["cantidad"]
    return [
        {"hora": h, "total": v["total"], "cantidad": v["cantidad"]}
        for h, v in sorted(totales.items())
    ]


def _fusionar_top_productos(lista_de_listas: list[list[dict]]) -> list[dict]:
    totales: dict[str, dict] = {}
    for lista in lista_de_listas:
        for p in lista:
            acc = totales.setdefault(p["producto_id"], {
                "producto_id": p["producto_id"], "nombre": p["nombre"],
                "cantidad_vendida": 0, "ganancia": 0.0,
            })
            acc["cantidad_vendida"] += p["cantidad_vendida"]
            acc["ganancia"] += p["ganancia"]
    return sorted(totales.values(), key=lambda p: p["cantidad_vendida"], reverse=True)[:10]


def _fusionar_alertas(lista_de_listas: list[list[dict]]) -> list[dict]:
    combinadas = [a for lista in lista_de_listas for a in lista]
    return sorted(combinadas, key=lambda a: a["cantidad_actual"])[:10]


def obtener_resumen_dueno(fecha: str) -> ResumenDueno:
    sucursales_resp = (
        supabase.table("sucursales").select("id, nombre").eq("activa", True).execute()
    )
    sucursales = sucursales_resp.data or []

    resultados_por_sucursal: list[ResumenSucursal] = []
    datos_crudos: list[dict] = []

    for s in sucursales:
        datos = _llamar_rpc_resumen(s["id"], fecha)
        datos_crudos.append(datos)
        resultados_por_sucursal.append(
            ResumenSucursal(sucursal_id=s["id"], sucursal_nombre=s["nombre"], **datos)
        )

    # Consolidado: sumar campos numéricos y fusionar listas
    consolidado_dict = {campo: sum(d[campo] for d in datos_crudos) for campo in CAMPOS_SUMABLES}
    consolidado_dict["ticket_promedio"] = (
        consolidado_dict["ventas_neto"] / consolidado_dict["ventas_cantidad"]
        if consolidado_dict["ventas_cantidad"] > 0 else 0
    )
    consolidado_dict["margen_porcentaje"] = (
        (consolidado_dict["ganancia"] / consolidado_dict["ventas_neto"]) * 100
        if consolidado_dict["ventas_neto"] > 0 else 0
    )
    consolidado_dict["metodos_pago"] = _fusionar_metodos_pago([d["metodos_pago"] for d in datos_crudos])
    consolidado_dict["ventas_por_hora"] = _fusionar_ventas_por_hora([d["ventas_por_hora"] for d in datos_crudos])
    consolidado_dict["top_productos"] = _fusionar_top_productos([d["top_productos"] for d in datos_crudos])
    consolidado_dict["alertas_inventario"] = _fusionar_alertas([d["alertas_inventario"] for d in datos_crudos])

    consolidado = ResumenSucursal(
        sucursal_id="00000000-0000-0000-0000-000000000000",
        sucursal_nombre="Todas las sucursales",
        **consolidado_dict,
    )

    return ResumenDueno(consolidado=consolidado, sucursales=resultados_por_sucursal)


def listar_ventas_dia(sucursal_id: str | None, fecha: str) -> dict:
    """Todas las ventas completadas del día (hora local de México), con
    desglose por sucursal cuando se consulta en modo consolidado.

    creado_en se guarda en UTC (timestamp without time zone). El día
    'fecha' que llega es una fecha local de México (UTC-6), así que el
    rango de comparación se recorre 6 horas hacia adelante para que
    coincida con el día real que vivió el cajero, no con el día UTC."""
    from datetime import datetime, timedelta

    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
    inicio_utc = (fecha_dt + timedelta(hours=6)).isoformat()
    fin_utc = (fecha_dt + timedelta(days=1, hours=6)).isoformat()

    query = (
        supabase.table("ventas")
        .select("id, folio, total, metodo_pago_principal, creado_en, sucursal_id, sucursales(nombre)")
        .eq("estado", "completada")
        .gte("creado_en", inicio_utc)
        .lt("creado_en", fin_utc)
        .order("creado_en", desc=True)
    )
    if sucursal_id:
        query = query.eq("sucursal_id", sucursal_id)

    resultado = query.execute()
    ventas = []
    for v in (resultado.data or []):
        suc = v.pop("sucursales", None)
        v["sucursal_nombre"] = suc.get("nombre") if suc else None
        ventas.append(v)
    return {"items": ventas, "total": len(ventas)}


def obtener_detalle_venta(venta_id: str) -> dict:
    """Desglose de artículos de una venta específica, para el panel
    flotante de la pantalla 'Ventas del día'."""
    resultado = (
        supabase.table("venta_articulos")
        .select("cantidad, precio_unitario, descuento, cantidad_devuelta, productos(descripcion)")
        .eq("venta_id", venta_id)
        .execute()
    )
    articulos = []
    for a in (resultado.data or []):
        prod = a.pop("productos", None)
        a["nombre"] = prod.get("descripcion") if prod else "Producto eliminado"
        articulos.append(a)
    return {"venta_id": venta_id, "articulos": articulos}


def listar_productos_faltantes(sucursal_id: str | None) -> dict:
    """Lista COMPLETA (sin límite) de productos en o bajo su mínimo,
    para la pantalla dedicada — distinta del preview de 5 en el resumen."""
    resultado = supabase.rpc(
        "listar_productos_faltantes", {"p_sucursal_id": sucursal_id}
    ).execute()
    items = resultado.data or []
    return {"items": items, "total": len(items)}