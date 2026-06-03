# core/database.py
# Cliente de Supabase para el backend de SmartVenta
# Usa service_role key para bypasear RLS en operaciones administrativas

from supabase import create_client, Client
from app.core.config import config

# ---------------------------------------------------------------
# Cliente ADMINISTRATIVO (service_role key)
# Úsalo en todos los servicios del backend
# Bypasea RLS — tiene acceso total a todas las tablas
# NUNCA expongas esta key en el frontend
# ---------------------------------------------------------------
supabase: Client = create_client(
    config.supabase_url,
    config.supabase_key
)