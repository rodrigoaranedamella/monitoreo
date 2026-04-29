import streamlit as st
import pandas as pd
from supabase import create_client
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# 1. Configuración de pantalla y autorefresco al minuto
st.set_page_config(page_title="Monitor SanLeon", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True) # Reduce espacio superior
st_autorefresh(interval=60 * 1000, key="datarefresh")

# Conexión a Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

# Listado de todas las estaciones para el selector y la tabla
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]

@st.cache_data(ttl=30)
def obtener_estado_actual():
    # Definimos las 5 estaciones principales para la tabla superior
    estaciones_top = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON"]
    resumen = []
    ahora = datetime.now(tz)
    
    for est in estaciones_top:
        try:
            # Traer último registro de cada una para la tabla superior
            res = supabase.table("historial_conexiones") \
                .select("*") \
                .eq("device", est) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res.data:
                ultimo = res.data[0]
                ts = pd.to_datetime(ultimo['timestamp']).tz_convert('America/Santiago')
                dif_min = int((ahora - ts).total_seconds() / 60)
                
                # Estado basado en reporte reciente (15 min de tolerancia)
                estado = "🟢 ONLINE" if ultimo['estado'] and dif_min < 15 else "🔴 OFFLINE"
                resumen.append({
                    "Estación": est,
                    "Estado": estado,
                    "Última conexión": ts.strftime('%H:%M:%S'),
                    "Inactivo hace": f"{dif_min} min"
                })
            else:
                resumen.append({"Estación": est, "Estado": "🔴 OFFLINE", "Última conexión": "--", "Inactivo hace": "--"})
        except:
            resumen.append({"Estación": est, "Estado": "Error DB", "Última conexión": "--", "Inactivo hace": "--"})
    
    return pd.DataFrame(resumen)

@st.cache_data(ttl=30)
def cargar_datos_totales(device, fecha):
    try:
        # Consulta automática a la base de datos para la gráfica
        res = supabase.table("historial_conexiones") \
            .select("*") \
            .eq("device", device) \
            .gte("timestamp", f"{fecha}T00:00:00") \
            .lte("timestamp", f"{fecha}T23:59:59") \
            .order("timestamp") \
            .execute()
        
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Santiago')
            # Lógica de persistencia de 2 minutos
            df['diff'] = df['timestamp'].diff().dt.total_seconds() / 60
            df['duracion_real'] = df['duracion_min']
            df.loc[df['diff'] <= 2.1, 'duracion_real'] = df['diff']
        return df
    except:
        return pd.DataFrame()

# --- PARTE SUPERIOR (Tabla de 5 filas y Controles) ---
st.markdown("### 📊 Monitor SanLeon")

col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    df_estado = obtener_estado_actual()
    # Tabla compacta para 5 estaciones
    st.dataframe(
        df_estado, 
        hide_index=True, 
        use_container_width=True,
        height=212 # Altura ajustada para 5 filas exactas
    )

with col_ctrl:
    st.caption(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación detalle", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())
    if st.button("🔄 Refrescar Manual", use_container_width=True):
        st.cache_data.clear()

# --- GRÁFICA ACTIVIDAD 24H (Estilo Recuadro) ---
df_hist = cargar_datos_totales(est_sel, fec_sel)

st.markdown(f"#### 📈 Actividad 24h: {est_sel}")

if not df_hist.empty:
    df_hist['Estado_Txt'] = df_hist['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
    df_hist['fin'] = df_hist['timestamp'] + pd.Timedelta(minutes=5)
    
    fig = px.timeline(
        df_hist, 
        x_start="timestamp", 
        x_end="fin", 
        y="device", 
        color="Estado_Txt",
        color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"},
        range_x=[f"{fec_sel} 00:00:00", f"{fec_sel} 23:59:59"] 
    )

    fig.update_layout(
        height=220,
        showlegend=True,
        legend_title_text="",
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(
            dtick=7200000, # Marcas cada 2 horas
            tickformat="%H:%M",
            gridcolor="#333", 
            title="Horario (pasos de 2h)"
        ),
        yaxis=dict(visible=False)
    )
    
    # Recuadro gris perimetral
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- MÉTRICAS Y TABLA DETALLE ---
    min_conectado = df_hist[df_hist['estado'] == True]['duracion_real'].sum()
    st.markdown(f"**Tiempo Conectado Permanente:** {int(min_conectado // 60)}h {int(min_conectado % 60)}min")
    
    st.markdown("#### 📜 Detalle de Registros")
    st.dataframe(
        df_hist[['timestamp', 'Estado_Txt', 'duracion_real']].rename(
            columns={'timestamp': 'Hora', 'Estado_Txt': 'Visual', 'duracion_real': 'Duración (min)'}
        ),
        use_container_width=True,
        height=200
    )
else:
    st.info("No hay datos disponibles para el día seleccionado.")
