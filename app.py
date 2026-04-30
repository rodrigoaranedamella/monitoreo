import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración de página
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)

# Refresco automático cada 1 minuto
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    """Calcula el estado actual basándose en la última conexión exitosa"""
    estados = []
    ahora = datetime.now(tz)
    
    for estacion in ESTACIONES:
        try:
            # Buscamos SOLO el último registro que sea TRUE
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .eq("estado", True) \
                .order("timestamp", desc=True) \
                .limit(1).execute()
            
            if res.data:
                data = res.data[0]
                ts_ultimo = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                minutos_desde_ultimo = (ahora - ts_ultimo).total_seconds() / 60
                
                # Si el último 'True' fue hace menos de 15 min, sigue ONLINE
                esta_online = minutos_desde_ultimo < 15
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_ultimo.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": "0 min" if esta_online else f"{int(minutos_desde_ultimo)} min"
                })
            else:
                estados.append({
                    "Estación": estacion, 
                    "Estado": "🔴 OFFLINE", 
                    "Última conexión (OK)": "Sin datos hoy", 
                    "Inactivo desde OK": "--"
                })
        except:
            continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_descarte(device, fecha):
    """Reconstruye la línea de tiempo usando lógica de descarte"""
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        # Solo usamos registros TRUE para dibujar la gráfica
        res = supabase.table("historial_conexiones").select("*") \
            .eq("device", device) \
            .eq("estado", True) \
            .gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        
        df_base = pd.DataFrame(res.data)
        if df_base.empty: return pd.DataFrame()

        df_base['timestamp'] = pd.to_datetime(df_base['timestamp']).dt.tz_convert('America/Santiago')
        
        timeline = []
        for i in range(len(df_base)):
            actual = df_base.iloc[i]['timestamp']
            # Bloque Verde (Conexión confirmada)
            timeline.append({'Inicio': actual, 'Fin': actual + timedelta(minutes=5), 'Estado': 'Conectado'})
            
            # Bloque Rojo (Si hay un hueco mayor a 12 min, rellenamos con rojo)
            if i < len(df_base) - 1:
                siguiente = df_base.iloc[i+1]['timestamp']
                if (siguiente - actual).total_seconds() / 60 > 12:
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
        st.warning("Base de datos vacía. Esperando primera conexión...")

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4) # Jennifer por defecto
    fec_sel = st.date_input("Fecha de consulta", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial de Conexión: {est_sel}")
df_g = cargar_grafica_descarte(est_sel, fec_sel)

if not df_g.empty:
    fig = px.timeline(df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    
    fig.update_layout(height=200, showlegend=True, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(dtick=7200000, tickformat="%H:%M", title="Hora del día"),
                      yaxis=dict(visible=False), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"No hay registros de conexión para {est_sel} el día de hoy.")
