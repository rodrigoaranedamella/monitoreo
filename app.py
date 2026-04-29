# --- PARTE SUPERIOR (Compacta con 5 Filas Reales) ---
st.markdown("### 📊 Monitor SanLeon")

@st.cache_data(ttl=30)
def obtener_estado_actual():
    # Definimos las 5 estaciones principales para la tabla superior
    estaciones_top = ["Marian_SANLEON", "Andrea_SANLEON", "Carmily_SANLEON", "Matias_SANLEON", "Jennifer_SANLEON"]
    resumen = []
    ahora = datetime.now(tz)
    
    for est in estaciones_top:
        try:
            # Traer solo el último registro de cada una (Source 5)
            res = supabase.table("historial_connections") \
                .select("*") \
                .eq("device", est) \
                .order("timestamp", desc=True) \
                .limit(1) \
                .execute()
            
            if res.data:
                ultimo = res.data[0]
                ts = pd.to_datetime(ultimo['timestamp']).tz_convert('America/Santiago')
                dif_min = int((ahora - ts).total_seconds() / 60)
                
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

col_tabla, col_ctrl = st.columns([3, 1])

with col_tabla:
    df_estado = obtener_estado_actual()
    # Mostramos las 5 filas de forma compacta (Source 3)
    st.dataframe(
        df_estado, 
        hide_index=True, 
        use_container_width=True,
        height=212 # Altura ajustada para mostrar exactamente 5 filas sin scroll excesivo
    )

with col_ctrl:
    st.caption(f"🕒 Actualización: {datetime.now(tz).strftime('%H:%M:%S')}")
    # Selector de estación (incluye todas las estaciones para el detalle)
    est_sel = st.selectbox("Estación", ESTACIONES, index=4)
    fec_sel = st.date_input("Fecha", value=datetime.now(tz).date())
    st.button("🔄 Refrescar Manual")
