import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github
import os

# Secrets
API_TOKEN = os.getenv("ZT_API_TOKEN")
NETWORK_ID = os.getenv("ZT_NETWORK_ID")
G_TOKEN = os.getenv("G_TOKEN")
GITHUB_REPO = os.getenv("REPO_NAME")

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

def run_monitor():
    print("=== ZERO TIER MONITOR - VERSIÓN DEFINITIVA SIMPLE ===")
    
    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(REPO_NAME)
        ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
        print(f"Hora actual: {ahora}")

        # Cargar historial o crear nuevo
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
            print(f"Historial cargado: {len(df)} registros")
        except Exception:
            print("Creando nuevo historial por primera vez...")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # Consultar ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"}
        ).json()

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            is_on = ((time.time() * 1000 - last_seen) / 1000) < 900

            print(f"{nombre:20} → {'🟢 ONLINE' if is_on else '🔴 OFFLINE'}")

            # Lógica simple
            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                if df.at[idx, 'estado'] == is_on and df.at[idx, 'timestamp'].date() == ahora.date():
                    diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                    df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            nuevo = pd.DataFrame([{'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}])
            df = pd.concat([df, nuevo], ignore_index=True)

        # Guardar
        df = df.sort_values(['device', 'timestamp']).reset_index(drop=True)
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        new_content = df.to_json(orient='records')

        if contents:
            repo.update_file(
                path=HISTORIAL_FILE,
                message=f"Auto-Monitor {ahora.strftime('%H:%M')}",
                content=new_content,
                sha=contents.sha
            )
        else:
            repo.create_file(
                path=HISTORIAL_FILE,
                message="Inicializando historial_conexiones.json",
                content=new_content
            )

        print("✅ HISTORIAL GUARDADO CON ÉXITO")

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__} - {e}")
        raise

if __name__ == "__main__":
    run_monitor()
