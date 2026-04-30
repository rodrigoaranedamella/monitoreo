import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración inicial
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    """Calcula el estado actual basándose en la ausencia de datos (descarte)"""
    estados = []
    ahora = datetime.now(tz)
    
    for estacion in ESTACIONES:
        try:
            res = supabase.table("historial_conexiones").select("*").eq("device", estacion).order("timestamp", desc=True).limit(1).execute()
            
            if res.data:
                data = res.data[0]
                ts_ultimo = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                minutos_desde_ultimo = (ahora - ts_ultimo).total_seconds() / 60
                
                # Si el último registro 'True' fue hace menos de 12 min, sigue ONLINE
                esta_online = minutos_desde_ultimo < 12
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_ultimo.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": "0 min" if esta_online else f"{int(minutos_desde_ultimo)} min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin registros", "Inactivo desde OK": "--"})
        except:
            continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_datos_grafica(device, fecha):
    """Reconstruye la línea de tiempo insertando bloques rojos donde hay huecos de tiempo"""
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        res = supabase.table("historial_conexiones").select("*").eq("device", device).gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        
        df_base = pd.DataFrame(res.data)
        if df_base.empty: return pd.DataFrame()

        df_base['timestamp'] = pd.to_datetime(df_base['timestamp']).dt.tz_convert('America/Santiago')
        
        timeline = []
        for i in range(len(df_base)):
            actual = df_base.iloc[i]['timestamp']
            # Bloque Verde (Conectado)
            timeline.append({'Inicio': actual, 'Fin': actual + timedelta(minutes=5), 'Estado': 'Conectado'})
            
            # Bloque Rojo (Desconectado por descarte)
            if i < len(df_base) - 1:
                siguiente = df_base.iloc[i+1]['timestamp']
                # Si hay un hueco mayor a 10 min, rellenamos con rojo
                if (siguiente - actual).total_seconds() / 60 > 10:
                    timeline.append({'Inicio': actual + timedelta(minutes=5), 'Fin': siguiente, 'Estado': 'Desconectado'})
        
        return pd.DataFrame(timeline)
    except:
        return pd.DataFrame()

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")
df_actual = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])

with col_t:
    if not df_actual.empty:
        st.table(df_actual)
    else:
        st.warning("Esperando datos de la base de datos...")

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")
df_g = cargar_datos_grafica(est_sel, fec_sel)

if not df_g.empty:
    fig = px.timeline(df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    
    fig.update_layout(height=200, showlegend=True, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(dtick=7200000, tickformat="%H:%M", title="Hora del día"),
                      yaxis=dict(visible=False), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"No hay actividad registrada para {est_sel} en esta fecha.")
