import os
import requests
import time
from datetime import datetime, timedelta
import pytz
from supabase import create_client

# Configuración desde variables de entorno (GitHub Secrets)
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
ZT_API_TOKEN = os.environ.get("ZT_API_TOKEN")
ZT_NETWORK_ID = os.environ.get("ZT_NETWORK_ID")

supabase = create_client(URL, KEY)
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def run_worker():
    ahora = datetime.now(tz)
    # Verifica si la App grabó en los últimos 14 min
    hace_14_min = (ahora - timedelta(minutes=14)).isoformat()
    
    check = supabase.table("historial_conexiones").select("id").gte("timestamp", hace_14_min).limit(1).execute()

    if not check.data:
        print("App.py inactiva. Iniciando grabación de respaldo (15 min)...")
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"}
        ).json()

        timestamp_chile = ahora.isoformat()
        datos_a_insertar = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Si se vio hace menos de 15 min
            if (time.time() * 1000 - last_seen) / 1000 < 900:
                datos_a_insertar.append({
                    "device": nombre, 
                    "estado": True,
                    "duracion_min": 15.0, # Bloque de 15 min para continuidad
                    "timestamp": timestamp_chile
                })
        
        if datos_a_insertar:
            supabase.table("historial_conexiones").insert(datos_a_insertar).execute()
            print(f"Grabados {len(datos_a_insertar)} dispositivos.")
    else:
        print("La App ya registró datos recientemente. Backend en espera.")

if __name__ == "__main__":
    run_worker()
