import streamlit as st
import pandas as pd
import os

# ==========================================
# 0. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Data CARP - Panel de Rendimiento", 
    page_icon="🐔", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 1. FUNCIONES DE LIMPIEZA Y CARGA
# ==========================================

def extraer_exitosos(valor):
    """Extrae el primer número de strings como '12/14' para poder operar matemáticamente."""
    try:
        if isinstance(valor, str):
            valor_limpio = valor.replace("'", "")
            return int(valor_limpio.split('/')[0])
        return int(valor)
    except:
        return 0

@st.cache_data
def cargar_datos():
    # ACÁ ESTÁ CORREGIDO: Una sola línea, con las comillas cerradas
    ruta_archivo = "Base_Datos_River_2026.csv"
    
    if os.path.exists(ruta_archivo):
        df = pd.read_csv(ruta_archivo)
        
        # Limpieza de columnas para poder calcular los MVP
        if 'Pases (Comp/Tot)' in df.columns:
            df['Pases Completados'] = df['Pases (Comp/Tot)'].apply(extraer_exitosos)
        if 'Regates (Exit/Tot)' in df.columns:
            df['Regates Exitosos'] = df['Regates (Exit/Tot)'].apply(extraer_exitosos)
            
        return df
    else:
        return pd.DataFrame()

# ==========================================
# 2. INICIALIZACIÓN DE LA APP
# ==========================================

st.title("🐔 Data CARP - Panel de Rendimiento 2026")
st.markdown("Plataforma de análisis de rendimiento individual y colectivo.")

df_stats = cargar_datos()

if df_stats.empty:
    st.error(f"⚠️ No se encontró la base de datos. Verificá que el archivo se llame exactamente 'Base_Datos_River_2026.csv' en tu repositorio.")
    st.stop()

# ==========================================
# 3. CREACIÓN DE LAS SOLAPAS
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📈 Análisis de Equipo", 
    "👤 Análisis Individual (Temporada)", 
    "🔥 Análisis Individual (Por Partido)"
])

# ------------------------------------------
# SOLAPA 1: ANÁLISIS DE EQUIPO
# ------------------------------------------
with tab1:
    st.header("Rendimiento General del Equipo")
    st.info("💡 Acá podés pegar los gráficos o tablas generales que ya tenías armados.")
    
    col1, col2, col3 = st.columns(3)
    if 'Goles' in df_stats.columns:
        col1.metric("Goles Totales", df_stats['Goles'].sum())
    if 'Partido' in df_stats.columns:
        col2.metric("Partidos Analizados", df_stats['Partido'].nunique())

# ------------------------------------------
# SOLAPA 2: ANÁLISIS INDIVIDUAL (TEMPORADA)
# ------------------------------------------
with tab2:
    st.header("Análisis Acumulado de la Temporada")
    st.info("💡 Acá podés pegar tu análisis histórico o acumulado de todo el torneo.")
    
    if st.checkbox("Mostrar Base de Datos Completa"):
        st.dataframe(df_stats, use_container_width=True)

# ------------------------------------------
# SOLAPA 3: ANÁLISIS POR PARTIDO (NUEVO)
# ------------------------------------------
with tab3:
    st.header("📊 Top Rendimientos por Partido")
    
    if 'Partido' in df_stats.columns:
        # Selector de Partido
        lista_partidos = df_stats['Partido'].dropna().unique()
        partido_seleccionado = st.selectbox("Seleccioná un partido para ver los MVP:", lista_partidos)
        
        # Filtrar el dataset
        df_partido = df_stats[df_stats['Partido'] == partido_seleccionado]
        
        st.markdown("---")
        st.markdown(f"### 🏆 Los Mejores vs {partido_seleccionado}")
        
        # Armar el podio (Top 3)
        col1, col2, col3, col4, col5 = st.columns(5)
        top_n = 3 
        
        with col1:
            st.subheader("🛡️ Quites")
            if 'Quites (Tackles)' in df_partido.columns:
                top_rec = df_partido.nlargest(top_n, 'Quites (Tackles)')[['Jugador', 'Quites (Tackles)']]
                st.dataframe(top_rec, hide_index=True, use_container_width=True)
            
        with col2:
            st.subheader("⭐ Nota")
            if 'Nota SofaScore' in df_partido.columns:
                top_nota = df_partido.nlargest(top_n, 'Nota SofaScore')[['Jugador', 'Nota SofaScore']]
                st.dataframe(top_nota, hide_index=True, use_container_width=True)
            
        with col3:
            st.subheader("🎯 Pases")
            if 'Pases Completados' in df_partido.columns:
                top_pases = df_partido.nlargest(top_n, 'Pases Completados')[['Jugador', 'Pases Completados']]
                st.dataframe(top_pases, hide_index=True, use_container_width=True)
            
        with col4:
            st.subheader("⚡ Regates")
            if 'Regates Exitosos' in df_partido.columns:
                top_regates = df_partido.nlargest(top_n, 'Regates Exitosos')[['Jugador', 'Regates Exitosos']]
                st.dataframe(top_regates, hide_index=True, use_container_width=True)
            
        with col5:
            st.subheader("👟 Remates")
            if 'Tiros Totales' in df_partido.columns:
                top_remates = df_partido.nlargest(top_n, 'Tiros Totales')[['Jugador', 'Tiros Totales']]
                st.dataframe(top_remates, hide_index=True, use_container_width=True)
    else:
        st.warning("⚠️ No se encontró la columna 'Partido'. Asegurate de que exista en tu CSV.")

# ==========================================
# FOOTER
# ==========================================
st.markdown("---")
st.caption("Desarrollado con Streamlit | Data CARP")
