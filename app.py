import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración
st.set_page_config(page_title="Monitor SanLeon", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh") # Refresco cada minuto

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    ahora = datetime.now(tz)
    for estacion in ESTACIONES:
        try:
            # Traer solo el último registro exitoso (estado=True)
            res = supabase.table("historial_conexiones").select("*").eq("device", estacion).eq("estado", True).order("timestamp", desc=True).limit(1).execute()
            
            if res.data:
                data = res.data[0]
                ts_v = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                diff_min = (ahora - ts_v).total_seconds() / 60
                
                # Si el último registro TRUE es reciente ( < 15 min), está ONLINE
                esta_online = diff_min < 15
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_v.strftime('%H:%M:%S'),
                    "Inactivo desde OK": f"{int(diff_min)} min" if not esta_online else "0 min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin datos hoy", "Inactivo desde OK": "--"})
        except: continue
    return pd.DataFrame(estados)

# --- UI ---
st.title("📊 Monitor SanLeon (En Vivo)")
df_act = obtener_estado_actual()
st.table(df_act)

# Filtros para la gráfica
est_sel = st.selectbox("Ver historial de:", ESTACIONES, index=4)
fec_sel = st.date_input("Fecha:", datetime.now(tz).date())

# Gráfica corregida
res_g = supabase.table("historial_conexiones").select("*").eq("device", est_sel).gte("timestamp", f"{fec_sel}T00:00:00").execute()
df_g = pd.DataFrame(res_g.data)

if not df_g.empty:
    df_g['timestamp'] = pd.to_datetime(df_g['timestamp']).dt.tz_convert('America/Santiago')
    fig = px.scatter(df_g, x="timestamp", y="device", color="estado", 
                     color_discrete_map={True: "#00CC96", False: "#EF553B"},
                     title=f"Conexiones de {est_sel}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay datos para mostrar en la gráfica todavía.")
