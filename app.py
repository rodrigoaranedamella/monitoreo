import streamlit as st
import pandas as pd
import pytz
import requests
import time

st.set_page_config(page_title="SanLeon Monitor", layout="wide")
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# TTL BAJO (10 seg) para que la actualización sea efectiva
@st.cache_data(ttl=10, show_spinner=False)
def obtener_vivo():
    try:
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'}
        ).json()
        
        datos = []
        for n in ESTACIONES:
            m = next((item for item in res if item.get('name') == n), {})
            ls = m.get('lastSeen', 0)
            online = ((time.time() * 1000 - ls) / 1000) < 900
            ts = pd.to_datetime(ls, unit='ms', utc=True).tz_convert(CHILE_TZ) if ls > 0 else None
            
            datos.append({
                'Estación': n,
                'Estado': "🟢 ONLINE" if online else "🔴 OFFLINE",
                'Última conexión': f"✅ {ts.strftime('%H:%M:%S')}" if online else ts.strftime('%H:%M:%S'),
                'Hace': f"{int((time.time()*1000-ls)/60000)} min"
            })
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

st.title("📊 Centro de Monitoreo SanLeon")
st.subheader("📡 Estado en Vivo")
st.dataframe(obtener_vivo(), use_container_width=True, hide_index=True)

# HISTORIAL: También con TTL bajo para ver los nuevos registros rápido
@st.cache_data(ttl=60)
def cargar_historial():
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json"
    try:
        df = pd.DataFrame(requests.get(url).json())
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
        return df
    except: return pd.DataFrame()

# Sidebar y Filtros
with st.sidebar:
    st.header("Filtros")
    est_sel = st.selectbox("Estación", ESTACIONES)
    fec_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())

st.subheader(f"📜 Historial: {est_sel}")
h_df = cargar_historial()
if not h_df.empty:
    filtro = h_df[(h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)]
    if not filtro.empty:
        st.dataframe(filtro.sort_values('timestamp', ascending=False), use_container_width=True, hide_index=True)

# REFRESCO FORZADO CADA 2 MINUTOS
st.markdown("""
    <script>
        setTimeout(function(){ window.location.reload(); }, 120000);
    </script>
""", unsafe_allow_html=True)
