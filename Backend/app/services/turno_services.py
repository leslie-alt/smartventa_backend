# turno_services.py
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.database import supabase
from app.services import caja_services


def abrir_turno(
    caja_id: str, sucursal_id: str, usuario_id: str,
    fondo_inicial: float = 0, notas: str | None = None,
) -> dict:
    """Abre un turno y registra el fondo inicial en movimientos_caja (RF-10.1)."""
    caja = caja_services.obtener_caja(caja_id, sucursal_id)

    if caja.get("es_verificador"):
        raise HTTPException(
            status_code=409,
            detail="No se puede abrir un turno en la estación de verificador de precios.",
        )

    
    
    try:
        resultado = supabase.rpc(
            "abrir_turno_con_fondo",
            {
                "p_caja_id": caja_id,
                "p_usuario_id": usuario_id,
                "p_fondo_inicial": fondo_inicial,
                "p_notas": notas,
            },
        ).execute()
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="Ya existe un turno abierto en esta caja. Cierra el turno actual antes de abrir uno nuevo.",
            )
        raise HTTPException(status_code=500, detail="No se pudo abrir el turno.")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo abrir el turno.")
    return resultado.data


def obtener_turno_activo_de_usuario(usuario_id: str, sucursal_id: str) -> dict | None:
    """Turno abierto del usuario actual, sin importar en qué caja —
    útil para reconstruir la sesión si el servidor de Express se reinició."""
    respuesta = (
        supabase.table("turnos")
        .select("*, cajas!inner(sucursal_id)")
        .eq("usuario_id", usuario_id)
        .eq("estado", "abierto")
        .eq("cajas.sucursal_id", sucursal_id)
        .execute()
    )
    if not respuesta.data:
        return None
    turno = respuesta.data[0]
    turno.pop("cajas", None)
    return turno


def obtener_resumen_turno(turno_id: str, sucursal_id: str) -> dict:
    turno = obtener_turno(turno_id)
    caja_services.obtener_caja(turno["caja_id"], sucursal_id)

    # Nombre del cajero dueño del turno — se resuelve aquí (con service_key,
    # sin restricción de permiso) para que cualquiera que vea este resumen
    # obtenga el nombre correcto, sin depender de /usuarios/ (que requiere
    # perm_administrar y le fallaba a los cajeros normales).
    usuario_turno = (
        supabase.table("usuarios")
        .select("nombre_completo")
        .eq("id", turno["usuario_id"])
        .single()
        .execute()
    ).data or {}
    turno["cajero_nombre"] = usuario_turno.get("nombre_completo")
    ventas = (
        supabase.table("ventas")
        .select("id, total, metodo_pago_principal")
        .eq("turno_id", turno_id)
        .eq("estado", "completada")
        .execute()
    ).data or []

    # El desglose por método debe sumar los montos REALES pagados en cada
    # método (tabla pagos, RF-06.4), no el total completo de la venta bajo
    # "mixto" — antes una venta pagada mitad efectivo/mitad tarjeta se
    # contaba entera como "mixto", sin reflejar cuánto fue de cada una.
    totales = {"efectivo": 0.0, "tarjeta": 0.0, "cheque": 0.0, "transferencia": 0.0, "mixto": 0.0}
    venta_ids = [v["id"] for v in ventas]
    if venta_ids:
        pagos_ventas = (
            supabase.table("pagos")
            .select("venta_id, metodo, monto, cambio")
            .in_("venta_id", venta_ids)
            .execute()
        ).data or []
        for p in pagos_ventas:
            metodo = p["metodo"]
            monto  = float(p["monto"] or 0)
            if metodo in totales:
                totales[metodo] += monto
            else:
                totales["mixto"] += monto

    movimientos = (
        supabase.table("movimientos_caja")
        .select("tipo_movimiento, monto, notas, registrado_en")
        .eq("turno_id", turno_id)
        .order("registrado_en")
        .execute()
    ).data or []

    entradas_lista = [m for m in movimientos if m["tipo_movimiento"] == "entrada"]
    salidas_lista  = [m for m in movimientos if m["tipo_movimiento"] == "salida"]

    # El fondo inicial es la primera entrada del turno (registrada por abrir_turno_con_fondo)
    fondo_inicial   = float(entradas_lista[0]["monto"]) if entradas_lista else 0.0
    entradas_manual = sum(float(m["monto"]) for m in entradas_lista[1:])  # entradas después del fondo
    salidas_total   = sum(float(m["monto"]) for m in salidas_lista)

    # Efectivo esperado en caja = fondo + ventas en efectivo + entradas manuales - salidas
    efectivo_esperado = (
        fondo_inicial
        + totales["efectivo"]
        + entradas_manual
        - salidas_total
    )

    return {
        "turno": turno,
        "total_tickets": len(ventas),
        "total_general": sum(totales.values()),
        "totales_por_metodo": totales,
        "fondo_inicial": fondo_inicial,
        "entradas_manual": entradas_manual,
        "salidas_total": salidas_total,
        "efectivo_esperado": efectivo_esperado,
        "movimientos_entradas": fondo_inicial + entradas_manual,
        "movimientos_salidas": salidas_total,
        "detalle_movimientos": movimientos,
    }


def obtener_turno(turno_id: str) -> dict:
    respuesta = (
        supabase.table("turnos")
        .select("*")
        .eq("id", turno_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Turno no encontrado.")
    return respuesta.data


def obtener_turno_activo(caja_id: str, sucursal_id: str) -> dict | None:
    """Regresa el turno abierto de una caja, o None. Útil para que Express
    reconstruya la sesión si el servidor se reinició o el cajero recargó la página."""
    caja_services.obtener_caja(caja_id, sucursal_id)

    respuesta = (
        supabase.table("turnos")
        .select("*")
        .eq("caja_id", caja_id)
        .eq("estado", "abierto")
        .execute()
    )
    return respuesta.data[0] if respuesta.data else None


def cerrar_turno(
    turno_id: str, sucursal_id: str, usuario_id: str, tiene_perm_corte_caja: bool,
) -> dict:
    """
    Cierra un turno abierto (RF-11.1). Cualquier usuario puede cerrar SU
    PROPIO turno; cerrar el turno de otro usuario requiere perm_corte_caja
    (por ejemplo, una supervisora cerrando el turno de un cajero que ya
    se fue sin cerrar).
    """
    turno = obtener_turno(turno_id)
    caja_services.obtener_caja(turno["caja_id"], sucursal_id)  # valida sucursal

    es_propio = str(turno["usuario_id"]) == str(usuario_id)
    if not es_propio and not tiene_perm_corte_caja:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para cerrar el turno de otro usuario.",
        )

    if turno["estado"] == "cerrado":
       raise HTTPException(status_code=409, detail="El turno ya está cerrado.")
    respuesta = (
        supabase.table("turnos")
        .update({
            "estado": "cerrado",
            "cierre": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", turno_id)
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=500, detail="No se pudo cerrar el turno.")
    return respuesta.data[0]


def listar_turnos(
    caja_id: str, sucursal_id: str, usuario_id: str, tiene_perm_corte_caja: bool,
    fecha: str | None = None,
) -> dict:
    """
    Lista turnos de una caja, opcionalmente filtrados por fecha (YYYY-MM-DD).
    Quien tiene perm_corte_caja ve todos los turnos de la caja; quien no,
    solo ve sus propios turnos.
    """
    query = (
        supabase.table("turnos")
        .select("id, inicio, cierre, estado, usuario_id")
        .eq("caja_id", caja_id)
        .order("inicio", desc=True)
    )
    if fecha:
        # El día completo se calcula en hora de México y se convierte a UTC
        # para el filtro — igual que en reporte_services._rango_fechas().
        d = datetime.strptime(fecha, "%Y-%m-%d").date()
        tz_mexico = ZoneInfo("America/Mexico_City")
        inicio_mx = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz_mexico)
        fin_mx = inicio_mx + timedelta(days=1)
        inicio_utc = inicio_mx.astimezone(timezone.utc).isoformat()
        fin_utc = fin_mx.astimezone(timezone.utc).isoformat()
        query = query.gte("inicio", inicio_utc).lt("inicio", fin_utc)
    if not tiene_perm_corte_caja:
        query = query.eq("usuario_id", usuario_id)

    respuesta = query.limit(20).execute()
    return {"items": respuesta.data or []}