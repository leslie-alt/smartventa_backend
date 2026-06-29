from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from app.core.database import supabase  # ajustar import según tu cliente de Supabase


def _validar_turno_abierto(turno_id: str, caja_id: str, usuario_id: str, sucursal_id: str) -> None:
    """Confirma que el turno está abierto, es del usuario actual y pertenece
    a la caja/sucursal indicadas (RNF-03.4: nadie ejecuta sin el contexto correcto)."""
    respuesta = (
        supabase.table("turnos")
        .select("id, estado, usuario_id, caja_id, cajas!inner(sucursal_id)")
        .eq("id", turno_id)
        .single()
        .execute()
    )
    turno = respuesta.data
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado.")
    if turno["estado"] != "abierto":
        raise HTTPException(status_code=409, detail="El turno ya está cerrado. Abre un turno antes de vender.")
    if turno["usuario_id"] != usuario_id:
        raise HTTPException(status_code=403, detail="Este turno no pertenece al usuario actual.")
    if turno["caja_id"] != caja_id:
        raise HTTPException(status_code=400, detail="La caja indicada no coincide con el turno abierto.")
    if turno["cajas"]["sucursal_id"] != sucursal_id:
        raise HTTPException(status_code=403, detail="El turno no pertenece a esta sucursal.")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _obtener_productos_para_venta(producto_ids: list[str], sucursal_id: str) -> dict:
    """Trae precio, costo, existencia y promoción activa por producto en una sola llamada."""
    respuesta = (
        supabase.table("productos")
        .select(
            "id, descripcion, precio_venta, precio_mayoreo, costo_unitario, activo,"
            "inventario!inner(cantidad_actual),"
            "promociones(id, cantidad_minima, tipo_beneficio, valor_beneficio, fecha_inicio, activa)"
        )
        .in_("id", producto_ids)
        .eq("sucursal_id", sucursal_id)
        .eq("inventario.sucursal_id", sucursal_id)
        .execute()
    )
    productos = {p["id"]: p for p in (respuesta.data or [])}

    faltantes = set(producto_ids) - set(productos.keys())
    if faltantes:
        raise HTTPException(
            status_code=404,
            detail=f"Producto(s) no encontrado(s) en esta sucursal: {', '.join(faltantes)}",
        )
    return productos


def _obtener_cliente_es_mayorista(cliente_id: str, sucursal_id: str) -> bool:
    respuesta = (
        supabase.table("clientes")
        .select("es_mayorista, activo")
        .eq("id", cliente_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en esta sucursal")
    return bool(respuesta.data.get("es_mayorista"))


def _promocion_aplicable(promociones: list[dict], cantidad: int) -> dict | None:
    hoy = date.today()
    for promo in promociones or []:
        if not promo.get("activa"):
            continue
        if promo.get("fecha_inicio") and date.fromisoformat(str(promo["fecha_inicio"])) > hoy:
            continue
        if cantidad >= promo["cantidad_minima"]:
            return promo
    return None


def _calcular_linea(producto: dict, cantidad: int, mayoreo_ticket: bool) -> dict:
    """Calcula precio_unitario, descuento y uso_precio_mayoreo para una línea,
    respetando RF-05.5 (promoción activa bloquea el mayoreo en ese producto)."""
    precio_venta = Decimal(str(producto["precio_venta"]))
    precio_mayoreo = Decimal(str(producto["precio_mayoreo"]))

    promo = _promocion_aplicable(producto.get("promociones"), cantidad)

    if promo:
        if promo["tipo_beneficio"] == "precio_especial":
            precio_unitario = Decimal(str(promo["valor_beneficio"]))
            descuento = Decimal("0")
        else:  # porcentaje
            precio_unitario = precio_venta
            porcentaje = Decimal(str(promo["valor_beneficio"]))
            descuento = _redondear(precio_venta * cantidad * porcentaje / Decimal("100"))
        uso_precio_mayoreo = False
    elif mayoreo_ticket:
        precio_unitario = precio_mayoreo
        descuento = Decimal("0")
        uso_precio_mayoreo = True
    else:
        precio_unitario = precio_venta
        descuento = Decimal("0")
        uso_precio_mayoreo = False

    subtotal = _redondear(precio_unitario * cantidad - descuento)

    return {
        "precio_unitario": _redondear(precio_unitario),
        "descuento": descuento,
        "uso_precio_mayoreo": uso_precio_mayoreo,
        "subtotal": subtotal,
        "costo_unitario": producto["costo_unitario"],
    }


def crear_venta(
    datos: dict,
    sucursal_id: str,
    caja_id: str,
    turno_id: str,
    usuario_id: str,
) -> dict:
    """Registra una venta directa completa: artículos, pagos, descuento de
    inventario, kardex y auditoría en una sola operación atómica (RPC).
    caja_id y turno_id se validan contra la base de datos antes de continuar
    (RNF-03.4)."""
    _validar_turno_abierto(turno_id, caja_id, usuario_id, sucursal_id)

    articulos_in = datos["articulos"]
    pagos_in = datos["pagos"]
    cliente_id = datos.get("cliente_id")

    producto_ids = [str(a["producto_id"]) for a in articulos_in]
    productos = _obtener_productos_para_venta(producto_ids, sucursal_id)

    # Validar stock antes de calcular precios (evita trabajo de más si ya falla)
    for art in articulos_in:
        existencia = productos[str(art["producto_id"])]["inventario"][0]["cantidad_actual"]
        if existencia < art["cantidad"]:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para el producto {art['producto_id']}",
            )

    # RF-05.3: tarjeta bloquea mayoreo sin importar monto o tipo de cliente
    tiene_tarjeta = any(p["metodo"] == "tarjeta" for p in pagos_in)

    subtotal_normal = sum(
        Decimal(str(productos[str(a["producto_id"])]["precio_venta"])) * a["cantidad"]
        for a in articulos_in
    )

    cliente_es_mayorista = False
    if cliente_id:
        cliente_es_mayorista = _obtener_cliente_es_mayorista(str(cliente_id), sucursal_id)

    if tiene_tarjeta:
        mayoreo_ticket = False
        motivo_mayoreo = "ninguno"
    elif cliente_es_mayorista:
        mayoreo_ticket = True
        motivo_mayoreo = "cliente"
    elif subtotal_normal > Decimal("350.00"):
        mayoreo_ticket = True
        motivo_mayoreo = "monto"
    else:
        mayoreo_ticket = False
        motivo_mayoreo = "ninguno"

    articulos_calculados = []
    total = Decimal("0")
    for art in articulos_in:
        producto = productos[str(art["producto_id"])]
        calculo = _calcular_linea(producto, art["cantidad"], mayoreo_ticket)
        total += calculo["subtotal"]
        articulos_calculados.append(
            {
                "producto_id": str(art["producto_id"]),
                "cantidad": art["cantidad"],
                "precio_unitario": float(calculo["precio_unitario"]),
                "uso_precio_mayoreo": calculo["uso_precio_mayoreo"],
                "descuento": float(calculo["descuento"]),
                "costo_unitario": float(calculo["costo_unitario"]),
            }
        )

    # RF-06.2: cambio automático en efectivo
    pagos_calculados = []
    suma_pagos = Decimal("0")
    for pago in pagos_in:
        monto = Decimal(str(pago["monto"]))
        suma_pagos += monto
        cambio = Decimal("0")
        if pago["metodo"] == "efectivo" and pago.get("recibido") is not None:
            recibido = Decimal(str(pago["recibido"]))
            cambio = _redondear(recibido - monto)
            if cambio < 0:
                raise HTTPException(status_code=400, detail="El monto recibido es menor al monto a pagar")
        pagos_calculados.append(
            {
                "metodo": pago["metodo"],
                "monto": float(monto),
                "cambio": float(cambio),
                "referencia": pago.get("referencia"),
            }
        )

    if _redondear(suma_pagos) != _redondear(total):
        raise HTTPException(
            status_code=400,
            detail=f"La suma de los pagos (${suma_pagos}) no coincide con el total (${total})",
        )

    metodo_pago_principal = "mixto" if len(pagos_calculados) > 1 else pagos_calculados[0]["metodo"]

    resultado = supabase.rpc(
        "registrar_venta_completa",
        {
            "p_sucursal_id": sucursal_id,
            "p_caja_id": caja_id,
            "p_turno_id": turno_id,
            "p_usuario_id": usuario_id,
            "p_cliente_id": str(cliente_id) if cliente_id else None,
            "p_total": float(total),
            "p_aplico_mayoreo": mayoreo_ticket,
            "p_motivo_mayoreo": motivo_mayoreo,
            "p_metodo_pago_principal": metodo_pago_principal,
            "p_notas": datos.get("notas"),
            "p_articulos": articulos_calculados,
            "p_pagos": pagos_calculados,
        },
    ).execute()

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo registrar la venta")

    return resultado.data


def obtener_venta(venta_id: str, sucursal_id: str) -> dict:

    respuesta = (
        supabase.table("ventas")
        .select(
            "*, venta_articulos(*, productos(descripcion)), pagos(*)"
        )
        .eq("id", venta_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return respuesta.data