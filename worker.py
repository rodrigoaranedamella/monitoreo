import requests
import time
import pytz
import json
import base64
import pandas as pd
from github import Github
import os

# Configuración de variables desde el entorno
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
    print(f"=== Iniciando monitoreo en {GITHUB_REPO} ===")
    
    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ahora = pd.Timestamp.now(tz=CHILE_TZ)
        
        # 1. Intentar cargar el historial existente
        try:
            contents = repo.get_contents(HISTORIAL_FILE)
            decoded = base64.b64decode(contents.content).decode('utf-8')
            data = json.loads(decoded)
            df = pd.DataFrame(data)
            # Asegurar que la columna de tiempo sea datetime
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"Historial cargado con {len(df)} registros.")
        except Exception as e:
            print(f"No se encontró historial previo o está vacío: {e}")
            df = pd.DataFrame(columns=['timestamp', 'estado', 'duracion_min', 'device'])
            contents = None

        # 2. Consultar la API de ZeroTier
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member",
            headers={"Authorization": f"token {API_TOKEN}"},
            timeout=15
        ).json()

        nuevos_registros = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            
            # Cálculo de estado: Online si se vio hace menos de 15 min (900 seg)
            segundos_inactivo = (time.time() * 1000 - last_seen) / 1000
            is_on = segundos_inactivo < 900

            print(f"{nombre:20} -> {'🟢 ONLINE' if is_on else '🔴 OFFLINE'}")

            # Lógica para no repetir registros innecesarios
            mask = df['device'] == nombre
            if not df[mask].empty:
                ultimo_idx = df[mask].index[-1]
                if df.at[ultimo_idx, 'estado'] == is_on:
                    # Si el estado no cambió, actualizamos duración
                    diff = (ahora - df.at[ultimo_idx, 'timestamp']).total_seconds() / 60
                    df.at[ultimo_idx, 'duracion_min'] = round(max(diff, 0.1), 2)
                    continue

            # Si el estado cambió o es nuevo, agregar registro
            nuevos_registros.append({
                'timestamp': ahora.isoformat(),
                'estado': is_on,
                'duracion_min': 0.1,
                'device': nombre
            })

        # 3. Consolidar y guardar
        if nuevos_registros:
            df_nuevos = pd.DataFrame(nuevos_registros)
            df_nuevos['timestamp'] = pd.to_datetime(df_nuevos['timestamp'])
            df = pd.concat([df, df_nuevos], ignore_index=True)

        # Limpiar formato de fechas para JSON
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
        json_output = df.to_json(orient='records')

        if contents:
            repo.update_file(
                path=HISTORIAL_FILE,
                message=f"Update monitor: {ahora.strftime('%H:%M')}",
                content=json_output,
                sha=contents.sha
            )
        else:
            repo.create_file(
                path=HISTORIAL_FILE,
                message="Create historial_conexiones.json",
                content=json_output
            )

        print("✅ Proceso completado exitosamente.")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        exit(1) # Forzar error en Actions si falla

if __name__ == "__main__":
    run_monitor()
