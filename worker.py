import os, requests, time, pytz
from datetime import datetime
from supabase import create_client

ZT_API_TOKEN = os.getenv("ZT_API_TOKEN")
ZT_NETWORK_ID = os.getenv("ZT_NETWORK_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_monitor():
    try:
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"}, timeout=15
        ).json()

        ahora_ms = time.time() * 1000
        timestamp_chile = datetime.now(tz).isoformat()
        datos_subir = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Margen de 10 min para ser más flexible
            if (ahora_ms - last_seen) / 1000 < 600: 
                datos_subir.append({
                    "device": nombre, "estado": True, "duracion_min": 5.0, "timestamp": timestamp_chile
                })

        if datos_subir:
            supabase.table("historial_conexiones").insert(datos_subir).execute()
            print(f"✅ [{timestamp_chile}] Registradas {len(datos_subir)} estaciones ONLINE.")
        else:
            print("ℹ️ Nadie online. No se inserta nada.")

    except Exception as e: print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_monitor()
