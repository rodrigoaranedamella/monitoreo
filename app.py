import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz
import requests
import time

# 1. Configuración de pantalla
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)

# REFRESCO CADA 1 MINUTO (60.000 ms) para actualizar la gráfica
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

# --- LÓGICA DE GRABACIÓN CADA 5 MINUTOS ---
def apoyo_persistencia_5min():
    """Graba en BDD solo cada 5 minutos exactos"""
    try:
        ahora = datetime.now(tz)
        # Verificamos si la App ya grabó algo en los últimos 4 minutos y 50 segundos
        hace_poco = (ahora - timedelta(minutes=4, seconds=50)).isoformat()
        
        check = supabase.table("historial_conexiones") \
            .select("id") \
            .gte("timestamp", hace_poco) \
            .limit(1).execute()

        # Si no hay registros recientes, la App graba
        if not check.data:
            ZT_API_TOKEN = st.secrets["ZT_API_TOKEN"]
            ZT_NETWORK_ID = st.secrets["ZT_NETWORK_ID"]
            res = requests.get(
                f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
                headers={"Authorization": f"token {ZT_API_TOKEN}"}, timeout=10
            ).json()

            timestamp_chile = ahora.isoformat()
            datos = []
            for nombre in ESTACIONES:
                m = next((item for item in res if item.get('name') == nombre), {})
                last_seen = m.get('lastSeen', 0)
                if (time.time() * 1000 - last_seen) / 1000 < 600:
                    datos.append({
                        "device": nombre, "estado": True,
                        "duracion_min": 5.0, "timestamp": timestamp_chile
                    })
            if datos:
                supabase.table("historial_conexiones").insert(datos).execute()
    except Exception: pass

apoyo_persistencia_5min()

@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    ahora = datetime.now(tz)
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones").select("*").eq("device", estacion).eq("estado", True).order("timestamp", desc=True).limit(1).execute()
            if res.data:
                ts_v = pd.to_datetime(res.data[0]['timestamp']).tz_convert('America/Santiago')
                diff_min = (ahora - ts_v).total_seconds() / 60
                esta_online = diff_min < 20 # Margen de tolerancia
                estados.append({
                    "Estación": estacion, "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_v.strftime('%H:%M:%S'),
                    "Inactivo": f"{int(diff_min)} min" if not esta_online else "0 min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin datos", "Inactivo": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_timeline(device, fecha):
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        res = supabase.table("historial_conexiones").select("*").eq("device", device).eq("estado", True).gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame()
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            # Bloques de 1 minuto para máxima sensibilidad en la gráfica
            timeline.append({'Inicio': curr, 'Fin': curr + timedelta(minutes=1), 'Estado': 'Conectado'})
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                if (prox - curr).total_seconds() / 60 > 7:
                    timeline.append({'Inicio': curr + timedelta(minutes=1), 'Fin': prox, 'Estado': 'Desconectado'})
        return pd.DataFrame(timeline)
    except: return pd.DataFrame()

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon (Actualización 1 min)")
df_act = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])
with col_t: st.table(df_act)
with col_c:
    st.caption(f"🕒 Sinc: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial: {est_sel}")
df_g = cargar_grafica_timeline(est_sel, fec_sel)
if not df_g.empty:
    fig = px.timeline(df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    fig.update_layout(height=180, showlegend=False, margin=dict(l=0, r=20, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
