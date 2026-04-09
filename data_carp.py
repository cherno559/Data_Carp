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

# ── RUTAS DINÁMICAS ──────────────────────────────────────────────────────────
CARPETA = Path(__file__).parent
archivos_excel = list(CARPETA.glob("*.xlsx"))
EXCEL = archivos_excel[0] if archivos_excel else CARPETA / "Base_Datos_River_2026.xlsx"

RUTA_LOGO_ACTUAL = CARPETA / "logo_river_actual.png"
RUTA_LOGO_RETRO  = CARPETA / "logo_river_retro.png"
RUTA_LOGO_CARP   = CARPETA / "logo_carp.png"

DICCIONARIO_COLORES = {'DEF': '#1f77b4', 'MED': '#2ca02c', 'DEL': '#ed1c24', 'POR': '#ff7f0e'}

# ── FUNCIONES DE PROCESAMIENTO ───────────────────────────────────────────────

def extraer_exitosos(valor):
    try:
        if isinstance(valor, str):
            return int(valor.replace("'", "").split('/')[0])
        return int(valor)
    except: return 0

@st.cache_data
def cargar_datos_completos():
    if not EXCEL.exists(): return pd.DataFrame(), "❌ Archivo no encontrado"
    try:
        xl = pd.ExcelFile(EXCEL)
        partes = []
        hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas", "Hoja"]
        for hoja in xl.sheet_names:
            if any(omitir in hoja for omitir in hojas_omitir): continue
            df = pd.read_excel(EXCEL, sheet_name=hoja)
            df.columns = df.columns.str.strip()
            if 'Jugador' in df.columns:
                df['Jugador'] = df['Jugador'].astype(str).str.strip()
                if 'Nota SofaScore' in df.columns:
                    df['Nota SofaScore'] = pd.to_numeric(df['Nota SofaScore'], errors="coerce")
                df['Partido'] = hoja 
                df['Hoja_Original'] = hoja
                df = df.dropna(subset=['Jugador'])
                df = df[df['Jugador'] != "nan"]
                cols_num = ['Minutos', 'Goles', 'Asistencias', 'Pases Clave', 'Quites (Tackles)', 'Intercepciones', 'Tiros Totales', 'Efectividad Pases', 'Tiros al Arco']
                for col in cols_num:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                partes.append(df)
        return pd.concat(partes, ignore_index=True), "OK"
    except Exception as e: return pd.DataFrame(), str(e)

@st.cache_data
def extraer_imagen_incrustada(ruta_excel_str, nombre_hoja, indice_imagen=0):
    try:
        wb = load_workbook(ruta_excel_str, data_only=True)
        ws = wb[nombre_hoja]
        if hasattr(ws, '_images') and len(ws._images) > indice_imagen:
            img = ws._images[indice_imagen]
            return img._data() if callable(img._data) else img._data
        return None
    except: return None

@st.cache_data
def extraer_estadisticas_equipo(ruta_excel_str, nombre_hoja):
    try:
        df = pd.read_excel(ruta_excel_str, sheet_name=nombre_hoja, header=None)
        row_idx, col_idx = None, None
        for r in range(min(120, len(df))):
            for c in range(min(15, len(df.columns))):
                val = str(df.iloc[r, c]).strip().lower()
                if val == 'métrica' or val == 'metrica':
                    row_idx, col_idx = r, c; break
            if row_idx is not None: break
        if row_idx is not None:
            df_team = df.iloc[row_idx+1:, col_idx:col_idx+3].copy()
            df_team.columns = df.iloc[row_idx, col_idx:col_idx+3].values
            return df_team.dropna(subset=[df_team.columns[0]])
        return pd.DataFrame()
    except: return pd.DataFrame()

# ── BARRA LATERAL ────────────────────────────────────────────────────────────
col_nav1, col_nav2 = st.sidebar.columns([1, 2])
with col_nav1:
    if RUTA_LOGO_ACTUAL.exists(): st.image(str(RUTA_LOGO_ACTUAL), width=70)
with col_nav2:
    st.markdown('<p class="sidebar-title">Data<br>CARP</p>', unsafe_allow_html=True)

st.sidebar.markdown("---")
categoria = st.sidebar.radio("Categoría de Análisis:", ["🏆 Por Temporada", "🗓️ Por Fecha"])
st.sidebar.markdown("---")

if categoria == "🏆 Por Temporada":
    menu = st.sidebar.radio("Sección:", ["Resumen General", "Mapas de Rendimiento", "Análisis Individual"])
else:
    menu = st.sidebar.radio("Sección:", ["Estadísticas de Equipo", "Estadísticas Individuales", "Parado Táctico", "Mapa de Tiros"])

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
col_bot1, col_bot2 = st.sidebar.columns(2)
with col_bot1:
    if RUTA_LOGO_RETRO.exists(): st.image(str(RUTA_LOGO_RETRO), width=80)
with col_bot2:
    if RUTA_LOGO_CARP.exists(): st.image(str(RUTA_LOGO_CARP), width=80)

# ── PROCESAMIENTO ────────────────────────────────────────────────────────────
df_raw, estado = cargar_datos_completos()
if estado != "OK": st.error(estado); st.stop()

# ── PÁGINAS: POR TEMPORADA ───────────────────────────────────────────────────

if menu == "Resumen General":
    st.markdown("<h1>🐔 Panel General del Equipo</h1>", unsafe_allow_html=True)
    
    df_agrupado = df_raw.groupby(['Jugador', 'Posición'], as_index=False).agg(
        Partidos=('Nota SofaScore', 'count'), Promedio=('Nota SofaScore', 'mean'),
        Goles=('Goles', 'sum'), Asistencias=('Asistencias', 'sum')
    )
    df_agrupado['Promedio'] = df_agrupado['Promedio'].round(2)
    
    # Estado de Forma para la tabla
    df_forma = df_raw.groupby('Jugador')['Nota SofaScore'].apply(lambda x: list(x)[-5:]).reset_index(name='Estado de Forma')
    df_agrupado = df_agrupado.merge(df_forma, on='Jugador')

    st.subheader("📊 Promedios y Tendencia")
    st.dataframe(
        df_agrupado[['Jugador', 'Promedio', 'Partidos', 'Estado de Forma']].sort_values('Promedio', ascending=False),
        column_config={
            "Estado de Forma": st.column_config.BarChartColumn(
                "Forma (Últ. 5)", y_min=5, y_max=10, width="large"
            )
        },
        hide_index=True, use_container_width=True
    )
    
    st.divider()
    st.subheader("⚽ Goleadores")
    st.dataframe(df_agrupado[df_agrupado['Goles']>0][['Jugador', 'Goles']].sort_values('Goles', ascending=False), hide_index=True, use_container_width=True)
    
    st.subheader("👟 Asistidores")
    st.dataframe(df_agrupado[df_agrupado['Asistencias']>0][['Jugador', 'Asistencias']].sort_values('Asistencias', ascending=False), hide_index=True, use_container_width=True)

elif menu == "Mapas de Rendimiento":
    st.markdown("<h1>🗺️ Mapas de Rendimiento</h1>", unsafe_allow_html=True)
    df_map = df_raw.groupby(['Jugador', 'Posición'], as_index=False).agg(
        Minutos=('Minutos', 'sum'), Pases_Clave=('Pases Clave', 'sum'), Asistencias=('Asistencias', 'sum'),
        Quites=('Quites (Tackles)', 'sum'), Intercepciones=('Intercepciones', 'sum'), 
        Tiros_Totales=('Tiros Totales', 'sum'), Goles=('Goles', 'sum'), Efectividad_Pases=('Efectividad Pases', 'mean')
    )
    min_min = st.sidebar.slider("Minutos Mínimos", 0, int(df_map['Minutos'].max()), 180)
    df_p90 = df_map[df_map['Minutos'] >= min_min].copy()
    
    # Cálculos P90
    for col in ['Pases_Clave', 'Asistencias', 'Quites', 'Intercepciones']:
        df_p90[f'{col}_P90'] = (df_p90[col] / df_p90['Minutos']) * 90

    st.markdown("### 🛡️ Defensa")
    st.plotly_chart(px.scatter(df_p90, x="Quites_P90", y="Inter_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=15)), use_container_width=True)
    
    st.divider()
    st.markdown("### 🧠 Creación")
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.scatter(df_p90, x="PasesClave_P90", y="Asistencias_P90", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=13)), use_container_width=True)
    with c2: st.plotly_chart(px.scatter(df_p90, x="PasesClave_P90", y="Efectividad_Pases", color="Posición", hover_name="Jugador", color_discrete_map=DICCIONARIO_COLORES).update_traces(marker=dict(size=13)), use_container_width=True)

elif menu == "Análisis Individual":
    st.markdown("<h1>🔎 Análisis Individual</h1>", unsafe_allow_html=True)
    jugador_sel = st.selectbox("Seleccioná un Jugador:", sorted(df_raw['Jugador'].unique()))
    
    if jugador_sel:
        df_j = df_raw[df_raw['Jugador'] == jugador_sel].copy()
        
        # 1. GRÁFICO DE BARRAS CON NOTAS (ESTADO DE FORMA)
        st.subheader("📈 Evolución de Forma (Últimos 5 Partidos)")
        df_last5 = df_j.tail(5)
        
        fig_forma = px.bar(
            df_last5, 
            x='Partido', 
            y='Nota SofaScore',
            text='Nota SofaScore', # Esto pone el número
            color='Nota SofaScore',
            color_continuous_scale='Reds',
            range_y=[0, 10]
        )
        fig_forma.update_traces(textposition='outside', textfont_size=14, marker_line_color='black', marker_line_width=1)
        fig_forma.update_layout(xaxis_title="Partido", yaxis_title="Nota", showlegend=False)
        st.plotly_chart(fig_forma, use_container_width=True)
        
        st.divider()
        
        # 2. RADAR Y ESTADÍSTICAS
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("### 📊 Perfil de Juego (Acumulado)")
            stats_radar = ['Pases Clave', 'Tiros Totales', 'Quites (Tackles)', 'Intercepciones']
            vals = df_j[stats_radar].sum().tolist()
            vals += [vals[0]] # Cerrar el radar
            
            fig_radar = go.Figure(data=go.Scatterpolar(
                r=vals, 
                theta=stats_radar + [stats_radar[0]], 
                fill='toself', 
                fillcolor='rgba(237,28,36,0.4)', 
                line_color='#ed1c24'
            ))
            st.plotly_chart(fig_radar, use_container_width=True)
            
        with c2:
            st.markdown("### 📁 Ficha Técnica")
            st.metric("Partidos Jugados", len(df_j))
            st.metric("Promedio SofaScore", round(df_j['Nota SofaScore'].mean(), 2))
            st.metric("Goles Totales", int(df_j['Goles'].sum()))
            st.metric("Asistencias Totales", int(df_j['Asistencias'].sum()))

# ── PÁGINAS: POR FECHA ───────────────────────────────────────────────────────

elif menu == "Estadísticas de Equipo":
    st.markdown("<h1>⚖️ Estadísticas de Equipo</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Seleccioná la fecha:", list(hojas.keys()))
    df_team = extraer_estadisticas_equipo(str(EXCEL), hojas[partido])
    if not df_team.empty:
        st.dataframe(df_team, hide_index=True, use_container_width=True)
    else: st.warning("No se encontró la tabla en esta hoja.")

elif menu == "Estadísticas Individuales":
    st.markdown("<h1>👤 Estadísticas Individuales</h1>", unsafe_allow_html=True)
    partidos = df_raw['Partido'].unique()
    partido_sel = st.selectbox("Fecha:", partidos)
    df_p = df_raw[df_raw['Partido'] == partido_sel].copy()
    
    # Limpieza para Top 7
    if 'Pases (Comp/Tot)' in df_p.columns: df_p['Pases Completados'] = df_p['Pases (Comp/Tot)'].apply(extraer_exitosos)
    if 'Regates (Exit/Tot)' in df_p.columns: df_p['Regates Exitosos'] = df_p['Regates (Exit/Tot)'].apply(extraer_exitosos)
    if 'Duelos (Gan/Tot)' in df_p.columns: df_p['Duelos Ganados'] = df_p['Duelos (Gan/Tot)'].apply(extraer_exitosos)
    if 'Quites (Tackles)' in df_p.columns: df_p = df_p.rename(columns={'Quites (Tackles)': 'Quites'})

    st.divider()
    top_n = 7
    metrics = [
        ("⭐ Nota SofaScore", "Nota SofaScore"),
        ("🛡️ Quites", "Quites"),
        ("🛑 Intercepciones", "Intercepciones"),
        ("⚔️ Duelos Ganados", "Duelos Ganados"),
        ("🎯 Pases Completados", "Pases Completados"),
        ("🔑 Pases Clave", "Pases Clave"),
        ("⚡ Regates Exitosos", "Regates Exitosos"),
        ("👟 Tiros al Arco", "Tiros al Arco")
    ]
    
    for title, col in metrics:
        st.markdown(f"### {title}")
        df_display = df_p.nlargest(top_n, col) if col != "Pases Clave" and col != "Regates Exitosos" else df_p[df_p[col]>0].nlargest(top_n, col)
        st.dataframe(df_display[['Jugador', col]], hide_index=True, use_container_width=True)

elif menu == "Parado Táctico":
    st.markdown("<h1>📋 Parado Táctico</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    img = extraer_imagen_incrustada(str(EXCEL), hojas[partido], 0)
    if img: st.image(img, use_container_width=True)

elif menu == "Mapa de Tiros":
    st.markdown("<h1>🎯 Mapa de Tiros</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    img = extraer_imagen_incrustada(str(EXCEL), hojas[partido], 1)
    if img: st.image(img, use_container_width=True)
