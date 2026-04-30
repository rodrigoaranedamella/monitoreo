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
        registros_para_insertar = []

        for nombre in ESTACIONES:
            # Buscar el dispositivo en la respuesta
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Lógica de detección: Si se vio hace menos de 10 minutos está ONLINE
            is_on = (ahora_ms - last_seen) / 1000 < 600 

            # CRÍTICO: Solo insertamos si está conectado (is_on == True)
            if is_on:
                registros_para_insertar.append({
                    "device": nombre,
                    "estado": True,
                    "duracion_min": 5.0,
                    "timestamp": timestamp_chile
                })

        if registros_para_insertar:
            supabase.table("historial_conexiones").insert(registros_para_insertar).execute()
            print(f"✅ [{timestamp_chile}] Se registraron {len(registros_para_insertar)} estaciones ONLINE.")
        else:
            print(f"ℹ️ [{timestamp_chile}] Todas las estaciones están OFFLINE. No se enviaron datos.")

    except Exception as e:
        print(f"❌ Error en el worker: {e}")

if __name__ == "__main__":
    run_monitor()
