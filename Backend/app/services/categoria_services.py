from app.core.database import supabase
from app.core.exceptions import ErrorNoEncontrado, ErrorConflicto


def _registrar_auditoria(
    usuario_id: str,
    sucursal_id: str,
    accion: str,
    registro_id: str,
    valores_anteriores: dict | None,
    valores_nuevos: dict | None,
):
    supabase.table("auditoria").insert({
        "usuario_id": usuario_id,
        "sucursal_id": sucursal_id,
        "modulo": "categorias",
        "accion": accion,
        "registro_id": registro_id,
        "valores_anteriores": valores_anteriores,
        "valores_nuevos": valores_nuevos,
    }).execute()


def obtener_categorias(sucursal_id: str) -> list[dict]:
    """Retorna todas las categorías activas de la sucursal con conteo de productos."""
    respuesta = (
        supabase.table("categorias")
        .select("*, productos(count)")
        .eq("sucursal_id", sucursal_id)
        .eq("activo", True)
        .order("nombre")
        .execute()
    )
    categorias = []
    for cat in (respuesta.data or []):
        total = cat.get("productos", [{}])
        categorias.append({
            **{k: v for k, v in cat.items() if k != "productos"},
            "total_productos": total[0].get("count", 0) if total else 0,
        })
    return categorias


def obtener_categoria_por_id(categoria_id: str, sucursal_id: str) -> dict:
    """Retorna una categoría verificando que pertenezca a la sucursal."""
    respuesta = (
        supabase.table("categorias")
        .select("*")
        .eq("id", categoria_id)
        .eq("sucursal_id", sucursal_id)
        .single()
        .execute()
    )
    if not respuesta.data:
        raise ErrorNoEncontrado("Categoría")
    return respuesta.data


def crear_categoria(nombre: str, sucursal_id: str, usuario_id: str) -> dict:
    """Crea una categoría verificando que no exista el mismo nombre en la sucursal."""
    existente = (
        supabase.table("categorias")
        .select("id")
        .eq("sucursal_id", sucursal_id)
        .eq("nombre", nombre)
        .execute()
    )
    if existente.data:
        raise ErrorConflicto(f"Ya existe una categoría con el nombre '{nombre}' en esta sucursal.")

    respuesta = supabase.table("categorias").insert({
        "nombre": nombre,
        "sucursal_id": sucursal_id,
        "activo": True,
    }).execute()

    categoria = respuesta.data[0]

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="crear_categoria",
        registro_id=categoria["id"],
        valores_anteriores=None,
        valores_nuevos=categoria,
    )
    return categoria


def actualizar_categoria(
    categoria_id: str,
    datos: dict,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """Actualiza nombre o estado de una categoría."""
    anterior = obtener_categoria_por_id(categoria_id, sucursal_id)

    # Verificar nombre único si se está cambiando
    if datos.get("nombre") and datos["nombre"] != anterior["nombre"]:
        existente = (
            supabase.table("categorias")
            .select("id")
            .eq("sucursal_id", sucursal_id)
            .eq("nombre", datos["nombre"])
            .neq("id", categoria_id)
            .execute()
        )
        if existente.data:
            raise ErrorConflicto(f"Ya existe una categoría con el nombre '{datos['nombre']}'.")

    respuesta = (
        supabase.table("categorias")
        .update(datos)
        .eq("id", categoria_id)
        .execute()
    )
    actualizado = respuesta.data[0]

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="actualizar_categoria",
        registro_id=categoria_id,
        valores_anteriores=anterior,
        valores_nuevos=actualizado,
    )
    return actualizado


def eliminar_categoria(
    categoria_id: str,
    sucursal_id: str,
    usuario_id: str,
) -> dict:
    """
    Soft delete de categoría (activo = False).
    No elimina el registro para mantener integridad con productos existentes.
    """
    anterior = obtener_categoria_por_id(categoria_id, sucursal_id)

    # Verificar si tiene productos activos asignados
    productos_activos = (
        supabase.table("productos")
        .select("id")
        .eq("categoria_id", categoria_id)
        .eq("activo", True)
        .execute()
    )
    if productos_activos.data:
        raise ErrorConflicto(
            f"No se puede desactivar la categoría porque tiene "
            f"{len(productos_activos.data)} producto(s) activo(s) asignados."
        )

    supabase.table("categorias").update({"activo": False}).eq("id", categoria_id).execute()

    _registrar_auditoria(
        usuario_id=usuario_id,
        sucursal_id=sucursal_id,
        accion="eliminar_categoria",
        registro_id=categoria_id,
        valores_anteriores=anterior,
        valores_nuevos={"activo": False},
    )
    return {"mensaje": "Categoría desactivada correctamente."}