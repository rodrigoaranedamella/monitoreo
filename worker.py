import os
import requests
import time
from datetime import datetime, timedelta
import pytz
from supabase import create_client

# Configuración
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
ZT_API_TOKEN = os.environ.get("ZT_API_TOKEN")
ZT_NETWORK_ID = os.environ.get("ZT_NETWORK_ID")

supabase = create_client(URL, KEY)
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def run_worker():
    ahora = datetime.now(tz)
    # VERIFICACIÓN: ¿La App grabó algo en los últimos 14 minutos?
    hace_14_min = (ahora - timedelta(minutes=14)).isoformat()
    
    check = supabase.table("historial_conexiones") \
        .select("id") \
        .gte("timestamp", hace_14_min) \
        .limit(1).execute()

    if not check.data:
        print("App.py inactiva. Backend iniciando grabación de respaldo...")
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"}
        ).json()

        timestamp_chile = ahora.isoformat()
        datos_a_insertar = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('last_seen' if 'last_seen' in m else 'lastSeen', 0)
            
            if (time.time() * 1000 - last_seen) / 1000 < 900:
                datos_a_insertar.append({
                    "device": nombre, "estado": True,
                    "duracion_min": 15.0, "timestamp": timestamp_chile
                })
        
        if datos_a_insertar:
            supabase.table("historial_conexiones").insert(datos_a_insertar).execute()
            print(f"Respaldo exitoso: {len(datos_a_insertar)} dispositivos.")
    else:
        print("App.py está activa. El Backend se mantiene en espera.")

if __name__ == "__main__":
    run_worker()
