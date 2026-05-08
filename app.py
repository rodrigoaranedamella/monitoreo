import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go  # <--- Verifica que esta línea exista
from datetime import datetime, timedelta
import pytz
import requests
import time

# 1. Configuración de pantalla
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")

# Estilos CSS específicos
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
    /* Recuadro de 0.5mm rodeando la gráfica con fondo negro */
    .graph-frame {
        background-color: black;
        border: 0.5px solid white; 
        padding: 5px;
        border-radius: 2px;
        max-width: 90%; /* Menos ancha */
        margin: 0 auto;  /* Centrada */
    }
    </style>
    """, unsafe_allow_html=True)

# Refresco cada 1 minuto
st_autorefresh(interval=60 * 1000, key="datarefresh")

# 2. Conexión y Configuración de Zona Horaria (Chile)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz_chile = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

def apoyo_persistencia_5min():
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
                # Busca esta parte dentro de la función obtener_estado_actual y cámbiala:
estados.append({
    "Estación": estacion, 
    "Estado": "<span style='font-size: 22px; color: #00CC96;'>●</span> ONLINE" if esta_online else "<span style='font-size: 12px; color: red;'>●</span> OFFLINE",
    "Última conexión": ts_v.strftime('%d-%m-%Y %H:%M:%S'),
    "Inactivo": f"{int(diff_min)} min" if not esta_online else "0 min"
})
                # estados.append({
                #    "Estación": estacion, "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                 #   "Última conexión": ts_v.strftime('%d-%m-%Y %H:%M:%S'),
                  #  "Inactivo": f"{int(diff_min)} min" if not esta_online else "0 min"
                #})
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión": "Sin datos", "Inactivo": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_timeline(device, fecha_str):
    try:
        fecha_obj = datetime.strptime(str(fecha_str), '%Y-%m-%d')
        inicio_dt = tz_chile.localize(datetime.combine(fecha_obj, datetime.min.time()))
        fin_dt = tz_chile.localize(datetime.combine(fecha_obj, datetime.max.time()))
        
        res = supabase.table("historial_conexiones").select("*") \
            .eq("device", device).eq("estado", True) \
            .gte("timestamp", inicio_dt.isoformat()) \
            .lte("timestamp", fin_dt.isoformat()) \
            .order("timestamp").execute()
        
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame(), 0
        
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        total_minutos = df['duracion_min'].sum()
        
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            duracion = float(df.iloc[i]['duracion_min'])
            fin_bloque = curr + timedelta(minutes=duracion)
            timeline.append({'Inicio': curr, 'Fin': fin_bloque, 'Estado': 'Conectado'})
            
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                if (prox - fin_bloque).total_seconds() / 60 > 2:
                    # Las desconexiones se marcan con el estado 'Desconectado' para el color Rojo
                    timeline.append({'Inicio': fin_bloque, 'Fin': prox, 'Estado': 'Desconectado'})
        
        return pd.DataFrame(timeline), total_minutos
    except Exception: return pd.DataFrame(), 0

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon")

df_act = obtener_estado_actual()
col_t, col_c = st.columns([2, 1])

with col_c:
    st.caption(f"🕒 Sincronización Local: {datetime.now(tz_chile).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz_chile).date())
    df_g, total_min = cargar_grafica_timeline(est_sel, fec_sel)
    
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
# Busca donde dice: st.table(df_act)
# Y cámbialo por esto:
st.markdown(df_act.to_html(escape=False, index=False), unsafe_allow_html=True)

# st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")

# Contenedor con marco fino blanco (0.5mm) y dimensiones ajustadas
st.markdown('<div class="graph-frame">', unsafe_allow_html=True)
if not df_g.empty:
    rango_inicio = f"{fec_sel} 00:00:00"
    rango_fin = f"{fec_sel} 23:59:59"
    
    fig = px.timeline(
        df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "red"}, # Desconexiones en Rojo
        range_x=[rango_inicio, rango_fin]
    )
    
    fig.update_layout(
        height=120, # Más delgada (altura reducida)
        showlegend=False, 
        margin=dict(l=10, r=60, t=5, b=25), # Margen derecho amplio para el 23:59
        plot_bgcolor="black",
        paper_bgcolor="black",
        font=dict(color="white"),
        xaxis=dict(
            dtick=7200000, tickformat="%H:%M",
            showgrid=True, gridcolor="#222222",
            range=[rango_inicio, rango_fin],
            color="white",
            tickvals=[f"{fec_sel} {h:02d}:00:00" for h in range(0, 25, 2)] + [rango_fin]
        ),
        yaxis=dict(visible=False)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
else:
    st.info(f"No hay registros de conexión para {est_sel} el día {fec_sel}.")
st.markdown('</div>', unsafe_allow_html=True)
