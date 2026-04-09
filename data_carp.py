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
    h1, h2, h3, h4 { color: #ed1c24 !important; font-family: 'Arial Black', sans-serif; }
    .block-container { padding-top: 2rem; }
    [data-testid="stSidebar"] { border-right: 4px solid #ed1c24; background-color: #f8f9fa; }
    .sidebar-title { color: #000000 !important; font-family: 'Arial Black', sans-serif; font-size: 24px; margin-top: -20px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# ── RUTAS DINÁMICAS (ESTO ARREGLA EL ERROR DEL EXCEL) ────────────────────────
CARPETA = Path(__file__).parent

# Buscamos cualquier archivo .xlsx en la carpeta (por si el nombre cambia un poquito)
archivos_excel = list(CARPETA.glob("*.xlsx"))
if archivos_excel:
    EXCEL = archivos_excel[0]
else:
    EXCEL = CARPETA / "Base_Datos_River_2026.xlsx"

# Logos locales
RUTA_LOGO_ACTUAL = CARPETA / "logo_river_actual.png"
RUTA_LOGO_RETRO  = CARPETA / "logo_river_retro.png"
RUTA_LOGO_CARP   = CARPETA / "logo_carp.png"

DICCIONARIO_COLORES = {'DEF': '#1f77b4', 'MED': '#2ca02c', 'DEL': '#ed1c24', 'POR': '#ff7f0e'}

# ── CARGA DE DATOS ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos_completos():
    if not EXCEL.exists():
        return pd.DataFrame(), f"❌ No se encontró el archivo Excel en: {EXCEL.name}"
    try:
        xl = pd.ExcelFile(EXCEL)
        partes = []
        hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"]
        for hoja in xl.sheet_names:
            if hoja in hojas_omitir: continue
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
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(), "OK"
    except Exception as e:
        return pd.DataFrame(), f"Error: {str(e)}"

@st.cache_data
def extraer_imagen_incrustada(ruta_excel_str, nombre_hoja, indice_imagen=0):
    try:
        wb = load_workbook(ruta_excel_str, data_only=True)
        if nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            if hasattr(ws, '_images') and len(ws._images) > indice_imagen:
                img = ws._images[indice_imagen]
                return img._data() if callable(img._data) else img._data
        return None
    except: return None

# ── BARRA LATERAL ────────────────────────────────────────────────────────────
col_nav1, col_nav2 = st.sidebar.columns([1, 2])
with col_nav1:
    if RUTA_LOGO_ACTUAL.exists(): st.image(str(RUTA_LOGO_ACTUAL), width=70)
with col_nav2:
    st.markdown('<p class="sidebar-title">Data<br>CARP</p>', unsafe_allow_html=True)

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegación:", ["Resumen General", "Mapas de Rendimiento", "Análisis Individual", "Parado Táctico", "Mapa de Tiros", "Partido a partido"])

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
col_bot1, col_bot2 = st.sidebar.columns(2)
with col_bot1:
    if RUTA_LOGO_RETRO.exists(): st.image(str(RUTA_LOGO_RETRO), width=80)
with col_bot2:
    if RUTA_LOGO_CARP.exists(): st.image(str(RUTA_LOGO_CARP), width=80)

# ── PROCESAMIENTO DE DATOS ───────────────────────────────────────────────────
df_raw, estado = cargar_datos_completos()
if estado != "OK":
    st.error(estado); st.stop()

if 'Efectividad Pases' in df_raw.columns:
    df_raw['Efectividad Pases'] = df_raw['Efectividad Pases'].replace(0, np.nan)

df_agrupado = df_raw.groupby(['Jugador', 'Posición'], as_index=False).agg(
    Partidos=('Nota SofaScore', 'count'), Promedio=('Nota SofaScore', 'mean'),
    Minutos=('Minutos', 'sum'), Goles=('Goles', 'sum'), Asistencias=('Asistencias', 'sum'),
    Pases_Clave=('Pases Clave', 'sum'), Quites=('Quites (Tackles)', 'sum'),
    Intercepciones=('Intercepciones', 'sum'), Tiros_Totales=('Tiros Totales', 'sum'),
    Efectividad_Pases=('Efectividad Pases', 'mean')
)
df_agrupado['Promedio'] = df_agrupado['Promedio'].round(2)
df_agrupado['Efectividad_Pases'] = df_agrupado['Efectividad_Pases'].round(1).fillna(0)

# ── PÁGINAS ──────────────────────────────────────────────────────────────────

if menu == "Resumen General":
    st.markdown("<h1>🐔 Panel General del Equipo</h1>", unsafe_allow_html=True)
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("📊 Promedios SofaScore")
        st.dataframe(df_agrupado[['Jugador', 'Promedio', 'Partidos']].sort_values('Promedio', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
    with c2:
        st.subheader("⚽ Goleadores")
        st.dataframe(df_agrupado[df_agrupado['Goles'] > 0][['Jugador', 'Goles']].sort_values('Goles', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
    with c3:
        st.subheader("👟 Asistidores")
        st.dataframe(df_agrupado[df_agrupado['Asistencias'] > 0][['Jugador', 'Asistencias']].sort_values('Asistencias', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)

elif menu == "Mapas de Rendimiento":
    st.markdown("<h1>🗺️ Mapas de Rendimiento</h1>", unsafe_allow_html=True)
    min_min = st.sidebar.slider("Minutos Mínimos", 0, int(df_agrupado['Minutos'].max()), 180)
    df_p90 = df_agrupado[df_agrupado['Minutos'] >= min_min].copy()
    df_p90['PasesClave_P90'] = (df_p90['Pases_Clave'] / df_p90['Minutos']) * 90
    df_p90['Asistencias_P90'] = (df_p90['Asistencias'] / df_p90['Minutos']) * 90
    df_p90['Quites_P90'] = (df_p90['Quites'] / df_p90['Minutos']) * 90
    df_p90['Inter_P90'] = (df_p90['Intercepciones'] / df_p90['Minutos']) * 90

    st.markdown("### 🛡️ Defensa")
    st.plotly_chart(px.scatter(df_p90, x="Quites_P90", y="Inter_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=15)), use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 🧠 Creación")
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.scatter(df_p90, x="PasesClave_P90", y="Asistencias_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=13)), use_container_width=True)
    with c2: st.plotly_chart(px.scatter(df_p90, x="PasesClave_P90", y="Efectividad_Pases", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=13)), use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 🎯 Ataque")
    df_t = df_agrupado[df_agrupado['Tiros_Totales'] > 0]
    if not df_t.empty:
        fig_of = px.scatter(df_t, x="Tiros_Totales", y="Goles", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=15))
        fig_of.add_shape(type="line", x0=0, y0=0, x1=df_t['Tiros_Totales'].max()+2, y1=(df_t['Tiros_Totales'].max()+2)*0.20, line=dict(color="Gray", dash="dot"))
        st.plotly_chart(fig_of, use_container_width=True)

elif menu == "Análisis Individual":
    st.markdown("<h1>🔎 Análisis Individual</h1>", unsafe_allow_html=True)
    jugador_sel = st.selectbox("Jugador:", sorted(df_raw['Jugador'].unique()))
    if jugador_sel:
        df_j = df_raw[df_raw['Jugador'] == jugador_sel]
        c1, c2 = st.columns([2, 1])
        with c1:
            fig_l = px.line(df_j, x="Partido", y="Nota SofaScore", markers=True).update_traces(line_color="#ed1c24", marker=dict(size=10))
            fig_l.add_hline(y=df_j['Nota SofaScore'].mean(), line_dash="dot", annotation_text="Promedio")
            st.plotly_chart(fig_l, use_container_width=True)
        with c2:
            stats = ['Pases Clave', 'Tiros Totales', 'Quites (Tackles)', 'Intercepciones']
            vals = df_j[stats].sum().tolist(); vals += [vals[0]]
            fig_r = go.Figure(data=go.Scatterpolar(r=vals, theta=stats+[stats[0]], fill='toself', fillcolor='rgba(237,28,36,0.4)', line_color='#ed1c24'))
            st.plotly_chart(fig_r, use_container_width=True)

elif menu == "Parado Táctico":
    st.markdown("<h1>📋 Parado Táctico</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    img = extraer_imagen_incrustada(str(EXCEL), hojas[partido], 0)
    if img: st.image(img, use_container_width=True)
    else: st.warning("Imagen no encontrada.")

elif menu == "Mapa de Tiros":
    st.markdown("<h1>🎯 Mapa de Tiros</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    img = extraer_imagen_incrustada(str(EXCEL), hojas[partido], 1)
    if img: st.image(img, use_container_width=True)
    else: st.warning("Imagen no encontrada.")

# -----------------------------------------------------------------------------
# NUEVA PESTAÑA: PARTIDO A PARTIDO (TOP 7 AMPLIADO)
# -----------------------------------------------------------------------------
elif menu == "Partido a partido":
    st.markdown("<h1>⚽ Análisis Partido a Partido</h1>", unsafe_allow_html=True)
    st.markdown("Seleccioná un partido para ver el **Top 7** de rendimiento en las métricas clave.")
    
    # Función para extraer el primer número de las columnas de texto ('15/20 -> 15)
    def extraer_exitosos(valor):
        try:
            if isinstance(valor, str):
                return int(valor.replace("'", "").split('/')[0])
            return int(valor)
        except:
            return 0

    # Selector de partido usando la base ya cargada
    partidos = df_raw['Partido'].unique()
    partido_seleccionado = st.selectbox("Seleccioná la fecha:", partidos)
    
    # Filtramos la base para el partido seleccionado
    df_p = df_raw[df_raw['Partido'] == partido_seleccionado].copy()
    
    # Limpiamos las columnas con datos fraccionados ('X/Y') solo para esta vista
    if 'Pases (Comp/Tot)' in df_p.columns:
        df_p['Pases Completados'] = df_p['Pases (Comp/Tot)'].apply(extraer_exitosos)
    if 'Duelos (Gan/Tot)' in df_p.columns:
        df_p['Duelos Ganados'] = df_p['Duelos (Gan/Tot)'].apply(extraer_exitosos)
    if 'Regates (Exit/Tot)' in df_p.columns:
        df_p['Regates Exitosos'] = df_p['Regates (Exit/Tot)'].apply(extraer_exitosos)
        
    # Aseguramos que las efectividades sean números para poder desempatar correctamente
    cols_a_num = ['Efectividad Pases', 'Efectividad Duelos', 'Efectividad Regates', 'Tiros al Arco', 'Tiros Totales', 'Pases Clave', 'Intercepciones']
    for col in cols_a_num:
        if col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)

    st.divider()
    st.subheader(f"🏆 Top 7 - {partido_seleccionado}")

    top_n = 7

    # 1. NOTA SOFASCORE
    st.markdown("### ⭐ Nota SofaScore")
    if 'Nota SofaScore' in df_p.columns:
        top_nota = df_p.nlargest(top_n, 'Nota SofaScore')[['Jugador', 'Nota SofaScore']]
        st.dataframe(top_nota, hide_index=True, use_container_width=True)
    
    # 2. PASES COMPLETADOS
    st.markdown("### 🎯 Pases Completados")
    if 'Pases Completados' in df_p.columns and 'Efectividad Pases' in df_p.columns:
        top_pases = df_p.sort_values(by=['Pases Completados', 'Efectividad Pases'], ascending=[False, False]).head(top_n)[['Jugador', 'Pases Completados', 'Efectividad Pases']]
        st.dataframe(top_pases, hide_index=True, use_container_width=True)

    # 3. PASES CLAVE (Acá filtramos para mostrar solo a los que tienen más de 0)
    st.markdown("### 🔑 Pases Clave")
    if 'Pases Clave' in df_p.columns:
        top_pases_clave = df_p[df_p['Pases Clave'] > 0].
