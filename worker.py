import os
import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github

API_TOKEN = os.getenv("ZT_API_TOKEN")
NETWORK_ID = os.getenv("ZT_NETWORK_ID")
G_TOKEN = os.getenv("G_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

def run_monitor():
    print("🚀 Iniciando ZeroTier Monitor - Versión Ultra Simple")

    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
        print(f"🕒 Hora: {ahora}")

        # Cargar historial o crear vacío
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
            print(f"📂 Historial cargado: {len(df)} registros")
        except:
            print("🆕 Creando nuevo historial...")
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

            print(f"   {nombre:25} → {'🟢 ONLINE' if is_on else '🔴 OFFLINE'}")

            # Actualizar duración o crear nuevo registro
            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                if df.at[idx, 'estado'] == is_on and df.at
