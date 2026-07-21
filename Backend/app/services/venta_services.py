# venta_services.py
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from app.core.database import supabase  # ajustar import según tu cliente de Supabase
from postgrest.exceptions import APIError
from datetime import date, datetime
from zoneinfo import ZoneInfo


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

    for p in (respuesta.data or []):
        print(f"DEBUG {p['descripcion']}: promociones={p.get('promociones')}")

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


def _calcular_linea(producto: dict, cantidad: int, mayoreo_ticket: bool, forzar_mayoreo: bool = False) -> dict:
    """Calcula precio_unitario, descuento y uso_precio_mayoreo para una línea.
    forzar_mayoreo=True ignora RF-05 por completo y aplica precio mayoreo
    sin importar monto/cliente/promoción — requiere perm_descuentos, validado
    en la capa de servicio antes de llegar aquí."""
    precio_venta = Decimal(str(producto["precio_venta"]))
    precio_mayoreo = Decimal(str(producto["precio_mayoreo"]))

    promo = _promocion_aplicable(producto.get("promociones"), cantidad)

    if forzar_mayoreo:
        precio_unitario = precio_mayoreo
        descuento = Decimal("0")
        uso_precio_mayoreo = True
    elif promo:
        if promo["tipo_beneficio"] == "precio_especial":
            precio_unitario = Decimal(str(promo["valor_beneficio"]))
            descuento = Decimal("0")
        else:
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
    tiene_perm_descuentos: bool = False,
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

    for art in articulos_in:
        existencia = productos[str(art["producto_id"])]["inventario"][0]["cantidad_actual"]
        if existencia < art["cantidad"]:
            raise HTTPException(status_code=409, detail=f"Stock insuficiente para el producto {art['producto_id']}")

    tiene_tarjeta = any(p["metodo"] == "tarjeta" for p in pagos_in)

    articulos_calculados, total, aplico_mayoreo, motivo_mayoreo = _calcular_articulos_y_total(
        articulos_in, productos, cliente_id, sucursal_id, tiene_perm_descuentos, tiene_tarjeta,
    )

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
        pagos_calculados.append({
            "metodo": pago["metodo"], "monto": float(monto),
            "cambio": float(cambio), "referencia": pago.get("referencia"),
        })

    if _redondear(suma_pagos) != _redondear(total):
        raise HTTPException(status_code=400, detail=f"La suma de los pagos (${suma_pagos}) no coincide con el total (${total})")

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
            "p_aplico_mayoreo": aplico_mayoreo,
            "p_motivo_mayoreo": motivo_mayoreo,
            "p_metodo_pago_principal": metodo_pago_principal,
            "p_notas": datos.get("notas"),
            "p_articulos": articulos_calculados,
            "p_pagos": pagos_calculados,
        },
    ).execute()
    print("DEBUG registrar_venta_completa resultado.data:", resultado.data)
    
    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo registrar la venta")

    # RPC regresa JSONB plano — obtener venta completa para VentaOut
    data = resultado.data
    venta_id = data.get("id") if isinstance(data, dict) else data[0].get("id")
    if not venta_id:
        raise HTTPException(status_code=500, detail="No se pudo obtener el ID de la venta registrada")

    return obtener_venta(venta_id, sucursal_id)

def _calcular_articulos_y_total(
    articulos_in: list[dict],
    productos: dict,
    cliente_id,
    sucursal_id: str,
    tiene_perm_descuentos: bool,
    tiene_tarjeta: bool,
) -> tuple[list[dict], Decimal, bool, str]:
    """Lógica compartida entre crear_venta y guardar_ticket_pendiente.
    Mayoreo POR PRODUCTO (RF-05.1): cada línea lleva mayoreo si su propio
    subtotal a precio de mayoreo supera $350, o si el cliente es mayorista.
    Tarjeta nunca lleva mayoreo (RF-05.3); promoción activa lo anula (RF-05.5)."""
    hay_forzados = any(a.get("forzar_mayoreo") for a in articulos_in)
    if hay_forzados and not tiene_perm_descuentos:
        raise HTTPException(status_code=403, detail="No tienes permiso para forzar precio de mayoreo (perm_descuentos)")

    cliente_es_mayorista = False
    if cliente_id:
        cliente_es_mayorista = _obtener_cliente_es_mayorista(str(cliente_id), sucursal_id)

    articulos_calculados = []
    total = Decimal("0")
    motivo_mayoreo = "ninguno"

    for art in articulos_in:
        producto = productos[str(art["producto_id"])]
        cantidad = art["cantidad"]
        precio_mayoreo = Decimal(str(producto["precio_mayoreo"]))
        forzar = bool(art.get("forzar_mayoreo")) and not tiene_tarjeta  # RF-05.3 absoluto

        # ¿Esta línea califica para mayoreo por monto? Umbral sobre precio de mayoreo.
        mayoreo_linea = False
        if not tiene_tarjeta:
            if cliente_es_mayorista:
                mayoreo_linea = True
            elif precio_mayoreo * cantidad > Decimal("350.00"):
                mayoreo_linea = True

        calculo = _calcular_linea(producto, cantidad, mayoreo_linea, forzar_mayoreo=forzar)
        total += calculo["subtotal"]

        # Motivo predominante del ticket (RF-05.6): manual > cliente > monto
        if calculo["uso_precio_mayoreo"]:
            if forzar:
                motivo_mayoreo = "manual"
            elif cliente_es_mayorista and motivo_mayoreo != "manual":
                motivo_mayoreo = "cliente"
            elif motivo_mayoreo not in ("manual", "cliente"):
                motivo_mayoreo = "monto"

        articulos_calculados.append({
            "producto_id": str(art["producto_id"]),
            "cantidad": cantidad,
            "precio_unitario": float(calculo["precio_unitario"]),
            "uso_precio_mayoreo": calculo["uso_precio_mayoreo"],
            "descuento": float(calculo["descuento"]),
            "costo_unitario": float(calculo["costo_unitario"]),
        })

    aplico_mayoreo = any(a["uso_precio_mayoreo"] for a in articulos_calculados)
    return articulos_calculados, total, aplico_mayoreo, motivo_mayoreo

def guardar_ticket_pendiente(
    venta_id: str | None,
    datos: dict,
    sucursal_id: str,
    caja_id: str,
    turno_id: str,
    usuario_id: str,
    tiene_perm_descuentos: bool,
) -> dict:
    """Crea o actualiza un ticket pendiente (RF-04 ampliado: tickets en espera)."""
    articulos_in = datos["articulos"]
    cliente_id = datos.get("cliente_id")

    producto_ids = [str(a["producto_id"]) for a in articulos_in]
    productos = _obtener_productos_para_venta(producto_ids, sucursal_id)

    articulos_calc, total, aplico_mayoreo, motivo_mayoreo = _calcular_articulos_y_total(
        articulos_in, productos, cliente_id, sucursal_id, tiene_perm_descuentos, tiene_tarjeta=False,
    )

    resultado = supabase.rpc(
        "guardar_ticket_pendiente",
        {
            "p_venta_id": venta_id,
            "p_sucursal_id": sucursal_id,
            "p_caja_id": caja_id,
            "p_turno_id": turno_id,
            "p_usuario_id": usuario_id,
            "p_cliente_id": str(cliente_id) if cliente_id else None,
            "p_total": float(total),
            "p_aplico_mayoreo": aplico_mayoreo,
            "p_motivo_mayoreo": motivo_mayoreo,
            "p_notas": datos.get("notas"),
            "p_articulos": articulos_calc,
        },
    ).execute()
    print("DEBUG registrar_venta_completa resultado.data:", resultado.data)
    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo guardar el ticket pendiente")
    return obtener_venta(resultado.data["id"], sucursal_id)


def listar_tickets_pendientes(caja_id: str, sucursal_id: str) -> list[dict]:
    respuesta = (
        supabase.table("ventas")
        .select("*, venta_articulos(*, productos(descripcion, codigo_barras, ruta_imagen))")
        .eq("caja_id", caja_id)
        .eq("sucursal_id", sucursal_id)
        .eq("estado", "pendiente")
        .order("creado_en")
        .execute()
    )
    return respuesta.data or []

def eliminar_ticket_pendiente(venta_id: str, sucursal_id: str, caja_id: str, usuario_id: str) -> dict:
    try:
        supabase.rpc(
            "eliminar_ticket_pendiente",
            {
                "p_venta_id": venta_id,
                "p_sucursal_id": sucursal_id,
                "p_usuario_id": usuario_id,
                "p_caja_id": caja_id,
            },
        ).execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Ticket pendiente no encontrado")
    return {"mensaje": "Ticket pendiente eliminado"}


def cobrar_ticket_pendiente(
    venta_id: str, datos: dict, sucursal_id: str, caja_id: str, turno_id: str, usuario_id: str,
) -> dict:
    pagos_in = datos["pagos"]

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
        pagos_calculados.append({
            "metodo": pago["metodo"], "monto": float(monto),
            "cambio": float(cambio), "referencia": pago.get("referencia"),
        })

    metodo_pago_principal = "mixto" if len(pagos_calculados) > 1 else pagos_calculados[0]["metodo"]

    try:
        resultado = supabase.rpc(
            "cobrar_ticket_pendiente",
            {
                "p_venta_id": venta_id,
                "p_sucursal_id": sucursal_id,
                "p_caja_id": caja_id,
                "p_turno_id": turno_id,
                "p_usuario_id": usuario_id,
                "p_metodo_pago_principal": metodo_pago_principal,
                "p_pagos": pagos_calculados,
            },
        ).execute()
    except APIError as e:
        mensaje = getattr(e, "message", None) or str(e)
        if mensaje.startswith("Stock insuficiente|"):
            partes = mensaje.split("|")
            producto_id = partes[1].strip() if len(partes) > 1 else None
            nombre      = partes[2].strip() if len(partes) > 2 else "un producto"
            existencia  = partes[3].strip() if len(partes) > 3 else "0"
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "stock_insuficiente",
                    "producto_id": producto_id,
                    "nombre": nombre,
                    "existencia": int(existencia),
                    "mensaje": f'Sin stock suficiente de "{nombre}" (disponible: {existencia}).',
                },
            )
        if "Stock insuficiente" in mensaje:
            raise HTTPException(status_code=409, detail="Un producto del ticket no tiene stock suficiente.")
        raise HTTPException(status_code=400, detail=mensaje)

   
    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo cobrar el ticket")
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



def listar_ventas_dia(
    sucursal_id: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    estado: str | None = None,
    metodo: str | None = None,
) -> list[dict]:
    """Lista ventas para la pantalla 'Ventas del día y Devoluciones'.
    Por defecto (sin filtro de fecha) trae SOLO las de hoy. Solo lectura."""
    query = (
        supabase.table("ventas")
        .select(
            "id, folio, total, metodo_pago_principal, estado, creado_en, "
            "aplico_mayoreo, motivo_mayoreo, "
            "usuarios!ventas_usuario_id_fkey(nombre_completo), clientes(nombre), cajas(nombre)"
        )
        .eq("sucursal_id", sucursal_id)
        .neq("estado", "pendiente")
    )


    # Si el usuario NO especificó ninguna fecha, limitar a HOY (horario de México).
    if not fecha_inicio and not fecha_fin:
        tz_mexico = ZoneInfo("America/Mexico_City")
        ahora_mx = datetime.now(tz_mexico)
        inicio_dia_mx = ahora_mx.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dia_mx = ahora_mx.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.gte("creado_en", inicio_dia_mx.astimezone(ZoneInfo("UTC")).isoformat())
        query = query.lte("creado_en", fin_dia_mx.astimezone(ZoneInfo("UTC")).isoformat())
    else:
        tz_mexico = ZoneInfo("America/Mexico_City")
        if fecha_inicio:
            # Inicio del día local (00:00 México) → UTC
            inicio_mx = datetime.fromisoformat(fecha_inicio).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_mexico
            )
            query = query.gte("creado_en", inicio_mx.astimezone(ZoneInfo("UTC")).isoformat())
        if fecha_fin:
            # Fin del día local (23:59:59 México) → UTC
            fin_mx = datetime.fromisoformat(fecha_fin).replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz_mexico
            )
            query = query.lte("creado_en", fin_mx.astimezone(ZoneInfo("UTC")).isoformat())

    if estado:
        query = query.eq("estado", estado)
    if metodo:
        query = query.eq("metodo_pago_principal", metodo)

    respuesta = query.order("creado_en", desc=True).execute()

    ventas = []
    for v in (respuesta.data or []):
        usuario = v.pop("usuarios", None)
        cliente = v.pop("clientes", None)
        caja = v.pop("cajas", None)
        v["cajero_nombre"] = usuario["nombre_completo"] if usuario else None
        v["cliente_nombre"] = cliente["nombre"] if cliente else "Público general"
        v["caja_nombre"] = caja["nombre"] if caja else None
        ventas.append(v)

    return ventas

def obtener_venta_detalle(venta_id: str, sucursal_id: str) -> dict:
    """Detalle completo de una venta para la vista de devolución.
    Incluye artículos (con cantidad_devuelta) y pagos."""
    respuesta = (
        supabase.table("ventas")
        .select(
            "id, folio, total, metodo_pago_principal, estado, creado_en, "
            "aplico_mayoreo, motivo_mayoreo, notas, cancelado_en, "
            "usuarios!ventas_usuario_id_fkey(nombre_completo), clientes(id, nombre, telefono, es_mayorista), "
            "cajas(nombre), "
            "venta_articulos(id, cantidad, cantidad_devuelta, precio_unitario, "
            "uso_precio_mayoreo, descuento, productos(descripcion, codigo_barras, ruta_imagen)), "
            "pagos(id, metodo, monto, cambio, referencia)"
        )
        .eq("id", venta_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    v = respuesta.data
    usuario = v.pop("usuarios", None)
    caja = v.pop("cajas", None)
    v["cajero_nombre"] = usuario["nombre_completo"] if usuario else None
    v["caja_nombre"] = caja["nombre"] if caja else None
    return v

def registrar_devolucion(
    venta_id: str,
    articulos: list[dict],   # [{"venta_articulo_id": str, "cantidad": int}]
    sucursal_id: str,
    caja_id: str,
    turno_id: str,
    usuario_id: str,
) -> dict:
    """Registra una devolución parcial o total (RF-04.6).
    Reingresa inventario, genera kardex, descuenta caja si el pago fue
    efectivo, y marca la venta como 'devuelta' si se devolvió todo.
    Todo atómico vía RPC."""
    if not articulos:
        raise HTTPException(status_code=400, detail="No se indicó ningún artículo a devolver.")

    try:
        resultado = supabase.rpc(
            "registrar_devolucion",
            {
                "p_venta_id": venta_id,
                "p_sucursal_id": sucursal_id,
                "p_caja_id": caja_id,
                "p_turno_id": turno_id,
                "p_usuario_id": usuario_id,
                "p_articulos": articulos,
            },
        ).execute()
    except APIError as e:
        mensaje = getattr(e, "message", None) or str(e)
        # Los RAISE EXCEPTION del RPC (validaciones de cantidad, estado) llegan aquí
        raise HTTPException(status_code=409, detail=mensaje)

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo registrar la devolución")
    return resultado.data



def listar_ventas_cliente(
    cliente_id: str, sucursal_id: str, limite: int = 10
) -> dict:
    """Últimas ventas de un cliente para su perfil (RF-07.1)."""
    respuesta = (
        supabase.table("ventas")
        .select("id, folio, total, metodo_pago_principal, estado, creado_en")
        .eq("cliente_id", cliente_id)
        .eq("sucursal_id", sucursal_id)
        .eq("estado", "completada")
        .order("creado_en", desc=True)
        .limit(limite)
        .execute()
    )
    ventas = respuesta.data or []
    total_gastado = sum(float(v["total"]) for v in ventas)

    # Total real de compras (sin límite) para estadísticas
    conteo = (
        supabase.table("ventas")
        .select("id", count="exact")
        .eq("cliente_id", cliente_id)
        .eq("sucursal_id", sucursal_id)
        .eq("estado", "completada")
        .execute()
    )

    return {
        "items": ventas,
        "total": conteo.count or 0,
        "total_gastado": total_gastado,
    }