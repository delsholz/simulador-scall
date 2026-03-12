import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.express as px  # <-- Nueva librería para el gráfico profesional

# --- FUNCIÓN PARA CALCULAR DISTANCIA ESPACIAL (Haversine) ---
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- REPARADOR MÁGICO DE COORDENADAS ---
def arreglar_coordenada(val, es_longitud=False):
    val = str(val).strip().replace(',', '.')
    if val == 'nan' or not val: return None
    
    val_clean = val.replace('.', '')
    
    if not val_clean.startswith('-'): return None
    if len(val_clean) <= 3:
        return float(val_clean)
        
    if es_longitud and val_clean.startswith('-10'):
        fixed = val_clean[:4] + '.' + val_clean[4:]
    else:
        fixed = val_clean[:3] + '.' + val_clean[3:]
        
    return float(fixed)

# --- DISEÑO DE LA PÁGINA ---
st.title("💧 Simulador de Cosecha de Aguas Lluvias (Base CR2)")
st.write("Calcula el balance hídrico utilizando **sólo estaciones con datos de alta calidad** (Últimos 20 años con ≥ 80% de registros válidos).")

# --- 1. MENÚ LATERAL (Siempre visible) ---
st.sidebar.header("1. Datos del Proyecto")
nombre_proyecto = st.sidebar.text_input("Nombre del Proyecto/Lugar", "Mi Proyecto SCALL")
techo = st.sidebar.number_input("Superficie del Techo (m2)", min_value=10.0, value=120.0)

capacidad_maxima = st.sidebar.number_input("Capacidad Máxima del Estanque (Litros)", min_value=0.0, value=5000.0, step=500.0)

st.sidebar.subheader("Consumo de Agua")
numero_personas = st.sidebar.number_input("Número de personas", min_value=1, value=4)
litros_persona_dia = st.sidebar.number_input("Consumo (Litros/persona/día)", min_value=1.0, value=50.0)
dias_mes = st.sidebar.number_input("Días de uso al mes", min_value=1, max_value=31, value=30)

consumo_mensual = numero_personas * litros_persona_dia * dias_mes
st.sidebar.info(f"💧 Consumo mensual calculado:\n**{consumo_mensual:,.0f} Litros/mes**".replace(",", "."))

st.sidebar.header("2. Coordenadas de Ubicación")
st.sidebar.write("Ingresa la latitud y longitud de tu proyecto.")
lat_proyecto = st.sidebar.number_input("Latitud", value=-33.4500, format="%.4f")
lon_proyecto = st.sidebar.number_input("Longitud", value=-70.6500, format="%.4f")

# --- 2. CARGAR Y FILTRAR LA BASE DE DATOS CR2 ---
@st.cache_data 
def cargar_base_cr2():
    df_cr2 = pd.read_csv("BBDD precipitaciones.csv", sep=';', header=None, low_memory=False)
    
    codigos_completos = df_cr2.iloc[1, 1:].values.astype(str)
    nombres_completos = df_cr2.iloc[4, 1:].values.astype(str)
    latitudes_crudas = df_cr2.iloc[6, 1:].values.astype(str)
    longitudes_crudas = df_cr2.iloc[7, 1:].values.astype(str)
    
    indices_validos = [i for i, cod in enumerate(codigos_completos) if cod != 'nan']
    
    codigos = [codigos_completos[i] for i in indices_validos]
    nombres = [nombres_completos[i] for i in indices_validos]
    
    latitudes = [arreglar_coordenada(latitudes_crudas[i], es_longitud=False) for i in indices_validos]
    longitudes = [arreglar_coordenada(longitudes_crudas[i], es_longitud=True) for i in indices_validos]
    
    df_estaciones = pd.DataFrame({
        'Codigo': codigos,
        'Nombre': nombres,
        'Latitud': latitudes,
        'Longitud': longitudes
    }).dropna(subset=['Latitud', 'Longitud'])
    
    df_data = df_cr2.iloc[16:].copy()
    df_data.columns = ['Fecha'] + list(codigos_completos)
    df_data = df_data[['Fecha'] + codigos].copy()
    df_data.replace([-9999, '-9999', '-9999.0', -9999.0, 'nan'], pd.NA, inplace=True)
    
    df_data['Año'] = df_data['Fecha'].astype(str).str.slice(0, 4).astype(int)
    max_year = df_data['Año'].max()
    start_year = max_year - 19 
    df_20_anos = df_data[df_data['Año'] >= start_year].copy()
    
    df_20_anos[codigos] = df_20_anos[codigos].astype(str).replace({',': '.'}, regex=True)
    df_20_anos[codigos] = df_20_anos[codigos].apply(pd.to_numeric, errors='coerce')
    
    total_meses = len(df_20_anos) 
    minimo_requerido = total_meses * 0.80
    
    conteo_validos = df_20_anos[codigos].notna().sum()
    estaciones_validas = conteo_validos[conteo_validos >= minimo_requerido].index.tolist()
    
    df_estaciones = df_estaciones[df_estaciones['Codigo'].isin(estaciones_validas)]
    
    return df_estaciones, df_20_anos

# --- 3. BOTÓN Y CÁLCULOS ---
if st.button("Buscar Estación y Calcular Balance"):
    try:
        with st.spinner('Evaluando calidad de datos y calculando distancias exactas...'):
            df_estaciones, df_data = cargar_base_cr2()
            
            if df_estaciones.empty:
                st.error("⚠️ Ninguna estación cumple con el estándar de 80% de calidad.")
            else:
                distancia_minima = float('inf')
                estacion_cercana = None
                
                for index, row in df_estaciones.iterrows():
                    dist = calcular_distancia(lat_proyecto, lon_proyecto, row['Latitud'], row['Longitud'])
                    if dist < distancia_minima:
                        distancia_minima = dist
                        estacion_cercana = row
                        
                codigo_estacion = str(estacion_cercana['Codigo'])
                lluvias_estacion = df_data[['Fecha', 'Año', codigo_estacion]].copy()
                
                meses_con_datos = lluvias_estacion[codigo_estacion].notna().sum()
                total_meses_evaluados = len(lluvias_estacion)
                porcentaje_calidad = (meses_con_datos / total_meses_evaluados) * 100
                
                anio_inicio = lluvias_estacion['Año'].min()
                anio_fin = lluvias_estacion['Año'].max()
                
                st.info(f"📍 **Estación más cercana (Aprobada):** {estacion_cercana['Nombre']}")
                st.write(f"*(Código DGA: {estacion_cercana['Codigo']} - Ubicada a **{distancia_minima:.1f} km** de tu proyecto)*".replace(".", ","))
                st.success(f"📊 **Calidad de Datos:** Evaluando periodo **{anio_inicio} - {anio_fin}**. Se encontraron {meses_con_datos} meses de registros reales válidos (**{porcentaje_calidad:.1f}% de los datos**).".replace(".", ","))
                
                lluvias_estacion['Mes'] = lluvias_estacion['Fecha'].astype(str).str.slice(-2)
                promedios = lluvias_estacion.groupby('Mes')[codigo_estacion].mean()
                
                meses_validos = [f"{i:02d}" for i in range(1, 13)]
                precipitaciones_promedio = promedios.reindex(meses_validos).fillna(0).tolist()
                
                # --- BALANCE HÍDRICO ---
                meses = ["01-Ene", "02-Feb", "03-Mar", "04-Abr", "05-May", "06-Jun", "07-Jul", "08-Ago", "09-Sep", "10-Oct", "11-Nov", "12-Dic"]
                
                eficiencia = 0.85 
                resultados = []
                agua_acumulada_anterior = 0
                
                captada_todos = [techo * p * eficiencia for p in precipitaciones_promedio]
                capacidad_sugerida = max(captada_todos)

                for i in range(12):
                    pp = precipitaciones_promedio[i]
                    agua_captada = techo * pp * eficiencia
                    agua_acumulada = agua_acumulada_anterior + agua_captada
                    agua_usada = min(agua_acumulada, consumo_mensual)
                    agua_restante = max(0, agua_acumulada - consumo_mensual)
                    agua_almacenada = max(0, min(agua_restante, capacidad_maxima))
                    
                    resultados.append({
                        "Mes": meses[i],
                        "Precipitación media (mm)": pp,
                        "Agua Captada (L)": agua_captada,
                        "Agua Acumulada (L)": agua_acumulada,
                        "Agua Usada (L)": agua_usada,
                        "Consumo Mensual (L)": consumo_mensual,
                        "Nivel Estanque (L)": agua_almacenada
                    })
                    agua_acumulada_anterior = agua_almacenada

                # --- RESULTADOS VISUALES ---
                st.markdown("---")
                st.metric(label="Estanque Evaluado (Según tu diseño)", value=f"{capacidad_maxima:,.0f} Litros".replace(",", "."))
                
                if capacidad_maxima < capacidad_sugerida:
                    st.warning(f"💡 **Tip de Diseño:** El mes más lluvioso bota mucha agua. La capacidad ideal de recolección sería de **{capacidad_sugerida:,.0f}** Litros (podrías estar perdiendo agua por rebalse).".replace(",", "."))
                elif capacidad_maxima > capacidad_sugerida:
                    st.info(f"💡 **Tip de Diseño:** Tienes un estanque grande. Con **{capacidad_sugerida:,.0f}** Litros ya captarías todo el potencial del mes más lluvioso.".replace(",", "."))
                else:
                    st.success("🎯 **¡Tamaño perfecto!** Coincide con la capacidad óptima de captación del techo.")
                
                df_resultados = pd.DataFrame(resultados)
                df_resultados.index = range(1, 13) 
                
                formato_miles = lambda x: f"{x:,.0f}".replace(",", ".")
                formato_decimal = lambda x: f"{x:,.1f}".replace(".", ",")
                
                df_estilizado = df_resultados.style.format({
                    "Precipitación media (mm)": formato_decimal,
                    "Agua Captada (L)": formato_miles,
                    "Agua Acumulada (L)": formato_miles,
                    "Agua Usada (L)": formato_miles,
                    "Consumo Mensual (L)": formato_miles,
                    "Nivel Estanque (L)": formato_miles
                })
                
                st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
                
                # --- GRÁFICO AVANZADO CON PLOTLY ---
                st.write("### Balance Mensual: Captación vs Uso Real")
                
                fig = px.bar(
                    df_resultados,
                    x="Mes",
                    y=["Agua Captada (L)", "Agua Usada (L)"],
                    barmode="group"
                )
                
                # Regla de formato: coma para decimal, punto para miles
                fig.update_layout(
                    separators=",.", 
                    yaxis_title="Volumen (Litros)",
                    xaxis_title="",
                    legend_title_text=""
                )
                
                # Aplica el formato de miles al globo de información al pasar el mouse
                fig.update_traces(hovertemplate="%{y:,.0f} L")
                
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:

        st.error(f"⚠️ Ocurrió un error inesperado al procesar los datos: {e}")
