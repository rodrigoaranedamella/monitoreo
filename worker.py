import pandas as pd
import requests
import time
import pytz
import json
import base64
import os
from github import Github

# Secrets
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
    print("🚀 Iniciando ZeroTier Monitor...")
    print(f"📍 Repositorio: {GITHUB_REPO}")
    print(f"🔑 ZT_NETWORK_ID: {NETWORK_ID[:10]}... (longitud: {len(NETWORK_ID) if NETWORK_ID else 0})")

    try:
        # 1. Conexión a GitHub
        print("🔗 Conectando a GitHub...")
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        print("✅ Conexión a GitHub exitosa")

        ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
        print(f"🕒 Hora actual: {ahora}")

        # 2. Leer o crear historial
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            raw = base64.b64decode(contents.content).decode('utf-8')
            df = pd.DataFrame(json.loads(raw))
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
            print(f"📂 Historial cargado con {len(df)} registros")
        except Exception as e:
            print(f"⚠️ No se encontró historial o error al leerlo: {e}")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None
            print("🆕 Se creará un nuevo historial")

        # 3. Consultar ZeroTier
        print("🌐 Consultando API de ZeroTier...")
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
            headers={'Authorization': f'token {API_TOKEN}'}
        )
        print(f"📡 Respuesta ZeroTier: código {res.status_code}")

        if res.status_code != 200:
            print(f"❌ Error en ZeroTier API: {res.text}")
            raise Exception(f"ZeroTier API error: {res.status_code}")

        members = res.json()

        # 4. Procesar cada estación
        for nombre in ESTACIONES:
            m = next((item for item in members if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            segundos_off = (time.time() * 1000 - last_seen) / 1000
            is_on = segundos_off < 600

            status = "🟢 ONLINE" if is_on else "🔴 OFFLINE"
            print(f"   {nombre:20} → {status} (última vez hace {int(segundos_off)} seg)")

            # Lógica de actualización
            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                if df.at[idx, 'estado'] == is_on and df.at[idx, 'timestamp'].date() == ahora.date():
                    diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                    df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            # Nuevo registro
            nuevo = pd.DataFrame([{'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}])
            df = pd.concat([df, nuevo], ignore_index=True)

        # 
