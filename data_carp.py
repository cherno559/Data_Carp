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
# Buscamos todos los archivos que coincidan con el patrón Base_Datos_River_XXXX.xlsx
archivos_disponibles = list(CARPETA.glob("Base_Datos_River_*.xlsx"))

temporadas_dict = {}
for archivo in archivos_disponibles:
    match = re.search(r"Base_Datos_River_(\d{4})\.xlsx", archivo.name)
    if match:
        anio = match.group(1)
        temporadas_dict[anio] = archivo

# Ordenamos los años de mayor a menor (Ej: 2026, 2025...)
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
                # Ya no limpiamos el "Base_Datos_River..." porque las hojas se llaman directo como el partido
                df['Partido'] = hoja 
                partes.append(df)
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(), "OK"
    except Exception as e:
        return pd.DataFrame(), f"Error al cargar {ruta_excel.name}: {str(e)}"

@st.cache_data
def cargar_todas_las_temporadas():
    """Carga y agrega datos de todas las temporadas disponibles"""
    todos_datos = []
    for anio, ruta in temporadas_dict.items():
        df, estado = cargar_datos_completos(ruta)
        if estado == "OK" and not df.empty:
            df['Temporada'] = anio
            todos_datos.append(df)
    
    if todos_datos:
        df_completo = pd.concat(todos_datos, ignore_index=True)
        if 'Efectividad Pases' in df_completo.columns:
            df_completo['Efectividad Pases'] = df_completo['Efectividad Pases'].replace(0, np.nan)
        return df_completo
    return pd.DataFrame()

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
    except:
        return pd.DataFrame()

@st.cache_data
def extraer_info_partido(ruta_excel_str, nombre_hoja):
    """Extrae el marcador del Excel."""
    try:
        df = pd.read_excel(ruta_excel_str, sheet_name=nombre_hoja, header=None)
        local, rival = "Local", "Rival"
        g_local, g_rival = "?", "?"
        
        for r in range(min(120, len(df))):
            for c in range(min(15, len(df.columns))):
                val = str(df.iloc[r, c]).strip().lower()
                if val in ['métrica', 'metrica']:
                    local = str(df.iloc[r, c+1]).strip()
                    rival = str(df.iloc[r, c+2]).strip()
                if val == 'resultado':
                    g_local = str(df.iloc[r, c+1]).strip()
                    g_rival = str(df.iloc[r, c+2]).strip()
                    return local, rival, g_local, g_rival
        return local, rival, g_local, g_rival
    except:
        return "Local", "Rival", "?", "?"

def mostrar_marcador(ruta_excel, hoja_excel):
    """Dibuja el cartel del resultado en la app."""
    local, rival, g_local, g_rival = extraer_info_partido(str(ruta_excel), hoja_excel)
    if g_local != "?" and g_rival != "?":
        st.markdown(f"""
            <div class="score-box">
                <p class="score-label">RESULTADO FINAL</p>
                <p class="score-text">{local} {g_local} - {g_rival} {rival}</p>
            </div>
        """, unsafe_allow_html=True)

# ── BARRA LATERAL ────────────────────────────────────────────────────────────
col_nav1, col_nav2 = st.sidebar.columns([1, 2])
with col_nav1:
    if RUTA_LOGO_ACTUAL.exists(): st.image(str(RUTA_LOGO_ACTUAL), width=70)
with col_nav2:
    st.markdown('<p class="sidebar-title">Data<br>CARP</p>', unsafe_allow_html=True)

st.sidebar.markdown("---")

if not anios_disponibles:
    st.sidebar.error("❌ No se encontraron archivos de Base de Datos.")
    st.stop()

temporada_sel = st.sidebar.selectbox("🗓️ Seleccioná la Temporada:", anios_disponibles)
EXCEL_ACTUAL = temporadas_dict[temporada_sel]

st.sidebar.markdown("---")

categoria = st.sidebar.radio("Categoría de Análisis:", ["🏆 Por Temporada", "🗓️ Por Fecha", "🔧 Herramientas"])
st.sidebar.markdown("---")

if categoria == "🏆 Por Temporada":
    menu = st.sidebar.radio("Sección:", ["Resumen General", "Mapas de Rendimiento", "Análisis Individual"])
elif categoria == "🗓️ Por Fecha":
    menu = st.sidebar.radio("Sección:", ["Estadísticas de Equipo", "Estadísticas Individuales", "Parado Táctico", "Mapa de Tiros"])
else:  # Herramientas
    menu = st.sidebar.radio("Sección:", ["Cara a Cara"])

st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
col_bot1, col_bot2 = st.sidebar.columns(2)
with col_bot1:
    if RUTA_LOGO_RETRO.exists(): st.image(str(RUTA_LOGO_RETRO), width=80)
with col_bot2:
    if RUTA_LOGO_CARP.exists(): st.image(str(RUTA_LOGO_CARP), width=80)

# ── PROCESAMIENTO DE DATOS ───────────────────────────────────────────────────
# Cargamos los datos del Excel seleccionado
df_raw, estado = cargar_datos_completos(EXCEL_ACTUAL)
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

# ESTADO DE FORMA
df_forma = df_raw.groupby('Jugador')['Nota SofaScore'].apply(
    lambda x: " | ".join([f"{n:.1f}" for n in list(x)[-5:]])
).reset_index(name='Forma (Últ. 5)')

df_agrupado = df_agrupado.merge(df_forma, on='Jugador', how='left')

# ── PÁGINAS: POR TEMPORADA ───────────────────────────────────────────────────

if menu == "Resumen General":
    st.markdown(f"<h1>🐔 Panel General del Equipo - {temporada_sel}</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.subheader("📊 Promedios SofaScore")
    df_promedios = df_agrupado[['Jugador', 'Promedio', 'Partidos', 'Forma (Últ. 5)']].sort_values('Promedio', ascending=False).reset_index(drop=True)
    
    st.dataframe(
        df_promedios,
        hide_index=True, 
        use_container_width=True
    )
    
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
        fig_l.update_traces(
            marker_color="#ed1c24", 
            textposition="outside", 
            textfont_size=12,
            texttemplate='%{text:.1f}'
        )
        fig_l.add_hline(y=df_j['Nota SofaScore'].mean(), line_dash="dot", annotation_text="Promedio", line_color="black")
        fig_l.update_layout(yaxis_range=[0, 11])
        st.plotly_chart(fig_l, use_container_width=True)
        
        st.divider()
        
        c_radar, c_metrics = st.columns([1.5, 1])
        with c_radar:
            st.markdown("#### 🛡️ Perfil Táctico Relativo al Plantel")
            st.write("*(El borde exterior representa el máximo alcanzado por un jugador del equipo en esa métrica)*")
            
            metrics_radar = ['Goles', 'Asistencias', 'Pases Clave', 'Quites (Tackles)', 'Intercepciones']
            labels_radar = ['Goles', 'Asistencias', 'Pases Clave', 'Quites', 'Intercep.']
            
            totales_jugador = [df_j[m].sum() if m in df_j.columns else 0 for m in metrics_radar]
            df_squad_totals = df_raw.groupby('Jugador')[metrics_radar].sum()
            maximos_equipo = [df_squad_totals[m].max() if m in df_squad_totals.columns else 0 for m in metrics_radar]
            
            valores_norm = [(v / m * 100) if m > 0 else 0 for v, m in zip(totales_jugador, maximos_equipo)]
            
            fig_radar = go.Figure(data=go.Scatterpolar(
                r=valores_norm + [valores_norm[0]],
                theta=labels_radar + [labels_radar[0]],
                fill='toself',
                fillcolor='rgba(237,28,36,0.3)',
                line=dict(color='#ed1c24', width=3),
                marker=dict(color='#ed1c24', size=8),
                hoverinfo='text',
                text=[f"{labels_radar[i]}: {totales_jugador[i]}" for i in range(len(labels_radar))] + [f"{labels_radar[0]}: {totales_jugador[0]}"]
            ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="LightGray"),
                    angularaxis=dict(gridcolor="LightGray", tickfont=dict(size=12, family="Arial Black"))
                ),
                showlegend=False,
                margin=dict(l=40, r=40, t=20, b=20)
            )
            st.plotly_chart(fig_radar, use_container_width=True)
            
        with c_metrics:
            st.markdown(f"#### 📋 Datos Temporada {temporada_sel}")
            st.metric("Promedio SofaScore", round(df_j['Nota SofaScore'].mean(), 2))
            st.metric("Minutos Jugados", int(df_j['Minutos'].sum()))
            st.metric("Participaciones en Goles", int(df_j['Goles'].sum() + df_j['Asistencias'].sum()))
            quites_totales = int(df_j['Quites (Tackles)'].sum() + df_j['Intercepciones'].sum()) if 'Quites (Tackles)' in df_j.columns else 0
            st.metric("Recuperaciones Totales", quites_totales)

# ── PÁGINAS: POR FECHA ───────────────────────────────────────────────────────

elif menu == "Estadísticas de Equipo":
    st.markdown("<h1>⚖️ Estadísticas de Equipo</h1>", unsafe_allow_html=True)
    st.markdown("Comparativa general del rendimiento colectivo frente al rival.")
    
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Seleccioná la fecha:", list(hojas.keys()))
    
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    
    df_equipo = extraer_estadisticas_equipo(str(EXCEL_ACTUAL), hojas[partido])
    
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
    
    hoja_original = df_raw[df_raw['Partido'] == partido_seleccionado]['Hoja_Original'].iloc[0]
    mostrar_marcador(EXCEL_ACTUAL, hoja_original)
    
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
    
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    
    img = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 0)
    if img: st.image(img, use_container_width=True)
    else: st.warning("Imagen no encontrada.")

elif menu == "Mapa de Tiros":
    st.markdown("<h1>🎯 Mapa de Tiros</h1>", unsafe_allow_html=True)
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])
    
    # 1. Mapa de Tiros de River (Índice 1 en el Excel)
    img_river = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 1)
    if img_river: 
        st.image(img_river, use_container_width=True)
    else: 
        st.warning("Mapa de tiros de River Plate no encontrado.")
        
    st.divider() # Línea separadora
        
    # 2. Mapa de Tiros del Rival (Índice 2 en el Excel)
    img_rival = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 2)
    if img_rival: 
        st.image(img_rival, use_container_width=True)
    else: 
        st.warning("Mapa de tiros del rival no encontrado.")

# ── PÁGINAS: HERRAMIENTAS ────────────────────────────────────────────────────

elif menu == "Cara a Cara":
    st.markdown("<h1>⚔️ Comparación Cara a Cara</h1>", unsafe_allow_html=True)
    st.markdown("Compará el rendimiento de dos jugadores de distintas temporadas")
    
    # Cargar datos de todas las temporadas
    df_todas_temporadas = cargar_todas_las_temporadas()
    
    if df_todas_temporadas.empty:
        st.error("No se pudieron cargar los datos de las temporadas")
        st.stop()
    
    # Agrupar datos por jugador y temporada
    df_comparacion = df_todas_temporadas.groupby(['Jugador', 'Temporada', 'Posición'], as_index=False).agg(
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
    
    st.markdown("---")
    
    # Selectores para jugadores
    col_j1, col_j2 = st.columns(2)
    
    with col_j1:
        st.markdown("### 🔴 Jugador 1")
        temp1 = st.selectbox("Temporada:", anios_disponibles, key="temp1")
        jugadores_temp1 = sorted(df_comparacion[df_comparacion['Temporada'] == temp1]['Jugador'].unique())
        jugador1 = st.selectbox("Jugador:", jugadores_temp1, key="jug1")
        
    with col_j2:
        st.markdown("### ⚪ Jugador 2")
        temp2 = st.selectbox("Temporada:", anios_disponibles, key="temp2")
        jugadores_temp2 = sorted(df_comparacion[df_comparacion['Temporada'] == temp2]['Jugador'].unique())
        jugador2 = st.selectbox("Jugador:", jugadores_temp2, key="jug2")
    
    if jugador1 and jugador2:
        # Obtener datos de cada jugador
        datos_j1 = df_comparacion[(df_comparacion['Jugador'] == jugador1) & 
                                   (df_comparacion['Temporada'] == temp1)].iloc[0]
        datos_j2 = df_comparacion[(df_comparacion['Jugador'] == jugador2) & 
                                   (df_comparacion['Temporada'] == temp2)].iloc[0]
        
        st.markdown("---")
        
        # Métricas generales comparativas
        st.subheader("📊 Comparación de Estadísticas Generales")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            st.markdown(f"**Promedio SofaScore**")
            st.metric(
                label=f"{jugador1} ({temp1})",
                value=f"{datos_j1['Promedio']:.2f}"
            )
            st.metric(
                label=f"{jugador2} ({temp2})",
                value=f"{datos_j2['Promedio']:.2f}",
                delta=f"{datos_j2['Promedio'] - datos_j1['Promedio']:.2f}"
            )
        
        with col_m2:
            st.markdown(f"**Partidos**")
            st.metric(
                label=f"{jugador1}",
                value=int(datos_j1['Partidos'])
            )
            st.metric(
                label=f"{jugador2}",
                value=int(datos_j2['Partidos']),
                delta=int(datos_j2['Partidos'] - datos_j1['Partidos'])
            )
        
        with col_m3:
            st.markdown(f"**Goles**")
            st.metric(
                label=f"{jugador1}",
                value=int(datos_j1['Goles'])
            )
            st.metric(
                label=f"{jugador2}",
                value=int(datos_j2['Goles']),
                delta=int(datos_j2['Goles'] - datos_j1['Goles'])
            )
        
        with col_m4:
            st.markdown(f"**Asistencias**")
            st.metric(
                label=f"{jugador1}",
                value=int(datos_j1['Asistencias'])
            )
            st.metric(
                label=f"{jugador2}",
                value=int(datos_j2['Asistencias']),
                delta=int(datos_j2['Asistencias'] - datos_j1['Asistencias'])
            )
        
        st.markdown("---")
        
        # Gráficos de radar comparativos
        st.subheader("🛡️ Comparación de Perfiles Tácticos")
        
        metrics_radar = ['Goles', 'Asistencias', 'Pases_Clave', 'Quites', 'Intercepciones']
        labels_radar = ['Goles', 'Asistencias', 'Pases Clave', 'Quites', 'Intercep.']
        
        # Valores de cada jugador
        valores_j1 = [float(datos_j1[m]) for m in metrics_radar]
        valores_j2 = [float(datos_j2[m]) for m in metrics_radar]
        
        # Máximos globales para normalización
        maximos_globales = [float(df_comparacion[m].max()) for m in metrics_radar]
        
        # Normalizar a escala 0-100
        valores_j1_norm = [(v / m * 100) if m > 0 else 0 for v, m in zip(valores_j1, maximos_globales)]
        valores_j2_norm = [(v / m * 100) if m > 0 else 0 for v, m in zip(valores_j2, maximos_globales)]
        
        # Crear gráfico de radar comparativo
        fig_radar_comparativo = go.Figure()
        
        # Jugador 1 (rojo)
        fig_radar_comparativo.add_trace(go.Scatterpolar(
            r=valores_j1_norm + [valores_j1_norm[0]],
            theta=labels_radar + [labels_radar[0]],
            fill='toself',
            fillcolor='rgba(237,28,36,0.3)',
            line=dict(color='#ed1c24', width=3),
            marker=dict(color='#ed1c24', size=8),
            name=f"{jugador1} ({temp1})",
            hoverinfo='text',
            text=[f"{labels_radar[i]}: {int(valores_j1[i])}" for i in range(len(labels_radar))] + 
                 [f"{labels_radar[0]}: {int(valores_j1[0])}"]
        ))
        
        # Jugador 2 (blanco/gris)
        fig_radar_comparativo.add_trace(go.Scatterpolar(
            r=valores_j2_norm + [valores_j2_norm[0]],
            theta=labels_radar + [labels_radar[0]],
            fill='toself',
            fillcolor='rgba(128,128,128,0.2)',
            line=dict(color='#808080', width=3),
            marker=dict(color='#808080', size=8),
            name=f"{jugador2} ({temp2})",
            hoverinfo='text',
            text=[f"{labels_radar[i]}: {int(valores_j2[i])}" for i in range(len(labels_radar))] + 
                 [f"{labels_radar[0]}: {int(valores_j2[0])}"]
        ))
        
        fig_radar_comparativo.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True, 
                    range=[0, 100], 
                    showticklabels=False, 
                    gridcolor="LightGray"
                ),
                angularaxis=dict(
                    gridcolor="LightGray", 
                    tickfont=dict(size=12, family="Arial Black")
                )
            ),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5,
                font=dict(size=14, family="Arial Black")
            ),
            margin=dict(l=80, r=80, t=40, b=80),
            height=600
        )
        
        st.plotly_chart(fig_radar_comparativo, use_container_width=True)
        
        st.markdown("---")
        
        # Tabla comparativa detallada
        st.subheader("📋 Tabla Comparativa Detallada")
        
        datos_tabla = pd.DataFrame({
            'Métrica': ['Promedio SofaScore', 'Partidos', 'Minutos', 'Goles', 'Asistencias', 
                       'Pases Clave', 'Quites', 'Intercepciones', 'Tiros Totales', 'Efect. Pases %'],
            f'{jugador1} ({temp1})': [
                f"{datos_j1['Promedio']:.2f}",
                int(datos_j1['Partidos']),
                int(datos_j1['Minutos']),
                int(datos_j1['Goles']),
                int(datos_j1['Asistencias']),
                int(datos_j1['Pases_Clave']),
                int(datos_j1['Quites']),
                int(datos_j1['Intercepciones']),
                int(datos_j1['Tiros_Totales']),
                f"{datos_j1['Efectividad_Pases']:.1f}"
            ],
            f'{jugador2} ({temp2})': [
                f"{datos_j2['Promedio']:.2f}",
                int(datos_j2['Partidos']),
                int(datos_j2['Minutos']),
                int(datos_j2['Goles']),
                int(datos_j2['Asistencias']),
                int(datos_j2['Pases_Clave']),
                int(datos_j2['Quites']),
                int(datos_j2['Intercepciones']),
                int(datos_j2['Tiros_Totales']),
                f"{datos_j2['Efectividad_Pases']:.1f}"
            ]
        })
        
        st.dataframe(datos_tabla, hide_index=True, use_container_width=True)
