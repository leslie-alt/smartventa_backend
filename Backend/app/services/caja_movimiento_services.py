# caja_movimiento_services.py
from fastapi import HTTPException
from app.core.database import supabase


def registrar_movimiento(
    turno_id: str, caja_id: str, sucursal_id: str, usuario_id: str,
    tipo_movimiento: str, monto: float, notas: str | None,
) -> dict:
    try:
        resultado = supabase.rpc(
            "registrar_movimiento_caja_manual",
            {
                "p_turno_id": turno_id,
                "p_caja_id": caja_id,
                "p_sucursal_id": sucursal_id,
                "p_usuario_id": usuario_id,
                "p_tipo_movimiento": tipo_movimiento,
                "p_monto": monto,
                "p_notas": notas,
            },
        ).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo registrar el movimiento de caja.")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo registrar el movimiento de caja.")
    return resultado.data