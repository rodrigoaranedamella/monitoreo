import streamlit as st
import pandas as pd
import pytz
import requests
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página
st.set_page_config(page_title="SanLeon Monitor Pro", layout="wide", page_icon="📊")

# 2. Constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# 3. Refresco automático nativo cada 2 minutos
st_autorefresh(interval=120 * 1000, key="datarefresh")

# 4. Obtención de datos en vivo
@st.cache_data(ttl=10, show_spinner=False)
def obtener_vivo():
    try:
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'},
            timeout=10
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
                'Última conexión': f"✅ {ts.strftime('%H:%M:%S')}" if online and ts else (ts.strftime('%H:%M:%S') if ts else "N/A"),
                'Inactivo hace': f"{int((time.time()*1000-ls)/60000)} min" if ls > 0 else "---"
            })
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

# 5. Carga de historial[cite: 1, 5]
@st.cache_data(ttl=60)
def cargar_historial():
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601').dt.tz_convert(CHILE_TZ)
        return df
    except: return pd.DataFrame()

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================
st.title("📊 Centro de Monitoreo SanLeon")
st.caption(f"Última actualización: {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')} (Auto-refresco 2 min)")

# TABLA ESTADO EN VIVO
st.subheader("📡 Estado en Vivo")
df_vivo = obtener_vivo()
if not df_vivo.empty:
    st.dataframe(df_vivo, use_container_width=True, hide_index=True)

st.divider()

# SIDEBAR
with st.sidebar:
    st.header("🔍 Configuración")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES)
    fec_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    if st.button("🔄 Forzar recarga manual"):
        st.cache_data.clear()
        st.rerun()

# PROCESAMIENTO DE HISTORIAL
h_df = cargar_historial()
if not h_df.empty:
    filtro = h_df[(h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)].copy()
    
    if not filtro.empty:
        # --- NUEVA SECCIÓN: GRÁFICA DE 24 HORAS ---
        st.subheader(f"📈 Actividad 24h: {est_sel}")
        
        # Preparar datos para el gráfico[cite: 1]
        filtro = filtro.sort_values('timestamp')
        filtro['Estado_Txt'] = filtro['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        
        fig = px.timeline(
            filtro, 
            x_start="timestamp", 
            x_end="timestamp", # Se visualiza como puntos/barras de actividad
            y="device", 
            color="Estado_Txt",
            color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
            labels={"timestamp": "Hora", "Estado_Txt": "Estado"}
        )
        
        fig.update_layout(
            xaxis_title="Línea de Tiempo (Horas)",
            yaxis_title="",
            showlegend=True,
            height=200,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(tickformat="%H:%M")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        # ------------------------------------------

        st.subheader("📜 Detalle de Registros")
        display_df = filtro.sort_values('timestamp', ascending=False).copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Estado Visual'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        st.dataframe(display_df[['Hora', 'Estado Visual', 'duracion_min']], use_container_width=True, hide_index=True)
    else:
        st.info(f"No hay registros históricos para {est_sel} en la fecha seleccionada.")
else:
    st.warning("Aún no hay datos en el historial de GitHub.")
