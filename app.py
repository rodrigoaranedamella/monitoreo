import streamlit as st
import pandas as pd
import plotly.express as px
import json
import base64
from github import Github
import os
import pytz

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor San León", layout="wide")

# --- PARÁMETROS Y TOKENS ---
G_TOKEN = os.getenv("G_TOKEN")
GITHUB_REPO = "rodrigoaranedamella/monitoreo"
HISTORIAL_FILE = 'historial_conexiones.json'
CHILE_TZ = pytz.timezone('America/Santiago')

# --- FUNCIONES DE CARGA ---
def cargar_historial():
    try:
        g = Github(G_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents(HISTORIAL_FILE)
        decoded = base64.b64decode(contents.content).decode('utf-8')
        data = json.loads(decoded)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
        return pd.DataFrame()

# --- INTERFAZ ---
st.title("📊 Panel de Monitoreo - San León")

h_df = cargar_historial()

# Sidebar para filtros
with st.sidebar:
    st.header("Filtros")
    # Fecha de hoy en Chile para el calendario
    hoy_chile = pd.Timestamp.now(tz=CHILE_TZ).date()
    fec_sel = st.date_input("Seleccionar Fecha", hoy_chile)
    
    estaciones = ["Jennifer_SANLEON", "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON"]
    est_sel = st.selectbox("Seleccionar Estación", estaciones)
    
    if st.button("🔄 Refrescar Datos"):
        st.rerun()

# --- PROCESAMIENTO DE DATOS ---
if not h_df.empty:
    # 1. Convertir timestamps a datetime (vienen en UTC 'Z' del worker)
    h_df['timestamp'] = pd.to_datetime(h_df['timestamp'], format='ISO8601')
    
    # 2. Convertir de UTC a Hora de Chile (UTC-4)
    # Si los datos no tienen zona horaria, se la asignamos (UTC) y luego convertimos
    if h_df['timestamp'].dt.tz is None:
        h_df['timestamp'] = h_df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(CHILE_TZ)
    else:
        h_df['timestamp'] = h_df['timestamp'].dt.tz_convert(CHILE_TZ)

    # 3. Filtrar por fecha (comparando solo el día) y estación
    mask = (h_df['timestamp'].dt.date == fec_sel) & (h_df['device'] == est_sel)
    filtro = h_df.loc[mask].copy()

    # --- VISUALIZACIÓN ---
    if not filtro.empty:
        st.subheader(f"Actividad de {est_sel} el {fec_sel}")
        
        # Crear gráfico de línea de tiempo
        fig = px.scatter(
            filtro, 
            x='timestamp', 
            y='estado',
            color='estado',
            color_discrete_map={True: '#00CC96', False: '#EF553B'},
            labels={'estado': '¿En Línea?', 'timestamp': 'Hora'},
            title=f"Conexiones detectadas (Hora Chile)"
        )
        
        fig.update_traces(marker=dict(size=12, symbol='square'))
        fig.update_layout(yaxis=dict(tickmode='array', tickvals=[0, 1], ticktext=['Offline', 'Online']))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar tabla de los últimos registros
        st.write("Últimos registros detectados:")
        st.dataframe(filtro.sort_values('timestamp', ascending=False))
    else:
        st.warning(f"No se encontraron registros para {est_sel} en la fecha {fec_sel}.")
        st.info("💡 Nota: Los datos de la madrugada (post 00:00) aparecen al seleccionar la fecha de hoy.")

# --- SECCIÓN DE DEPURACIÓN (Opcional, borrar después) ---
with st.expander("Ver RAW Data (Depuración)"):
    st.write("Últimas 5 líneas del archivo original en GitHub:")
    st.write(h_df.tail(5))
