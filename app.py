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

# Estilos CSS: Cuadro azul, recuadro blanco para la gráfica y ajustes generales
st.markdown("""
    <style>
    div.block-container { padding-top: 1rem; }
    .blue-box {
        background-color: #e1f5fe;
        border-left: 5px solid #01579b;
        padding: 15px;
        border-radius: 5px;
        color: #01579b;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .graph-container {
        background-color: white;
        border: 1px solid #dcdcdc;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# Refresco cada 1 minuto
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión y Configuración de Zona Horaria (Chile)
# Se asume que los parámetros están en st.secrets de Streamlit Cloud
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz_chile = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def apoyo_persistencia_5min():
    """Graba en BDD cada 5 minutos usando la zona horaria correcta"""
    try:
        ahora = datetime.now(tz_chile)
        hace_poco = (ahora - timedelta(minutes=4, seconds=50)).isoformat()
        
        check = supabase.table("historial_conexiones").select("id").gte("timestamp", hace_poco).limit(1).execute()

        if not check.data:
            res = requests.get(
                f"https://api.zerotier.com/api/v1/network/{st.secrets['ZT_NETWORK_ID']}/member",
                headers={"Authorization": f"token {st.secrets['ZT_API_TOKEN']}"}, timeout=10
            ).json()

            timestamp_iso = ahora.isoformat()
            datos = []
            for nombre in ESTACIONES:
                m = next((item for item in res if item.get('name') == nombre), {})
                last_seen = m.get('lastSeen', 0)
                if (time.time() * 1000 - last_seen) / 1000 < 600:
                    datos.append({
                        "device": nombre, "estado": True,
                        "duracion_min": 5.0, "timestamp": timestamp_iso
                    })
            if datos:
                supabase.table("historial_conexiones").insert(datos).execute()
    except Exception: pass

apoyo_persistencia_5min()

@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    ahora = datetime.now(tz_chile)
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones").select("*").eq("device", estacion).eq("estado", True).order("timestamp", desc=True).limit(1).execute()
            if res.data:
                ts_v = pd.to_datetime(res.data[0]['timestamp']).astimezone(tz_chile)
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
def cargar_grafica_timeline(device, fecha_str):
    """
    IMPORTANTE: Manejo de zona horaria para la consulta histórica.
    Convertimos el inicio y fin del día de Chile a formato ISO con offset para Supabase.
    """
    try:
        # Crear objetos datetime para el inicio y fin del día en Chile
        fecha_obj = datetime.strptime(str(fecha_str), '%Y-%m-%d')
        inicio_dt = tz_chile.localize(datetime.combine(fecha_obj, datetime.min.time()))
        fin_dt = tz_chile.localize(datetime.combine(fecha_obj, datetime.max.time()))
        
        # Consultar usando los ISO con offset (ej: 2026-05-07T00:00:00-04:00)
        res = supabase.table("historial_conexiones").select("*") \
            .eq("device", device).eq("estado", True) \
            .gte("timestamp", inicio_dt.isoformat()) \
            .lte("timestamp", fin_dt.isoformat()) \
            .order("timestamp").execute()
        
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(), 0
        
        # Convertir timestamps de BDD a hora de Chile
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        total_minutos = df['duracion_min'].sum()
        
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            duracion = float(df.iloc[i]['duracion_min'])
            fin_bloque = curr + timedelta(minutes=duracion)
            
            timeline.append({'Inicio': curr, 'Fin': fin_bloque, 'Estado': 'Conectado'})
            
            # Si hay un salto mayor a la duración + 2 min de margen, marcar desconexión
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                if (prox - fin_bloque).total_seconds() / 60 > 2:
                    timeline.append({'Inicio': fin_bloque, 'Fin': prox, 'Estado': 'Desconectado'})
        
        return pd.DataFrame(timeline), total_minutos
    except Exception:
        return pd.DataFrame(), 0

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon")

df_act = obtener_estado_actual()
col_t, col_c = st.columns([2, 1])

with col_c:
    st.caption(f"🕒 Sincronización Local: {datetime.now(tz_chile).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz_chile).date())
    
    df_g, total_min = cargar_grafica_timeline(est_sel, fec_sel)
    
    # Cuadro Azul de Tiempo Total
    horas = int(total_min // 60)
    mins = int(total_min % 60)
    st.markdown(f"""
        <div class="blue-box">
            ⏱️ TIEMPO TOTAL CONECTADO<br>
            <span style="font-size: 26px;">{horas}h {mins}m</span><br>
            <small>Basado en registros históricos Chile</small>
        </div>
        """, unsafe_allow_html=True)

with col_t:
    st.table(df_act)

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")

# Contenedor con fondo blanco para la gráfica
with st.container():
    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    if not df_g.empty:
        # Definimos el rango del eje X para que sea visible hasta el final
        # Añadimos un pequeño margen (10 min) para que el "23:59" no quede pegado al borde
        rango_inicio = f"{fec_sel} 00:00:00"
        rango_fin = f"{fec_sel} 23:59:59"
        
        fig = px.timeline(
            df_g, 
            x_start="Inicio", 
            x_end="Fin", 
            y=[est_sel]*len(df_g), 
            color="Estado",
            color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
            range_x=[rango_inicio, rango_fin]
        )
        
        fig.update_layout(
            height=180, 
            showlegend=False, 
            margin=dict(l=10, r=40, t=10, b=10), # Margen derecho (r=40) para ver el horario final
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis=dict(
                dtick=7200000, # Marcas cada 2 horas
                tickformat="%H:%M",
                showgrid=True,
                gridcolor="#f0f0f0",
                range=[rango_inicio, rango_fin]
            ),
            yaxis=dict(visible=False)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info(f"No hay registros de conexión para {est_sel} el día {fec_sel}.")
    st.markdown('</div>', unsafe_allow_html=True)
