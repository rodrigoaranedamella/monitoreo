import streamlit as st
import pandas as pd
import pytz
import requests
import time
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página
st.set_page_config(page_title="SanLeon Monitor", layout="wide", page_icon="📊")

# 2. Configuración de constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# ==========================================================
# 3. REFRESCO AUTOMÁTICO NATIVO (Cada 2 minutos)
# ==========================================================
# Esto reemplaza al script de JavaScript y es mucho más confiable.
st_autorefresh(interval=120 * 1000, key="datarefresh")

# 4. Lógica de obtención de datos en vivo
@st.cache_data(ttl=10, show_spinner=False)
def obtener_vivo():
    try:
        # Usar st.secrets para mayor seguridad
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'},
            timeout=10
        ).json()
        
        datos = []
        for n in ESTACIONES:
            m = next((item for item in res if item.get('name') == n), {})
            ls = m.get('lastSeen', 0)
            # 15 min de margen para estado ONLINE
            online = ((time.time() * 1000 - ls) / 1000) < 900
            ts = pd.to_datetime(ls, unit='ms', utc=True).tz_convert(CHILE_TZ) if ls > 0 else None
            
            datos.append({
                'Estación': n,
                'Estado': "🟢 ONLINE" if online else "🔴 OFFLINE",
                'Última conexión': f"✅ {ts.strftime('%H:%M:%S')}" if online and ts else (ts.strftime('%H:%M:%S') if ts else "N/A"),
                'Inactivo hace': f"{int((time.time()*1000-ls)/60000)} min" if ls > 0 else "---"
            })
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# 5. Lógica de historial
@st.cache_data(ttl=60)
def cargar_historial():
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
            return df
    except:
        pass
    return pd.DataFrame()

# ==========================================================
# INTERFAZ DE USUARIO
# ==========================================================
st.title("📊 Centro de Monitoreo SanLeon")
ahora_str = pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')
st.caption(f"Última actualización automática: {ahora_str} (Refresco cada 2 min)")

# Mostrar Estado en Vivo
st.subheader("📡 Estado en Vivo")
df_vivo = obtener_vivo()
if not df_vivo.empty:
    st.dataframe(df_vivo, use_container_width=True, hide_index=True)

st.divider()

# Sidebar y Filtros
with st.sidebar:
    st.header("🔍 Filtros de Historial")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES)
    fec_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Forzar recarga manual"):
        st.cache_data.clear()
        st.rerun()

# Mostrar Historial
st.subheader(f"📜 Historial: {est_sel}")
h_df = cargar_historial()

if not h_df.empty:
    # Filtrado estricto por usuario y fecha
    filtro = h_df[
        (h_df['device'] == est_sel) & 
        (h_df['timestamp'].dt.date == fec_sel)
    ].copy()
    
    if not filtro.empty:
        filtro = filtro.sort_values('timestamp', ascending=False)
        # Formatear para visualización
        display_df = filtro[['timestamp', 'estado', 'duracion_min']].copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Estado'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        
        st.dataframe(display_df[['Hora', 'Estado', 'duracion_min']], use_container_width=True, hide_index=True)
    else:
        st.info(f"No hay registros para {est_sel} el día {fec_sel}")
else:
    st.warning("No se pudo cargar el archivo de historial desde GitHub.")
