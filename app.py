import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# 1. Configuración de pantalla y autorefresco (60 segundos)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30)
def obtener_estado_actual():
    """Obtiene el último registro de cada estación para el monitor en vivo."""
    estados = []
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res.data:
                data = res.data[0]
                last_time = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                diff = (datetime.now(tz) - last_time).total_seconds() / 60
                
                # Un dispositivo se considera ONLINE solo si el registro es reciente (< 15 min) y el estado es True
                is_online = data['estado'] and diff < 15
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                    "Última conexión": last_time.strftime('%H:%M:%S'),
                    "Inactivo hace": f"{int(diff)} min" if diff > 0 else "0 min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "⚪ SIN DATOS", "Última conexión": "--", "Inactivo hace": "--"})
        except:
            continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_datos_totales(device, fecha):
    """Carga el historial de un dispositivo para un día específico."""
    try:
        # Ajuste de rango de fecha para consulta en Supabase
        inicio = f"{fecha}T00:00:00+00:00"
        fin = f"{fecha}T23:59:59+00:00"
        
        res = supabase.table("historial_conexiones") \
            .select("*") \
            .eq("device", device) \
            .gte("timestamp", inicio) \
            .lte("timestamp", fin) \
            .order("timestamp") \
            .execute()
        
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
            df['duracion_real'] = df['duracion_min']
            # Cálculo de diferencia entre registros para detectar desconexiones
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df.loc[df['diff'] <= 5.5, 'duracion_real'] = df['diff'] # Basado en cron de 5min
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")

# Obtener datos en tiempo real
df_actual = obtener_estado_actual()

col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    if not df_actual.empty:
        # Mostrar tabla dinámica con colores
        st.dataframe(df_actual, hide_index=True, use_container_width=True)
    else:
        st.warning("No se pudieron recuperar estados en vivo.")

with col_ctrl:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=0)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

# --- GRÁFICA DE ACTIVIDAD ---
df_hist = cargar_datos_totales(est_sel, fec_sel)

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")

if not df_hist.empty:
    # Preparación de datos para px.timeline
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    # El bloque dura hasta el siguiente registro o 5 minutos por defecto
    df_hist['fin'] = df_hist['timestamp'] + pd.Timedelta(minutes=5)
    
    fig = px.timeline(
        df_hist, 
        x_start="timestamp", 
        x_end="fin", 
        y="device", 
        color="Estado_Txt",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"]
    )

    fig.update_layout(
        height=200,
        showlegend=True,
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(dtick=7200000, tickformat="%H:%M", title="Hora del día"),
        yaxis=dict(visible=False)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Métricas de tiempo
    min_conectado = df_hist[df_hist['estado'] == True]['duracion_real'].sum()
    st.info(f"⏱️ **Tiempo Total Conectado:** {int(min_conectado // 60)}h {int(min_conectado % 60)}min")
else:
    st.info(f"No hay registros de historial para {est_sel} en la fecha seleccionada.")
