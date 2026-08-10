# reporte_email_services.py
# Arma y envía por correo el reporte diario/semanal: corte de caja + resumen de ventas.
# El adjunto es un PDF con gráficas, con el mismo estilo visual de la app.

import os
import smtplib
import datetime as dt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import date, timedelta
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    HRFlowable, PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from app.core.config import config
from app.core.database import supabase
from app.services import corte_services, reporte_services


# =============================================================
# FUENTES Y PALETA (idéntica a la de la app)
# =============================================================

_DIR_FUENTES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
_RUTA_PLAYFAIR = os.path.join(_DIR_FUENTES, "PlayfairDisplay.ttf")
_RUTA_DMSANS = os.path.join(_DIR_FUENTES, "DMSans.ttf")

pdfmetrics.registerFont(TTFont("Playfair", _RUTA_PLAYFAIR))
pdfmetrics.registerFont(TTFont("DMSans", _RUTA_DMSANS))
fm.fontManager.addfont(_RUTA_DMSANS)
fm.fontManager.addfont(_RUTA_PLAYFAIR)
plt.rcParams["font.family"] = fm.FontProperties(fname=_RUTA_DMSANS).get_name()

BURGUNDY = colors.HexColor("#6C0820")
PINK_LIGHT = colors.HexColor("#FCE4EE")
PINK_BORDER = colors.HexColor("#F2DCDB")
NAVY = colors.HexColor("#3D5D91")
TEXT = colors.HexColor("#1a1a2e")
MUTED = colors.HexColor("#888888")

_PALETA_HEX = ["#6C0820", "#B5294E", "#3D5D91", "#F4A0C0", "#92400e"]
_NOMBRES_METODO = {"efectivo": "Efectivo", "tarjeta": "Tarjeta", "transferencia": "Transferencia", "cheque": "Cheque", "mixto": "Mixto"}
_DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _money(v) -> str:
    return f"${float(v or 0):,.2f}"


# =============================================================
# GRÁFICAS (regresan un BytesIO con PNG)
# =============================================================

def _grafica_metodos_pago(por_metodo: dict):
    labels, valores, colores = [], [], []
    i = 0
    for k, v in por_metodo.items():
        if v and v > 0:
            labels.append(_NOMBRES_METODO.get(k, k))
            valores.append(v)
            colores.append(_PALETA_HEX[i % len(_PALETA_HEX)])
            i += 1
    if not valores:
        return None

    fig, ax = plt.subplots(figsize=(2.7, 2.4), dpi=200)
    wedges, _ = ax.pie(
        valores, colors=colores, startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    ax.legend(
        wedges, [f"{l}  {_money(v)}" for l, v in zip(labels, valores)],
        loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7,
    )
    fig.patch.set_alpha(0)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", transparent=True, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafica_barra_horizontal(items: list, top_n: int, formato_valor="dinero"):
    """Barra horizontal compacta y reutilizable, para caber en un grid 2x1.
    `items` es una lista de dicts con 'etiqueta' y 'valor'."""
    if not items:
        return None
    recortados = items[:top_n]
    etiquetas = [i["etiqueta"] for i in recortados]
    valores = [i["valor"] for i in recortados]
    maximo = max(valores)

    fmt = (lambda v: _money(v)) if formato_valor == "dinero" else (lambda v: str(int(v)))

    alto = max(1.3, 0.42 * len(recortados) + 0.5)
    fig, ax = plt.subplots(figsize=(3.15, alto), dpi=200)
    barras = ax.barh(etiquetas, valores, color="#6C0820", height=0.5, zorder=3)
    ax.invert_yaxis()
    ax.set_xlim(0, maximo * 1.42)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E0C8C8")
    ax.tick_params(axis="y", length=0, labelsize=8, colors="#3D5D91")
    ax.tick_params(axis="x", length=0, labelsize=7, colors="#888")
    ax.xaxis.grid(True, color="#F2DCDB", zorder=0)
    ax.set_axisbelow(True)
    for barra, valor in zip(barras, valores):
        ax.text(barra.get_width() + maximo * 0.04, barra.get_y() + barra.get_height() / 2,
                 fmt(valor), va="center", fontsize=7.5, color="#1a1a2e", fontweight="bold")
    fig.patch.set_alpha(0)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", transparent=True, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf





def _grafica_ventas_dia(ventas_por_dia: list):
    if not ventas_por_dia:
        return None
    labels = [_DIAS_ES[dt.date.fromisoformat(d["fecha"]).weekday()] for d in ventas_por_dia]
    valores = [d["total"] for d in ventas_por_dia]
    maximo = max(valores)
    maximo_idx = valores.index(maximo)

    ancho_fig = max(3.4, min(6.6, 1.0 * len(labels) + 1.5))
    fig, ax = plt.subplots(figsize=(ancho_fig, 2.9), dpi=200)
    colores_barras = ["#6C0820" if i == maximo_idx else "#F4A0C0" for i in range(len(valores))]
    ancho_barra = 0.38 if len(labels) <= 3 else 0.55
    barras = ax.bar(labels, valores, color=colores_barras, width=ancho_barra, zorder=3)
    ax.set_ylim(0, maximo * 1.28)
    ax.set_xlim(-1, len(labels))
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#E0C8C8")
    ax.tick_params(axis="x", length=0, labelsize=9.5, colors="#3D5D91")
    ax.tick_params(axis="y", length=0, labelsize=8, colors="#888")
    ax.yaxis.grid(True, color="#F2DCDB", zorder=0)
    ax.set_axisbelow(True)
    for barra, total in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height() + maximo * 0.03,
                 f"${total:,.0f}", ha="center", fontsize=7.6, color="#1a1a2e", fontweight="bold")
    fig.patch.set_alpha(0)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", transparent=True, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# =============================================================
# ARMAR EL PDF
# =============================================================

def _armar_pdf(sucursal_nombre: str, fecha_label: str, corte, ventas) -> bytes:
    titulo_style = ParagraphStyle("titulo", fontName="Playfair", fontSize=20, leading=24, textColor=BURGUNDY, spaceAfter=6)
    subtitulo_style = ParagraphStyle("subtitulo", fontName="DMSans", fontSize=9.5, leading=13, textColor=MUTED)
    seccion_style = ParagraphStyle("seccion", fontName="Playfair", fontSize=13.5, textColor=BURGUNDY, spaceBefore=18, spaceAfter=8)
    kpi_label_style = ParagraphStyle("kpiLabel", fontName="DMSans", fontSize=8, textColor=MUTED, alignment=TA_CENTER)
    kpi_valor_style = ParagraphStyle("kpiValor", fontName="Playfair", fontSize=16, textColor=BURGUNDY, alignment=TA_CENTER, spaceBefore=2)
    footer_style = ParagraphStyle("footer", fontName="DMSans", fontSize=7.5, textColor=colors.HexColor("#bbbbbb"), alignment=TA_CENTER)

    elementos = []

    elementos.append(Paragraph(sucursal_nombre, titulo_style))
    elementos.append(Paragraph(f"Reporte &middot; {fecha_label} &middot; Generado automáticamente por SmartVenta", subtitulo_style))
    elementos.append(Spacer(1, 6))
    elementos.append(HRFlowable(width="100%", thickness=1.4, color=BURGUNDY, spaceAfter=4))

    def kpi_cell(label, valor):
        return [Paragraph(label, kpi_label_style), Paragraph(valor, kpi_valor_style)]

    if ventas or corte:
        total_ventas = ventas["total_ventas"] if ventas else corte["total_general"]
        total_tickets = ventas["total_tickets"] if ventas else corte["num_tickets"]
        ticket_prom = ventas["ticket_promedio"] if ventas else (total_ventas / total_tickets if total_tickets else 0)
        efectivo_esp = corte["caja"]["efectivo_esperado"] if corte else None

        kpi_data = [[
            kpi_cell("VENTAS TOTALES", _money(total_ventas)),
            kpi_cell("TICKETS", str(total_tickets)),
            kpi_cell("TICKET PROMEDIO", _money(ticket_prom)),
        ]]
        anchos = [150, 150, 150]
        if efectivo_esp is not None:
            kpi_data[0].append(kpi_cell("EFECTIVO ESPERADO", _money(efectivo_esp)))
            anchos = [115] * 4

        kpi_table = Table(kpi_data, colWidths=anchos, rowHeights=[54])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PINK_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ("LINEAFTER", (0, 0), (-2, -1), 1.2, colors.white),
        ]))
        elementos.append(Spacer(1, 14))
        elementos.append(kpi_table)

    if corte:
        elementos.append(Paragraph("Corte de caja", seccion_style))
        c = corte["caja"]
        filas_corte = [
            ["Fondo inicial", _money(c["fondo_inicial"])],
            ["Ventas en efectivo", _money(c["ventas_efectivo"])],
            ["Entradas de efectivo", _money(c["entradas"])],
            ["Salidas de efectivo", _money(c["salidas"])],
            ["Efectivo esperado en caja", _money(c["efectivo_esperado"])],
            ["Tickets completados / cancelados", f"{corte['num_tickets']} / {corte['num_canceladas']}"],
        ]
        tabla_corte = Table(filas_corte, colWidths=[280, 180])
        tabla_corte.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DMSans"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.6, PINK_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, -1), (-1, -1), 1.4, BURGUNDY),
        ]))
        elementos.append(tabla_corte)

    def _fila_dos_graficas(titulo_izq, img_izq, titulo_der, img_der):
        """Arma una fila de 2 columnas: cada una con su título y su gráfica,
        para que quepan lado a lado en media página."""
        col_izq, col_der = [], []
        if img_izq:
            col_izq.append(Paragraph(titulo_izq, seccion_style))
            col_izq.append(Image(img_izq, width=225, height=190, kind="proportional"))
        if img_der:
            col_der.append(Paragraph(titulo_der, seccion_style))
            col_der.append(Image(img_der, width=225, height=190, kind="proportional"))
        if not col_izq and not col_der:
            return None
        tabla = Table([[col_izq or "", col_der or ""]], colWidths=[255, 255])
        tabla.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        return tabla

    if ventas:
        img_dona = _grafica_metodos_pago(ventas["por_metodo"])
        cajeros_items = [{"etiqueta": c["nombre"], "valor": c["total"]} for c in ventas["cajeros"]]
        img_cajeros = _grafica_barra_horizontal(cajeros_items, top_n=5, formato_valor="dinero")

        fila1 = _fila_dos_graficas(
            "Ventas por método de pago", img_dona,
            "Ventas por cajero (top 5)", img_cajeros,
        )
        if fila1:
            elementos.append(fila1)

    tiene_pagina_2 = ventas and (
        ventas.get("ventas_por_dia") or ventas.get("top_productos") or ventas.get("ventas_por_caja") or ventas.get("turnos")
    )
    if tiene_pagina_2:
        elementos.append(PageBreak())

        img_dias = _grafica_ventas_dia(ventas.get("ventas_por_dia") or [])
        if img_dias:
            elementos.append(Paragraph("Tendencia de ventas por día", seccion_style))
            elementos.append(Image(img_dias, width=460, height=200, kind="proportional"))

        productos_items = [{"etiqueta": p["descripcion"][:22], "valor": p["cantidad"]} for p in (ventas.get("top_productos") or [])]
        img_productos = _grafica_barra_horizontal(productos_items, top_n=5, formato_valor="cantidad")

        cajas_items = [{"etiqueta": c["caja_nombre"], "valor": c["total"]} for c in (ventas.get("ventas_por_caja") or [])]
        img_cajas = _grafica_barra_horizontal(cajas_items, top_n=5, formato_valor="dinero") if len(ventas.get("ventas_por_caja") or []) > 1 else None

        fila2 = _fila_dos_graficas(
            "Productos más vendidos (top 5)", img_productos,
            "Ventas por caja", img_cajas,
        )
        if fila2:
            elementos.append(fila2)

        turnos = ventas.get("turnos") or []
        if turnos:
            elementos.append(Paragraph("Ventas por turno", seccion_style))
            encabezado = [["Caja", "Inicio", "Estado", "Tickets", "Total"]]
            filas = [
                [t["caja_nombre"], t["inicio"][:16].replace("T", " "), t["estado"].capitalize(), str(t["tickets"]), _money(t["total"])]
                for t in turnos[:6]  # se recorta para no pasar de 2 páginas
            ]
            tabla_turnos = Table(encabezado + filas, colWidths=[80, 130, 80, 70, 100])
            tabla_turnos.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "DMSans"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BACKGROUND", (0, 0), (-1, 0), BURGUNDY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (3, 0), (4, -1), "RIGHT"),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PINK_LIGHT]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, PINK_BORDER),
            ]))
            elementos.append(Spacer(1, 8))
            elementos.append(tabla_turnos)

    elementos.append(Spacer(1, 24))
    elementos.append(HRFlowable(width="100%", thickness=0.6, color=PINK_BORDER, spaceAfter=8))
    elementos.append(Paragraph(
        "Este reporte se generó automáticamente. Si no reconoces esta suscripción, contacta al administrador del sistema.",
        footer_style,
    ))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=42, rightMargin=42, topMargin=40, bottomMargin=36,
    )
    doc.build(elementos)
    return buffer.getvalue()


# =============================================================
# ENVÍO SMTP
# =============================================================

def _enviar_correo(destinatario: str, asunto: str, html: str, adjunto_pdf: bytes, nombre_adjunto: str):
    """Manda un correo con cuerpo HTML y un PDF adjunto vía SMTP (Gmail)."""
    if not config.smtp_usuario or not config.smtp_contrasena:
        raise RuntimeError("SMTP no configurado (revisa SMTP_USUARIO / SMTP_CONTRASENA en .env)")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = asunto
    msg["From"] = config.smtp_usuario
    msg["To"] = destinatario

    msg.attach(MIMEText(html, "html"))

    parte_pdf = MIMEApplication(adjunto_pdf, _subtype="pdf")
    parte_pdf.add_header("Content-Disposition", "attachment", filename=nombre_adjunto)
    msg.attach(parte_pdf)

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
        server.starttls()
        server.login(config.smtp_usuario, config.smtp_contrasena)
        server.send_message(msg)


def _fila_html(label: str, valor: str) -> str:
    return f"""
    <tr>
      <td style="padding:6px 0;color:#888;font-size:13px;">{label}</td>
      <td style="padding:6px 0;text-align:right;font-weight:600;color:#1a1a2e;font-size:13px;">{valor}</td>
    </tr>"""


def _armar_html(sucursal_nombre: str, fecha_label: str, corte, ventas) -> str:
    """Cuerpo completo del correo, con las tablas de datos — el PDF adjunto
    incluye además las gráficas y el detalle de turnos."""
    secciones = ""

    if corte:
        c = corte["caja"]
        secciones += f"""
        <h2 style="font-family:'Playfair Display',serif;color:#6C0820;font-size:17px;margin:24px 0 10px;">
          Corte de caja — {fecha_label}
        </h2>
        <table style="width:100%;border-collapse:collapse;background:#FCE4EE;border-radius:10px;padding:14px;">
          {_fila_html("Fondo inicial", _money(c["fondo_inicial"]))}
          {_fila_html("Ventas en efectivo", _money(c["ventas_efectivo"]))}
          {_fila_html("Entradas", _money(c["entradas"]))}
          {_fila_html("Salidas", _money(c["salidas"]))}
          {_fila_html("Efectivo esperado en caja", _money(c["efectivo_esperado"]))}
          {_fila_html("Tickets del día", str(corte["num_tickets"]))}
          {_fila_html("Ventas totales del día", _money(corte["total_general"]))}
        </table>"""

    if ventas:
        top_cajeros = "".join(
            f"<li style='margin-bottom:4px;'>{c['nombre']}: {_money(c['total'])} ({c['tickets']} tickets)</li>"
            for c in ventas["cajeros"][:5]
        ) or "<li>Sin ventas registradas</li>"

        top_productos_html = "".join(
            f"<li style='margin-bottom:4px;'>{p['descripcion']} — {p['cantidad']} unidades</li>"
            for p in (ventas.get("top_productos") or [])[:10]
        ) or "<li>Sin productos vendidos</li>"

        secciones += f"""
        <h2 style="font-family:'Playfair Display',serif;color:#6C0820;font-size:17px;margin:24px 0 10px;">
          Resumen de ventas — {ventas['fecha_inicio']} a {ventas['fecha_fin']}
        </h2>
        <table style="width:100%;border-collapse:collapse;background:#FCE4EE;border-radius:10px;padding:14px;">
          {_fila_html("Total vendido", _money(ventas["total_ventas"]))}
          {_fila_html("Tickets totales", str(ventas["total_tickets"]))}
          {_fila_html("Ticket promedio", _money(ventas["ticket_promedio"]))}
          {_fila_html("Efectivo", _money(ventas["por_metodo"]["efectivo"]))}
          {_fila_html("Tarjeta", _money(ventas["por_metodo"]["tarjeta"]))}
        </table>
        <h3 style="font-size:14px;color:#3D5D91;margin:16px 0 6px;">Top cajeros</h3>
        <ul style="font-size:13px;color:#555;padding-left:18px;margin:0;">{top_cajeros}</ul>
        <h3 style="font-size:14px;color:#3D5D91;margin:16px 0 6px;">Top 10 productos más vendidos</h3>
        <ul style="font-size:13px;color:#555;padding-left:18px;margin:0;">{top_productos_html}</ul>"""
    return f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
      <h1 style="font-family:'Playfair Display',serif;color:#6C0820;font-size:20px;margin:0 0 4px;">
        {sucursal_nombre}
      </h1>
      <p style="color:#aaa;font-size:12px;margin:0 0 8px;">
        Reporte automático — SmartVenta &middot; también adjuntamos un PDF con gráficas y el detalle de turnos.
      </p>
      {secciones}
      <p style="color:#bbb;font-size:11px;margin-top:28px;">
        Este correo se generó automáticamente. Si no reconoces esta suscripción, contacta al administrador del sistema.
      </p>
    </div>"""


# =============================================================
# FUNCIÓN PRINCIPAL — arma y envía el reporte de UN destinatario
# =============================================================

def enviar_reporte_destinatario(destinatario: dict, sucursal_id: str, forzar_frecuencia: str):
    """
    Arma el PDF (corte + ventas, según lo que el destinatario tenga
    activado) y lo envía por correo. `destinatario` es una fila de
    destinatarios_reportes.
    `forzar_frecuencia`, si se indica ('diario' o 'semanal'), ignora la
    frecuencia guardada del destinatario solo para esta llamada — útil
    para el botón "Enviar resumen semanal" bajo demanda.
    """

    sucursal = (
        supabase.table("sucursales")
        .select("nombre")
        .eq("id", sucursal_id)
        .single()
        .execute()
    ).data or {}
    sucursal_nombre = sucursal.get("nombre", "SmartVenta")

    hoy = date.today()
    fecha_str = hoy.isoformat()

    corte = None
    if destinatario["recibe_corte"]:
        cajas = (
            supabase.table("cajas")
            .select("id")
            .eq("sucursal_id", sucursal_id)
            .execute()
        ).data or []
        cortes_cajas = [
            corte_services.corte_por_caja_dia(c["id"], sucursal_id, fecha_str)
            for c in cajas
        ]
        if cortes_cajas:
            corte = cortes_cajas[0]
            for otro in cortes_cajas[1:]:
                corte["total_general"] += otro["total_general"]
                corte["num_tickets"] += otro["num_tickets"]
                for k in corte["caja"]:
                    corte["caja"][k] += otro["caja"][k]

    frecuencia_usada = forzar_frecuencia

    ventas = None
    if destinatario["recibe_ventas"]:
        if frecuencia_usada == "semanal":
            # Semana actual: del lunes de esta semana hasta hoy (domingo).
            dias_desde_lunes = hoy.weekday()  # lunes=0 ... domingo=6
            inicio_semana = hoy - timedelta(days=dias_desde_lunes)
            inicio = inicio_semana.isoformat()
            fin_para_ventas = fecha_str
        else:
            inicio = fecha_str
            fin_para_ventas = fecha_str
        ventas = reporte_services.reporte_ventas(sucursal_id, inicio, fin_para_ventas)


    
    pdf_bytes = _armar_pdf(sucursal_nombre, fecha_str, corte, ventas)
    html = _armar_html(sucursal_nombre, fecha_str, corte, ventas)

    asunto = f"Reporte {frecuencia_usada} — {sucursal_nombre} — {fecha_str}"
    _enviar_correo(
        destinatario=destinatario["correo"],
        asunto=asunto,
        html=html,
        adjunto_pdf=pdf_bytes,
        nombre_adjunto=f"reporte_{fecha_str}.pdf",
    )


def enviar_reportes_pendientes():
    """
    Recorre todos los destinatarios activos y envía lo que les corresponda
    hoy: el diario (si tienen recibe_diario) todos los días, y el semanal
    (si tienen recibe_semanal) solo los domingos.
    """
    es_domingo = date.today().weekday() == 6  # lunes=0 ... domingo=6

    destinatarios = (
        supabase.table("destinatarios_reportes")
        .select("*")
        .eq("activo", True)
        .execute()
    ).data or []

    enviados, errores = 0, []
    for d in destinatarios:
        if d.get("recibe_diario"):
            try:
                enviar_reporte_destinatario(d, d["sucursal_id"], forzar_frecuencia="diario")
                enviados += 1
            except Exception as e:
                errores.append({"correo": d["correo"], "tipo": "diario", "error": str(e)})

        if d.get("recibe_semanal") and es_domingo:
            try:
                enviar_reporte_destinatario(d, d["sucursal_id"], forzar_frecuencia="semanal")
                enviados += 1
            except Exception as e:
                errores.append({"correo": d["correo"], "tipo": "semanal", "error": str(e)})
    return {"enviados": enviados, "errores": errores}