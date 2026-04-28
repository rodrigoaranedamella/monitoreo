# ====================== 2. HISTORIAL DESDE GITHUB ======================
# Título dinámico que cambia según el selector de la izquierda
st.subheader(f"📜 Historial Detallado: {estacion_sel}") 

@st.cache_data(ttl=300) 
def cargar_historial_github():
    try:
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/{HISTORIAL_FILE}"
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            # Convertir timestamp y asegurar zona horaria de Chile
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert(CHILE_TZ)
            return df
    except: return pd.DataFrame()

historial_df = cargar_historial_github()

if not historial_df.empty:
    # Creamos una columna de fecha para el filtro
    historial_df['fecha_solo'] = historial_df['timestamp'].dt.date
    
    # FILTRO ESTRICTO: Por dispositivo Y por fecha seleccionada
    filtrado = historial_df[
        (historial_df['device'] == estacion_sel) & 
        (historial_df['fecha_solo'] == fecha_sel)
    ].copy()
    
    if not filtrado.empty:
        # Ordenar por hora más reciente arriba
        filtrado = filtrado.sort_values(by='timestamp', ascending=False)
        
        # Formatear para la vista
        display_df = filtrado[['timestamp', 'estado', 'duracion_min']].copy()
        display_df['estado'] = display_df['estado'].apply(lambda x: "🟢 Conectado" if x else "🔴 Desconectado")
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        
        # Cambiamos nombres de columnas para claridad
        display_df.columns = ['Hora', 'Evento', 'Duración (min)']
        
        st.write(f"Mostrando registros para el día **{fecha_sel}**")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No hay registros históricos para **{estacion_sel}** en la fecha seleccionada ({fecha_sel}).")
else:
    st.warning("El archivo de historial aún no contiene datos o no se pudo leer.")
