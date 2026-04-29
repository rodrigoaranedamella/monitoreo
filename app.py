import streamlit as st
import pandas as pd
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# Configuración de página y autorefresco (Source 3)
st.set_page_config(page_title="Monitor SanLeon", layout="wide")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st_autorefresh(interval=60 * 1000, key="datarefresh") # La interfaz pide datos a la BDD cada 1 min

# Conexión (Source 5)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
tz = pytz.timezone('America/Santiago')

@st.cache_data(ttl=30) # Cache corto para forzar la lectura de datos nuevos de la BDD
def obtener_datos_desde_bdd(device, fecha):
    try:
        # Rescata los datos vivos directamente de la BDD (Source 5)
        res = supabase.table("historial_conexiones") \
            .select("*") \
            .eq("device", device) \
            .gte("timestamp", f"{fecha}T00:00:00") \
            .lte("timestamp", f"{fecha}T23:59:59") \
            .order("timestamp") \
            .execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

# Lógica de Interfaz
st.markdown("### 📊 Monitor en Vivo (Datos de Backend)")

# ... (Aquí va el resto de la lógica de tablas y gráficas que ya tienes)
# Al usar st_autorefresh y obtener_datos_desde_bdd, la app siempre mostrará 
# lo último que el proceso backend de GitHub guardó, sin importar tu navegador.
