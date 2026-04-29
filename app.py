import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# 1. Configuración de pantalla y autorefresco al minuto (Source 3)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True) # Reduce espacio superior
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase (Source 5)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30)
def cargar_datos_totales(device, fecha):
    try:
        # Consulta automática a la base de datos (Source 5)
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
            # Lógica de persistencia de 2 minutos (Source 5)
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df['duracion_real'] = df['duracion_min']
            df.loc[df['diff'] <= 2.1, 'duracion_real'] = df['diff']
        return df
    except:
        return pd.DataFrame()

# --- PARTE SUPERIOR (Compacta) ---
st.markdown("### 📊 Monitor SanLeon")

col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    # Aquí puedes integrar una consulta a Supabase para que esta tabla sea real (Source 3, 5)
    st.markdown("""
    | Estación | Estado | Última conexión | Inactivo hace |
    | :--- | :--- | :--- | :--- |
    | Marian_SANLEON | 🔴 OFFLINE | -- | -- |
    | Andrea_SANLEON | 🔴 OFFLINE | -- | -- |
    | Matias_SANLEON | 🔴 OFFLINE | -- | -- |
    | **Jennifer_SANLEON** | 🟢 **ONLINE** | **Actualizado** | **0 min** |
    """, unsafe_allow_html=True)

with col_ctrl:
    st.caption(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())

# --- GRÁFICA ACTIVIDAD 24H (Estilo Original) ---
df_hist = cargar_datos_totales(est_sel, fec_sel)

st.markdown(f"#### 📈 Actividad 24h: {est_sel}")

if not df_hist.empty:
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    df_hist['fin'] = df_hist['timestamp'] + pd.Timedelta(minutes=5)
    
    # Recreación de la gráfica de la foto (Source 3)
    fig = px.timeline(
        df_hist, 
        x_start="timestamp", 
        x_end="fin", 
        y="device", 
        color="Estado_Txt",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"] # Escala completa 00:00 a 23:59
    )

    fig.update_layout(
        height=220,
        showlegend=True,
        legend_title_text="",
        plot_bgcolor="rgba(0,0,0,0)", # Fondo transparente para ver el recuadro
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(
            dtick=7200000, # Marcas cada 2 horas
            tickformat="%H:%M",
            gridcolor="#333", # Recrea las líneas de guía de la foto
            title="Horario (pasos de 2h)"
        ),
        yaxis=dict(visible=False)
    )
    
    # Dibujar el recuadro de la gráfica (Source 3)
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- MÉTRICAS Y TABLA DETALLE ---
    min_conectado = df_hist[df_hist['estado'] == True]['duracion_real'].sum()
    st.markdown(f"**Tiempo Conectado Permanente:** {int(min_conectado // 60)}h {int(min_conectado % 60)}min")
    
    st.markdown("#### 📜 Detalle de Registros")
    st.dataframe(
        df_hist[['timestamp', 'Estado_Txt', 'duracion_real']].rename(
            columns={'timestamp': 'Hora', 'Estado_Txt': 'Visual', 'duracion_real': 'Duración (min)'}
        ),
        use_container_width=True,
        height=200
    )
else:
    st.info("No hay datos disponibles para el día seleccionado.")
