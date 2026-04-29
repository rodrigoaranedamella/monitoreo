import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github
import os
import sys

# Configuración
API_TOKEN = os.getenv("ZT_API_TOKEN")
NETWORK_ID = os.getenv("ZT_NETWORK_ID")
G_TOKEN = os.getenv("G_TOKEN")
GITHUB_REPO = os.getenv("REPO_NAME")
CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def run_monitor():
    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ)
        
        # 1. Consultar ZeroTier primero (así tenemos datos frescos)
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"},
            timeout=15
        ).json()

        # 2. Intentar leer y escribir con reintentos (para evitar errores de SHA)
        for intento in range(3):
            try:
                contents = repo.get_contents(HISTORIAL_FILE)
                decoded = base64.b64decode(contents.content).decode('utf-8')
                data = json.loads(decoded)
                df = pd.DataFrame(data)
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
                
                nuevos_registros = []
                for nombre in ESTACIONES:
                    m = next((item for item in res if item.get('name') == nombre), {})
                    last_seen = m.get('lastSeen', 0)
                    is_on = ((time.time() * 1000 - last_seen) / 1000) < 900

                    nuevos_registros.append({
                        'timestamp': ahora.isoformat(),
                        'estado': is_on,
                        'duracion_min': 5.0,
                        'device': nombre
                    })

                df_nuevos = pd.DataFrame(nuevos_registros)
                df = pd.concat([df, df_nuevos], ignore_index=True).tail(2000)
                json_output = df.to_json(orient='records', date_format='iso')

                # Intentar actualizar[cite: 5]
                repo.update_file(
                    HISTORIAL_FILE, 
                    f"Check {ahora.strftime('%H:%M')}", 
                    json_output, 
                    contents.sha
                )
                print(f"✅ Grabado en el intento {intento + 1}")
                break # Si tiene éxito, salimos del bucle de reintentos
            except Exception as e:
                print(f"⚠️ Intento {intento + 1} falló: {e}")
                time.sleep(5) # Esperar 5 segundos antes de reintentar
        
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_monitor()
