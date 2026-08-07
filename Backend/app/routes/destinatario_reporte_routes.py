from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import verificar_permiso
from app.models.destinatario_reporte_model import (
    DestinatarioCreate, DestinatarioUpdate, DestinatarioOut,
    DestinatarioList, ResultadoEnvio,
)
from app.services import destinatario_reporte_services, reporte_email_services

router = APIRouter()


@router.get("/", response_model=DestinatarioList)
def listar(usuario: dict = Depends(verificar_permiso("perm_administrar"))):
    """Lista los destinatarios de reportes de la sucursal."""
    return destinatario_reporte_services.listar_destinatarios(usuario["sucursal_id"])


@router.post("/", response_model=DestinatarioOut)
def crear(
    datos: DestinatarioCreate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Agrega un nuevo destinatario de reportes."""
    return destinatario_reporte_services.crear_destinatario(
        datos=datos.model_dump(),
        sucursal_id=usuario["sucursal_id"],
    )


@router.put("/{destinatario_id}", response_model=DestinatarioOut)
def actualizar(
    destinatario_id: UUID,
    datos: DestinatarioUpdate,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Actualiza un destinatario (correo, qué recibe, frecuencia, activo)."""
    return destinatario_reporte_services.actualizar_destinatario(
        destinatario_id=str(destinatario_id),
        datos=datos.model_dump(exclude_none=True),
        sucursal_id=usuario["sucursal_id"],
    )


@router.delete("/{destinatario_id}")
def eliminar(
    destinatario_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Elimina un destinatario de reportes."""
    return destinatario_reporte_services.eliminar_destinatario(
        destinatario_id=str(destinatario_id),
        sucursal_id=usuario["sucursal_id"],
    )


@router.post("/{destinatario_id}/enviar-ahora")
def enviar_ahora(
    destinatario_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Envía el resumen DIARIO a un destinatario de inmediato (prueba/consulta bajo demanda)."""
    destinatario = destinatario_reporte_services.obtener_destinatario(
        destinatario_id=str(destinatario_id),
        sucursal_id=usuario["sucursal_id"],
    )
    reporte_email_services.enviar_reporte_destinatario(
        destinatario, usuario["sucursal_id"], forzar_frecuencia="diario",
    )
    return {"mensaje": f"Reporte diario enviado a {destinatario['correo']}."}

@router.post("/{destinatario_id}/enviar-ahora-semanal")
def enviar_ahora_semanal(
    destinatario_id: UUID,
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Envía el resumen SEMANAL a un destinatario de inmediato (prueba/consulta bajo demanda)."""
    destinatario = destinatario_reporte_services.obtener_destinatario(
        destinatario_id=str(destinatario_id),
        sucursal_id=usuario["sucursal_id"],
    )
    reporte_email_services.enviar_reporte_destinatario(
        destinatario, usuario["sucursal_id"], forzar_frecuencia="semanal",
    )
    return {"mensaje": f"Resumen semanal enviado a {destinatario['correo']}."}
@router.post("/enviar-pendientes", response_model=ResultadoEnvio)
def enviar_pendientes(
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """
    Dispara manualmente el envío de todos los reportes pendientes del día
    (misma lógica que corre automáticamente el scheduler).
    """
    return reporte_email_services.enviar_reportes_pendientes()