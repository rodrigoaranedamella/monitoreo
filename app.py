import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

st.set_page_config(page_title="Monitor SanLeon", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh")

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

# Conexión a Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

@st.cache_data(ttl=30) # Cache más corto para ver cambios rápido
def cargar_datos_db(device, fecha):
    try:
        # NOMBRE DE TABLA CORREGIDO: historial_conexiones
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
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

st.title("📊 Monitor de Conexiones SanLeon")

st.sidebar.header("Filtros")
est_sel = st.sidebar.selectbox("Seleccionar Estación", ESTACIONES)
fec_sel = st.sidebar.date_input("Fecha", value=datetime.now(tz).date())

df_hist = cargar_datos_db(est_sel, fec_sel)

if not df_hist.empty:
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Online" if x else "Offline")
    df_hist['fin'] = df_hist['timestamp'] + pd.Timedelta(minutes=5)
    
    fig = px.timeline(df_hist, x_start="timestamp", x_end="fin", y="device", 
                      color="Estado_Txt", color_discrete_map={"Online": "#00CC96", "Offline": "#EF553B"})
    
    minutos_on = df_hist[df_hist['estado'] == True]['duracion_min'].sum()
    st.metric(f"Tiempo Total Online", f"{int(minutos_on // 60)}h {int(minutos_on % 60)}min")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Esperando datos de la base de datos...")
