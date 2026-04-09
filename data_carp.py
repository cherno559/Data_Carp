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
if archivos_excel:
    EXCEL = archivos_excel[0]
else:
    EXCEL = CARPETA / "Base_Datos_River_2026.xlsx"

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

@st.cache_data
def extraer_estadisticas_equipo(ruta_excel_str, nombre_hoja):
    try:
        df = pd.read_excel(ruta_excel_str, sheet_name=nombre_hoja, header=None)
        row_idx, col_idx = None, None
        
        for r in range(min(100, len(df))):
            for c in range(min(10, len(df.columns))):
                val = str(df.iloc[r, c]).strip().lower()
                if val == 'métrica' or val == 'metrica':
                    row_idx, col_idx = r, c
                    break
            if row_idx is not None: break
        
        if row_idx is not None:
            df_team = df.iloc[row_idx+1:, col_idx:col_idx+3].copy()
            df_team.columns = df.iloc[row_idx, col_idx:col_idx+3].values
            df_team = df_team.dropna(subset=[df_team.columns[0]])
            df_team = df_team[df_team[df_team.columns[0]].astype(str).str.strip() != '']
            df_team = df_team.dropna(subset=[df_team.columns[1], df_team.columns[2]], how='all')
            return df_team
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ── BARRA LATERAL (DOBLE PESTAÑA) ────────────────────────────────────────────
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

# ── PROCESAMIENTO DE DATOS ───────────────────────────────────────────────────
df_raw, estado = cargar_datos_completos()
if estado != "OK":
    st.error(estado); st.stop()

if 'Efectividad Pases' in df_raw.columns:
    df_raw['Efectividad Pases'] = df_raw['Efectividad Pases'].replace(0, np.nan)

# Agrupación general
df_agrupado = df_raw.groupby(['Jugador', 'Posición'], as_index=False).agg(
    Partidos=('Nota SofaScore', 'count'), Promedio=('Nota SofaScore', 'mean'),
    Minutos=('Minutos', 'sum'), Goles=('Goles', 'sum'), Asistencias=('Asistencias', 'sum'),
    Pases_Clave=('Pases Clave', 'sum'), Quites=('Quites (Tackles)', 'sum'),
    Intercepciones=('Intercepciones', 'sum'), Tiros_Totales=('Tiros Totales', 'sum'),
    Efectividad_Pases=('Efectividad Pases', 'mean')
)
df_agrupado['Promedio'] = df_agrupado['Promedio'].round(2)
df_agrupado['Efectividad_Pases'] = df_agrupado['Efectividad_Pases'].round(1).fillna(0)

# ESTADO DE FORMA: Formateamos las últimas 5 notas en un texto claro y directo
df_forma = df_raw.groupby('Jugador')['Nota SofaScore'].apply(
    lambda x: " | ".join([f"{n:.1f}" for n in list(x)[-5:]])
).reset_index(name='Forma (Últ. 5)')

# Unimos la tendencia al DataFrame agrupado
df_agrupado = df_agrupado.merge(df_forma, on='Jugador', how='left')

# ── PÁGINAS: POR TEMPORADA ───────────────────────────────────────────────────

if menu == "Resumen General":
    st.markdown("<h1>🐔 Panel General del Equipo</h1>", unsafe_allow_html=True)
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("📊 Promedios SofaScore")
        df_promedios = df_agrupado[['Jugador', 'Promedio', 'Partidos', 'Forma (Últ. 5)']].sort_values('Promedio', ascending=False).reset_index(drop=True)
        
        # Mostramos la tabla directamente con los números legibles
        st.dataframe(
            df_promedios,
            hide_index=True, 
            use_container_width=True
        )
        
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
            # Gráfico de barras sólido y con números legibles
            fig_l = px.bar(df_j, x="Partido", y="Nota SofaScore", text="Nota SofaScore")
            fig_l.update_traces(
                marker_color="#ed1c24", 
                textposition="outside", 
                textfont_size=12,
                texttemplate='%{text:.1f}'
            )
            fig_l.add_hline(y=df_j['Nota SofaScore'].mean(), line_dash="dot", annotation_text="Promedio", line_color="black")
            fig_l.update_layout(yaxis_range=[0, 11])
            st.plotly_chart(fig_l, use_container_width=True)
        with c2:
            stats = ['Pases Clave', 'Tiros Totales', 'Quites (Tackles)', 'Intercepciones']
            vals = df_j[stats].sum().tolist(); vals += [vals[0]]
            fig_r = go.Figure(data=go.Scatterpolar(r=vals, theta=stats+[stats[0]], fill='toself', fillcolor='rgba(237,28,36,0.4)', line_color='#ed1c24'))
            st.plotly_chart(fig_r, use_container_width=True)

# ── PÁGINAS: POR FECHA ───────────────────────────────────────────────────────

elif menu == "Estadísticas de Equipo":
    st.markdown("<h1>⚖️ Estadísticas de Equipo</h1>", unsafe_allow_html=True)
    st.markdown("Comparativa general del rendimiento colectivo frente al rival.")
    
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Seleccioná la fecha:", list(hojas.keys()))
    
    df_equipo = extraer_estadisticas_equipo(str(EXCEL), hojas[partido])
    
    st.divider()
    if not df_equipo.empty:
        st.dataframe(df_equipo, hide_index=True, use_container_width=True)
    else:
        st.warning("⚠️ No se encontraron las estadísticas colectivas al final de esta hoja.")

elif menu == "Estadísticas Individuales":
    st.markdown("<h1>👤 Estadísticas Individuales</h1>", unsafe_allow_html=True)
    st.markdown("Seleccioná un partido para ver el **Top 7** de rendimiento en las métricas clave.")
    
    def extraer_exitosos(valor):
        try:
            if isinstance(valor, str):
                return int(valor.replace("'", "").split('/')[0])
            return int(valor)
        except:
            return 0

    partidos = df_raw['Partido'].unique()
    partido_seleccionado = st.selectbox("Seleccioná la fecha:", partidos)
    
    df_p = df_raw[df_raw['Partido'] == partido_seleccionado].copy()
    
    if 'Pases (Comp/Tot)' in df_p.columns:
        df_p['Pases Completados'] = df_p['Pases (Comp/Tot)'].apply(extraer_exitosos)
    if 'Duelos (Gan/Tot)' in df_p.columns:
        df_p['Duelos Ganados'] = df_p['Duelos (Gan/Tot)'].apply(extraer_exitosos)
    if 'Regates (Exit/Tot)' in df_p.columns:
        df_p['Regates Exitosos'] = df_p['Regates (Exit/Tot)'].apply(extraer_exitosos)
        
    if 'Quites (Tackles)' in df_p.columns:
        df_p = df_p.rename(columns={'Quites (Tackles)': 'Quites'})
        
    cols_a_num = ['Efectividad Pases', 'Efectividad Duelos', 'Efectividad Regates', 'Tiros al Arco', 'Tiros Totales', 'Pases Clave', 'Intercepciones']
    for col in cols_a_num:
        if col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)

    st.divider()
    st.subheader(f"🏆 Top 7 - {partido_seleccionado}")
    top_n = 7

    # 1. VALORACIÓN GENERAL
    st.markdown("### ⭐ Nota SofaScore")
    if 'Nota SofaScore' in df_p.columns:
        top_nota = df_p.nlargest(top_n, 'Nota SofaScore')[['Jugador', 'Nota SofaScore']]
        st.dataframe(top_nota, hide_index=True, use_container_width=True)

    # 2. ASPECTO DEFENSIVO
    st.markdown("### 🛡️ Quites")
    if 'Quites' in df_p.columns:
        top_quites = df_p.nlargest(top_n, 'Quites')[['Jugador', 'Quites']]
        st.dataframe(top_quites, hide_index=True, use_container_width=True)

    st.markdown("### 🛑 Intercepciones")
    if 'Intercepciones' in df_p.columns:
        top_intercepciones = df_p.nlargest(top_n, 'Intercepciones')[['Jugador', 'Intercepciones']]
        st.dataframe(top_intercepciones, hide_index=True, use_container_width=True)

    st.markdown("### ⚔️ Duelos Ganados")
    if 'Duelos Ganados' in df_p.columns and 'Efectividad Duelos' in df_p.columns:
        top_duelos = df_p.sort_values(by=['Duelos Ganados', 'Efectividad Duelos'], ascending=[False, False]).head(top_n)[['Jugador', 'Duelos Ganados', 'Efectividad Duelos']]
        st.dataframe(top_duelos, hide_index=True, use_container_width=True)

    # 3. CREACIÓN Y POSESIÓN
    st.markdown("### 🎯 Pases Completados")
    if 'Pases Completados' in df_p.columns and 'Efectividad Pases' in df_p.columns:
        top_pases = df_p.sort_values(by=['Pases Completados', 'Efectividad Pases'], ascending=[False, False]).head(top_n)[['Jugador', 'Pases Completados', 'Efectividad Pases']]
        st.dataframe(top_pases, hide_index=True, use_container_width=True)

    st.markdown("### 🔑 Pases Clave")
    if 'Pases Clave' in df_p.columns:
        top_pases_clave = df_p[df_p['Pases Clave'] > 0].nlargest(top_n, 'Pases Clave')[['Jugador', 'Pases Clave']]
        if not top_pases_clave.empty:
            st.dataframe(top_pases_clave, hide_index=True, use_container_width=True)
        else:
            st.info("Ningún jugador registró pases clave en este partido.")

    # 4. ATAQUE Y DEFINICIÓN
    st.markdown("### ⚡ Regates Exitosos")
    if 'Regates Exitosos' in df_p.columns and 'Efectividad Regates' in df_p.columns:
        top_regates = df_p[df_p['Regates Exitosos'] > 0].sort_values(by=['Regates Exitosos', 'Efectividad Regates'], ascending=[False, False]).head(top_n)[['Jugador', 'Regates Exitosos', 'Efectividad Regates']]
        if not top_regates.empty:
            st.dataframe(top_regates, hide_index=True, use_container_width=True)
        else:
            st.info("Ningún jugador registró regates exitosos en este partido.")

    st.markdown("### 👟 Tiros al Arco")
    if 'Tiros al Arco' in df_p.columns and 'Tiros Totales' in df_p.columns:
        top_tiros = df_p.sort_values(by=['Tiros al Arco', 'Tiros Totales'], ascending=[False, False]).head(top_n)[['Jugador', 'Tiros al Arco', 'Tiros Totales']]
        st.dataframe(top_tiros, hide_index=True, use_container_width=True)

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
