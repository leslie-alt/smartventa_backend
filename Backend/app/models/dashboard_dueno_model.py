"""Modelos del dashboard de la dueña (RF-14: acceso remoto de consulta)."""

from uuid import UUID
from pydantic import BaseModel


class MetodoPago(BaseModel):
    metodo: str
    total: float


class VentaPorHora(BaseModel):
    hora: int
    total: float
    cantidad: int


class ProductoTop(BaseModel):
    producto_id: UUID
    nombre: str
    cantidad_vendida: int
    ganancia: float


class AlertaInventario(BaseModel):
    producto_id: UUID
    nombre: str
    cantidad_actual: int
    inventario_minimo: int


class ResumenSucursal(BaseModel):
    sucursal_id: UUID
    sucursal_nombre: str
    dinero_actual: float
    ventas_bruto: float
    descuentos_total: float
    ventas_neto: float
    ventas_cantidad: int
    ticket_promedio: float
    ganancia: float
    margen_porcentaje: float
    entradas: float
    salidas: float
    devoluciones_total: float
    devoluciones_cantidad: int
    canceladas_cantidad: int
    metodos_pago: list[MetodoPago]
    ventas_por_hora: list[VentaPorHora]
    top_productos: list[ProductoTop]
    alertas_inventario: list[AlertaInventario]
    alertas_inventario_cantidad: int
    venta_semana_pasada: float



class ResumenDueno(BaseModel):
    consolidado: ResumenSucursal
    sucursales: list[ResumenSucursal]

class VentaDia(BaseModel):
    id: UUID
    folio: int
    total: float
    metodo_pago_principal: str
    creado_en: str
    sucursal_id: UUID
    sucursal_nombre: str | None = None


class ArticuloVenta(BaseModel):
    nombre: str
    cantidad: int
    precio_unitario: float
    descuento: float
    cantidad_devuelta: int


class DetalleVenta(BaseModel):
    venta_id: UUID
    articulos: list[ArticuloVenta]


class ProductoFaltante(BaseModel):
    producto_id: UUID
    nombre: str
    cantidad_actual: int
    inventario_minimo: int
    sucursal_id: UUID
    sucursal_nombre: str