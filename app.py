import streamlit as st
import pandas as pd
import requests
import time
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# 1. Configuración de pantalla
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)

# Refresco automático cada 60 segundos (Esto gatilla el respaldo de grabación)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión y Configuración
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

# --- FUNCIÓN NUEVA: RESPALDO DE GRABACIÓN EN TIEMPO REAL ---
def respaldo_grabacion_activa():
    """Esta función graba en la BDD cada vez que alguien mira la App"""
    try:
        # Consulta a ZeroTier desde la App
        res = requests.get(
            f"https://api.zerotier.com/api/v1/network/{st.secrets['ZT_NETWORK_ID']}/member",
            headers={"Authorization": f"token {st.secrets['ZT_API_TOKEN']}"},
            timeout=10
        ).json()

        ahora_ms = time.time() * 1000
        timestamp_chile = datetime.now(tz).isoformat()
        datos_a_insertar = []

        for nombre in ESTACIONES:
            m = next((item for item in res if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen', 0)
            
            # Si se vio hace menos de 7 minutos, grabamos como ONLINE
            if (ahora_ms - last_seen) / 1000 < 420: 
                datos_a_insertar.append({
                    "device": nombre,
                    "estado": True,
                    "duracion_min": 1.0, # Al ser refresco de app, es minuto a minuto
                    "timestamp": timestamp_chile
                })

        if datos_a_insertar:
            # Grabamos solo si hay gente online para no saturar
            supabase.table("historial_conexiones").insert(datos_a_insertar).execute()
    except Exception as e:
        # Falla silenciosa para no interrumpir al usuario
        pass

# Ejecutamos el respaldo justo al cargar/refrescar
respaldo_grabacion_activa()

# --- LÓGICA DE VISTA (Original) ---
@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    ahora = datetime.now(tz)
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones") \
                .select("*").eq("device", estacion).eq("estado", True) \
                .order("timestamp", desc=True).limit(1).execute()
            
            if res.data:
                ts_v = pd.to_datetime(res.data[0]['timestamp']).tz_convert('America/Santiago')
                diff_min = (ahora - ts_v).total_seconds() / 60
                esta_online = diff_min < 15 # Tolerancia de visualización
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_v.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": "0 min" if esta_online else f"{int(diff_min)} min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin datos", "Inactivo desde OK": "--"})
        except: continue
    return pd.DataFrame(estados)

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")
df_act = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])

with col_t:
    st.table(df_act)

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

# Gráfica Timeline
# (Aquí sigue tu código de carga_grafica_timeline que ya tienes)
