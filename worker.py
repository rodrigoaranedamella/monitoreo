import os
import requests
import time
from supabase import create_client

# Configuración desde GitHub Secrets
ZT_API_TOKEN = os.getenv("ZT_API_TOKEN")
ZT_NETWORK_ID = os.getenv("ZT_NETWORK_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Lista oficial de tus estaciones
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

# Conexión con Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_monitor():
    try:
        # 1. Consultar ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=15
        ).json()

        ahora_ms = time.time() * 1000
        nuevos_registros = []

        for nombre in ESTACIONES:
            # Buscar el dispositivo por nombre
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Criterio: Online si se vio en los últimos 15 min
            is_on = (ahora_ms - last_seen) / 1000 < 900

            nuevos_registros.append({
                "device": nombre,
                "estado": is_on,
                "duracion_min": 5.0
            })

        # 2. Insertar en la tabla de Supabase
        supabase.table("historial_connections").insert(nuevos_registros).execute()
        print(f"✅ Éxito: {len(nuevos_registros)} registros enviados a Supabase.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_monitor()
