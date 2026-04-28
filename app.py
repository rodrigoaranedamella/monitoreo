import streamlit as st
import pandas as pd
import pytz
import json
import base64
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

# ====================== CARGAR DATOS ======================
@st.cache_data(ttl=60)  # Actualiza cada minuto
def cargar_datos_nube():
    try:
        g = Github(st.secrets["G_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        contents = repo.get_contents(HISTORIAL_FILE)
        data = json.loads(base64.b64decode(contents.content))
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
        return df
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")
        return pd.DataFrame()

df = cargar_datos_nube()

# ====================== ESTADO ACTUAL (PANTALLA PRINCIPAL) ======================
st.subheader("📡 Estado Actual de las Estaciones")

if df.empty:
    st.warning("No hay datos aún. Ejecuta el monitor desde GitHub Actions.")
else:
    # Obtener el estado más reciente de cada estación
    estado_actual = []
    
    for estacion in ESTACIONES:
        df_est = df[df['device'] == estacion]
        if not df_est.empty:
            ultimo = df_est.iloc[-1]
            ultimo_ts = ultimo['timestamp']
            
            # Calcular si sigue online (últimos 10 minutos)
            minutos_desde_ultimo = (pd.Timestamp.now(tz=CHILE_TZ) - ultimo_ts).total_seconds() / 60
            
            is_online = ultimo['estado'] and minutos_desde_ultimo < 10
            
            estado_actual.append({
                'Estación': estacion,
                'Estado': "🟢 **ONLINE**" if is_online else "🔴 OFFLINE",
                'Última conexión': ultimo_ts.strftime('%Y-%m-%d %H:%M:%S'),
                'Duración último registro': f"{ultimo['duracion_min']:.1f} min"
            })
    
    estado_df = pd.DataFrame(estado_actual)
    st.dataframe(estado_df, use_container_width=True, hide_index=True)

# ====================== FILTROS PARA HISTORIAL ======================
st.divider()
st.subheader("📜 Ver Historial Detallado")

with st.sidebar:
    st.header("Filtros de Historial")
    estacion_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fecha_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Actualizar todo"):
        st.cache_data.clear()
        st.rerun()

# Filtrar historial
if not df.empty:
    df_filtrado = df[(df['device'] == estacion_sel) & (df['timestamp'].dt.date == fecha_sel)]
    
    if not df_filtrado.empty:
        st.success(f"Historial de **{estacion_sel}** - {fecha_sel}")
        
        # Gráfico de timeline
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
            yaxis=dict(showticklabels=False, range=[0.5, 1.5]),
            xaxis_title="Hora del día",
            margin=dict(l=0, r=0, t=10, b=10),
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df_filtrado.sort_values('timestamp', ascending=False), use_container_width=True)
    else:
        st.info(f"No hay registros para **{estacion_sel}** en la fecha seleccionada.")
else:
    st.info("Ejecuta el monitor para comenzar a registrar datos.")

st.caption("Estado en tiempo real actualizado cada minuto • Historial cada 5 minutos")
