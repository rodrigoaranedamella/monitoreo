import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# 1. Configuración de pantalla y autorefresco (60s)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase (Asegúrate que coincidan con tus secrets)[cite: 1, 5]
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

# Lista de estaciones[cite: 1, 5]
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30)
def cargar_historial(device, fecha):
    """Carga los datos para la gráfica de 24h usando el nombre correcto de la tabla[cite: 1, 5]."""
    try:
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
            df['duracion_real'] = df['duracion_min']
        return df
    except:
        return pd.DataFrame()

# --- ENCABEZADO ---
st.markdown("### 📊 Monitor SanLeon")

col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    # Construcción de datos para la tabla en vivo
    datos_vivos = []
    for est in ESTACIONES:
        try:
            # Consulta al nombre exacto: historial_conexiones
            res_live = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", est) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res_live.data:
                ultimo = res_live.data[0]
                ts_visto = pd.to_datetime(ultimo['timestamp']).tz_convert('America/Santiago')
                esta_online = ultimo['estado'] # Lee el booleano de la BDD
                
                # Formateo visual
                status = "🟢 ONLINE" if esta_online else "🔴 OFFLINE"
                conexion = "Actualizado" if esta_online else ts_visto.strftime('%H:%M')
                
                # Cálculo de inactividad
                diff = int((datetime.now(tz) - ts_visto).total_seconds() / 60)
                inactivo = "0 min" if esta_online else f"{max(0, diff)} min"
                
                datos_vivos.append({
                    "Estación": est,
                    "Estado": status,
                    "Última conexión": conexion,
                    "Inactivo hace": inactivo
                })
            else:
                datos_vivos.append({"Estación": est, "Estado": "⚪ SIN DATOS", "Última conexión": "--", "Inactivo hace": "--"})
        except:
            datos_vivos.append({"Estación": est, "Estado": "⚠️ ERROR", "Última conexión": "--", "Inactivo hace": "--"})

    # Se muestra como tabla nativa de Streamlit para que se vea ordenado y limpio[cite: 1]
    st.table(pd.DataFrame(datos_vivos))

with col_ctrl:
    st.caption(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Ver Historial de:", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha Consulta", value=datetime.now(tz).date())

# --- GRÁFICA DE ACTIVIDAD 24H ---
df_hist = cargar_historial(est_sel, fec_sel)

st.markdown(f"#### 📈 Actividad 24h: {est_sel}")

if not df_hist.empty:
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
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
        xaxis=dict(dtick=7200000, tickformat="%H:%M", gridcolor="#333", title=""),
        yaxis=dict(visible=False)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Métricas
    min_conectado = df_hist[df_hist['estado'] == True]['duracion_real'].sum()
    st.info(f"**Tiempo Conectado:** {int(min_conectado // 60)}h {int(min_conectado % 60)}min")
else:
    st.warning(f"No se encontraron registros para {est_sel} el día {fec_sel}.")
