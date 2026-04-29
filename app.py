import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# 1. Configuración de pantalla y autorefresco al minuto (Source 3)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh") # Actualización automática cada 1 min

# Conexión a Supabase (Source 5)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30) # TTL bajo para asegurar datos frescos de la BDD (Source 5)
def cargar_datos_totales(device, fecha):
    try:
        res = supabase.table("historial_connections") \
            .select("*") \
            .eq("device", device) \
            .gte("timestamp", f"{fecha}T00:00:00") \
            .lte("timestamp", f"{fecha}T23:59:59") \
            .order("timestamp") \
            .execute()
        
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
            
            # --- LÓGICA DE CONTINUIDAD ---
            # Identificamos bloques continuos (si la diferencia es > 6 min, es un bloque nuevo)
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df['nuevo_bloque'] = (df['diff'] > 6) | (df['estado'] != df['estado'].shift())
            df['grupo'] = df['nuevo_bloque'].cumsum()
            
            # Agrupamos para crear segmentos de inicio y fin (Source 3)
            df_segmentos = df.groupby(['grupo', 'estado', 'device']).agg(
                inicio=('timestamp', 'min'),
                fin=('timestamp', 'max')
            ).reset_index()
            
            # Añadimos un pequeño margen al fin para que los puntos aislados sean visibles
            df_segmentos['fin'] = df_segmentos['fin'] + pd.Timedelta(minutes=5)
            return df_segmentos
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- PARTE SUPERIOR DINÁMICA ---
st.markdown("### 📊 Monitor SanLeon")
col_tabla, col_ctrl = st.columns([3, 1])

with col_ctrl:
    st.caption(f"🕒 BDD Live: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())

# --- GRÁFICA DE ACTIVIDAD CONTINUA ---
df_plot = cargar_datos_totales(est_sel, fec_sel)

if not df_plot.empty:
    df_plot['Estado_Txt'] = df_plot['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    
    # Gráfica estilo Timeline con bloques unidos (Source 3)
    fig = px.timeline(
        df_plot, 
        x_start="inicio", 
        x_end="fin", 
        y="device", 
        color="Estado_Txt",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"]
    )

    fig.update_layout(
        height=220,
        showlegend=True,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(dtick=7200000, tickformat="%H:%M", gridcolor="#333", title="Horario (pasos de 2h)"),
        yaxis=dict(visible=False)
    )
    
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
else:
    st.info("Esperando datos de la BDD...")
