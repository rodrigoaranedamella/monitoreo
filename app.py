import streamlit as st
import pandas as pd
import pytz
import requests
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página y estilo profesional
st.set_page_config(page_title="SanLeon Monitor Pro", layout="wide", page_icon="📊")

# CSS para igualar la estética de la imagen de referencia
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { margin-top: -1rem; margin-bottom: 0.5rem; font-size: 1.8rem; font-weight: bold; }
        .stDataFrame { border: 1px solid #444; border-radius: 5px; }
        .stPlotlyChart { border: 1px solid #444; border-radius: 5px; padding: 5px; background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# 2. Constantes y Configuración
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"]
REPO_NAME = "rodrigoaranedamella/monitoreo"

# Refresco automático cada 2 minutos
st_autorefresh(interval=120 * 1000, key="datarefresh")

@st.cache_data(ttl=15, show_spinner=False)
def obtener_vivo():
    try:
        # Llamada a la API de ZeroTier para el estado actual
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
            # Consideramos online si se vio hace menos de 15 minutos[cite: 9]
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
        # Cargamos el JSON y forzamos la conversión a la zona horaria de Chile
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(CHILE_TZ)
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.title("📊 Monitor SanLeon")

# Fila superior: Tabla de estado vivo y controles
col_tabla, col_controles = st.columns([3.5, 1.5])

with col_tabla:
    df_vivo = obtener_vivo()
    if not df_vivo.empty:
        st.dataframe(df_vivo, use_container_width=True, hide_index=True, height=230)

with col_controles:
    st.info(f"🕒 **Actualización:** {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")
    est_sel = st.selectbox("Estación", ESTACIONES, index=4) # Jennifer por defecto
    # Fecha actual en Chile
    fecha_hoy = pd.Timestamp.now(tz=CHILE_TZ).date()
    fec_sel = st.date_input("Fecha", value=fecha_hoy)
    
    if st.button("🔄 Refrescar Manual", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Sección de Gráfica Histórica
h_df = cargar_historial()
if not h_df.empty:
    # Filtrado robusto por fecha y dispositivo[cite: 7]
    mask = (h_df['device'] == est_sel) & (h_df['timestamp'].dt.date == fec_sel)
    filtro = h_df.loc[mask].copy()
    
    if not filtro.empty:
        st.subheader(f"📈 Actividad 24h: {est_sel}")
        filtro = filtro.sort_values('timestamp')
        filtro['Estado_Txt'] = filtro['estado'].apply(lambda x: "Conectado" if x else "Desconectado")
        
        # El worker graba cada 5-10 min; creamos bloques visibles
        filtro['fin'] = filtro['timestamp'] + pd.Timedelta(minutes=10)
        
        # Rango del eje X: de 00:00 a 23:59 del día seleccionado
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
            xaxis=dict(
                title="Horario (pasos de 2h)",
                range=[inicio_eje, fin_eje],
                dtick=7200000, # Intervalos de 2 horas en ms
                tickformat="%H:%M",
                gridcolor="#333",
                showgrid=True
            ),
            yaxis=dict(visible=False),
            showlegend=True,
            height=180,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1)
        )
        
        # Estilo del recuadro del gráfico
        fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de detalle inferior
        st.subheader("📜 Detalle de Registros")
        display_df = filtro.sort_values('timestamp', ascending=False).copy()
        display_df['Hora'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['Visual'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        st.dataframe(
            display_df[['Hora', 'Visual', 'duracion_min']], 
            use_container_width=True, 
            hide_index=True, 
            height=300
        )
    else:
        st.info(f"No se encontraron registros para {est_sel} el día {fec_sel}.")
        st.caption("Nota: Si los registros son de madrugada, asegúrate de seleccionar la fecha correcta según el horario de Chile.")
else:
    st.warning("No se pudo cargar el historial desde GitHub.")
