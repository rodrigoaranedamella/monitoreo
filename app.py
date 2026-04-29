import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración de página y refresco al minuto
st.set_page_config(page_title="Monitor SanLeon", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Credenciales desde Secrets
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30)
def obtener_datos(dispositivo, fecha, modo_historial):
    try:
        query = supabase.table("historial_conexiones") \
            .select("*") \
            .eq("device", dispositivo) \
            .gte("timestamp", f"{fecha}T00:00:00") \
            .lte("timestamp", f"{fecha}T23:59:59") \
            .order("timestamp")
        
        res = query.execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
            # Lógica de tolerancia: Si el hueco es <= 2 min, se considera continuo
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df.loc[df['diff'] <= 2.1, 'duracion_min'] = df['diff'] 
        return df
    except Exception as e:
        return pd.DataFrame()

# --- HEADER Y ESTADO ACTUAL ---
st.markdown("### 📊 Monitor SanLeon")

col1, col2 = st.columns([3, 1])

with col1:
    # Simulación de tabla de estado actual (puedes conectarla a una vista de Supabase)
    st.markdown("""
    | Estación | Estado | Última conexión | Inactivo hace |
    | :--- | :--- | :--- | :--- |
    | Marian_SANLEON | 🔴 OFFLINE | -- | -- |
    | Andrea_SANLEON | 🔴 OFFLINE | -- | -- |
    | Jennifer_SANLEON | 🟢 ONLINE | Actualizado | 0 min |
    """)

with col2:
    st.info(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())
    ver_historial = st.checkbox("Acceder a historial almacenado (DB)")

# --- GRÁFICA DE ACTIVIDAD 24H ---
if ver_historial:
    df_plot = obtener_datos(est_sel, fec_sel, True)
    
    if not df_plot.empty:
        st.markdown(f"#### 📈 Actividad 24h: {est_sel}")
        
        df_plot['Estado_Txt'] = df_plot['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        df_plot['fin'] = df_plot['timestamp'] + pd.Timedelta(minutes=5)
        
        fig = px.timeline(
            df_plot, 
            x_start="timestamp", 
            x_end="fin", 
            y="device", 
            color="Estado_Txt",
            color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
            range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"]
        )

        fig.update_layout(
            height=180, # Altura reducida para ahorrar espacio
            margin=dict(l=0, r=0, t=20, b=20),
            xaxis=dict(
                dtick=7200000, # Marcas cada 2 horas (en milisegundos)
                tickformat="%H:%M",
                title="Horario (pasos de 2h)"
            ),
            yaxis=dict(visible=False),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # --- TABLA DE DETALLE ---
        st.markdown("#### 📜 Detalle de Registros")
        minutos_totales = df_plot[df_plot['estado'] == True]['duracion_min'].sum()
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Tiempo Conectado Permanente", f"{int(minutos_totales // 60)}h {int(minutos_totales % 60)}min")
        
        st.dataframe(
            df_plot[['timestamp', 'Estado_Txt', 'duracion_min']].rename(
                columns={'timestamp': 'Hora', 'Estado_Txt': 'Visual', 'duracion_min': 'Minutos'}
            ), 
            use_container_width=True,
            height=250
        )
    else:
        st.warning("No se encontraron registros en la base de datos para los criterios seleccionados.")
else:
    st.write("Seleccione el checkbox para cargar el historial de la base de datos.")
