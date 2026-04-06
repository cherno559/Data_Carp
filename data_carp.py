import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from openpyxl import load_workbook
import io

# ── CONFIGURACIÓN DE LA PÁGINA ───────────────────────────────────────────────
st.set_page_config(page_title="Data CARP", page_icon="🐔", layout="wide")

# ── ESTILOS CSS (TEMA RIVER PLATE) ───────────────────────────────────────────
st.markdown("""
    <style>
    /* Rojo River para títulos principales */
    h1, h2, h3, h4 {
        color: #ed1c24 !important;
        font-family: 'Arial Black', sans-serif;
    }
    .block-container {
        padding-top: 2rem;
    }
    /* Estilo del menú lateral */
    [data-testid="stSidebar"] {
        border-right: 4px solid #ed1c24;
        background-color: #f8f9fa;
    }
    /* Estilo para que el título Data CARP del menú quede bien */
    .sidebar-title {
        color: #000000 !important;
        font-family: 'Arial Black', sans-serif;
        font-size: 24px;
        margin-top: -20px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# ── RUTAS Y COLORES ──────────────────────────────────────────────────────────
CARPETA = Path(r"C:\Users\user\Documents\football")
EXCEL = CARPETA / "Base_Datos_River_2026.xlsx"

RUTA_LOGO_ACTUAL = CARPETA / "logo_river_actual.png"
RUTA_LOGO_RETRO  = CARPETA / "logo_river_retro.png"
RUTA_LOGO_CARP   = CARPETA / "logo_carp.png"

DICCIONARIO_COLORES = {'DEF': '#1f77b4', 'MED': '#2ca02c', 'DEL': '#ed1c24', 'POR': '#ff7f0e'}

# ── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos_completos():
    if not EXCEL.exists():
        return pd.DataFrame(), "❌ No se encontró el archivo Excel."

    try:
        xl = pd.ExcelFile(EXCEL)
        partes = []
        hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"]
        
        for hoja in xl.sheet_names:
            if hoja in hojas_omitir:
                continue
                
            df = pd.read_excel(EXCEL, sheet_name=hoja)
            df.columns = df.columns.str.strip()
            
            if 'Jugador' in df.columns and 'Nota SofaScore' in df.columns:
                df['Jugador'] = df['Jugador'].str.strip()
                df['Nota SofaScore'] = pd.to_numeric(df['Nota SofaScore'], errors="coerce")
                df = df.dropna(subset=['Jugador', 'Nota SofaScore'])
                df = df[(df['Jugador'] != "") & (df['Nota SofaScore'] > 0)]
                
                cols_num = ['Minutos', 'Goles', 'Asistencias', 'Pases Clave', 'Quites (Tackles)', 'Intercepciones', 'Tiros Totales', 'Efectividad Pases']
                for col in cols_num:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                
                df['Hoja_Original'] = hoja
                df['Partido'] = hoja.replace("Base_Datos_River_2026.xlsx - ", "").replace(".csv", "")
                partes.append(df)
                
        if not partes:
            return pd.DataFrame(), "⚠️ El Excel está vacío o no tiene las columnas correctas."
            
        return pd.concat(partes, ignore_index=True), "OK"
    except Exception as e:
        return pd.DataFrame(), f"Error al procesar los datos: {str(e)}"

@st.cache_data
def extraer_imagen_incrustada(ruta_excel_str, nombre_hoja, indice_imagen=0):
    try:
        wb = load_workbook(ruta_excel_str, data_only=True)
        if nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            if hasattr(ws, '_images') and len(ws._images) > indice_imagen:
                img = ws._images[indice_imagen]
                if hasattr(img, '_data'):
                    return img._data() if callable(img._data) else img._data
                elif hasattr(img, 'ref'):
                    img.ref.seek(0)
                    return img.ref.read()
        return None
    except Exception:
        return None

# ── BARRA LATERAL (MENÚ) ─────────────────────────────────────────────────────
col_nav1, col_nav2 = st.sidebar.columns([1, 2])
with col_nav1:
    if RUTA_LOGO_ACTUAL.exists():
        st.image(str(RUTA_LOGO_ACTUAL), width=70)
    else:
        st.write("🐔")

with col_nav2:
    st.markdown('<p class="sidebar-title">Data<br>CARP</p>', unsafe_allow_html=True)

st.sidebar.markdown("---")

menu = st.sidebar.radio("Navegación:", [
    "Resumen General", 
    "Mapas de Rendimiento", 
    "Análisis Individual",
    "Parado Táctico",
    "Mapa de Tiros"
])

st.sidebar.markdown("<br><br><br><br><br><br><br><br>", unsafe_allow_html=True)
st.sidebar.markdown("---")

col_bot1, col_bot2 = st.sidebar.columns(2)
with col_bot1:
    if RUTA_LOGO_RETRO.exists():
        st.image(str(RUTA_LOGO_RETRO), width=80)
with col_bot2:
    if RUTA_LOGO_CARP.exists():
        st.image(str(RUTA_LOGO_CARP), width=80)

# ── PROCESAMIENTO DE DATOS ───────────────────────────────────────────────────
df_raw, estado = cargar_datos_completos()

if estado != "OK":
    st.error(estado)
    st.stop()

if 'Efectividad Pases' in df_raw.columns:
    df_raw['Efectividad Pases'] = df_raw['Efectividad Pases'].replace(0, np.nan)

df_agrupado = df_raw.groupby(['Jugador', 'Posición'], as_index=False).agg(
    Partidos=('Nota SofaScore', 'count'),
    Promedio=('Nota SofaScore', 'mean'),
    Minutos=('Minutos', 'sum'),
    Goles=('Goles', 'sum'),
    Asistencias=('Asistencias', 'sum'),
    Pases_Clave=('Pases Clave', 'sum'),
    Quites=('Quites (Tackles)', 'sum'),
    Intercepciones=('Intercepciones', 'sum'),
    Tiros_Totales=('Tiros Totales', 'sum'),
    Efectividad_Pases=('Efectividad Pases', 'mean')
)
df_agrupado['Promedio'] = df_agrupado['Promedio'].round(2)
df_agrupado['Efectividad_Pases'] = df_agrupado['Efectividad_Pases'].round(1).fillna(0)

# ── PÁGINAS ──────────────────────────────────────────────────────────────────

if menu == "Resumen General":
    t_col1, t_col2 = st.columns([1, 15])
    with t_col1:
        if RUTA_LOGO_CARP.exists():
            st.image(str(RUTA_LOGO_CARP), width=50)
    with t_col2:
        st.markdown("<h1>Panel General del Equipo</h1>", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("📊 Promedios SofaScore")
        st.dataframe(df_agrupado[['Jugador', 'Promedio', 'Partidos']].sort_values('Promedio', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
    with col2:
        st.subheader("⚽ Tabla de Goleadores")
        st.dataframe(df_agrupado[df_agrupado['Goles'] > 0][['Jugador', 'Goles']].sort_values('Goles', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
    with col3:
        st.subheader("👟 Tabla de Asistidores")
        st.dataframe(df_agrupado[df_agrupado['Asistencias'] > 0][['Jugador', 'Asistencias']].sort_values('Asistencias', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)

elif menu == "Mapas de Rendimiento":
    st.markdown("<h1>🗺️ Mapas de Rendimiento y Efectividad</h1>", unsafe_allow_html=True)
    st.info("💡 Tip: Pasá el mouse sobre los puntos para ver el nombre.")
    min_minutos = st.sidebar.slider("Minutos Mínimos Jugados", 0, int(df_agrupado['Minutos'].max()), 180)
    df_p90 = df_agrupado[df_agrupado['Minutos'] >= min_minutos].copy()
    df_p90['PasesClave_P90'] = (df_p90['Pases_Clave'] / df_p90['Minutos']) * 90
    df_p90['Asistencias_P90'] = (df_p90['Asistencias'] / df_p90['Minutos']) * 90
    df_p90['Quites_P90'] = (df_p90['Quites'] / df_p90['Minutos']) * 90
    df_p90['Inter_P90'] = (df_p90['Intercepciones'] / df_p90['Minutos']) * 90

    st.markdown("---")
    st.markdown("#### 🛡️ Rendimiento Defensivo")
    fig_def = px.scatter(df_p90, x="Quites_P90", y="Inter_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES)
    st.plotly_chart(fig_def, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🧠 Creación de Juego y Pases")
    c1, c2 = st.columns(2)
    with c1:
        fig_crea = px.scatter(df_p90, x="PasesClave_P90", y="Asistencias_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES)
        st.plotly_chart(fig_crea, use_container_width=True)
    with c2:
        fig_pases = px.scatter(df_p90, x="PasesClave_P90", y="Efectividad_Pases", color="Posición", hover_name="Jugador", labels={"Efectividad_Pases": "Efectividad Promedio (%)"}, color_discrete_map=DICCIONARIO_COLORES)
        st.plotly_chart(fig_pases, use_container_width=True)
    
    st.markdown("---")
    st.markdown("#### 🎯 Efectividad Ofensiva (Tiros vs Goles)")
    df_tiros = df_agrupado[df_agrupado['Tiros_Totales'] > 0].copy()
    fig_of = px.scatter(df_tiros, x="Tiros_Totales", y="Goles", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES)
    fig_of.add_shape(type="line", x0=0, y0=0, x1=df_tiros['Tiros_Totales'].max()+2, y1=(df_tiros['Tiros_Totales'].max()+2)*0.20, line=dict(color="Gray", dash="dot"))
    st.plotly_chart(fig_of, use_container_width=True)

elif menu == "Análisis Individual":
    st.markdown("<h1>🔎 Evolución y Perfil del Jugador</h1>", unsafe_allow_html=True)
    jugador_sel = st.selectbox("Seleccionar Jugador:", sorted(df_raw['Jugador'].unique()))
    if jugador_sel:
        df_j = df_raw[df_raw['Jugador'] == jugador_sel]
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Evolución SofaScore")
            fig_l = px.line(df_j, x="Partido", y="Nota SofaScore", markers=True)
            fig_l.update_traces(line_color="#ed1c24", marker=dict(color="#ed1c24", size=10))
            fig_l.add_hline(y=df_j['Nota SofaScore'].mean(), line_dash="dot", line_color="gray", annotation_text="Promedio")
            fig_l.update_yaxes(range=[4, 10])
            st.plotly_chart(fig_l, use_container_width=True)
        with col2:
            st.subheader("Perfil Estadístico")
            stats = ['Pases Clave', 'Tiros Totales', 'Quites (Tackles)', 'Intercepciones']
            vals = df_j[stats].sum().values.tolist()
            if vals:
                vals += [vals[0]]
                theta = stats + [stats[0]]
                fig_r = go.Figure(data=go.Scatterpolar(r=vals, theta=theta, fill='toself', fillcolor='rgba(237,28,36,0.4)', line_color='#ed1c24'))
                fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, max(vals)+2])), showlegend=False)
                st.plotly_chart(fig_r, use_container_width=True)

elif menu == "Parado Táctico":
    st.markdown("<h1>📋 Parado Táctico por Partido</h1>", unsafe_allow_html=True)
    hojas_dict = df_raw.drop_duplicates(subset=['Partido'])[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido_sel = st.selectbox("Seleccioná la fecha:", list(hojas_dict.keys()))
    if partido_sel:
        with st.spinner("Cargando parado táctico..."):
            img = extraer_imagen_incrustada(str(EXCEL), hojas_dict[partido_sel], indice_imagen=0)
        if img:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(img, use_container_width=True)
        else:
            st.warning("No se encontró la imagen del parado en el Excel.")

elif menu == "Mapa de Tiros":
    st.markdown("<h1>🎯 Mapa de Tiros (River vs Rival)</h1>", unsafe_allow_html=True)
    hojas_dict = df_raw.drop_duplicates(subset=['Partido'])[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido_sel = st.selectbox("Seleccioná la fecha para ver los tiros:", list(hojas_dict.keys()))
    if partido_sel:
        with st.spinner("Cargando mapa de tiros..."):
            img_tiros = extraer_imagen_incrustada(str(EXCEL), hojas_dict[partido_sel], indice_imagen=1)
        if img_tiros:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(img_tiros, use_container_width=True)
        else:
            st.warning("No se encontró el mapa de tiros en el Excel para esta fecha.")