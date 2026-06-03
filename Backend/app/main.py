from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import config
from app.routes.auth_routes import router as router_auth

app = FastAPI(
    title="SmartVenta — Maquillaje y más Jean",
    description="Sistema de punto de venta para dos sucursales independientes.",
    version="1.0.0"
)

# CORS: permite que el frontend HTML/JS consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Routers (se irán agregando por módulo) ---
# from app.routes.productos import router as router_productos
# app.include_router(router_productos, prefix="/productos", tags=["Productos"])


@app.get("/", tags=["Status"])
def raiz():
    """Verifica que el servidor esté corriendo."""
    return {"status": "ok", "sistema": "SmartVenta"}

app.include_router(router_auth, prefix="/auth", tags=["Autenticación"])

