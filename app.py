import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones").select("*").eq("device", estacion).order("timestamp", desc=True).limit(1).execute()
            if res.data:
                data = res.data[0]
                ts = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                # Si el último registro 'True' fue hace más de 10 min, está OFFLINE
                is_online = (datetime.now(tz) - ts).total_seconds() / 60 < 10
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": f"{int((datetime.now(tz)-ts).total_seconds()/60)} min" if not is_online else "0 min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Nunca", "Inactivo desde OK": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_datos_grafica(device, fecha):
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        res = supabase.table("historial_conexiones").select("*").eq("device", device).gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame()

        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        df = df.sort_values('timestamp')
        
        # --- LÓGICA DE DESCARTE PARA LA GRÁFICA ---
        timeline = []
        for i in range(len(df)):
            curr_ts = df.iloc[i]['timestamp']
            # Bloque de conexión (Verde)
            timeline.append({'inicio': curr_ts, 'fin': curr_ts + timedelta(minutes=5), 'Estado': 'Conectado'})
            
            # Si hay un salto mayor a 10 min entre registros, insertar bloque rojo
            if i < len(df) - 1:
                next_ts = df.iloc[i+1]['timestamp']
                if (next_ts - curr_ts).total_seconds() / 60 > 10:
                    timeline.append({'inicio': curr_ts + timedelta(minutes=5), 'fin': next_ts, 'Estado': 'Desconectado'})
        
        return pd.DataFrame(timeline)
    except: return pd.DataFrame()

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")
df_actual = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])

with col_t:
    st.table(df_actual) if not df_actual.empty else st.warning("Conectando...")

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")
df_g = cargar_datos_grafica(est_sel, fec_sel)

if not df_g.empty:
    fig = px.timeline(df_g, x_start="inicio", x_end="fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    fig.update_layout(height=200, showlegend=True, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(dtick=7200000, tickformat="%H:%M", title="Hora del día"), yaxis=dict(visible=False))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin actividad registrada hoy.")
