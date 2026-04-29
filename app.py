import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# Configuración y Autorefresh (Source 3)
st.set_page_config(page_title="SanLeon Monitor Pro", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a DB usando Secrets de Streamlit
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

@st.cache_data(ttl=60)
def cargar_historial_db(device, fecha):
    # Consulta a Supabase filtrada por dispositivo y día
    res = supabase.table("historial_conexiones") \
        .select("*") \
        .eq("device", device) \
        .gte("timestamp", f"{fecha}T00:00:00") \
        .lte("timestamp", f"{fecha}T23:59:59") \
        .order("timestamp") \
        .execute()
    
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
    return df

st.title("📊 Monitor de Conexiones SanLeon")

# Sidebar para filtros
st.sidebar.header("Filtros de Historial")
est_sel = st.sidebar.selectbox("Estación", ESTACIONES_LISTA_COMPLETA) # Usa tu lista de nombres
fec_sel = st.sidebar.date_input("Fecha", value=datetime.now(tz).date())

# Lógica de visualización
h_df = cargar_historial_db(est_sel, fec_sel)

if not h_df.empty:
    h_df['Estado_Txt'] = h_df['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    # Creamos el bloque de 5 minutos para la línea de tiempo
    h_df['fin'] = h_df['timestamp'] + pd.Timedelta(minutes=5)
    
    fig = px.timeline(h_df, 
                      x_start="timestamp", 
                      x_end="fin", 
                      y="device", 
                      color="Estado_Txt",
                      color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                      title=f"Línea de Tiempo: {est_sel}")
    
    # Cálculo de horas totales conectadas
    min_conectado = h_df[h_df['estado'] == True]['duracion_min'].sum()
    st.metric("Tiempo Total Online", f"{int(min_conectado // 60)}h {int(min_conectado % 60)}min")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No se encontraron registros para la fecha seleccionada.")
