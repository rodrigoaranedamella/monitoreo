import os
import requests
import time
from supabase import create_client

# Configuración desde GitHub Secrets
ZT_API_TOKEN = os.getenv("ZT_API_TOKEN")
ZT_NETWORK_ID = os.getenv("ZT_NETWORK_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_monitor():
    try:
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=15
        ).json()

        ahora_ms = time.time() * 1000
        nuevos_registros = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            is_on = (ahora_ms - last_seen) / 1000 < 900

            nuevos_registros.append({
                "device": nombre,
                "estado": is_on,
                "duracion_min": 5.0
            })

        # USAMOS EL NOMBRE EXACTO: historial_conexiones
        supabase.table("historial_conexiones").insert(nuevos_registros).execute()
        print(f"✅ Datos enviados a Supabase con éxito.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_monitor()
