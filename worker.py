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

# Estaciones a monitorear
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_monitor():
    try:
        # 1. Obtener datos de ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=15
        ).json()

        ahora_ms = time.time() * 1000
        timestamp_chile = datetime.now(tz).isoformat()
        datos_para_subir = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('last_seen', m.get('lastSeen', 0))
            
            # Margen de 10 minutos para considerar ONLINE (600 segundos)
            is_on = (ahora_ms - last_seen) / 1000 < 600 

            # CRÍTICO: Solo insertamos si el estado es TRUE
            if is_on:
                datos_para_subir.append({
                    "device": nombre,
                    "estado": True,
                    "duracion_min": 5.0,
                    "timestamp": timestamp_chile
                })

        # 2. Guardar en Supabase solo si hay alguien online
        if datos_para_subir:
            supabase.table("historial_conexiones").insert(datos_para_subir).execute()
            print(f"✅ [{timestamp_chile}] Se registraron {len(datos_para_subir)} estaciones ONLINE.")
        else:
            print(f"ℹ️ [{timestamp_chile}] Nadie online. No se insertaron registros para mantener limpia la BDD.")

    except Exception as e:
        print(f"❌ Error en el worker: {e}")

if __name__ == "__main__":
    run_monitor()
