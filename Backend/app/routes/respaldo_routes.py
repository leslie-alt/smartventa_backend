from fastapi import APIRouter, Depends
from fastapi.responses import Response
from datetime import datetime, timezone

from app.core.deps import verificar_permiso
from app.services import respaldo_services

router = APIRouter()


@router.get("/json")
def respaldo_json(
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Descarga un respaldo completo en JSON de los datos de la sucursal."""
    contenido = respaldo_services.generar_respaldo_json(sucursal_id=usuario["sucursal_id"])
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nombre = f"respaldo_smartventa_{fecha}.json"
    return Response(
        content=contenido,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@router.get("/excel")
def respaldo_excel(
    usuario: dict = Depends(verificar_permiso("perm_administrar")),
):
    """Descarga un respaldo completo en Excel (una hoja por tabla) de los datos de la sucursal."""
    contenido = respaldo_services.generar_respaldo_excel(sucursal_id=usuario["sucursal_id"])
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nombre = f"respaldo_smartventa_{fecha}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )