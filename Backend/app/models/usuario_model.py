from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class UsuarioCreate(BaseModel):
    """
    Ya no recibe rol_id — el backend crea automáticamente un rol exclusivo
    para este usuario (nombrado igual que nombre_usuario) con los permisos
    aquí indicados.
    """
    nombre_completo: str = Field(min_length=2, max_length=150)
    nombre_usuario: str = Field(min_length=3, max_length=60)
    contrasena: str = Field(min_length=6, max_length=72)
    perm_inventario_entrada: bool = False
    perm_inventario_ajuste: bool = False
    perm_kardex: bool = False
    perm_corte_caja: bool = False
    perm_modificar_precios: bool = False
    perm_cancelar_tickets: bool = False
    perm_clientes: bool = False
    perm_descuentos: bool = False
    perm_reportes: bool = False
    perm_exportar: bool = False
    perm_promociones: bool = False
    perm_administrar: bool = False
    perm_movimientos_caja: bool = False
    perm_devoluciones: bool = False
    perm_auditoria: bool = False
    perm_dueno: bool | None = None


class UsuarioUpdate(BaseModel):
    """
    nombre_completo/nombre_usuario se actualizan directo en 'usuarios'.
    Si se envía algún perm_*, se crea un ROL NUEVO con esos permisos y se
    reasigna rol_id — nunca se edita un rol existente (queda huérfano).
    """
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=150)
    nombre_usuario: str | None = Field(default=None, min_length=3, max_length=60)
    perm_inventario_entrada: bool | None = None
    perm_inventario_ajuste: bool | None = None
    perm_kardex: bool | None = None
    perm_corte_caja: bool | None = None
    perm_modificar_precios: bool | None = None
    perm_cancelar_tickets: bool | None = None
    perm_clientes: bool | None = None
    perm_descuentos: bool | None = None
    perm_reportes: bool | None = None
    perm_exportar: bool | None = None
    perm_promociones: bool | None = None
    perm_administrar: bool | None = None
    perm_movimientos_caja: bool | None = None
    perm_devoluciones: bool | None = None
    perm_auditoria: bool | None = None
    perm_dueno: bool | None = None


class UsuarioOut(BaseModel):
    id: UUID
    nombre_completo: str
    nombre_usuario: str
    activo: bool
    ultimo_login: datetime | None
    creado_en: datetime
    rol_id: UUID
    rol_nombre: str | None = None
    # Solo se llena cuando un usuario edita SUS PROPIOS permisos — permite
    # refrescar el JWT sin pedirle que vuelva a iniciar sesión. Si edita
    # los permisos de OTRO usuario, este campo queda None.
    nuevo_token: str | None = None
    perm_inventario_entrada: bool = False
    perm_inventario_ajuste: bool = False
    perm_kardex: bool = False
    perm_corte_caja: bool = False
    perm_modificar_precios: bool = False
    perm_cancelar_tickets: bool = False
    perm_clientes: bool = False
    perm_descuentos: bool = False
    perm_reportes: bool = False
    perm_exportar: bool = False
    perm_promociones: bool = False
    perm_administrar: bool = False
    perm_movimientos_caja: bool = False
    perm_devoluciones: bool = False
    perm_auditoria: bool = False
    perm_dueno: bool | None = None

    class Config:
        from_attributes = True


class UsuarioList(BaseModel):
    total: int
    items: list[UsuarioOut]