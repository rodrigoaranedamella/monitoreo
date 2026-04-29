import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# Configuración inicial (Source 3)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

# Listado completo de estaciones (Source 3)
ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", 
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]

@st.cache_data(ttl=30)
def obtener_resumen_estaciones():
    datos_resumen = []
    ahora = datetime.now(tz)
    hoy = ahora.strftime('%Y-%m-%d')
    
    for est in ESTACIONES:
        try:
            # Obtener último registro y datos del día (Source 5)
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", est) \
                .gte("timestamp", f"{hoy}T00:00:00") \
                .order("timestamp", desc=True) \
                .execute()
            
            df_est = pd.DataFrame(res.data)
            
            if not df_est.empty:
                ultimo = df_est.iloc[0]
                ts_ultimo = pd.to_datetime(ultimo['timestamp']).tz_convert('America/Santiago')
                min_inactivo = int((ahora - ts_ultimo).total_seconds() / 60)
                
                # Cálculos de valor agregado (Source 5)
                min_on = df_est[df_est['estado'] == True].shape[0] * 5 # Estimado por bloques
                uptime_pct = round((min_on / (ahora.hour * 60 + ahora.minute)) * 100, 1) if ahora.hour > 0 else 100
                
                status_icon = "🟢 ONLINE" if ultimo['estado'] and min_inactivo < 15 else "🔴 OFFLINE"
                
                datos_resumen.append({
                    "Estación": est,
                    "Estado": status_icon,
                    "Última Conexión": ts_ultimo.strftime('%H:%M:%S'),
                    "Inactivo hace": f"{min_inactivo} min",
                    "Uptime Hoy": f"{uptime_pct}%",
                    "Total Online": f"{min_on} min"
                })
            else:
                datos_resumen.append({
                    "Estación": est, "Estado": "⚪ SIN DATOS", "Última Conexión": "--", 
                    "Inactivo hace": "--", "Uptime Hoy": "0%", "Total Online": "0 min"
                })
        except:
            pass
    return pd.DataFrame(datos_resumen)

# --- INTERFAZ SUPERIOR ---
st.markdown("### 📊 Monitor SanLeon")

df_resumen = obtener_resumen_estaciones()

# Mostrar tabla resumen con todas las estaciones y nuevas métricas (Source 3)
st.dataframe(
    df_resumen,
    column_config={
        "Estado": st.column_config.TextColumn("Estado", help="Online si reportó hace menos de 15 min"),
        "Uptime Hoy": st.column_config.ProgressColumn("Uptime Hoy", format="%s", min_value=0, max_value=100),
    },
    hide_index=True,
    use_container_width=True
)

st.divider()

# --- CONTROLES Y GRÁFICA (Igual a la versión anterior pero optimizado) ---
c1, c2 = st.columns([2, 1])
with c1:
    est_sel = st.selectbox("Visualizar detalle de:", ESTACIONES, index=4)
with c2:
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

# (Aquí sigue el código de la gráfica de Actividad 24h que ya teníamos...)
