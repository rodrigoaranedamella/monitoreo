import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración de página
st.set_page_config(page_title="Monitor SanLeon", layout="wide", page_icon="📊")

# Refresco automático cada 1 minuto (Source 3)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase (Source 5)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

# Estaciones a monitorear
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def obtener_resumen_actual():
    """Obtiene el último estado registrado para cada estación"""
    resumen = []
    ahora = datetime.now(tz)
    
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res.data:
                ultimo = res.data[0]
                ts = pd.to_datetime(ultimo['timestamp']).astimezone(tz)
                inactivo = int((ahora - ts).total_seconds() / 60) if not ultimo['estado'] else 0
                
                resumen.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if ultimo['estado'] else "🔴 OFFLINE",
                    "Última conexión": ts.strftime("%H:%M:%S"),
                    "Inactivo hace": f"{max(0, inactivo)} min"
                })
            else:
                resumen.append({"Estación": estacion, "Estado": "⚪ SIN DATOS", "Última conexión": "--", "Inactivo hace": "--"})
        except:
            continue
    return pd.DataFrame(resumen)

@st.cache_data(ttl=30)
def cargar_historial_grafico(device, fecha):
    """Carga los datos para la línea de tiempo"""
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
            df['Estado_Txt'] = df['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
            df['fin'] = df['timestamp'] + pd.Timedelta(minutes=5)
        return df
    except:
        return pd.DataFrame()

# --- INTERFAZ ---
st.title("📊 Monitor SanLeon")

# Fila Superior: Tabla de Resumen y Filtros
col_tabla, col_filtros = st.columns([3, 1])

with col_tabla:
    df_resumen = obtener_resumen_actual()
    st.table(df_resumen)

with col_filtros:
    st.info(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4) # Default Jennifer
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())
    if st.button("🔄 Refrescar Manual"):
        st.rerun()

st.markdown("---")

# Fila Inferior: Gráfica de Actividad
st.subheader(f"📈 Actividad 24h: {est_sel}")
df_hist = cargar_historial_grafico(est_sel, fec_sel)

if not df_hist.empty:
    fig = px.timeline(
        df_hist, 
        x_start="timestamp", 
        x_end="fin", 
        y="device", 
        color="Estado_Txt",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        labels={"Estado_Txt": "Estado"}
    )
    
    fig.update_layout(
        xaxis_title="Horario (pasos de 2h)",
        yaxis_title="",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detalle de Registros
    with st.expander("📄 Ver Detalle de Registros"):
        st.dataframe(df_hist[['timestamp', 'Estado_Txt', 'duracion_min']].rename(columns={'timestamp': 'Hora', 'Estado_Txt': 'Visual'}), use_container_width=True)
else:
    st.warning(f"No hay actividad registrada para {est_sel} en la fecha seleccionada.")
