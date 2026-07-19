from fastapi import APIRouter, Depends
from app.core.deps import verificar_permiso
from app.services import reporte_services

router = APIRouter()


@router.get("/")
def consultar_reporte(
    fecha_inicio: str,
    fecha_fin: str,
    usuario: dict = Depends(verificar_permiso("perm_reportes")),
):
    """
    Reporte de ventas del periodo para la sucursal del usuario.
    Requiere permiso perm_reportes.
    """
    return reporte_services.reporte_ventas(
        sucursal_id=usuario["sucursal_id"],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )