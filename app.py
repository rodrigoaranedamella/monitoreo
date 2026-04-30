import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# 1. Configuración de pantalla y autorefresco (60 segundos)[cite: 1]
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase[cite: 1, 5]
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    """Obtiene el estado actual y la fecha del último registro 'Conectado' (verde)[cite: 5]."""
    estados = []
    for estacion in ESTACIONES:
        try:
            # 1. Consultar el estado más reciente (para el círculo 🟢/🔴)[cite: 5]
            res_reciente = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            # 2. Consultar el último registro donde estuvo ONLINE (para la hora y cálculo de inactividad)[cite: 5]
            res_online = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .eq("estado", True) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res_reciente.data:
                # Determinamos si está ONLINE ahora[cite: 5]
                data_ahora = res_reciente.data[0]
                ts_ahora = pd.to_datetime(data_ahora['timestamp']).tz_convert('America/Santiago')
                minutos_desde_last_seen = (datetime.now(tz) - ts_ahora).total_seconds() / 60
                is_online = data_ahora['estado'] and minutos_desde_last_seen < 15
                
                # Datos de la última vez que estuvo en verde[cite: 5]
                if res_online.data:
                    data_v = res_online.data[0]
                    ts_verde = pd.to_datetime(data_v['timestamp']).tz_convert('America/Santiago')
                    
                    # Cálculo de inactividad desde la última conexión exitosa[cite: 1]
                    diff_inactivo = (datetime.now(tz) - ts_verde).total_seconds() / 60
                    
                    estados.append({
                        "Estación": estacion,
                        "Estado": "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                        "Última conexión (OK)": ts_verde.strftime('%Y-%m-%d %H:%M:%S'),
                        "Inactivo desde OK": f"{int(diff_inactivo)} min" if not is_online else "0 min"
                    })
                else:
                    estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Nunca", "Inactivo desde OK": "--"})
            else:
                estados.append({"Estación": estacion, "Estado": "⚪ SIN DATOS", "Última conexión (OK)": "--", "Inactivo desde OK": "--"})
        except:
            continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_datos_totales(device, fecha):
    """Carga el historial de un dispositivo para un día específico[cite: 5]."""
    try:
        inicio = f"{fecha}T00:00:00Z"
        fin = f"{fecha}T23:59:59Z"
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
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df.loc[df['diff'] <= 5.5, 'duracion_real'] = df['diff']
        return df
    except:
        return pd.DataFrame()

# --- INTERFAZ DE USUARIO ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")

df_actual = obtener_estado_actual()
col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    if not df_actual.empty:
        st.table(df_actual) 
    else:
        st.warning("Cargando datos desde la base de datos...")

with col_ctrl:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

# --- GRÁFICA DE ACTIVIDAD (CONTINUA) ---
df_hist = cargar_datos_totales(est_sel, fec_sel)

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")

if not df_hist.empty:
    df_hist = df_hist.sort_values('timestamp')
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    
    # Lógica de barras continuas[cite: 1]
    df_hist['fin'] = df_hist['timestamp'].shift(-1)
    
    ultimo_idx = df_hist.index[-1]
    if fec_sel == datetime.now(tz).date():
        df_hist.at[ultimo_idx, 'fin'] = datetime.now(tz)
    else:
        df_hist.at[ultimo_idx, 'fin'] = df_hist.at[ultimo_idx, 'timestamp'] + pd.Timedelta(minutes=5)
    
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
        yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig, use_container_width=True)

    min_conectado = df_hist[df_hist['estado'] == True]['duracion_real'].sum()
    st.info(f"⏱️ **Tiempo Total Conectado:** {int(min_conectado // 60)}h {int(min_conectado % 60)}min")
else:
    st.info(f"No hay registros de historial para {est_sel} en la fecha seleccionada.")
