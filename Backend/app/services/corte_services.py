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
    Incluye el detalle de cada turno (abierto/cerrado) de esa caja en el día,
    con sus propios totales (para el desglose por turno, distinto del
    desglose por caja).
    """
    inicio, fin = _rango_dia(fecha)

    # 1. Ventas completadas de esa caja en ese día
    ventas = (
        supabase.table("ventas")
        .select("id, total, estado, metodo_pago_principal, creado_en, turno_id")
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

    # Mapa venta_id -> turno_id, para poder atribuir cada pago a su turno
    turno_por_venta = {v["id"]: v.get("turno_id") for v in completadas}

    # Acumuladores por turno (para el desglose por turno)
    por_turno_ventas: dict[str, dict] = {}

    def _bucket_turno(turno_id_venta: str | None) -> dict:
        if turno_id_venta not in por_turno_ventas:
            por_turno_ventas[turno_id_venta] = {
                "total_general": 0.0, "num_tickets": 0, "efectivo_neto": 0.0,
            }
        return por_turno_ventas[turno_id_venta]

    for v in completadas:
        b = _bucket_turno(v.get("turno_id"))
        b["total_general"] += float(v["total"] or 0)
        b["num_tickets"] += 1

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
                turno_de_venta = turno_por_venta.get(p["venta_id"])
                _bucket_turno(turno_de_venta)["efectivo_neto"] += (monto - cambio)

    # 3. Turnos de esa caja "relevantes" para este día: un turno puede
    # haberse abierto en un día anterior y seguir abierto (o cerrarse)
    # hoy — filtrar solo por "inicio dentro del día" lo excluía aunque
    # tuviera ventas hoy, dejando esas ventas sin turno visible en el
    # desglose. Se incluye un turno si: sigue abierto, O su cierre cae
    # hoy, O su inicio cae hoy (cualquiera de los tres casos).
    turnos_ids_con_ventas_hoy = {v["turno_id"] for v in ventas if v.get("turno_id")}

    turnos = (
        supabase.table("turnos")
        .select("id, inicio, cierre, estado, usuarios(nombre_completo)")
        .eq("caja_id", caja_id)
        .or_(f"estado.eq.abierto,and(cierre.gte.{inicio},cierre.lt.{fin}),and(inicio.gte.{inicio},inicio.lt.{fin})")
        .order("inicio")
        .execute()
    ).data or []

    # Red de seguridad: si por alguna razón un turno con ventas hoy no
    # quedó incluido arriba (caso extremo), lo agregamos igual para que
    # ninguna venta del día quede huérfana en el desglose por turno.
    ids_turnos_traidos = {t["id"] for t in turnos}
    faltantes = turnos_ids_con_ventas_hoy - ids_turnos_traidos
    if faltantes:
        extra = (
            supabase.table("turnos")
            .select("id, inicio, cierre, estado, usuarios(nombre_completo)")
            .in_("id", list(faltantes))
            .execute()
        ).data or []
        turnos.extend(extra)
        turnos.sort(key=lambda t: t["inicio"])

    fondo_inicial = 0.0
    entradas_efectivo = 0.0
    salidas_efectivo = 0.0

    # Movimientos de caja por turno (para el desglose por turno)
    movimientos_por_turno: dict[str, dict] = {}

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

        for turno_id_mov, movs_turno in por_turno.items():
            entradas = [m for m in movs_turno if m["tipo_movimiento"] == "entrada"]
            salidas  = [m for m in movs_turno if m["tipo_movimiento"] == "salida"]

            fondo_turno = float(entradas[0]["monto"] or 0) if entradas else 0.0
            entradas_manual_turno = sum(float(m["monto"] or 0) for m in entradas[1:])
            salidas_turno = sum(float(m["monto"] or 0) for m in salidas)

            movimientos_por_turno[turno_id_mov] = {
                "fondo_inicial": fondo_turno,
                "entradas": entradas_manual_turno,
                "salidas": salidas_turno,
            }

            fondo_inicial += fondo_turno
            entradas_efectivo += entradas_manual_turno
            salidas_efectivo += salidas_turno

    # 4. Efectivo esperado en caja
    efectivo_esperado = fondo_inicial + efectivo_neto + entradas_efectivo - salidas_efectivo

    total_general = sum(float(v["total"] or 0) for v in completadas)

    # Detalle de turnos con estado, para marcar cuáles siguen abiertos (RF-11.1)
    turnos_detalle = []
    hay_turno_abierto = False
    for t in turnos:
        usuario_data = t.get("usuarios") or {}
        if t["estado"] == "abierto":
            hay_turno_abierto = True

        ventas_turno = por_turno_ventas.get(t["id"], {"total_general": 0.0, "num_tickets": 0, "efectivo_neto": 0.0})
        mov_turno = movimientos_por_turno.get(t["id"], {"fondo_inicial": 0.0, "entradas": 0.0, "salidas": 0.0})
        efectivo_esperado_turno = (
            mov_turno["fondo_inicial"] + ventas_turno["efectivo_neto"]
            + mov_turno["entradas"] - mov_turno["salidas"]
        )

        turnos_detalle.append({
            "id": t["id"],
            "inicio": t["inicio"],
            "cierre": t.get("cierre"),
            "estado": t["estado"],
            "cajero_nombre": usuario_data.get("nombre_completo") or "—",
            "total_general": round(ventas_turno["total_general"], 2),
            "num_tickets": ventas_turno["num_tickets"],
            "efectivo_esperado": round(efectivo_esperado_turno, 2),
        })

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
        "turnos_detalle": turnos_detalle,
        "hay_turno_abierto": hay_turno_abierto,
    }


def corte_consolidado_dia(sucursal_id: str, fecha: str) -> dict:
    """
    Corte consolidado de TODAS las cajas de la sucursal en un día (distinto
    del cierre de turno individual que hace el cajero): suma los totales de
    todas las cajas y desglosa cada una por separado, incluyendo turnos
    que sigan abiertos al momento de la consulta (RF-11).
    Se excluyen las cajas marcadas como verificador (no venden, RF-01.4).
    """
    cajas = (
        supabase.table("cajas")
        .select("id, nombre, es_verificador")
        .eq("sucursal_id", sucursal_id)
        .eq("es_verificador", False)
        .order("nombre")
        .execute()
    ).data or []

    desglose_cajas = []
    total_general = 0.0
    total_tickets = 0
    total_canceladas = 0
    total_turnos = 0
    hay_algun_turno_abierto = False
    totales_metodo_consolidado = {
        "efectivo": 0.0, "tarjeta": 0.0,
        "transferencia": 0.0, "cheque": 0.0, "mixto": 0.0,
    }
    efectivo_esperado_consolidado = 0.0

    todos_los_turnos = []

    for caja in cajas:
        corte_caja = corte_por_caja_dia(caja["id"], sucursal_id, fecha)
        corte_caja["caja_nombre"] = caja["nombre"]
        desglose_cajas.append(corte_caja)

        for t in corte_caja["turnos_detalle"]:
            todos_los_turnos.append({**t, "caja_nombre": caja["nombre"]})

        total_general += corte_caja["total_general"]
        total_tickets += corte_caja["num_tickets"]
        total_canceladas += corte_caja["num_canceladas"]
        total_turnos += corte_caja["num_turnos"]
        efectivo_esperado_consolidado += corte_caja["caja"]["efectivo_esperado"]
        if corte_caja["hay_turno_abierto"]:
            hay_algun_turno_abierto = True

        for metodo, monto in corte_caja["totales_metodo"].items():
            totales_metodo_consolidado[metodo] += monto

    # Ordenar todos los turnos por hora de inicio, sin importar la caja
    todos_los_turnos.sort(key=lambda t: t["inicio"])

    return {
        "fecha": fecha,
        "total_general": round(total_general, 2),
        "num_tickets": total_tickets,
        "num_canceladas": total_canceladas,
        "num_turnos": total_turnos,
        "hay_turno_abierto": hay_algun_turno_abierto,
        "totales_metodo": {k: round(v, 2) for k, v in totales_metodo_consolidado.items()},
        "efectivo_esperado_total": round(efectivo_esperado_consolidado, 2),
        "cajas": desglose_cajas,
        "turnos": todos_los_turnos,
    }