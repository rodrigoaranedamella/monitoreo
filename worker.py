import pandas as pd
import requests
import time
import pytz
import json
import base64
import os
from github import Github
from datetime import datetime

API_TOKEN = os.getenv("ZT_API_TOKEN")
NETWORK_ID = os.getenv("ZT_NETWORK_ID")
G_TOKEN = os.getenv("G_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON"]

def run_monitor():
    g = Github(G_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    ahora = pd.Timestamp.now(tz=CHILE_TZ).floor('S')
    
    # Leer historial
    try:
        contents = repo.get_contents(HISTORIAL_FILE)
        df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
    except:
        df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])

    # Consultar ZeroTier
    res = requests.get(
        f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
        headers={'Authorization': f'token {API_TOKEN}'}
    ).json()

    for nombre in ESTACIONES:
        m = next((item for item in res if item.get('name') == nombre), {})
        
        # Usar lastSeen (campo recomendado actualmente)
        last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
        segundos_desde_ultima = (time.time() * 1000 - last_seen) / 1000
        
        is_on = segundos_desde_ultima < 600   # 10 minutos (más tolerante)

        # Buscar último registro de este dispositivo
        mask = df['device'] == nombre
        if not df[mask].empty:
            idx = df[mask].index[-1]
            ultimo_estado = df.at[idx, 'estado']
            
            if ultimo_estado == is_on and df.at[idx, 'timestamp'].date() == ahora.date():
                diff = (ahora - df.at[idx, 'timestamp']).total_seconds() / 60
                df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                continue
        
        # Si cambió de estado o es primer registro del día
        nuevo = pd.DataFrame([{
            'timestamp': ahora,
            'estado': is_on,
            'duracion_min': 0.1,
            'device': nombre
        }])
        df = pd.concat([df, nuevo], ignore_index=True)

    # Guardar
    df = df.sort_values(['device', 'timestamp']).reset_index(drop=True)
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    
    new_content = df.to_json(orient='records')
    
    repo.update_file(
        path=HISTORIAL_FILE,
        message=f"Auto-Monitor: {ahora.strftime('%Y-%m-%d %H:%M')}",
        content=new_content,
        sha=contents.sha
    )

if __name__ == "__main__":
    run_monitor()
