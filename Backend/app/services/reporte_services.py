# reporte_services.py
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException

from app.core.database import supabase


def _rango_fechas(fecha_inicio_str: str, fecha_fin_str: str):
    """Convierte fecha_inicio y fecha_fin (AAAA-MM-DD, día completo en hora
    México) a un rango UTC [inicio, fin) para filtrar por creado_en."""
    try:
        d_inicio = date.fromisoformat(fecha_inicio_str)
        d_fin = date.fromisoformat(fecha_fin_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas. Usa formato AAAA-MM-DD.")

    tz_mexico = ZoneInfo("America/Mexico_City")
    inicio_mx = datetime(d_inicio.year, d_inicio.month, d_inicio.day, 0, 0, 0, tzinfo=tz_mexico)
    fin_mx = datetime(d_fin.year, d_fin.month, d_fin.day, 0, 0, 0, tzinfo=tz_mexico) + timedelta(days=1)

    inicio_utc = inicio_mx.astimezone(ZoneInfo("UTC")).isoformat()
    fin_utc = fin_mx.astimezone(ZoneInfo("UTC")).isoformat()
    return inicio_utc, fin_utc


def reporte_ventas(sucursal_id: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """
    Reporte de ventas del periodo para una sucursal: totales, desglose por
    día, por método de pago, por cajero y por turno. Solo ventas completadas.
    """
    inicio, fin = _rango_fechas(fecha_inicio, fecha_fin)

    ventas = (
        supabase.table("ventas")
        .select(
            "id, total, creado_en, metodo_pago_principal, turno_id, "
            "usuarios!ventas_usuario_id_fkey(nombre_completo)"
        )
        .eq("sucursal_id", sucursal_id)
        .eq("estado", "completada")
        .gte("creado_en", inicio)
        .lt("creado_en", fin)
        .execute()
    ).data or []

    # Totales generales
    total_ventas = sum(float(v["total"] or 0) for v in ventas)
    total_tickets = len(ventas)
    ticket_promedio = total_ventas / total_tickets if total_tickets > 0 else 0.0

    # Ventas por día (hora México, para que la gráfica agrupe correctamente)
    tz_mexico = ZoneInfo("America/Mexico_City")
    por_dia: dict[str, float] = {}
    for v in ventas:
        fecha_local = datetime.fromisoformat(v["creado_en"]).astimezone(tz_mexico).date().isoformat()
        por_dia[fecha_local] = por_dia.get(fecha_local, 0.0) + float(v["total"] or 0)
    ventas_por_dia = [{"fecha": f, "total": round(t, 2)} for f, t in sorted(por_dia.items())]

    # Por método de pago
    por_metodo = {"efectivo": 0.0, "tarjeta": 0.0, "transferencia": 0.0, "cheque": 0.0, "mixto": 0.0}
    for v in ventas:
        metodo = v["metodo_pago_principal"]
        if metodo in por_metodo:
            por_metodo[metodo] += float(v["total"] or 0)
    por_metodo = {k: round(v, 2) for k, v in por_metodo.items()}

    # Por cajero
    por_cajero: dict[str, dict] = {}
    for v in ventas:
        usuario = v.get("usuarios") or {}
        nombre = usuario.get("nombre_completo") or "Sin asignar"
        if nombre not in por_cajero:
            por_cajero[nombre] = {"nombre": nombre, "tickets": 0, "total": 0.0}
        por_cajero[nombre]["tickets"] += 1
        por_cajero[nombre]["total"] += float(v["total"] or 0)
    cajeros = sorted(
        [{"nombre": c["nombre"], "tickets": c["tickets"], "total": round(c["total"], 2)} for c in por_cajero.values()],
        key=lambda c: c["total"],
        reverse=True,
    )

    # Turnos de la sucursal en el rango (vía cajas, porque turnos no tiene sucursal_id)
    turnos = (
        supabase.table("turnos")
        .select("id, inicio, cierre, estado, cajas!inner(nombre, sucursal_id)")
        .eq("cajas.sucursal_id", sucursal_id)
        .gte("inicio", inicio)
        .lt("inicio", fin)
        .order("inicio", desc=True)
        .limit(10)
        .execute()
    ).data or []

    turnos_con_ventas = []
    for t in turnos:
        ventas_turno = [v for v in ventas if v["turno_id"] == t["id"]]
        if not ventas_turno:
            continue
        turnos_con_ventas.append({
            "caja_nombre": (t.get("cajas") or {}).get("nombre", "—"),
            "inicio": t["inicio"],
            "estado": t["estado"],
            "tickets": len(ventas_turno),
            "total": round(sum(float(v["total"] or 0) for v in ventas_turno), 2),
        })

    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_ventas": round(total_ventas, 2),
        "total_tickets": total_tickets,
        "ticket_promedio": round(ticket_promedio, 2),
        "ventas_por_dia": ventas_por_dia,
        "por_metodo": por_metodo,
        "cajeros": cajeros,
        "turnos": turnos_con_ventas,
    }