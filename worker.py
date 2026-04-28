import os
import requests
import time
import pytz
import json
import base64
import pandas as pd
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
    print("🚀 Iniciando ZeroTier Monitor (versión simple)")

    try:
        # 1. Conexión a GitHub
        print(f"🔑 Conectando a GitHub con G_TOKEN...")
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        print(f"✅ Conectado al repositorio: {GITHUB_REPO}")

        ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
        print(f"🕒 Hora actual: {ahora}")

        # 2. Leer o crear historial
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
            print(f"📂 Historial cargado con {len(df)} registros")
        except Exception as e:
            print(f"🆕 No existe historial o error al leerlo → Creando nuevo. Error: {e}")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # 3. Consultar ZeroTier
        print("🌐 Consultando ZeroTier API...")
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
            headers={'Authorization': f'token {API_TOKEN}'}
        )
        print(f"   Respuesta ZeroTier: {res.status_code}")

        if res.status_code != 200:
            print(f"❌ Error ZeroTier: {res.text[:500]}")
            raise Exception(f"ZeroTier error {res.status_code}")

        members = res.json()

        # 4. Procesar estaciones
        for nombre in ESTACIONES:
            m = next((item for item in members if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            is_on = ((time.time() * 1000 - last_seen) / 1000) < 900   # 15 minutos

            print(f"   {nombre:20} → {'🟢 ONLINE' if is_on else '🔴 OFFLINE'}")

            # Actualizar o crear registro
            mask = df['device'] == nombre
            if not df[mask].empty:
                idx = df[mask].index[-1]
                if df.at[idx, 'estado'] == is_on and df.at[idx, 'timestamp'].date() == ahora.date():
                    diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                    df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            nuevo = pd.DataFrame([{'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}])
            df = pd.concat([df, nuevo], ignore_index=True)

        # 5. Guardar
        df = df.sort_values(['device', 'timestamp']).reset_index(drop=True)
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        new_content = df.to_json(orient='records')

        if contents:
            repo.update_file(
                path=HISTORIAL_FILE,
                message=f"Auto-Monitor: {ahora.strftime('%H:%M')}",
                content=new_content,
                sha=contents.sha
            )
        else:
            repo.create_file(
                path=HISTORIAL_FILE,
                message="Inicializando historial_conexiones.json",
                content=new_content
            )

        print("🎉 ¡ÉXITO! Historial guardado correctamente.")

    except Exception as e:
        print(f"💥 ERROR CRÍTICO: {type(e).__name__} → {e}")
        raise   # Para que el workflow marque como fallido

if __name__ == "__main__":
    run_monitor()
