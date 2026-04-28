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
GITHUB_REPO = os.getenv("REPO_NAME") # Mantenemos REPO_NAME como origen del env

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

def run_monitor():
    print("=== ZERO TIER MONITOR - VERSIÓN CORREGIDA ===")
    
    try:
        g = Github(G_TOKEN)
        # CORRECCIÓN AQUÍ: Usamos GITHUB_REPO que es la variable definida arriba
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
        print(f"Hora actual: {ahora}")

        # Cargar historial o crear nuevo
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
            df['timestamp'] = pd.to_datetime(df['timestamp'])
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

            # Lógica de actualización
            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                # Si el estado es igual, solo actualizamos duración
                if df.at[idx, 'estado'] == is_on:
                    diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                    df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            # Si el estado cambió, creamos nueva entrada
            nuevo = pd.DataFrame([{'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}])
            df = pd.concat([df, nuevo], ignore_index=True)

        # Guardar
        df = df.sort_values(['device', 'timestamp']).reset_index(drop=True)
        # Convertir a string para JSON
        df_save = df.copy()
        df_save['timestamp'] = df_save['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        new_content = df_save.to_json(orient='records')

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
