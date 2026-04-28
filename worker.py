import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github
import os
import traceback
import sys

# Configuración de variables
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
    print(f"--- DIAGNÓSTICO INICIAL ---")
    print(f"Repositorio objetivo: {GITHUB_REPO}")
    print(f"Network ID: {NETWORK_ID}")
    
    if not G_TOKEN:
        print("❌ ERROR: G_TOKEN está vacío. Revisa tus secrets.")
        sys.exit(1)

    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ)
        
        # 1. Cargar historial
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            decoded = base64.b64decode(contents.content).decode('utf-8')
            df = pd.DataFrame(json.loads(decoded))
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"✅ Historial cargado: {len(df)} registros.")
        except Exception as e:
            print(f"ℹ️ Creando historial nuevo (No se encontró el archivo {HISTORIAL_FILE})")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # 2. ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"},
            timeout=15
        ).json()

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            is_on = ((time.time() * 1000 - last_seen) / 1000) < 900

            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                if df.at[idx, 'estado'] == is_on:
                    diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                    df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            nuevo = pd.DataFrame([{
                'timestamp': ahora.isoformat(),
                'estado': is_on,
                'duracion_min': 0.1,
                'device': nombre
            }])
            df = pd.concat([df, nuevo], ignore_index=True)

        # 3. Guardar con codificación forzada UTF-8
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        json_output = df.to_json(orient='records', force_ascii=False)

        if contents:
            repo.update_file(
                path=HISTORIAL_FILE,
                message=f"Log {ahora.strftime('%H:%M')}",
                content=json_output,
                sha=contents.sha
            )
        else:
            repo.create_file(
                path=HISTORIAL_FILE,
                message="Primer registro de historial",
                content=json_output
            )
        print("✅ PROCESO FINALIZADO CON ÉXITO")

    except Exception as e:
        print("\n--- DETALLE DEL ERROR ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_monitor()
