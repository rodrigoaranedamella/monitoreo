import streamlit as st
import pandas as pd
import pytz
import requests
import time
from streamlit_autorefresh import st_autorefresh # Recomendado instalar esta librería

# Configuración de página
st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

# 1. REFRESCO AUTOMÁTICO (Cada 2 minutos = 120,000 milisegundos)
# Si no tienes instalada la librería 'streamlit-autorefresh', 
# puedes usar el método de JavaScript que corregí abajo.
count = st_autorefresh(interval=120000, key="frefresher")

CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

st.title("📊 Centro de Monitoreo SanLeon")

# ====================== LÓGICA DE ESTADO ACTUAL ======================
@st.cache_data(ttl=30, show_spinner=False)
def obtener_estado_actual():
    try:
        API_TOKEN = st.secrets["ZT_API_TOKEN"]
        NETWORK_ID = st.secrets["ZT_NETWORK_ID"]
        
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
            headers={'Authorization': f'token {API_TOKEN}'}
        )
        members = res.json()

        estado_actual = []
        for nombre in ESTACIONES:
            m = next((item for item in members if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            
            segundos_inactivo = (time.time() * 1000 - last_seen) / 1000
            is_online = segundos_inactivo < 900  # 15 minutos

            ultima_conexion = pd.to_datetime(last_seen, unit='ms', utc=True).tz_convert(CHILE_TZ) if last_seen > 0 else None
            
            # Formatear la fecha con color si está online
            fecha_str = ultima_conexion.strftime('%Y-%m-%d %H:%M:%S') if ultima_conexion else "Nunca"
            
            estado_actual.append({
                'Estación': nombre,
                'Estado': "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                'Última conexión': f"✅ {fecha_str}" if is_online else fecha_str,
                'Inactivo hace': f"{int(segundos_inactivo/60)} min" if segundos_inactivo > 60 else f"{int(segundos_inactivo)} seg"
            })

        return pd.DataFrame(estado_actual)
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# Mostrar Tabla
estado_df = obtener_estado_actual()
if not estado_df.empty:
    # Usamos st.table o formateamos el dataframe para que se vea el emoji ✅ en la fecha
    st.dataframe(estado_df, use_container_width=True, hide_index=True)

# ====================== SCRIPT DE REFRESCO (BACKUP) ======================
# Este script asegura que el navegador recargue la página cada 120 segundos
st.markdown(f"""
    <script>
        setTimeout(function(){{
            window.location.reload();
        }}, 120000);
    </script>
""", unsafe_allow_html=True)

st.caption(f"🔄 Última actualización del dashboard: {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')} • Refresco cada 2 min")
