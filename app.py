import streamlit as st
import pandas as pd
import pytz
import json
import base64
import requests
import time
from github import Github

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

st.title("📊 Centro de Monitoreo SanLeon")
st.markdown("### Monitoreo de conexiones ZeroTier en tiempo real")

# ====================== ESTADO EN TIEMPO REAL ======================
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
        ahora = pd.Timestamp.now(tz=CHILE_TZ)

        for nombre in ESTACIONES:
            m = next((item for item in members if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            
            segundos_inactivo = (time.time() * 1000 - last_seen) / 1000
            is_online = segundos_inactivo < 900  # 15 minutos

            ultima_conexion = pd.to_datetime(last_seen, unit='ms', utc=True).tz_convert(CHILE_TZ) if last_seen > 0 else None

            estado_actual.append({
                'Estación': nombre,
                'Estado': "🟢 **ONLINE**" if is_online else "🔴 OFFLINE",
                'Última conexión': ultima_conexion.strftime('%Y-%m-%d %H:%M:%S') if ultima_conexion else "Nunca",
                'Inactivo hace': f"{int(segundos_inactivo/60)} min" if segundos_inactivo > 60 else f"{int(segundos_inactivo)} seg"
            })

        return pd.DataFrame(estado_actual)
    
    except Exception as e:
        st.error(f"Error consultando ZeroTier: {e}")
        return pd.DataFrame()

# ====================== INTERFAZ PRINCIPAL ======================
st.subheader("📡 Estado Actual en Tiempo Real")

estado_df = obtener_estado_actual()

if not estado_df.empty:
    st.dataframe(
        estado_df,
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No se pudo obtener el estado actual.")

st.divider()

# ====================== HISTORIAL ======================
st.subheader("📜 Historial Detallado")

with st.sidebar:
    st.header("Filtros de Historial")
    estacion_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fecha_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Actualizar Todo"):
        st.cache_data.clear()
        st.rerun()

# (Mantengo el código del historial simple para no complicar)
st.info("El historial detallado se activará cuando el workflow funcione correctamente.")

# ====================== REFRESCO AUTOMÁTICO FORZADO ======================
st.markdown("""
    <style>
        .stApp {
            animation: refresh 60s infinite;
        }
    </style>
    <script>
        function autoRefresh() {
            console.log("Refrescando página automáticamente...");
            window.location.reload(true);
        }
        setTimeout(autoRefresh, 60000);  // 60 segundos
    </script>
""", unsafe_allow_html=True)

st.caption("🔄 La página se actualiza automáticamente cada 60 segundos • Estado en vivo desde ZeroTier")
