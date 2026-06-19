import time, sys
sys.path.insert(0, '.')
from app.core.database import supabase

inicio = time.time()
supabase.table('productos').select('id').limit(1).execute()
print(f'Query simple: {(time.time() - inicio)*1000:.0f}ms')

inicio = time.time()
supabase.table('productos').select('*').limit(1).execute()
print(f'SELECT completo: {(time.time() - inicio)*1000:.0f}ms')