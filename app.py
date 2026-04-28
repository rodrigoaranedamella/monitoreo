import streamlit as st
import pandas as pd
import pytz
import requests
import json
import base64
import time

# Configuración
st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]
REPO_NAME = "rodrigoaranedamella/monitoreo"
HISTORIAL_FILE = 'historial_conexiones.json'

st.title("📊 Centro de Monitoreo SanLeon")

# ====================== 1. ESTADO EN TIEMPO REAL ======================
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
            is_online = segundos_inactivo < 900
            ultima_conexion = pd.to_datetime(last_seen, unit='ms', utc=True).tz_convert(CHILE_TZ) if last_seen > 0 else None
            
            fecha_str = ultima_conexion.strftime('%Y-%m-%d %H:%M:%S') if ultima_conexion else "Nunca"
            
            estado_actual.append({
                'Estación': nombre,
                'Estado': "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                'Última conexión': f"✅ {fecha_str}" if is_online else fecha_str,
                'Inactivo hace': f"{int(segundos_inactivo/60)} min" if segundos_inactivo > 60 else f"{int(segundos_inactivo)} seg"
            })
        return pd.DataFrame(estado_actual)
    except: return pd.DataFrame()

st.subheader("📡 Estado Actual")
st.dataframe(obtener_estado_actual(), use_container_width=True, hide_index=True)

st.divider()

# ====================== 2. HISTORIAL DESDE GITHUB ======================
st.subheader("📜 Historial Detallado")

@st.cache_data(ttl=300) # Cache de 5 minutos para el historial
def cargar_historial_github():
    try:
        # Usamos la API pública de contenido de GitHub para leer el JSON
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/{HISTORIAL_FILE}"
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
    except: return pd.DataFrame()

historial_df = cargar_historial_github()

with st.sidebar:
    st.header("Filtros")
    estacion_sel = st.selectbox("Seleccionar Estación", ESTACIONES)
    fecha_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

if not historial_df.empty:
    # Filtrar datos
    historial_df['fecha'] = historial_df['timestamp'].dt.date
    filtrado = historial_df[(historial_df['device'] == estacion_sel) & (historial_df['fecha'] == fecha_sel)]
    
    if not filtrado.empty:
        # Limpiar visualización
        display_df = filtrado[['timestamp', 'estado', 'duracion_min']].copy()
        display_df['estado'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No hay registros para {estacion_sel} en la fecha {fecha_sel}")
else:
    st.warning("Aún no hay datos grabados en el historial.")

# ====================== 3. REFRESCO AUTOMÁTICO 2 MIN ======================
st.markdown("""
    <script>
        setTimeout(function(){ window.location.reload(); }, 120000);
    </script>
""", unsafe_allow_html=True)

st.caption(f"🔄 Refresco automático cada 2 min • Última actualización: {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")
