from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RolOut(BaseModel):
    id: UUID
    sucursal_id: UUID
    nombre: str
    perm_inventario_entrada: bool
    perm_inventario_ajuste: bool
    perm_kardex: bool
    perm_corte_caja: bool
    perm_modificar_precios: bool
    perm_cancelar_tickets: bool
    perm_clientes: bool
    perm_descuentos: bool
    perm_reportes: bool
    perm_exportar: bool
    perm_promociones: bool
    perm_administrar: bool
    perm_movimientos_caja: bool
    perm_devoluciones: bool
    perm_auditoria: bool
    creado_en: datetime

    class Config:
        from_attributes = True


class RolList(BaseModel):
    total: int
    items: list[RolOut]