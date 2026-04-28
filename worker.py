import pandas as pd
import requests
import time
import pytz
import json
import base64
import os
from github import Github
from datetime import datetime

# Configuración desde Secrets de GitHub
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
    
    # Leer historial actual
    try:
        contents = repo.get_contents(HISTORIAL_FILE)
        df = pd.DataFrame(json.loads(base64.b64decode(contents.content)))
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
    except:
        # Si no existe, crear vacío
        df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])

    # Consultar ZeroTier (usamos lastSeen que es el campo actual)
    res = requests.get(
        f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
        headers={'Authorization': f'token {API_TOKEN}'}
    ).json()

    nuevos_registros = []

    for nombre in ESTACIONES:
        m = next((item for item in res if item.get('name') == nombre), {})
        
        last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
        # Consideramos "online" si habló con el controlador en los últimos 5 minutos
        is_on = ((time.time() * 1000 - last_seen) / 1000) < 300  

        mask = df['device'] == nombre
        registros_device = df[mask].copy()
        
        if not registros_device.empty:
            idx = registros_device.index[-1]
            ultimo_estado = df.at[idx, 'estado']
            ultimo_ts = df.at[idx, 'timestamp']
            
            if ultimo_estado == is_on and ultimo_ts.date() == ahora.date():
                # Actualizar duración
                diff = (ahora - ultimo_ts).total_seconds() / 60
                df.at[idx, 'duracion_min'] = round(max(diff, 0.1), 2)
            else:
                # Nuevo evento (cambio de estado o nuevo día)
                nuevo = {'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}
                nuevos_registros.append(nuevo)
        else:
            # Primera vez para este dispositivo
            nuevo = {'timestamp': ahora, 'estado': is_on, 'duracion_min': 0.1, 'device': nombre}
            nuevos_registros.append(nuevo)

    if nuevos_registros:
        df = pd.concat([df, pd.DataFrame(nuevos_registros)], ignore_index=True)

    # Guardar en GitHub
    df_sorted = df.sort_values(['device', 'timestamp'])
    df_sorted['timestamp'] = df_sorted['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    
    new_content = df_sorted.to_json(orient='records')
    
    if 'contents' in locals():
        repo.update_file(
            path=contents.path,
            message=f"Auto-Monitor: {ahora.strftime('%Y-%m-%d %H:%M')}",
            content=new_content,
            sha=contents.sha
        )
    else:
        repo.create_file(
            path=HISTORIAL_FILE,
            message="Inicializando historial_conexiones.json",
            content=new_content
        )

if __name__ == "__main__":
    run_monitor()
