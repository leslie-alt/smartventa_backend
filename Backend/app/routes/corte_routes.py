from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.deps import verificar_permiso
from app.services import corte_services

router = APIRouter()


@router.get("/")
def consultar_corte(
    caja_id: UUID,
    fecha: str,
    usuario: dict = Depends(verificar_permiso("perm_corte_caja")),
):
    """
    Corte de caja de consulta: calcula al vuelo el corte de una caja
    en una fecha específica (AAAA-MM-DD). No cierra nada.
    Requiere permiso perm_corte_caja.
    """
    return corte_services.corte_por_caja_dia(
        caja_id=str(caja_id),
        sucursal_id=usuario["sucursal_id"],
        fecha=fecha,
    )