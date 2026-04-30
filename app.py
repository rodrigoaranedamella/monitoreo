import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz
import requests
import time

# 1. Configuración de pantalla y estilos (Original)
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)

# Refresco automático cada 60 segundos
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión y Configuración
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

# --- NUEVA FUNCIÓN DE APOYO A LA PERSISTENCIA ---
def apoyo_persistencia_realtime():
    """Esta función graba en la BDD si detecta conexión mientras usas la app"""
    try:
        ZT_API_TOKEN = st.secrets["ZT_API_TOKEN"]
        ZT_NETWORK_ID = st.secrets["ZT_NETWORK_ID"]
        
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{ZT_NETWORK_ID}/member",
            headers={"Authorization": f"token {ZT_API_TOKEN}"},
            timeout=10
        ).json()

        ahora_ms = time.time() * 1000
        timestamp_chile = datetime.now(tz).isoformat()
        datos_respaldo = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Si se vio hace menos de 5 min y estamos en la app, grabamos el 'checkpoint'
            if (ahora_ms - last_seen) / 1000 < 300:
                datos_respaldo.append({
                    "device": nombre,
                    "estado": True,
                    "duracion_min": 1.0, # Registro de apoyo
                    "timestamp": timestamp_chile
                })

        if datos_respaldo:
            supabase.table("historial_conexiones").insert(datos_respaldo).execute()
    except Exception as e:
        pass # Silencioso para no interrumpir la experiencia del usuario

# Ejecutar el apoyo de grabación cada vez que la app carga/refresca
apoyo_persistencia_realtime()

@st.cache_data(ttl=10)
def obtener_estado_actual():
    """Busca el último registro exitoso para determinar el estado"""
    estados = []
    ahora = datetime.now(tz)
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones") \
                .select("*").eq("device", estacion).eq("estado", True) \
                .order("timestamp", desc=True).limit(1).execute()
            
            if res.data:
                data = res.data[0]
                ts_v = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                diff_min = (ahora - ts_v).total_seconds() / 60
                
                # Tolerancia de 30 min por retrasos de GitHub
                esta_online = diff_min < 30
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🔴 OFFLINE" if not esta_online else "🟢 ONLINE",
                    "Última conexión (OK)": ts_v.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": "0 min" if esta_online else f"{int(diff_min)} min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin datos hoy", "Inactivo desde OK": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_timeline(device, fecha):
    """Mantiene la gráfica de barras original"""
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        res = supabase.table("historial_conexiones").select("*").eq("device", device) \
            .eq("estado", True).gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame()

        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            timeline.append({'Inicio': curr, 'Fin': curr + timedelta(minutes=5), 'Estado': 'Conectado'})
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                if (prox - curr).total_seconds() / 60 > 12:
                    timeline.append({'Inicio': curr + timedelta(minutes=5), 'Fin': prox, 'Estado': 'Desconectado'})
        return pd.DataFrame(timeline)
    except: return pd.DataFrame()

# --- INTERFAZ (Frontend original intacto) ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")
df_act = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])

with col_t:
    if not df_act.empty:
        st.table(df_act)

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")
df_g = cargar_grafica_timeline(est_sel, fec_sel)

if not df_g.empty:
    fig = px.timeline(df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    fig.update_layout(height=180, showlegend=True, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(dtick=7200000, tickformat="%H:%M"), yaxis=dict(visible=False),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"No hay actividad registrada para {est_sel} en esta fecha.")
