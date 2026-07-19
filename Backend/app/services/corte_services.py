# corte_services.py
from fastapi import HTTPException
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from app.core.database import supabase


def _rango_dia(fecha_str: str):
    """Devuelve inicio y fin del día (hora México) convertidos a UTC, para filtrar por creado_en."""
    try:
        d = date.fromisoformat(fecha_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa formato AAAA-MM-DD.")

    tz_mexico = ZoneInfo("America/Mexico_City")
    inicio_mx = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz_mexico)
    fin_mx    = inicio_mx + timedelta(days=1)

    inicio_utc = inicio_mx.astimezone(ZoneInfo("UTC")).isoformat()
    fin_utc    = fin_mx.astimezone(ZoneInfo("UTC")).isoformat()
    return inicio_utc, fin_utc


def corte_por_caja_dia(caja_id: str, sucursal_id: str, fecha: str) -> dict:
    """
    Calcula el corte de una caja en un día específico (al vuelo, desde las ventas).
    No depende de la tabla 'cortes'. Solo cuenta ventas completadas.
    """
    inicio, fin = _rango_dia(fecha)

    # 1. Ventas completadas de esa caja en ese día
    ventas = (
        supabase.table("ventas")
        .select("id, total, estado, metodo_pago_principal, creado_en")
        .eq("sucursal_id", sucursal_id)
        .eq("caja_id", caja_id)
        .gte("creado_en", inicio)
        .lt("creado_en", fin)
        .execute()
    ).data or []

    completadas = [v for v in ventas if v["estado"] == "completada"]
    canceladas  = [v for v in ventas if v["estado"] == "cancelada"]

    ids_completadas = [v["id"] for v in completadas]

    # 2. Pagos de esas ventas (soporta pago mixto)
    totales_metodo = {
        "efectivo": 0.0, "tarjeta": 0.0,
        "transferencia": 0.0, "cheque": 0.0, "mixto": 0.0,
    }
    efectivo_neto = 0.0  # efectivo real en caja (monto - cambio)

    if ids_completadas:
        pagos = (
            supabase.table("pagos")
            .select("venta_id, metodo, monto, cambio")
            .in_("venta_id", ids_completadas)
            .execute()
        ).data or []

        for p in pagos:
            metodo = p["metodo"]
            monto  = float(p["monto"] or 0)
            cambio = float(p["cambio"] or 0)
            if metodo in totales_metodo:
                totales_metodo[metodo] += monto
            else:
                totales_metodo["mixto"] += monto
            if metodo == "efectivo":
                efectivo_neto += (monto - cambio)

    # 3. Turnos de esa caja en ese día → fondo y movimientos
    turnos = (
        supabase.table("turnos")
        .select("id, inicio")
        .eq("caja_id", caja_id)
        .gte("inicio", inicio)
        .lt("inicio", fin)
        .execute()
    ).data or []

    fondo_inicial = 0.0
    entradas_efectivo = 0.0
    salidas_efectivo = 0.0

    ids_turnos = [t["id"] for t in turnos]
    if ids_turnos:
        movimientos = (
            supabase.table("movimientos_caja")
            .select("turno_id, tipo_movimiento, monto, registrado_en")
            .in_("turno_id", ids_turnos)
            .order("registrado_en")
            .execute()
        ).data or []

        por_turno: dict[str, list[dict]] = {}
        for m in movimientos:
            por_turno.setdefault(m["turno_id"], []).append(m)

        for movs_turno in por_turno.values():
            entradas = [m for m in movs_turno if m["tipo_movimiento"] == "entrada"]
            salidas  = [m for m in movs_turno if m["tipo_movimiento"] == "salida"]

            if entradas:
                fondo_inicial += float(entradas[0]["monto"] or 0)
                entradas_efectivo += sum(float(m["monto"] or 0) for m in entradas[1:])

            salidas_efectivo += sum(float(m["monto"] or 0) for m in salidas)

    # 4. Efectivo esperado en caja
    efectivo_esperado = fondo_inicial + efectivo_neto + entradas_efectivo - salidas_efectivo

    total_general = sum(float(v["total"] or 0) for v in completadas)

    return {
        "fecha": fecha,
        "caja_id": caja_id,
        "num_tickets": len(completadas),
        "num_canceladas": len(canceladas),
        "total_general": round(total_general, 2),
        "totales_metodo": {k: round(v, 2) for k, v in totales_metodo.items()},
        "caja": {
            "fondo_inicial": round(fondo_inicial, 2),
            "ventas_efectivo": round(totales_metodo["efectivo"], 2),
            "efectivo_neto": round(efectivo_neto, 2),
            "entradas": round(entradas_efectivo, 2),
            "salidas": round(salidas_efectivo, 2),
            "efectivo_esperado": round(efectivo_esperado, 2),
        },
        "num_turnos": len(turnos),
    }