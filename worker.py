import os
import requests
import time
from datetime import datetime
import pytz
from supabase import create_client

# Configuración desde GitHub Secrets
ZT_API_TOKEN = os.getenv("ZT_API_TOKEN")
ZT_NETWORK_ID = os.getenv("ZT_NETWORK_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_monitor():
    try:
        # Consulta a ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=15
        ).json()

        ahora_ms = time.time() * 1000
        timestamp_chile = datetime.now(tz).isoformat()
        datos_a_insertar = []

        for nombre in ESTACIONES:
            # Buscar el dispositivo por nombre
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Si se vio hace menos de 15 min, está ONLINE (ampliamos el margen para persistencia)
            is_on = (ahora_ms - last_seen) / 1000 < 900 

            # IMPORTANTE: Solo registramos si está conectado para no ensuciar la BDD
            if is_on:
                datos_a_insertar.append({
                    "device": nombre,
                    "estado": True,
                    "duracion_min": 5.0,
                    "timestamp": timestamp_chile
                })

        if datos_a_insertar:
            supabase.table("historial_conexiones").insert(datos_a_insertar).execute()
            print(f"✅ [{timestamp_chile}] Se grabaron {len(datos_a_insertar)} estaciones online.")
        else:
            print(f"ℹ️ [{timestamp_chile}] Nadie detectado online.")

    except Exception as e:
        print(f"❌ Error en el worker: {e}")

if __name__ == "__main__":
    run_monitor()
