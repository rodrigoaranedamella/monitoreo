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
        /* Sube todo el contenido eliminando el padding superior */
        .block-container { padding-top: 0.5rem; padding-bottom: 0rem; margin-top: -1.5rem; }
        /* Título ultra compacto */
        h2 { margin-top: -0.5rem; margin-bottom: 0.5rem; font-size: 1.5rem; }
        .stDataFrame { border: 1px solid #444; border-radius: 5px; }
        .stPlotlyChart { border: 1px solid #444; border-radius: 5px; background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# 2. Constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

st_autorefresh(interval=60 * 1000, key="datarefresh") # Refresco cada 1 min para más precisión

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
                'Inactivo hace': f"{int((ahora_ms - ls)/60000)} min" if ls > 0 else "---",
                'raw_ts': ts # Para uso interno del gráfico
            })
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

@st.cache_data(ttl=30)
def cargar_historial():
    # El parámetro '?t=' evita que GitHub sirva datos viejos por error de caché
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json?t={int(time.time())}"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(CHILE_TZ)
        return df
    except: return pd.DataFrame()

# ==========================================
# INTERFAZ COMPACTA
# ==========================================
# Título y Reloj en la misma fila para ahorrar espacio
c1, c2 = st.columns([3, 1])
with c1: st.subheader("📊 Monitor SanLeon")
with c2: st.info(f"🕒 **Act:** {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")

df_vivo = obtener_vivo()
col_tabla, col_controles = st.columns([3.8, 1.2])

with col_tabla:
    if not df_vivo.empty:
        # Altura de 260px garantiza ver las 6 estaciones de un vistazo
        st.dataframe(df_vivo[['Estación', 'Estado', 'Última conexión', 'Inactivo hace']], 
                     use_container_width=True, hide_index=True, height=260)

with col_controles:
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    if st.button("🔄 Forzar Actualización", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ==========================================
# LÓGICA DE GRÁFICO CON "PUENTE EN VIVO"
# ==========================================
h_df = cargar_historial()
if not h_df.empty:
    mask = (h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)
    filtro = h_df.loc[mask].copy()
    
    # Inyección de Actividad Actual: Si está online, dibujamos el bloque faltante
    info_vivo = df_vivo[df_vivo['Estación'] == est_sel].iloc[0]
    if "ONLINE" in info_vivo['Estado'] and fec_sel == pd.Timestamp.now(tz=CHILE_TZ).date():
        ahora = pd.Timestamp.now(tz=CHILE_TZ)
        # Usamos su última conexión de ZeroTier como inicio del bloque actual
        inicio_vivo = info_vivo['raw_ts'] if info_vivo['raw_ts'] else ahora - pd.Timedelta(minutes=5)
        
        fila_live = pd.DataFrame([{
            'device': est_sel, 'estado': True, 'timestamp': inicio_vivo, 
            'fin': ahora, 'Estado_Txt': "Conectado", 'duracion_min': 5
        }])
        filtro = pd.concat([filtro, fila_live], ignore_index=True)

    if not filtro.empty:
        st.write(f"📈 **Actividad 24h: {est_sel}**")
        filtro = filtro.sort_values('timestamp')
        filtro['Estado_Txt'] = filtro['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        
        # Continuidad: El fin de cada barra es el inicio de la siguiente
        filtro['fin'] = filtro['timestamp'].shift(-1)
        # Si el hueco es mayor a 30 min, lo tratamos como desconexión real
        gap_mask = (filtro['fin'] - filtro['timestamp']) > pd.Timedelta(minutes=30)
        filtro.loc[filtro['fin'].isna() | gap_mask, 'fin'] = filtro['timestamp'] + pd.Timedelta(minutes=10)
        
        inicio_eje = pd.Timestamp.combine(fec_sel, pd.Timestamp.min.time()).replace(tzinfo=CHILE_TZ)
        fin_eje = pd.Timestamp.combine(fec_sel, pd.Timestamp.max.time()).replace(tzinfo=CHILE_TZ)

        fig = px.timeline(filtro, x_start="timestamp", x_end="fin", y="device", color="Estado_Txt",
                          color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"})
        
        fig.update_layout(
            xaxis=dict(range=[inicio_eje, fin_eje], dtick=7200000, tickformat="%H:%M", gridcolor="#333", title="Horas"),
            yaxis=dict(visible=False), height=140, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        st.write("📜 **Detalle de Registros**")
        display_df = filtro.sort_values('timestamp', ascending=False).copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Visual'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        st.dataframe(display_df[['Hora', 'Visual', 'duracion_min']], use_container_width=True, hide_index=True, height=300)
