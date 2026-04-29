import streamlit as st
import pandas as pd
import pytz
import requests
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# Configuración de página compacta
st.set_page_config(page_title="SanLeon Monitor Real-Time", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        .stMetric { background-color: #1e2127; border: 1px solid #00CC96; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# Refresco rápido para no perder sincronía
st_autorefresh(interval=30 * 1000, key="datarefresh")

@st.cache_data(ttl=5, show_spinner=False) # TTL muy bajo para forzar sincronización
def obtener_vivo():
    try:
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'},
            timeout=5
        ).json()
        datos = []
        ahora_ms = time.time() * 1000
        for n in ESTACIONES:
            m = next((item for item in res if item.get('name') == n), {})
            ls = m.get('lastSeen', 0)
            online = (ahora_ms - ls) / 1000 < 600 # 10 min de margen
            ts = pd.to_datetime(ls, unit='ms', utc=True).tz_convert(CHILE_TZ) if ls > 0 else None
            datos.append({'Estación': n, 'Estado': "🟢 ONLINE" if online else "🔴 OFFLINE", 
                          'Última': ts.strftime('%H:%M:%S') if ts else "---", 'raw_ts': ts, 'online_bool': online})
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

@st.cache_data(ttl=10) # Forzamos descarga de GitHub casi constante
def cargar_historial():
    # El timestamp en la URL destruye el caché de GitHub
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json?nocache={int(time.time())}"
    try:
        response = requests.get(url, timeout=10)
        df = pd.DataFrame(response.json())
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(CHILE_TZ)
        return df
    except Exception as e:
        return pd.DataFrame()

# --- INTERFAZ ---
st.subheader("📊 Monitor de Conectividad Efectiva")
df_vivo = obtener_vivo()

col_tabla, col_controles = st.columns([3, 1])
with col_tabla:
    st.dataframe(df_vivo[['Estación', 'Estado', 'Última']], use_container_width=True, hide_index=True)

with col_controles:
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    if st.button("🔄 Sincronizar Historial Ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

h_df = cargar_historial()
if not h_df.empty:
    hoy = pd.Timestamp.now(tz=CHILE_TZ).date()
    filtro = h_df[(h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == hoy)].copy()
    
    if not filtro.empty:
        # Sumamos solo lo que está escrito en el historial (Datos Reales)
        total_m = int(filtro[filtro['estado'] == True]['duracion_min'].sum())
        h, m = divmod(total_m, 60)
        st.metric(label=f"Tiempo Total Registrado en Historial (Hoy)", value=f"{h}h {m}min")

        # Gráfica de alta fidelidad
        fig = px.timeline(filtro, x_start="timestamp", 
                          x_end=filtro['timestamp'] + pd.to_timedelta(filtro['duracion_min'], unit='m'), 
                          y="device", color="estado",
                          color_discrete_map={True: "#00CC96", False: "#EF553B"})
        
        fig.update_layout(xaxis_title="Línea de Tiempo Efectiva", height=150, showlegend=False,
                          margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("📂 **Registros en el archivo JSON:**")
        st.table(filtro.sort_values('timestamp', ascending=False).head(10)[['timestamp', 'duracion_min']])
    else:
        st.warning(f"⚠️ Atención: No existen registros grabados para {est_sel} el día de hoy en el historial.")
