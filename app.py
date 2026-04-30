import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz

# Configuración de pantalla
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=10)
def obtener_estado_actual():
    estados = []
    ahora = datetime.now(tz)
    for estacion in ESTACIONES:
        try:
            # FILTRO CRÍTICO: Solo buscamos el último registro que sea TRUE (Conectado)
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", estacion) \
                .eq("estado", True) \
                .order("timestamp", desc=True) \
                .limit(1).execute()
            
            if res.data:
                data = res.data[0]
                ts_v = pd.to_datetime(data['timestamp']).tz_convert('America/Santiago')
                diff_min = (ahora - ts_v).total_seconds() / 60
                
                # Si el último "OK" fue hace menos de 15 min, está ONLINE
                esta_online = diff_min < 15
                
                estados.append({
                    "Estación": estacion,
                    "Estado": "🟢 ONLINE" if esta_online else "🔴 OFFLINE",
                    "Última conexión (OK)": ts_v.strftime('%Y-%m-%d %H:%M:%S'),
                    "Inactivo desde OK": "0 min" if esta_online else f"{int(diff_min)} min"
                })
            else:
                estados.append({"Estación": estacion, "Estado": "🔴 OFFLINE", "Última conexión (OK)": "Sin datos hoy", "Inactivo desde OK": "--"})
        except: continue
    return pd.DataFrame(estados)

@st.cache_data(ttl=30)
def cargar_grafica_descarte(device, fecha):
    try:
        inicio, fin = f"{fecha}T00:00:00", f"{fecha}T23:59:59"
        # Solo cargamos registros TRUE para la gráfica
        res = supabase.table("historial_conexiones").select("*") \
            .eq("device", device) \
            .eq("estado", True) \
            .gte("timestamp", inicio).lte("timestamp", fin).order("timestamp").execute()
        
        df = pd.DataFrame(res.data)
        if df.empty: return pd.DataFrame()

        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
        timeline = []
        for i in range(len(df)):
            curr = df.iloc[i]['timestamp']
            timeline.append({'Inicio': curr, 'Fin': curr + timedelta(minutes=5), 'Estado': 'Conectado'})
            if i < len(df) - 1:
                prox = df.iloc[i+1]['timestamp']
                # Si hay más de 12 min de silencio, marcamos desconexión (descarte)
                if (prox - curr).total_seconds() / 60 > 12:
                    timeline.append({'Inicio': curr + timedelta(minutes=5), 'Fin': prox, 'Estado': 'Desconectado'})
        return pd.DataFrame(timeline)
    except: return pd.DataFrame()

# --- INTERFAZ ---
st.markdown("### 📊 Monitor SanLeon (En Vivo)")
df_act = obtener_estado_actual()
col_t, col_c = st.columns([3, 1])

with col_t:
    if not df_act.empty:
        st.table(df_act)

with col_c:
    st.caption(f"🕒 Sincronización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Seleccionar Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())

st.markdown(f"#### 📈 Historial: {est_sel}")
df_g = cargar_grafica_descarte(est_sel, fec_sel)

if not df_g.empty:
    fig = px.timeline(df_g, x_start="Inicio", x_end="Fin", y=[est_sel]*len(df_g), color="Estado",
                     color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
                     range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"])
    fig.update_layout(height=180, showlegend=True, margin=dict(l=0, r=20, t=10, b=10),
                      xaxis=dict(dtick=7200000, tickformat="%H:%M"), yaxis=dict(visible=False),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay actividad registrada para esta fecha.")
