import streamlit as st
import pandas as pd
import pytz
import requests
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página y optimización de espacio
st.set_page_config(page_title="SanLeon Monitor Pro", layout="wide", page_icon="📊")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { margin-top: -1rem; margin-bottom: 0.5rem; font-size: 2rem; }
        .stPlotlyChart { border: 1px solid #444; border-radius: 5px; padding: 5px; }
    </style>
""", unsafe_allow_html=True)

# 2. Constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# 3. Refresco automático nativo cada 2 minutos
st_autorefresh(interval=120 * 1000, key="datarefresh")

@st.cache_data(ttl=10, show_spinner=False)
def obtener_vivo():
    try:
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{st.secrets["ZT_NETWORK_ID"]}/member',
            headers={'Authorization': f'token {st.secrets["ZT_API_TOKEN"]}'},
            timeout=10
        ).json()
        
        datos = []
        for n in ESTACIONES:
            m = next((item for item in res if item.get('name') == n), {})
            ls = m.get('lastSeen', 0)
            online = ((time.time() * 1000 - ls) / 1000) < 900
            ts = pd.to_datetime(ls, unit='ms', utc=True).tz_convert(CHILE_TZ) if ls > 0 else None
            
            datos.append({
                'Estación': n,
                'Estado': "🟢 ONLINE" if online else "🔴 OFFLINE",
                'Última conexión': ts.strftime('%H:%M:%S') if ts else "N/A",
                'Inactivo hace': f"{int((time.time()*1000-ls)/60000)} min" if ls > 0 else "---"
            })
        return pd.DataFrame(datos)
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def cargar_historial():
    url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/historial_conexiones.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601').dt.tz_convert(CHILE_TZ)
        return df
    except: return pd.DataFrame()

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================
st.title("📊 Monitor SanLeon")

# Fila superior compacta[cite: 4]
col_v1, col_v2 = st.columns([4, 1.2])
with col_v1:
    df_vivo = obtener_vivo()
    if not df_vivo.empty:
        st.dataframe(df_vivo, use_container_width=True, hide_index=True, height=220)

with col_v2:
    st.info(f"🕒 **Actualización:** {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES)
    fec_sel = st.date_input("Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    if st.button("🔄 Refrescar Manual", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Historial y Gráfica
h_df = cargar_historial()
if not h_df.empty:
    filtro = h_df[(h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)].copy()
    
    if not filtro.empty:
        st.subheader(f"📈 Actividad 24h: {est_sel}")
        filtro = filtro.sort_values('timestamp')
        filtro['Estado_Txt'] = filtro['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        
        # Intervalo de 5 minutos para los bloques[cite: 1]
        filtro['fin'] = filtro['timestamp'] + pd.Timedelta(minutes=5)
        
        # Definir el rango estricto de 00:00 a 23:59 del día seleccionado
        start_day = pd.Timestamp.combine(fec_sel, pd.Timestamp.min.time()).replace(tzinfo=CHILE_TZ)
        end_day = pd.Timestamp.combine(fec_sel, pd.Timestamp.max.time()).replace(tzinfo=CHILE_TZ)

        fig = px.timeline(
            filtro, 
            x_start="timestamp", 
            x_end="fin", 
            y="device", 
            color="Estado_Txt",
            color_discrete_map={"Conectado": "#00CC96", "Desconectado": "#EF553B"}
        )
        
        fig.update_layout(
            xaxis=dict(
                title="Horario (pasos de 2h)",
                range=[start_day, end_day],
                dtick=7200000, # 2 horas en milisegundos
                tickformat="%H:%M",
                gridcolor="#333",
                showgrid=True
            ),
            yaxis=dict(visible=False),
            showlegend=True,
            height=180,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # Recuadro demarcador con línea fina[cite: 5]
        fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
        fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
        
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📜 Detalle de Registros")
        display_df = filtro.sort_values('timestamp', ascending=False).copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Visual'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        st.dataframe(display_df[['Hora', 'Visual', 'duracion_min']], use_container_width=True, hide_index=True, height=250)
    else:
        st.info(f"Sin registros para {est_sel} el {fec_sel}.")
else:
    st.warning("No hay datos históricos disponibles.")
