import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from openpyxl import load_workbook
import io
import re

# ── CONFIGURACIÓN DE LA PÁGINA ───────────────────────────────────────────────
st.set_page_config(page_title="Data CARP", page_icon="🐔", layout="wide")

# ── ESTILOS CSS (TEMA RIVER PLATE) ───────────────────────────────────────────
st.markdown("""
    <style>
    h1, h2, h3, h4 { color: #ed1c24 !important; font-family: 'Arial Black', sans-serif; }
    .block-container { padding-top: 2rem; }
    [data-testid="stSidebar"] { border-right: 4px solid #ed1c24; background-color: #f8f9fa; }
    .sidebar-title { color: #000000 !important; font-family: 'Arial Black', sans-serif; font-size: 24px; margin-top: -20px; margin-bottom: 20px; }
    .score-box { background-color: #ffffff; border: 2px solid #ed1c24; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 25px; margin-top: 10px; }
    .score-text { font-size: 32px; font-weight: bold; color: #000000; margin: 0; }
    .score-label { margin: 0; font-size: 14px; color: gray; text-transform: uppercase; letter-spacing: 2px; }
    </style>
""", unsafe_allow_html=True)

# ── RUTAS Y LOGOS ────────────────────────────────────────────────────────────
CARPETA = Path(__file__).parent

RUTA_LOGO_ACTUAL = CARPETA / "logo_river_actual.png"
RUTA_LOGO_RETRO  = CARPETA / "logo_river_retro.png"
RUTA_LOGO_CARP   = CARPETA / "logo_carp.png"

DICCIONARIO_COLORES = {'DEF': '#1f77b4', 'MED': '#2ca02c', 'DEL': '#ed1c24', 'POR': '#ff7f0e'}

# ── DETECCIÓN DE TEMPORADAS DISPONIBLES ──────────────────────────────────────
archivos_disponibles = list(CARPETA.glob("Base_Datos_River_*.xlsx"))

temporadas_dict = {}
for archivo in archivos_disponibles:
    match = re.search(r"Base_Datos_River_(\d{4})\.xlsx", archivo.name)
    if match:
        anio = match.group(1)
        temporadas_dict[anio] = archivo

anios_disponibles = sorted(list(temporadas_dict.keys()), reverse=True)

# ── CARGA Y EXTRACCIÓN DE DATOS ──────────────────────────────────────────────
@st.cache_data
def cargar_datos_completos(ruta_excel):
    if not ruta_excel.exists():
        return pd.DataFrame(), f"❌ No se encontró el archivo Excel en: {ruta_excel.name}"
    try:
        xl = pd.ExcelFile(ruta_excel)
        partes = []
        hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"]
        for hoja in xl.sheet_names:
            if hoja in hojas_omitir: continue
            df = pd.read_excel(ruta_excel, sheet_name=hoja)
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
                df['Partido'] = hoja 
                partes.append(df)
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(), "OK"
    except Exception as e:
        return pd.DataFrame(), f"Error al cargar {ruta_excel.name}: {str(e)}"

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
        for r in range(min(120, len(df))):
            for c in range(min(15, len(df.columns))):
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
    except: return pd.DataFrame()

@st.cache_data
def extraer_info_partido(ruta_excel_str, nombre_hoja):
    try:
        df = pd.read_excel(ruta_excel_str, sheet_name=nombre_hoja, header=None)
        local, rival, g_local, g_rival = "Local", "Rival", "?", "?"
        for r in range(min(120, len(df))):
            for c in range(min(15, len(df.columns))):
                val = str(df.iloc[r, c]).strip().lower()
                if val in ['métrica', 'metrica']:
                    local, rival = str(df.iloc[r, c+1]).strip(), str(df.iloc[r, c+2]).strip()
                if val == 'resultado':
                    g_local, g_rival = str(df.iloc[r, c+1]).strip(), str(df.iloc[r, c+2]).strip()
                    return local, rival, g_local, g_rival
        return local, rival, g_local, g_rival
    except: return "Local", "Rival", "?", "?"

def mostrar_marcador(ruta_excel, hoja_excel):
    local, rival, g_local, g_rival = extraer_info_partido(str(ruta_excel), hoja_excel)
    if g_local != "?" and g_rival != "?":
        st.markdown(f'<div class="score-box"><p class="score-label">RESULTADO FINAL</p><p class="score-text">{local} {g_local} - {g_rival} {rival}</p></div>', unsafe_allow_html=True)

# ── BARRA LATERAL ────────────────────────────────────────────────────────────
col_nav1, col_nav2 = st.sidebar.columns([1, 2])
with col_nav1:
    if RUTA_LOGO_ACTUAL.exists(): st.image(str(RUTA_LOGO_ACTUAL), width=70)
with col_nav2:
    st.markdown('<p class="sidebar-title">Data<br>CARP</p>', unsafe_allow_html=True)

st.sidebar.markdown("---")
if not anios_disponibles:
    st.sidebar.error("❌ No se encontraron archivos de Base de Datos."); st.stop()

temporada_sel = st.sidebar.selectbox("🗓️ Seleccioná la Temporada:", anios_disponibles)
EXCEL_ACTUAL = temporadas_dict[temporada_sel]

st.sidebar.markdown("---")
categoria = st.sidebar.radio("Categoría de Análisis:", ["🏆 Por Temporada", "🗓️ Por Fecha", "🛠️ Herramientas"])
st.sidebar.markdown("---")

if categoria == "🏆 Por Temporada":
    menu = st.sidebar.radio("Sección:", ["Resumen General", "Mapas de Rendimiento", "Análisis Individual"])
elif categoria == "🗓️ Por Fecha":
    menu = st.sidebar.radio("Sección:", ["Estadísticas de Equipo", "Estadísticas Individuales", "Parado Táctico", "Mapa de Tiros"])
else:
    menu = st.sidebar.radio("Sección:", ["Cara a Cara"])

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
col_bot1, col_bot2 = st.sidebar.columns(2)
with col_bot1:
    if RUTA_LOGO_RETRO.exists(): st.image(str(RUTA_LOGO_RETRO), width=80)
with col_bot2:
    if RUTA_LOGO_CARP.exists(): st.image(str(RUTA_LOGO_CARP), width=80)

# ── PROCESAMIENTO DE DATOS ───────────────────────────────────────────────────
df_raw, estado = cargar_datos_completos(EXCEL_ACTUAL)
if estado != "OK": st.error(estado); st.stop()

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
df_forma = df_raw.groupby('Jugador')['Nota SofaScore'].apply(lambda x: " | ".join([f"{n:.1f}" for n in list(x)[-5:]])).reset_index(name='Forma (Últ. 5)')
df_agrupado = df_agrupado.merge(df_forma, on='Jugador', how='left')

# ── PÁGINAS: POR TEMPORADA ───────────────────────────────────────────────────
if menu == "Resumen General":
    st.markdown(f"<h1>🐔 Panel General del Equipo - {temporada_sel}</h1>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("📊 Promedios SofaScore")
    df_promedios = df_agrupado[['Jugador', 'Promedio', 'Partidos', 'Forma (Últ. 5)']].sort_values('Promedio', ascending=False).reset_index(drop=True)
    st.dataframe(df_promedios, hide_index=True, use_container_width=True)
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("⚽ Goleadores")
        st.dataframe(df_agrupado[df_agrupado['Goles'] > 0][['Jugador', 'Goles']].sort_values('Goles', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
    with c2:
        st.subheader("👟 Asistidores")
        st.dataframe(df_agrupado[df_agrupado['Asistencias'] > 0][['Jugador', 'Asistencias']].sort_values('Asistencias', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)

elif menu == "Mapas de Rendimiento":
    st.markdown(f"<h1>🗺️ Mapas de Rendimiento - {temporada_sel}</h1>", unsafe_allow_html=True)
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
        st.subheader(f"📈 Evolución de Notas: {jugador_sel}")
        fig_l = px.bar(df_j, x="Partido", y="Nota SofaScore", text="Nota SofaScore")
        fig_l.update_traces(marker_color="#ed1c24", textposition="outside", textfont_size=12, texttemplate='%{text:.1f}')
        fig_l.add_hline(y=df_j['Nota SofaScore'].mean(), line_dash="dot", annotation_text="Promedio", line_color="black")
        fig_l.update_layout(yaxis_range=[0, 11]); st.plotly_chart(fig_l, use_container_width=True)
        st.divider()
        c_radar, c_metrics = st.columns([1.5, 1])
        with c_radar:
            st.markdown("#### 🛡️ Perfil Táctico Relativo al Plantel")
            metrics_radar = ['Goles', 'Asistencias', 'Pases Clave', 'Quites (Tackles)', 'Intercepciones']
            labels_radar = ['Goles', 'Asistencias', 'Pases Clave', 'Quites', 'Intercep.']
            totales_jugador = [df_j[m].sum() if m in df_j.columns else 0 for m in metrics_radar]
            maximos_equipo = [df_raw.groupby('Jugador')[m].sum().max() for m in metrics_radar]
            valores_norm = [(v / m * 100) if m > 0 else 0 for v, m in zip(totales_jugador, maximos_equipo)]
            fig_radar = go.Figure(data=go.Scatterpolar(r=valores_norm + [valores_norm[0]], theta=labels_radar + [labels_radar[0]], fill='toself', fillcolor='rgba(237,28,36,0.3)', line=dict(color='#ed1c24', width=3), marker=dict(color='#ed1c24', size=8)))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="LightGray"), angularaxis=dict(gridcolor="LightGray", tickfont=dict(size=12, family="Arial Black"))), showlegend=False, margin=dict(l=40, r=40, t=20, b=20))
            st.plotly_chart(fig_radar, use_container_width=True)
        with c_metrics:
            st.markdown(f"#### 📋 Datos Temporada {temporada_sel}")
            st.metric("Promedio SofaScore", round(df_j['Nota SofaScore'].mean(), 2))
            st.metric("Minutos Jugados", int(df_j['Minutos'].sum()))
            st.metric("Participaciones en Goles", int(df_j['Goles'].sum() + df_j['Asistencias'].sum()))
            st.metric("Recuperaciones Totales", int(df_j['Quites (Tackles)'].sum() + df_j['Intercepciones'].sum()))

# ── PÁGINAS: POR FECHA ───────────────────────────────────────────────────────
elif menu == "Estadísticas de Equipo":
    st.markdown("<h1>⚖️ Estadísticas de Equipo</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Seleccioná la fecha:", list(hojas.keys()))
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    df_equipo = extraer_estadisticas_equipo(str(EXCEL_ACTUAL), hojas[partido])
    st.divider()
    if not df_equipo.empty: st.dataframe(df_equipo, hide_index=True, use_container_width=True)

elif menu == "Estadísticas Individuales":
    st.markdown("<h1>👤 Estadísticas Individuales</h1>", unsafe_allow_html=True)
    def extraer_exitosos(valor):
        try: return int(valor.replace("'", "").split('/')[0]) if isinstance(valor, str) else int(valor)
        except: return 0
    partido_sel = st.selectbox("Seleccioná la fecha:", df_raw['Partido'].unique())
    hoja_orig = df_raw[df_raw['Partido'] == partido_sel]['Hoja_Original'].iloc[0]
    mostrar_marcador(EXCEL_ACTUAL, hoja_orig)
    df_p = df_raw[df_raw['Partido'] == partido_sel].copy()
    if 'Pases (Comp/Tot)' in df_p.columns: df_p['Pases Completados'] = df_p['Pases (Comp/Tot)'].apply(extraer_exitosos)
    if 'Quites (Tackles)' in df_p.columns: df_p = df_p.rename(columns={'Quites (Tackles)': 'Quites'})
    st.divider(); st.subheader(f"🏆 Top 7 - {partido_sel}")
    st.markdown("### ⭐ Nota SofaScore"); st.dataframe(df_p.nlargest(7, 'Nota SofaScore')[['Jugador', 'Nota SofaScore']], hide_index=True, use_container_width=True)
    st.markdown("### 🛡️ Quites"); st.dataframe(df_p.nlargest(7, 'Quites')[['Jugador', 'Quites']], hide_index=True, use_container_width=True)

elif menu == "Parado Táctico":
    st.markdown("<h1>📋 Parado Táctico</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    img = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 0)
    if img: st.image(img, use_container_width=True)

elif menu == "Mapa de Tiros":
    st.markdown("<h1>🎯 Mapa de Tiros</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    img_r = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 1)
    if img_r: st.image(img_r, use_container_width=True)
    st.divider()
    img_v = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 2)
    if img_v: st.image(img_v, use_container_width=True)

# ── NUEVA SECCIÓN: HERRAMIENTAS - CARA A CARA ────────────────────────────────
elif menu == "Cara a Cara":
    st.markdown("<h1>⚔️ Comparador de Jugadores (P90)</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        t_a = st.selectbox("Temporada A:", anios_disponibles, key="ta")
        df_a, _ = cargar_datos_completos(temporadas_dict[t_a])
        j_a = st.selectbox("Jugador A:", sorted(df_a['Jugador'].unique()), key="ja")
    with c2:
        t_b = st.selectbox("Temporada B:", anios_disponibles, key="tb")
        df_b, _ = cargar_datos_completos(temporadas_dict[t_b])
        j_b = st.selectbox("Jugador B:", sorted(df_b['Jugador'].unique()), key="jb")

    if j_a and j_b:
        def get_p90(df, name):
            d = df[df['Jugador'] == name]
            m = d['Minutos'].sum()
            if m == 0: return None
            return {'Mins': m, 'Nota': d['Nota SofaScore'].mean(), 'Goles': (d['Goles'].sum()/m)*90, 'Asist': (d['Asistencias'].sum()/m)*90, 'KP': (d['Pases Clave'].sum()/m)*90, 'Quites': (d['Quites (Tackles)'].sum()/m)*90, 'Inter': (d['Intercepciones'].sum()/m)*90}
        
        s_a, s_b = get_p90(df_a, j_a), get_p90(df_b, j_b)
        if s_a and s_b:
            st.divider(); cr1, cr2 = st.columns(2)
            mets = ['Goles', 'Asist', 'KP', 'Quites', 'Inter']
            for col, jug, stat, color in zip([cr1, cr2], [j_a, j_b], [s_a, s_b], ['#ed1c24', '#333333']):
                with col:
                    st.subheader(jug)
                    r_v = [stat[m] for m in mets]
                    fig = go.Figure(data=go.Scatterpolar(r=r_v + [r_v[0]], theta=mets + [mets[0]], fill='toself', fillcolor=color, opacity=0.3, line_color=color))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True)), height=350); st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### 📊 Duelo Estadístico P90")
            df_comp = pd.DataFrame({"Métrica": ["Minutos", "Nota", "Goles", "Asistencias", "Pases Clave", "Quites", "Intercep."], j_a: [int(s_a['Mins']), round(s_a['Nota'], 2), round(s_a['Goles'], 2), round(s_a['Asist'], 2), round(s_a['KP'], 2), round(s_a['Quites'], 2), round(s_a['Inter'], 2)], j_b: [int(s_b['Mins']), round(s_b['Nota'], 2), round(s_b['Goles'], 2), round(s_b['Asist'], 2), round(s_b['KP'], 2), round(s_b['Quites'], 2), round(s_b['Inter'], 2)]})
            st.table(df_comp)
