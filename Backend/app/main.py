# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import config
from app.core.database import supabase

from app.routes.auth_routes import router as router_auth
from app.routes.productos import router as router_productos
from app.routes.categoria import router as router_categorias
from app.routes.promociones import router as router_promociones
from app.routes.inventario import router as router_inventario
from app.routes.kardex import router as router_kardex
from app.routes import usuario_routes
from app.routes import caja_movimiento_router
from app.routes import turno_routes   # ← agregar
from app.routes import caja_routes
from app.routes import sucursal_routes   # ← agregar
from app.routes.venta_routes import router as router_ventas
from app.routes.cliente_routes import router as router_clientes
from app.routes import auditoria_routes
from app.routes import corte_routes
from app.routes import reporte_routes   # ← agregar

# --- Scheduler para mantener activa la conexión con Supabase ---
scheduler = AsyncIOScheduler()

async def ping_db():
    """Evita el cold start de Supabase Free haciendo un ping cada 4 minutos."""
    try:
        supabase.table("sucursales").select("id").limit(1).execute()
    except Exception:
        pass  # Silencioso — solo es keep-alive

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la app: inicia y detiene el scheduler."""
    scheduler.add_job(ping_db, "interval", minutes=4)
    scheduler.start()
    yield
    scheduler.shutdown()

# --- Aplicación principal ---
app = FastAPI(
    title="SmartVenta — Maquillaje y más Jean",
    description="Sistema de punto de venta para dos sucursales independientes.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: permite que el frontend HTML/JS consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", tags=["Status"])
def raiz():
    """Verifica que el servidor esté corriendo."""
    return {"status": "ok", "sistema": "SmartVenta"}

app.include_router(router_auth, prefix="/auth", tags=["Autenticación"])
app.include_router(router_productos, prefix="/productos", tags=["Productos"])
app.include_router(router_categorias, prefix="/categorias", tags=["Categorías"])
app.include_router(router_promociones, prefix="/promociones", tags=["Promociones"])
app.include_router(router_inventario, prefix="/inventario", tags=["Inventario"])
app.include_router(router_kardex, prefix="/kardex", tags=["Kardex"])
app.include_router(usuario_routes.router, prefix="/usuarios", tags=["Usuarios"])
app.include_router(caja_movimiento_router.router, prefix="/movimientos-caja", tags=["Movimientos de caja"])
app.include_router(turno_routes.router, prefix="/turnos", tags=["Turnos"])     
app.include_router(corte_routes.router, prefix="/cortes", tags=["Cortes"])
app.include_router(reporte_routes.router, prefix="/reportes", tags=["Reportes"])
app.include_router(caja_routes.router, prefix="/cajas", tags=["Cajas"])           
app.include_router(router_ventas, prefix="/ventas", tags=["Ventas"]) 
app.include_router(sucursal_routes.router, prefix="/sucursales", tags=["Sucursales"])
app.include_router(router_clientes, prefix="/clientes", tags=["Clientes"])
app.include_router(auditoria_routes.router, tags=["Auditoria"])