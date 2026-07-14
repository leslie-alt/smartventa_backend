from datetime import datetime, timezone

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

    ventas = (
        supabase.table("ventas")
        .select("total, metodo_pago_principal")
        .eq("turno_id", turno_id)
        .eq("estado", "completada")
        .execute()
    ).data or []

    totales = {"efectivo": 0.0, "tarjeta": 0.0, "cheque": 0.0, "transferencia": 0.0, "mixto": 0.0}
    for v in ventas:
        metodo = v["metodo_pago_principal"]
        if metodo in totales:
            totales[metodo] += float(v["total"])

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


def cerrar_turno(turno_id: str, sucursal_id: str) -> dict:
    """Cierra un turno abierto (RF-11.1). Requiere perm_corte_caja, validado en el router."""
    turno = obtener_turno(turno_id)
    caja_services.obtener_caja(turno["caja_id"], sucursal_id)  # valida sucursal

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


def listar_turnos(caja_id: str, sucursal_id: str, fecha: str | None = None) -> dict:
    """Lista turnos de una caja, opcionalmente filtrados por fecha (YYYY-MM-DD)."""
    query = (
        supabase.table("turnos")
        .select("id, inicio, cierre, estado, usuario_id")
        .eq("caja_id", caja_id)
        .order("inicio", desc=True)
    )
    if fecha:
        # Filtrar por día completo en UTC
        query = query.gte("inicio", f"{fecha}T00:00:00Z").lt("inicio", f"{fecha}T23:59:59Z")

    respuesta = query.limit(20).execute()
    return {"items": respuesta.data or []}