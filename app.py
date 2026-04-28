import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pytz
import json
import base64
from github import Github
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
CHILE_TZ = pytz.timezone('America/Santiago')
HISTORIAL_FILE = 'historial_conexiones.json'
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON"]

st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

st.title("📊 Centro de Monitoreo SanLeon")
st.markdown("### Monitoreo de conexiones ZeroTier")

# ==================== CARGAR DATOS CON ERRORES VISIBLES ====================
@st.cache_data(ttl=60)   # Reducido a 1 minuto para pruebas
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
        st.error(f"❌ Error al cargar datos desde GitHub:")
        st.code(str(e))
        st.info("Verifica que los secrets estén correctamente configurados en Streamlit Cloud.")
        return pd.DataFrame()

df = cargar_datos_nube()

# ==================== INTERFAZ ====================
if df.empty:
    st.warning("No se pudieron cargar los datos. Revisa los errores arriba.")
    st.stop()

with st.sidebar:
    st.header("Filtros")
    estacion_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fecha_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

# Filtrar datos
df_filtrado = df[(df['device'] == estacion_sel) & (df['timestamp'].dt.date == fecha_sel)]

if not df_filtrado.empty:
    st.success(f"Mostrando datos de **{estacion_sel}** - {fecha_sel}")
    
    # Gráfico mejorado
    fig = go.Figure()
    for _, fila in df_filtrado.iterrows():
        fin = fila['timestamp'] + pd.Timedelta(minutes=fila['duracion_min'])
        color = '#238636' if fila['estado'] else '#da3633'
        
        fig.add_trace(go.Scatter(
            x=[fila['timestamp'], fin],
            y=[1, 1],
            mode='lines',
            line=dict(width=30, color=color),
            showlegend=False
        ))

    fig.update_layout(
        height=180,
        yaxis=dict(showticklabels=False, range=[0.5, 1.5]),
        xaxis_title="Hora del día",
        margin=dict(l=10, r=10, t=10, b=10),
        template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("📋 Últimos registros")
    st.dataframe(df_filtrado.sort_values('timestamp', ascending=False).head(20), use_container_width=True)
    
else:
    st.warning(f"No hay datos para **{estacion_sel}** en la fecha seleccionada.")

st.caption("Actualizado automáticamente cada 5 minutos por GitHub Actions")
