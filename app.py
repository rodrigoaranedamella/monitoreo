import streamlit as st
import pandas as pd
import pytz
import requests
import json
import time

# ====================== CONFIGURACIÓN INICIAL ======================
st.set_page_config(page_title="SanLeon Dashboard", layout="wide", page_icon="🛡️")

# Definición de constantes
CHILE_TZ = pytz.timezone('America/Santiago')
ESTACIONES = [
    "Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON",
    "Matias_SANLEON", "Jennifer_SANLEON", "Jennifer2_SANLEON"
]
REPO_NAME = "rodrigoaranedamella/monitoreo"
HISTORIAL_FILE = 'historial_conexiones.json'

# Estilos personalizados para mejorar la visibilidad
st.markdown("""
    <style>
    .stDataFrame { border: 1px solid #333; border-radius: 10px; }
    h1, h2, h3 { color: #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Centro de Monitoreo SanLeon")
st.markdown("---")

# ====================== 1. LÓGICA DE ESTADO ACTUAL ======================
@st.cache_data(ttl=30, show_spinner=False)
def obtener_estado_actual():
    try:
        API_TOKEN = st.secrets["ZT_API_TOKEN"]
        NETWORK_ID = st.secrets["ZT_NETWORK_ID"]
        
        res = requests.get(
            f'https://api.zerotier.com/api/v1/network/{NETWORK_ID}/member',
            headers={'Authorization': f'token {API_TOKEN}'},
            timeout=10
        )
        members = res.json()

        estado_actual = []
        for nombre in ESTACIONES:
            m = next((item for item in members if item.get('name') == nombre), {})
            last_seen = m.get('lastSeen') or m.get('lastOnline', 0)
            
            # Cálculo de inactividad
            segundos_inactivo = (time.time() * 1000 - last_seen) / 1000
            is_online = segundos_inactivo < 900  # 15 minutos de margen[cite: 2]

            ultima_conexion = pd.to_datetime(last_seen, unit='ms', utc=True).tz_convert(CHILE_TZ) if last_seen > 0 else None
            fecha_str = ultima_conexion.strftime('%Y-%m-%d %H:%M:%S') if ultima_conexion else "Sin registros"
            
            estado_actual.append({
                'Estación': nombre,
                'Estado': "🟢 ONLINE" if is_online else "🔴 OFFLINE",
                # Se agrega el check verde si la conexión es efectiva ahora[cite: 2, 4]
                'Última conexión': f"✅ {fecha_str}" if is_online else fecha_str,
                'Inactivo hace': f"{int(segundos_inactivo/60)} min" if segundos_inactivo > 60 else f"{int(segundos_inactivo)} seg"
            })

        return pd.DataFrame(estado_actual)
    
    except Exception as e:
        st.error(f"Error consultando ZeroTier: {e}")
        return pd.DataFrame()

# Mostrar la tabla de estado en vivo
st.subheader("📡 Estado Actual de Estaciones")
df_en_vivo = obtener_estado_actual()
if not df_en_vivo.empty:
    st.dataframe(df_en_vivo, use_container_width=True, hide_index=True)
else:
    st.warning("No se pudo obtener información de ZeroTier en este momento.")

st.markdown("<br>", unsafe_allow_html=True)
st.divider()

# ====================== 2. BARRA LATERAL (FILTROS) ======================
with st.sidebar:
    st.header("⚙️ Configuración y Filtros")
    estacion_sel = st.selectbox("Seleccionar Estación para Historial", ESTACIONES)
    fecha_sel = st.date_input("Seleccionar Fecha", value=pd.Timestamp.now(tz=CHILE_TZ).date())
    
    if st.button("🔄 Refrescar Datos Manualmente"):
        st.cache_data.clear()
        st.rerun()
    
    st.info("El historial se actualiza automáticamente cada 5 minutos mediante GitHub Actions.")

# ====================== 3. HISTORIAL DESDE GITHUB ======================
st.subheader(f"📜 Historial Detallado: {estacion_sel}")

@st.cache_data(ttl=120) # Cache corto para reflejar cambios del worker.py[cite: 4]
def cargar_historial_github():
    try:
        # URL directa al archivo JSON en el repositorio[cite: 4]
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/{HISTORIAL_FILE}"
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            # Convertir a datetime y asegurar zona horaria de Chile[cite: 4]
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

historial_df = cargar_historial_github()

if not historial_df.empty:
    # Filtrado estricto por dispositivo y fecha[cite: 2, 4]
    historial_df['fecha_solo'] = historial_df['timestamp'].dt.date
    
    filtrado = historial_df[
        (historial_df['device'] == estacion_sel) & 
        (historial_df['fecha_solo'] == fecha_sel)
    ].copy()
    
    if not filtrado.empty:
        # Ordenar: Lo más nuevo primero[cite: 4]
        filtrado = filtrado.sort_values(by='timestamp', ascending=False)
        
        # Formatear tabla final
        display_df = filtrado[['timestamp', 'estado', 'duracion_min']].copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df['estado'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        
        # Renombrar columnas para el usuario
        display_df.columns = ['Hora del Evento', 'Estado registrado', 'Duración estimada (min)']
        
        st.write(f"Mostrando registros del **{fecha_sel}** para la estación seleccionada.")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No existen registros históricos para **{estacion_sel}** en la fecha {fecha_sel}.")
else:
    st.warning("No se encontró el archivo de historial en el repositorio. Asegúrate de que el Workflow de GitHub haya corrido al menos una vez.")

# ====================== 4. REFRESCO AUTOMÁTICO (JS) ======================
# Configurado para 120,000 milisegundos (2 minutos)[cite: 2]
st.markdown("""
    <script>
        var refreshInterval = 120000; 
        setTimeout(function(){
            window.location.reload();
        }, refreshInterval);
    </script>
    """, unsafe_allow_html=True)

st.caption(f"🔄 Refresco automático cada 2 minutos • Última actualización del sistema: {pd.Timestamp.now(tz=CHILE_TZ).strftime('%H:%M:%S')}")
