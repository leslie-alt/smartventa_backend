# core/database.py
# Cliente de Supabase para el backend de SmartVenta
# Usa service_role key para bypasear RLS en operaciones administrativas

import httpx
from supabase import create_client, Client, ClientOptions
from app.core.config import config

# ---------------------------------------------------------------
# Cliente ADMINISTRATIVO (service_role key)
# Úsalo en todos los servicios del backend
# Bypasea RLS — tiene acceso total a todas las tablas
# NUNCA expongas esta key en el frontend
#
# http2=False: evita httpcore.ReadError [WinError 10035] intermitente
# en Windows, causado por incompatibilidades conocidas entre HTTP/2 y
# el manejo de sockets no bloqueantes de Windows. Con HTTP/1.1 el
# cliente es más lento por request individual, pero mucho más estable
# en este entorno — el error aparecía en endpoints aleatorios
# (categorías, clientes, ventas) sin relación con la lógica de negocio.
# ---------------------------------------------------------------
supabase: Client = create_client(
    config.supabase_url,
    config.supabase_key,
    options=ClientOptions(
        httpx_client=httpx.Client(http2=False, timeout=30.0)
    )
)