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

# Estilo para el cuadro azul solicitado
st.markdown("""
    <style>
    .blue-box {
        background-color: #e1f5fe;
        border-left: 5px solid #01579b;
        padding: 10px;
        border-radius: 5px;
        color: #01579b;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# REFRESCO CADA 1 MINUTO
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión (Usando tus parámetros confirmados)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def apoyo_persistencia_5min():
    """Graba en BDD cada 5 minutos si la app está abierta"""
    try:
        ahora = datetime.now(tz)
        hace_poco = (ahora - timedelta(minutes=4, seconds=50)).isoformat()
        
        check = supabase.table("historial_conexiones").select("id").gte("timestamp", hace_poco).limit(1).execute()

        if not check.data:
            res = requests.get(
                f"https://api.zerotier.com/api/v1/network/{st.secrets['ZT_NETWORK_ID']}/member",
                headers={"Authorization": f"token {st.secrets['ZT_API_TOKEN']}"}, timeout=10
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
                esta_online = diff_min < 20
                estados.append({
                    "Estación": estacion, "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión": ts_v.strftime('%H:%M:%S'),
                    "Inactivo": f"{int(diff_min)} min" if not esta_online else "0 min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión": "Sin datos", "Inactivo": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_timeline(device, fecha):
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        res = supabase.table("historial_conexiones").select("*").eq("device", device).eq("estado", True).gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        df = pd.DataFrame(res.data)
        
        if df.empty: return pd.DataFrame(), 0
        
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        total_minutos = df['duracion_min'].sum()
        
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            duracion = float(df.iloc[i]['duracion_min'])
            
            # El fin del bloque es el inicio + la duración registrada
            fin_bloque = curr + timedelta(minutes=duracion)
            
            timeline.append({'Inicio': curr, 'Fin': fin_bloque, 'Estado': 'Conectado'})
            
            # Lógica de continuidad: Si el siguiente registro está muy lejos, marcar desconexión
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                # Si hay un hueco mayor a la duración + 2 minutos de margen
                if (prox - fin_bloque).total_seconds() / 60 > 2:
                    timeline.append({'Inicio': fin_bloque, 'Fin': prox, 'Estado': 'Desconectado'})
        
        return pd.DataFrame(timeline), total_minutos
    except Exception as e:
        return pd.DataFrame(), 0

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon")

df_act = obtener_estado_actual()
col_t, col_c = st.columns([2, 1])

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())
    
    # Obtener datos de la gráfica y el total
    df_g, total_min = cargar_grafica_timeline(est_sel, fec_sel)
    
    # CUADRO AZUL SOLICITADO (Resumen de tiempo)
    horas = int(total_min // 60)
    mins = int(total_min % 60)
    st.markdown(f"""
        <div class="blue-box">
            ⏱️ TIEMPO TOTAL CONECTADO<br>
            <span style="font-size: 24px;">{horas}h {mins}m</span><br>
            <small>Basado en registros de BDD</small>
        </div>
        """, unsafe_allow_html=True)

with col_t:
    st.table(df_act)

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")

if not df_g.empty:
    fig = px.timeline(
        df_g, 
        x_start="Inicio", 
        x_end="Fin", 
        y=[est_sel]*len(df_g), 
        color="Estado",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        # Rango forzado hasta las 23:59
        range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"]
    )
    fig.update_layout(
        height=180, 
        showlegend=False, 
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(dtick=7200000, tickformat="%H:%M") # Marcas cada 2 horas
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"No hay actividad registrada para {est_sel} el {fec_sel}.")
