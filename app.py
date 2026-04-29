import streamlit as st
import pandas as pd
import pytz
import requests
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página y optimización EXTREMA de espacio
st.set_page_config(page_title="SanLeon Monitor Pro", layout="wide", page_icon="📊")

st.markdown("""
    <style>
        /* Elimina el espacio blanco superior del contenedor */
        .block-container { padding-top: 0rem; padding-bottom: 0rem; margin-top: -1rem; }
        /* Reduce el tamaño y margen del título */
        h1 { margin-top: -0.5rem; margin-bottom: 0.2rem; font-size: 1.6rem; font-weight: bold; }
        /* Bordes y fondo para el gráfico */
        .stPlotlyChart { border: 1px solid #444; border-radius: 5px; padding: 2px; background-color: #0e1117; }
        /* Ajuste fino para los widgets de la derecha */
        .stSelectbox, .stDateInput { margin-bottom: -1rem; }
    </style>
""", unsafe_allow_html=True)

# 2. Constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# Refresco automático cada 2 minutos
st_autorefresh(interval=120 * 1000, key="datarefresh")

@st.cache_data(ttl=15, show_spinner=False)
def obtener_vivo():
    try:
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'},
            timeout=10
        ).json()
        
        datos = []
        ahora_ms = time.time() * 1000
        for n in ESTACIONES:
            m = next((item for item in res if item.get('name') == n), {})
            ls = m.get('lastSeen', 0)
            online = (ahora_ms - ls) / 1000 < 900
            ts = pd.to_datetime(ls, unit='ms', utc=True).tz_convert(CHILE_TZ) if ls > 0 else None
            
            datos.append({
                'Estación': n,
                'Estado': "🟢 ONLINE" if online else "🔴 OFFLINE",
                'Última conexión': ts.strftime('%H:%M:%S') if ts else "N/A",
                'Inactivo hace': f"{int((ahora_ms - ls)/60000)} min" if ls > 0 else "---"
            })
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def cargar_historial():
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        # Conversión robusta a hora de Chile
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(CHILE_TZ)
        return df
    except: return pd.DataFrame()

# ==========================================
# INTERFAZ PRINCIPAL (Subida horizontalmente)
# ==========================================
st.title("📊 Monitor SanLeon")

col_tabla, col_controles = st.columns([3.8, 1.2])

with col_tabla:
    df_vivo = obtener_vivo()
    if not df_vivo.empty:
        # Altura aumentada a 280 para que quepan las 6 estaciones sin scroll
        st.dataframe(df_vivo, use_container_width=True, hide_index=True, height=280)

with col_controles:
    st.info(f"🕒 **Act:** {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    st.write("") # Espaciador
    if st.button("🔄 Refrescar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ==========================================
# LÓGICA DE CONTINUIDAD PARA EL GRÁFICO
# ==========================================
h_df = cargar_historial()
if not h_df.empty:
    mask = (h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)
    filtro = h_df.loc[mask].copy()
    
    if not filtro.empty:
        st.subheader(f"📈 Actividad 24h: {est_sel}")
        filtro = filtro.sort_values('timestamp')
        filtro['Estado_Txt'] = filtro['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        
        # --- NUEVA LÓGICA DE CONTINUIDAD ---
        # El 'fin' de un bloque es el 'inicio' del siguiente para que se vean unidos
        filtro['fin'] = filtro['timestamp'].shift(-1)
        
        # Si el salto entre registros es > 40 min, asumimos que hubo un corte real y no unimos
        gap_limit = pd.Timedelta(minutes=40)
        corte_mask = (filtro['fin'] - filtro['timestamp']) > gap_limit
        
        # Para los registros finales o con saltos grandes, damos 10 min de duración estándar
        filtro.loc[filtro['fin'].isna() | corte_mask, 'fin'] = filtro['timestamp'] + pd.Timedelta(minutes=10)
        
        inicio_eje = pd.Timestamp.combine(fec_sel, pd.Timestamp.min.time()).replace(tzinfo=CHILE_TZ)
        fin_eje = pd.Timestamp.combine(fec_sel, pd.Timestamp.max.time()).replace(tzinfo=CHILE_TZ)

        fig = px.timeline(
            filtro, 
            x_start="timestamp", 
            x_end="fin", 
            y="device", 
            color="Estado_Txt",
            color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"}
        )
        
        fig.update_layout(
            xaxis=dict(range=[inicio_eje, fin_eje], dtick=7200000, tickformat="%H:%M", gridcolor="#333", title="Horario (pasos de 2h)"),
            yaxis=dict(visible=False),
            height=160,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📜 Detalle de Registros")
        display_df = filtro.sort_values('timestamp', ascending=False).copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Visual'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        st.dataframe(display_df[['Hora', 'Visual', 'duracion_min']], use_container_width=True, hide_index=True, height=350)
    else:
        st.info(f"Sin registros para {est_sel} el {fec_sel}.")
