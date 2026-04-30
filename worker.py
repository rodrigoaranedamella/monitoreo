import os
import requests
import time
from datetime import datetime
import pytz  # Asegúrate de que esté en tu requirements.txt
from supabase import create_client

# Configuración de zona horaria
tz = pytz.timezone('America/Santiago')

# ... (tus variables de entorno y cliente supabase se mantienen igual) ...

def run_monitor():
    try:
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=15
        ).json()

        # Generamos el timestamp con la zona horaria de Chile
        timestamp_ahora = datetime.now(tz).isoformat()
        ahora_ms = time.time() * 1000
        nuevos_registros = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            is_on = (ahora_ms - last_seen) / 1000 < 900

            nuevos_registros.append({
                "device": nombre,
                "estado": is_on,
                "duracion_min": 5.0,
                "timestamp": timestamp_ahora  # <--- FORZAMOS LA HORA DE CHILE
            })

        supabase.table("historial_conexiones").insert(nuevos_registros).execute()
        print(f"✅ Datos enviados con timestamp local: {timestamp_ahora}")

    except Exception as e:
        print(f"❌ Error: {e}")
