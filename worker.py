import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github
import os

# Configuración de Entorno
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
        
        # 1. Obtener datos actuales de ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"},
            timeout=15
        ).json()

        # 2. Leer historial actual del repositorio
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            decoded = base64.b64decode(contents.content).decode('utf-8')
            df = pd.DataFrame(json.loads(decoded))
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
        except:
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # 3. Procesar estados
        nuevos = []
        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            is_on = ((time.time() * 1000 - last_seen) / 1000) < 900 # Online si se vio hace menos de 15 min

            nuevos.append({
                'timestamp': ahora.isoformat(),
                'estado': is_on,
                'duracion_min': 5.0,
                'device': nombre
            })

        # 4. Consolidar y guardar (máximo 3000 registros para evitar pesadez)
        df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True).tail(3000)
        json_output = df.to_json(orient='records', date_format='iso')

        if contents:
            repo.update_file(HISTORIAL_FILE, f"Auto-check {ahora.strftime('%H:%M')}", json_output, contents.sha)
        else:
            repo.create_file(HISTORIAL_FILE, "Init", json_output)
        
        print(f"✅ Grabado con éxito: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_monitor()
