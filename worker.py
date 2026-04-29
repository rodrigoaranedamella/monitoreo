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

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

def run_monitor():
    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ)
        
        # Cargar historial existente
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            decoded = base64.b64decode(contents.content).decode('utf-8')
            data = json.loads(decoded)
            df = pd.DataFrame(data)
            # CORRECCIÓN AQUÍ: Usamos format='ISO8601' para que acepte cualquier variante de fecha
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
        except Exception as e:
            print(f"Iniciando nuevo historial o error leve: {e}")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # Consultar ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"},
            timeout=15
        ).json()

        nuevos_registros = []
        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            # Margen de 15 min
            is_on = ((time.time() * 1000 - last_seen) / 1000) < 900

            nuevos_registros.append({
                'timestamp': ahora.isoformat(),
                'estado': is_on,
                'duracion_min': 5.0,
                'device': nombre
            })

        # Consolidar y mantener solo los últimos 2000 para no saturar el archivo
        df_nuevos = pd.DataFrame(nuevos_registros)
        df_nuevos['timestamp'] = pd.to_datetime(df_nuevos['timestamp'])
        
        df = pd.concat([df, df_nuevos], ignore_index=True).tail(2000)
        
        # Guardar en formato ISO estándar para evitar errores futuros
        json_output = df.to_json(orient='records', date_format='iso')

        if contents:
            repo.update_file(HISTORIAL_FILE, f"Check {ahora.strftime('%H:%M')}", json_output, contents.sha)
        else:
            repo.create_file(HISTORIAL_FILE, "Init Historial", json_output)
        
        print(f"✅ Historial actualizado con éxito a las {ahora.strftime('%H:%M:%S')}")

    except Exception as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_monitor()
