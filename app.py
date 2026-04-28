import streamlit as st
import pandas as pd
import pytz
import json
import base64
import requests
import time
from github import Github
from datetime import datetime

CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'

ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

st.title("📊 Centro de Monitoreo SanLeon")
st.markdown("### Monitoreo de conexiones ZeroTier en tiempo real")

# ====================== CONSULTA EN TIEMPO REAL ======================
@st.cache_data(ttl=60)  # Se refresca cada 60 segundos
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
            is_online = segundos_inactivo < 900  # 15 minutos de tolerancia

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

# ====================== CARGA DE HISTORIAL ======================
@st.cache_data(ttl=300)
def cargar_historial():
    try:
        g = Github(st.secrets["G_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        contents = repo.get_contents(HISTORIAL_FILE)
        data = json.loads(base64.b64decode(contents.content))
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
        return df
    except:
        return pd.DataFrame()

# ====================== INTERFAZ ======================
estado_df = obtener_estado_actual()

st.subheader("📡 Estado Actual en Tiempo Real")
if not estado_df.empty:
    st.dataframe(
        estado_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Estado": st.column_config.TextColumn("Estado", width="medium"),
            "Última conexión": st.column_config.TextColumn("Última conexión", width="medium"),
        }
    )
else:
    st.warning("No se pudo obtener el estado actual de ZeroTier.")

st.divider()

# ====================== HISTORIAL DETALLADO ======================
st.subheader("📜 Historial Detallado")

with st.sidebar:
    st.header("Filtros de Historial")
    estacion_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fecha_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Actualizar Todo"):
        st.cache_data.clear()
        st.rerun()

df_historial = cargar_historial()

if not df_historial.empty:
    df_filtrado = df_historial[
        (df_historial['device'] == estacion_sel) & 
        (df_historial['timestamp'].dt.date == fecha_sel)
    ]
    
    if not df_filtrado.empty:
        import plotly.graph_objects as go
        fig = go.Figure()
        
        for _, fila in df_filtrado.iterrows():
            fin = fila['timestamp'] + pd.Timedelta(minutes=fila['duracion_min'])
            color = '#238636' if fila['estado'] else '#da3633'
            fig.add_trace(go.Scatter(
                x=[fila['timestamp'], fin],
                y=[1, 1],
                mode='lines',
                line=dict(width=35, color=color),
                showlegend=False
            ))
        
        fig.update_layout(
            height=200,
            yaxis=dict(showticklabels=False),
            xaxis_title="Hora del día",
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df_filtrado.sort_values('timestamp', ascending=False), use_container_width=True)
    else:
        st.info(f"No hay registros para **{estacion_sel}** en la fecha {fecha_sel}")
else:
    st.info("El historial aún no se ha generado. Ejecuta el monitor desde GitHub Actions.")

st.caption("🔄 Estado en tiempo real se actualiza cada 60 segundos • Historial cada 5 minutos")
