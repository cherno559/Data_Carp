import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from openpyxl import load_workbook
import re

# ── CONFIGURACIÓN DE LA PÁGINA ───────────────────────────────────────────────
st.set_page_config(
    page_title="Data CARP | River Plate Analytics",
    page_icon="🐔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── SISTEMA DE DISEÑO: VARIABLES Y ESTILOS ───────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Rajdhani:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --red-primary:   #D0021B;
    --red-hover:     #A80016;
    --red-light:     rgba(208,2,27,0.08);
    --red-glow:      rgba(208,2,27,0.25);
    --white:         #FFFFFF;
    --gray-50:       #F9FAFB;
    --gray-100:      #F3F4F6;
    --gray-200:      #E5E7EB;
    --gray-400:      #9CA3AF;
    --gray-600:      #4B5563;
    --gray-800:      #1F2937;
    --gray-900:      #111827;
    --black:         #0A0A0A;
    --gold:          #C9A84C;
    --shadow-sm:     0 1px 3px rgba(0,0,0,0.08);
    --shadow-md:     0 4px 12px rgba(0,0,0,0.10);
    --shadow-lg:     0 8px 32px rgba(0,0,0,0.14);
    --radius-sm:     6px;
    --radius-md:     10px;
    --radius-lg:     16px;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.main .block-container { padding: 1.5rem 2rem 3rem 2rem !important; max-width: 1400px; }

[data-testid="stSidebar"] { background: var(--black) !important; border-right: 3px solid var(--red-primary) !important; }
[data-testid="stSidebar"] * { color: var(--gray-200) !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    color: var(--gray-400) !important; font-size: 11px !important;
    text-transform: uppercase !important; letter-spacing: 1.5px !important;
    font-weight: 600 !important; font-family: 'Rajdhani', sans-serif !important;
}
[data-testid="stSidebar"] .stRadio div[role="radio"] p {
    font-family: 'Rajdhani', sans-serif !important; font-weight: 600 !important;
    font-size: 15px !important; color: var(--gray-200) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: #1a1a1a !important; border: 1px solid #333 !important;
    color: var(--white) !important; border-radius: var(--radius-sm) !important;
}
[data-testid="stSidebar"] hr { border-color: #2a2a2a !important; margin: 1rem 0 !important; }

.sidebar-section-label {
    font-family: 'Rajdhani', sans-serif !important; font-size: 10px !important;
    text-transform: uppercase !important; letter-spacing: 2px !important;
    color: #555 !important; font-weight: 700 !important;
    margin-bottom: 6px !important; margin-top: 8px !important;
}

.section-title {
    font-family: 'Bebas Neue', cursive !important; font-size: 26px !important;
    color: var(--gray-800) !important; letter-spacing: 2px !important;
    margin: 0 0 12px 0 !important;
}
.section-title-red { color: var(--red-primary) !important; }

.red-divider {
    height: 3px; background: linear-gradient(90deg, var(--red-primary), transparent);
    border: none; margin: 8px 0 24px 0; border-radius: 2px;
}

.score-card {
    background: linear-gradient(135deg, var(--black) 0%, #1a1a1a 100%);
    border: 1px solid #2a2a2a; border-left: 4px solid var(--red-primary);
    border-radius: var(--radius-md); padding: 20px 28px; text-align: center;
    margin-bottom: 24px; box-shadow: var(--shadow-lg); position: relative; overflow: hidden;
}
.score-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, var(--red-primary), transparent);
}
.score-card .label { font-family: 'Rajdhani', sans-serif; font-size: 11px; color: var(--gray-400);
    text-transform: uppercase; letter-spacing: 3px; font-weight: 700; margin-bottom: 8px; }
.score-card .score { font-family: 'Bebas Neue', cursive; font-size: 52px; color: var(--white);
    line-height: 1; letter-spacing: 4px; }
.score-card .score .goals { color: var(--red-primary); }

[data-testid="stDataFrame"] { border-radius: var(--radius-md) !important; overflow: hidden !important;
    border: 1px solid var(--gray-200) !important; box-shadow: var(--shadow-sm) !important; }
[data-testid="stDataFrame"] table thead tr th {
    background: var(--black) !important; color: var(--white) !important;
    font-family: 'Rajdhani', sans-serif !important; font-size: 12px !important;
    text-transform: uppercase !important; letter-spacing: 1px !important;
    font-weight: 700 !important; padding: 10px 16px !important;
}
[data-testid="stDataFrame"] table tbody tr:nth-child(even) td { background: var(--gray-50) !important; }
[data-testid="stDataFrame"] table tbody tr:hover td { background: var(--red-light) !important; }
[data-testid="stDataFrame"] table tbody tr td {
    font-family: 'Inter', sans-serif !important; font-size: 14px !important;
    padding: 9px 16px !important; color: var(--gray-800) !important;
    border-bottom: 1px solid var(--gray-100) !important;
}

[data-testid="stMetric"] { background: var(--white) !important; border: 1px solid var(--gray-200) !important;
    border-radius: var(--radius-md) !important; padding: 16px !important; box-shadow: var(--shadow-sm) !important; }
[data-testid="stMetricValue"] { font-family: 'Bebas Neue', cursive !important; font-size: 32px !important; color: var(--red-primary) !important; }
[data-testid="stMetricLabel"] { font-family: 'Rajdhani', sans-serif !important; text-transform: uppercase !important;
    letter-spacing: 1px !important; font-size: 11px !important; font-weight: 700 !important; color: var(--gray-400) !important; }
[data-testid="stMetricDelta"] { font-family: 'Rajdhani', sans-serif !important; font-weight: 700 !important; }

.info-box {
    background: var(--red-light); border-left: 3px solid var(--red-primary);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 10px 16px;
    margin-bottom: 16px; font-family: 'Rajdhani', sans-serif; font-size: 13px;
    color: var(--gray-600); font-weight: 500;
}

.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 2px solid var(--gray-200) !important; }
.stTabs [data-baseweb="tab"] {
    font-family: 'Rajdhani', sans-serif !important; font-weight: 700 !important;
    font-size: 14px !important; text-transform: uppercase !important; letter-spacing: 1px !important;
    color: var(--gray-400) !important; border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    padding: 10px 20px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--red-primary) !important; border-bottom: 3px solid var(--red-primary) !important;
    background: var(--red-light) !important;
}

.player-header { display: flex; align-items: center; gap: 10px; padding: 14px 20px;
    border-radius: var(--radius-md); margin-bottom: 16px; font-family: 'Bebas Neue', cursive;
    font-size: 22px; letter-spacing: 2px; }
.player-header-red  { background: linear-gradient(135deg, var(--red-primary), #ff2d3a); color: white; }
.player-header-gray { background: linear-gradient(135deg, #374151, #6b7280); color: white; }

.footer { text-align: center; padding: 24px 0 8px 0; font-family: 'Rajdhani', sans-serif;
    font-size: 12px; color: var(--gray-400); letter-spacing: 1px; text-transform: uppercase;
    border-top: 1px solid var(--gray-200); margin-top: 48px; }

/* Selector horizontal customizado */
div.row-widget.stRadio > div {
    flex-direction: row;
    gap: 20px;
    background: var(--gray-50);
    padding: 10px 15px;
    border-radius: var(--radius-md);
    border: 1px solid var(--gray-200);
}
</style>
""", unsafe_allow_html=True)

# ── PALETA Y CONSTANTES ───────────────────────────────────────────────────────
COLORES_POSICION = {
    'DEF': '#3B82F6',
    'MED': '#22C55E',
    'DEL': '#EF4444',
    'POR': '#F59E0B'
}

PLOTLY_LAYOUT = dict(
    font=dict(family="Rajdhani, Inter, sans-serif", size=13, color="#1F2937"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(249,250,251,1)",
    margin=dict(l=16, r=16, t=40, b=16),
    title_font=dict(family="Bebas Neue, cursive", size=22, color="#1F2937"),
    legend=dict(
        bgcolor="rgba(255,255,255,0.9)", bordercolor="#E5E7EB", borderwidth=1,
        font=dict(family="Rajdhani", size=12),
    ),
    hoverlabel=dict(
        bgcolor="#111827", bordercolor="#D0021B", font_color="white",
        font_family="Rajdhani", font_size=13,
    ),
)

def apply_plotly_style(fig, title="", xaxis_title="", yaxis_title=""):
    fig.update_layout(
        **PLOTLY_LAYOUT, title=title,
        xaxis=dict(title=xaxis_title, gridcolor="#E5E7EB", linecolor="#E5E7EB",
                   zeroline=True, zerolinecolor="#D1D5DB", zerolinewidth=1,
                   title_font=dict(family="Rajdhani", size=12, color="#6B7280")),
        yaxis=dict(title=yaxis_title, gridcolor="#E5E7EB", linecolor="#E5E7EB",
                   zeroline=True, zerolinecolor="#D1D5DB", zerolinewidth=1,
                   title_font=dict(family="Rajdhani", size=12, color="#6B7280")),
    )
    return fig

# ── RUTAS Y LOGOS ─────────────────────────────────────────────────────────────
CARPETA = Path(__file__).parent
RUTA_LOGO_ACTUAL = CARPETA / "logo_river_actual.png"
RUTA_LOGO_RETRO  = CARPETA / "logo_river_retro.png"
RUTA_LOGO_CARP   = CARPETA / "logo_carp.png"

# ── DETECCIÓN DE TEMPORADAS ───────────────────────────────────────────────────
archivos_disponibles = list(CARPETA.glob("Base_Datos_River_*.xlsx"))
temporadas_dict = {}
for archivo in archivos_disponibles:
    match = re.search(r"Base_Datos_River_(\d{4})\.xlsx", archivo.name)
    if match:
        temporadas_dict[match.group(1)] = archivo

anios_disponibles = sorted(list(temporadas_dict.keys()), reverse=True)

# ── CARGA DE DATOS ────────────────────────────────────────────────────────────
@st.cache_data
def cargar_datos_completos(ruta_excel):
    if not ruta_excel.exists():
        return pd.DataFrame(), f"❌ No se encontró el archivo: {ruta_excel.name}"
    try:
        xl = pd.ExcelFile(ruta_excel)
        partes = []
        hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"]
        for hoja in xl.sheet_names:
            if hoja in hojas_omitir:
                continue
            df = pd.read_excel(ruta_excel, sheet_name=hoja)
            df.columns = df.columns.astype(str).str.strip()
            if 'Jugador' not in df.columns or 'Nota SofaScore' not in df.columns:
                continue
            df['Jugador'] = df['Jugador'].astype(str).str.strip()
            df['Nota SofaScore'] = pd.to_numeric(df['Nota SofaScore'], errors="coerce")
            df = df.dropna(subset=['Jugador', 'Nota SofaScore'])
            df = df[(df['Jugador'] != "") & (df['Nota SofaScore'] > 0)]
            cols_num = ['Minutos', 'Goles', 'Asistencias', 'Pases Clave',
                        'Quites (Tackles)', 'Intercepciones', 'Tiros Totales', 'Efectividad Pases']
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
def extraer_estadisticas_equipo(ruta_excel_str, nombre_hoja):
    try:
        df = pd.read_excel(ruta_excel_str, sheet_name=nombre_hoja, header=None)
        row_idx, col_idx = None, None
        for r in range(min(120, len(df))):
            for c in range(min(15, len(df.columns))):
                val = str(df.iloc[r, c]).strip().lower()
                if val in ['métrica', 'metrica']:
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
def extraer_imagen_incrustada(ruta_excel_str, nombre_hoja, indice_imagen=0):
    try:
        wb = load_workbook(ruta_excel_str, data_only=True)
        if nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            if hasattr(ws, '_images') and len(ws._images) > indice_imagen:
                img = ws._images[indice_imagen]
                return img._data() if callable(img._data) else img._data
        return None
    except:
        return None

@st.cache_data
def extraer_info_partido(ruta_excel_str, nombre_hoja):
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

@st.cache_data
def generar_historial_rivales(ruta_excel_str, hojas, condicion="Total"):
    historial = {}
    for hoja in hojas:
        local, rival, g_local, g_rival = extraer_info_partido(ruta_excel_str, hoja)
        if g_local == "?" or g_rival == "?": continue

        # Filtro de localía
        is_river_local = 'River' in local
        if condicion == "Local" and not is_river_local: continue
        if condicion == "Visitante" and is_river_local: continue

        def clean_goals(g_str):
            m = re.match(r'^(\d+)', str(g_str).strip())
            return int(m.group(1)) if m else 0

        gl = clean_goals(g_local)
        gv = clean_goals(g_rival)

        if is_river_local:
            equipo_rival = rival
            gf, gc = gl, gv
        else:
            equipo_rival = local
            gf, gc = gv, gl

        if equipo_rival not in historial:
            historial[equipo_rival] = {'PJ': 0, 'PG': 0, 'PE': 0, 'PP': 0, 'GF': 0, 'GC': 0}

        historial[equipo_rival]['PJ'] += 1
        historial[equipo_rival]['GF'] += gf
        historial[equipo_rival]['GC'] += gc

        if gf > gc:   historial[equipo_rival]['PG'] += 1
        elif gf < gc: historial[equipo_rival]['PP'] += 1
        else:         historial[equipo_rival]['PE'] += 1

    df_hist = pd.DataFrame.from_dict(historial, orient='index').reset_index()
    if not df_hist.empty:
        df_hist.rename(columns={'index': 'Rival'}, inplace=True)
        df_hist['DIF'] = df_hist['GF'] - df_hist['GC']
        df_hist = df_hist.sort_values(by=['PJ', 'PG', 'DIF'], ascending=[False, False, False])
    return df_hist

@st.cache_data
def generar_historial_completo(condicion="Total"):
    historial = {}
    for anio, ruta in temporadas_dict.items():
        try:
            xl = pd.ExcelFile(ruta)
            hojas_omitir = ["Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"]
            hojas_validas = [h for h in xl.sheet_names if h not in hojas_omitir]
            for hoja in hojas_validas:
                local, rival, g_local, g_rival = extraer_info_partido(str(ruta), hoja)
                if g_local == "?" or g_rival == "?": continue

                is_river_local = 'River' in local
                if condicion == "Local" and not is_river_local: continue
                if condicion == "Visitante" and is_river_local: continue

                def clean_goals(g_str):
                    m = re.match(r'^(\d+)', str(g_str).strip())
                    return int(m.group(1)) if m else 0

                gl = clean_goals(g_local)
                gv = clean_goals(g_rival)

                if is_river_local:
                    equipo_rival = rival
                    gf, gc = gl, gv
                else:
                    equipo_rival = local
                    gf, gc = gv, gl

                if equipo_rival not in historial:
                    historial[equipo_rival] = {'PJ': 0, 'PG': 0, 'PE': 0, 'PP': 0, 'GF': 0, 'GC': 0}

                historial[equipo_rival]['PJ'] += 1
                historial[equipo_rival]['GF'] += gf
                historial[equipo_rival]['GC'] += gc

                if gf > gc:   historial[equipo_rival]['PG'] += 1
                elif gf < gc: historial[equipo_rival]['PP'] += 1
                else:         historial[equipo_rival]['PE'] += 1
        except Exception:
            continue

    df_hist = pd.DataFrame.from_dict(historial, orient='index').reset_index()
    if not df_hist.empty:
        df_hist.rename(columns={'index': 'Rival'}, inplace=True)
        df_hist['DIF'] = df_hist['GF'] - df_hist['GC']
        df_hist = df_hist.sort_values(by=['PJ', 'PG', 'DIF'], ascending=[False, False, False])
    return df_hist

def mostrar_marcador(ruta_excel, hoja_excel):
    local, rival, g_local, g_rival = extraer_info_partido(str(ruta_excel), hoja_excel)
    if g_local != "?" and g_rival != "?":
        st.markdown(f"""
        <div class="score-card">
            <div class="label">Resultado Final</div>
            <div class="score">{local} <span class="goals">{g_local} – {g_rival}</span> {rival}</div>
        </div>
        """, unsafe_allow_html=True)

def page_header(icon, title, subtitle=""):
    st.markdown(f"""
    <div style="margin-bottom:4px;">
        <div style="font-family:'Bebas Neue',cursive;font-size:42px;color:#111827;letter-spacing:3px;line-height:1;">
            <span style="color:#D0021B;">{icon}</span> {title}
        </div>
        {"<div style='font-family:Rajdhani,sans-serif;font-size:12px;color:#9CA3AF;text-transform:uppercase;letter-spacing:2px;font-weight:600;margin-top:2px;'>" + subtitle + "</div>" if subtitle else ""}
    </div>
    <div class="red-divider"></div>
    """, unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    col_logo, col_text = st.columns([1, 2])
    with col_logo:
        if RUTA_LOGO_ACTUAL.exists():
            st.image(str(RUTA_LOGO_ACTUAL), width=64)
    with col_text:
        st.markdown("""
        <div style="padding-top:6px;">
            <div style="font-family:'Bebas Neue',cursive;font-size:30px;color:white;line-height:1;letter-spacing:2px;">DATA CARP</div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:10px;color:#D0021B;letter-spacing:3px;font-weight:700;text-transform:uppercase;">Analytics</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#222;margin:12px 0;'>", unsafe_allow_html=True)

    if not anios_disponibles:
        st.error("❌ No se encontraron archivos de Base de Datos.")
        st.stop()

    st.markdown("<div class='sidebar-section-label'>Temporada</div>", unsafe_allow_html=True)
    temporada_sel = st.selectbox("", anios_disponibles, label_visibility="collapsed")
    EXCEL_ACTUAL = temporadas_dict[temporada_sel]

    st.markdown("<hr style='border-color:#222;margin:12px 0;'>", unsafe_allow_html=True)

    st.markdown("<div class='sidebar-section-label'>Categoría</div>", unsafe_allow_html=True)
    categoria = st.radio("", ["🏆 Por Temporada", "🗓️ Por Fecha", "🔧 Herramientas"], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#222;margin:12px 0;'>", unsafe_allow_html=True)

    if categoria == "🏆 Por Temporada":
        st.markdown("<div class='sidebar-section-label'>Sección</div>", unsafe_allow_html=True)
        menu = st.radio("", ["Resumen General", "Historial", "Mapas de Rendimiento", "Análisis Individual"], label_visibility="collapsed")
    elif categoria == "🗓️ Por Fecha":
        st.markdown("<div class='sidebar-section-label'>Sección</div>", unsafe_allow_html=True)
        menu = st.radio("", ["Estadísticas de Equipo", "Estadísticas Individuales", "Parado Táctico", "Mapa de Tiros"], label_visibility="collapsed")
    else:
        st.markdown("<div class='sidebar-section-label'>Sección</div>", unsafe_allow_html=True)
        menu = st.radio("", ["Cara a Cara", "Historial General"], label_visibility="collapsed")

    st.markdown("<br><br>", unsafe_allow_html=True)

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if RUTA_LOGO_RETRO.exists():
            st.image(str(RUTA_LOGO_RETRO), width=72)
    with col_b2:
        if RUTA_LOGO_CARP.exists():
            st.image(str(RUTA_LOGO_CARP), width=72)

# ── CARGA Y PROCESAMIENTO GENERAL ─────────────────────────────────────────────
df_raw, estado = cargar_datos_completos(EXCEL_ACTUAL)
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

df_forma = df_raw.groupby('Jugador')['Nota SofaScore'].apply(
    lambda x: " | ".join([f"{n:.1f}" for n in list(x)[-5:]])
).reset_index(name='Forma (Últ. 5)')
df_agrupado = df_agrupado.merge(df_forma, on='Jugador', how='left')

# =============================================================================
# PÁGINAS
# =============================================================================

# ─── RESUMEN GENERAL ──────────────────────────────────────────────────────────
if menu == "Resumen General":
    page_header("🐔", "PANEL GENERAL", f"Temporada {temporada_sel}")

    total_partidos = df_raw['Partido'].nunique()
    promedio_equipo = df_raw['Nota SofaScore'].mean()
    total_goles = df_agrupado['Goles'].sum()
    total_asist = df_agrupado['Asistencias'].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Partidos Analizados", int(total_partidos))
    k2.metric("Promedio SofaScore Equipo", f"{promedio_equipo:.2f}")
    k3.metric("Goles Totales", int(total_goles))
    k4.metric("Asistencias Totales", int(total_asist))

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Promedios SofaScore", "⚽ Goles & Asistencias", "📋 Plantel Completo"])

    with tab1:
        df_promedios = df_agrupado[['Jugador', 'Posición', 'Promedio', 'Partidos', 'Forma (Últ. 5)']].sort_values('Promedio', ascending=False).reset_index(drop=True)
        df_promedios.index = df_promedios.index + 1

        fig_prom = go.Figure()
        colores_barras = [COLORES_POSICION.get(p, '#9CA3AF') for p in df_promedios['Posición']]
        fig_prom.add_trace(go.Bar(
            x=df_promedios['Promedio'], y=df_promedios['Jugador'], orientation='h',
            marker=dict(color=colores_barras, line=dict(width=0)),
            text=df_promedios['Promedio'].apply(lambda x: f"{x:.2f}"),
            textposition='outside',
            textfont=dict(family="Rajdhani", size=12, color="#374151"),
            hovertemplate="<b>%{y}</b><br>Nota: %{x:.2f}<br>Partidos: %{customdata}<extra></extra>",
            customdata=df_promedios['Partidos'],
        ))
        fig_prom.add_vline(x=promedio_equipo, line_dash="dot", line_color="#D0021B", line_width=2,
            annotation_text=f"Prom. Equipo: {promedio_equipo:.2f}", annotation_position="top right",
            annotation_font=dict(family="Rajdhani", size=12, color="#D0021B"))
        apply_plotly_style(fig_prom, xaxis_title="Nota Promedio SofaScore", yaxis_title="")
        fig_prom.update_layout(height=max(400, len(df_promedios) * 28),
            xaxis=dict(range=[5, 8.5]), yaxis=dict(categoryorder='total ascending'))
        st.plotly_chart(fig_prom, use_container_width=True)

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='section-title'>⚽ GOLEADORES</div>", unsafe_allow_html=True)
            df_gol = df_agrupado[df_agrupado['Goles'] > 0][['Jugador', 'Posición', 'Goles']].sort_values('Goles', ascending=False).reset_index(drop=True)
            df_gol.index = df_gol.index + 1
            if not df_gol.empty:
                fig_gol = go.Figure(go.Bar(
                    x=df_gol['Jugador'], y=df_gol['Goles'], marker_color='#D0021B',
                    text=df_gol['Goles'], textposition='outside',
                    textfont=dict(family="Bebas Neue", size=18, color="#D0021B"),
                    hovertemplate="<b>%{x}</b><br>Goles: %{y}<extra></extra>",
                ))
                apply_plotly_style(fig_gol, yaxis_title="Goles")
                fig_gol.update_layout(height=320, xaxis_tickangle=-25)
                st.plotly_chart(fig_gol, use_container_width=True)
            st.dataframe(df_gol, hide_index=False, use_container_width=True)

        with c2:
            st.markdown("<div class='section-title'>👟 ASISTIDORES</div>", unsafe_allow_html=True)
            df_ast = df_agrupado[df_agrupado['Asistencias'] > 0][['Jugador', 'Posición', 'Asistencias']].sort_values('Asistencias', ascending=False).reset_index(drop=True)
            df_ast.index = df_ast.index + 1
            if not df_ast.empty:
                fig_ast = go.Figure(go.Bar(
                    x=df_ast['Jugador'], y=df_ast['Asistencias'], marker_color='#3B82F6',
                    text=df_ast['Asistencias'], textposition='outside',
                    textfont=dict(family="Bebas Neue", size=18, color="#3B82F6"),
                    hovertemplate="<b>%{x}</b><br>Asistencias: %{y}<extra></extra>",
                ))
                apply_plotly_style(fig_ast, yaxis_title="Asistencias")
                fig_ast.update_layout(height=320, xaxis_tickangle=-25)
                st.plotly_chart(fig_ast, use_container_width=True)
            st.dataframe(df_ast, hide_index=False, use_container_width=True)

    with tab3:
        st.dataframe(
            df_agrupado[['Jugador', 'Posición', 'Partidos', 'Promedio', 'Minutos', 'Goles', 'Asistencias',
                          'Pases_Clave', 'Quites', 'Intercepciones', 'Forma (Últ. 5)']].sort_values('Promedio', ascending=False).reset_index(drop=True),
            hide_index=True, use_container_width=True, height=500,
        )

# ─── HISTORIAL (POR TEMPORADA) ────────────────────────────────────────────────
elif menu == "Historial":
    page_header("📖", "HISTORIAL VS RIVALES", f"Temporada {temporada_sel}")

    condicion_sel = st.radio("Condición:", ["Total", "Local", "Visitante"], horizontal=True)
    st.markdown("<br>", unsafe_allow_html=True)

    hojas_unicas = df_raw.drop_duplicates('Partido')['Hoja_Original'].tolist()
    df_historial = generar_historial_rivales(str(EXCEL_ACTUAL), hojas_unicas, condicion_sel)

    if df_historial.empty:
        st.info(f"No hay partidos registrados bajo la condición '{condicion_sel}' en esta temporada.")
    else:
        total_pj = df_historial['PJ'].sum()
        total_pg = df_historial['PG'].sum()
        total_pe = df_historial['PE'].sum()
        total_pp = df_historial['PP'].sum()
        efectividad = (total_pg * 3 + total_pe) / (total_pj * 3) * 100 if total_pj > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Partidos Jugados", int(total_pj))
        c2.metric("Victorias", int(total_pg))
        c3.metric("Empates", int(total_pe))
        c4.metric("Derrotas", int(total_pp))
        c5.metric("Efectividad Puntos", f"{efectividad:.1f}%")

        st.markdown("<br>", unsafe_allow_html=True)
        c_graf, c_tabla = st.columns([1.5, 1])

        with c_graf:
            st.markdown("<div class='section-title'>📊 EFECTIVIDAD POR RIVAL</div>", unsafe_allow_html=True)
            df_hist_graf = df_historial.sort_values(by='PJ', ascending=True)
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Bar(y=df_hist_graf['Rival'], x=df_hist_graf['PG'],
                name='Ganados', orientation='h', marker=dict(color='#22C55E'),
                text=df_hist_graf['PG'].replace(0, ''), textposition='inside',
                textfont=dict(color='white', family='Bebas Neue')))
            fig_hist.add_trace(go.Bar(y=df_hist_graf['Rival'], x=df_hist_graf['PE'],
                name='Empatados', orientation='h', marker=dict(color='#9CA3AF'),
                text=df_hist_graf['PE'].replace(0, ''), textposition='inside',
                textfont=dict(color='white', family='Bebas Neue')))
            fig_hist.add_trace(go.Bar(y=df_hist_graf['Rival'], x=df_hist_graf['PP'],
                name='Perdidos', orientation='h', marker=dict(color='#EF4444'),
                text=df_hist_graf['PP'].replace(0, ''), textposition='inside',
                textfont=dict(color='white', family='Bebas Neue')))
            apply_plotly_style(fig_hist, xaxis_title="Cantidad de Partidos", yaxis_title="")
            fig_hist.update_layout(barmode='stack', height=max(400, len(df_hist_graf) * 35),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_hist, use_container_width=True)

        with c_tabla:
            st.markdown("<div class='section-title'>📋 TABLA DETALLADA</div>", unsafe_allow_html=True)
            st.dataframe(df_historial[['Rival', 'PJ', 'PG', 'PE', 'PP', 'GF', 'GC', 'DIF']],
                hide_index=True, use_container_width=True, height=600)

# ─── MAPAS DE RENDIMIENTO ─────────────────────────────────────────────────────
elif menu == "Mapas de Rendimiento":
    page_header("🗺️", "MAPAS DE RENDIMIENTO", f"Temporada {temporada_sel} · Estadísticas P90")

    with st.sidebar:
        st.markdown("<div class='sidebar-section-label'>Filtro de Minutos</div>", unsafe_allow_html=True)
        min_min = st.slider("Minutos mínimos", 0, int(df_agrupado['Minutos'].max()), 180, label_visibility="collapsed")

    df_p90 = df_agrupado[df_agrupado['Minutos'] >= min_min].copy()

    for col_base, col_p90 in [
        ('Pases_Clave', 'PasesClave_P90'), ('Asistencias', 'Asistencias_P90'),
        ('Quites', 'Quites_P90'), ('Intercepciones', 'Inter_P90'), ('Goles', 'Goles_P90'),
    ]:
        df_p90[col_p90] = (df_p90[col_base] / df_p90['Minutos'].replace(0, 1)) * 90

    def scatter_cuadrantes(df, x_col, y_col, x_label, y_label, title):
        x_mean, y_mean = df[x_col].mean(), df[y_col].mean()
        fig = px.scatter(df, x=x_col, y=y_col, color='Posición', hover_name='Jugador',
            color_discrete_map=COLORES_POSICION, size_max=18)
        fig.update_traces(marker=dict(size=14, line=dict(width=1.5, color='white')),
            hovertemplate="<b>%{hovertext}</b><br>" + x_label + ": %{x:.2f}<br>" + y_label + ": %{y:.2f}<extra></extra>")
        fig.add_vline(x=x_mean, line_dash="dash", line_color="#9CA3AF", line_width=1)
        fig.add_hline(y=y_mean, line_dash="dash", line_color="#9CA3AF", line_width=1)
        apply_plotly_style(fig, title=title, xaxis_title=x_label, yaxis_title=y_label)
        return fig

    tab_def, tab_cre, tab_ata = st.tabs(["🛡️ Defensa", "🧠 Creación", "🎯 Ataque"])

    with tab_def:
        fig_def = scatter_cuadrantes(df_p90, 'Quites_P90', 'Inter_P90', 'Quites p90', 'Intercepciones p90', 'PERFIL DEFENSIVO')
        st.plotly_chart(fig_def, use_container_width=True)

    with tab_cre:
        fig_kp = scatter_cuadrantes(df_p90, 'PasesClave_P90', 'Asistencias_P90', 'Pases Clave p90', 'Asistencias p90', 'CREACIÓN')
        st.plotly_chart(fig_kp, use_container_width=True)

    with tab_ata:
        df_t = df_agrupado[df_agrupado['Tiros_Totales'] > 0].copy()
        if not df_t.empty:
            df_t['Conv_Rate'] = (df_t['Goles'] / df_t['Tiros_Totales'] * 100).round(1)
            fig_of = px.scatter(df_t, x='Tiros_Totales', y='Goles', color='Posición',
                hover_name='Jugador', color_discrete_map=COLORES_POSICION, custom_data=['Conv_Rate'])
            apply_plotly_style(fig_of, title='EFICIENCIA GOLEADORA', xaxis_title='Tiros Totales', yaxis_title='Goles')
            st.plotly_chart(fig_of, use_container_width=True)

# ─── ANÁLISIS INDIVIDUAL ──────────────────────────────────────────────────────
elif menu == "Análisis Individual":
    page_header("🔎", "ANÁLISIS INDIVIDUAL", f"Temporada {temporada_sel}")

    jugadores_ordenados = sorted(df_raw['Jugador'].unique())
    jugador_sel = st.selectbox("Seleccioná un jugador:", jugadores_ordenados)

    if jugador_sel:
        df_j = df_raw[df_raw['Jugador'] == jugador_sel].copy()
        pos = df_j['Posición'].mode()[0] if not df_j['Posición'].isnull().all() else "—"
        min_tot = int(df_j['Minutos'].sum())
        prom = df_j['Nota SofaScore'].mean()

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#111827,#1F2937);border-left:4px solid #D0021B;
                    border-radius:10px;padding:20px 28px;margin-bottom:24px;">
            <div style="font-family:'Bebas Neue',cursive;font-size:36px;color:white;letter-spacing:2px;">{jugador_sel}</div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:13px;color:#D0021B;letter-spacing:2px;font-weight:700;">
                {pos} · {min_tot} MINUTOS JUGADOS
            </div>
            <div style="margin-top:12px;font-family:'Bebas Neue',cursive;font-size:56px;color:#D0021B;line-height:1;">{prom:.2f}
                <span style="font-family:'Rajdhani',sans-serif;font-size:11px;color:#9CA3AF;letter-spacing:2px;vertical-align:middle;"> NOTA PROMEDIO</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig_l = go.Figure()
        fig_l.add_trace(go.Bar(x=df_j['Partido'], y=df_j['Nota SofaScore'], marker_color='#D0021B'))
        fig_l.add_hline(y=prom, line_dash="dot", line_color="white", annotation_text="Promedio")
        apply_plotly_style(fig_l, title="EVOLUCIÓN DE NOTAS", yaxis_title="Nota SofaScore")
        st.plotly_chart(fig_l, use_container_width=True)

# ─── ESTADÍSTICAS DE EQUIPO ───────────────────────────────────────────────────
elif menu == "Estadísticas de Equipo":
    page_header("⚖️", "ESTADÍSTICAS DE EQUIPO", "Comparativa por partido")

    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Seleccioná la fecha:", list(hojas.keys()))
    mostrar_marcador(EXCEL_ACTUAL, hojas[partido])

    df_equipo = extraer_estadisticas_equipo(str(EXCEL_ACTUAL), hojas[partido])
    
    if not df_equipo.empty:
        try:
            cols = df_equipo.columns.tolist()
            df_equipo[cols[1]] = pd.to_numeric(df_equipo[cols[1]], errors='coerce')
            df_equipo[cols[2]] = pd.to_numeric(df_equipo[cols[2]], errors='coerce')
            
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Bar(name=str(cols[1]), x=df_equipo[cols[0]], y=df_equipo[cols[1]], marker_color='#D0021B'))
            fig_eq.add_trace(go.Bar(name=str(cols[2]), x=df_equipo[cols[0]], y=df_equipo[cols[2]], marker_color='#374151'))
            apply_plotly_style(fig_eq, title="COMPARATIVA DE MÉTRICAS")
            fig_eq.update_layout(barmode='group')
            st.plotly_chart(fig_eq, use_container_width=True)
        except Exception: pass
        st.dataframe(df_equipo, hide_index=True, use_container_width=True)

# ─── ESTADÍSTICAS INDIVIDUALES ────────────────────────────────────────────────
elif menu == "Estadísticas Individuales":
    page_header("👤", "ESTADÍSTICAS INDIVIDUALES", "Top 7 por categoría")

    def extraer_exitosos(valor):
        try: return int(str(valor).split('/')[0])
        except: return 0

    partido_sel = st.selectbox("Seleccioná la fecha:", df_raw['Partido'].unique())
    df_p = df_raw[df_raw['Partido'] == partido_sel].copy()
    
    if 'Pases (Comp/Tot)' in df_p.columns: df_p['Pases Completados'] = df_p['Pases (Comp/Tot)'].apply(extraer_exitosos)
    
    categorias = {
        "⭐ Nota SofaScore": "Nota SofaScore",
        "🛡️ Quites": "Quites (Tackles)",
        "🎯 Pases Completados": "Pases Completados",
        "🔑 Pases Clave": "Pases Clave"
    }

    cols_grid = st.columns(2)
    for i, (label, col) in enumerate(categorias.items()):
        if col in df_p.columns:
            with cols_grid[i % 2]:
                st.markdown(f"### {label}")
                st.dataframe(df_p.nlargest(7, col)[['Jugador', col]], hide_index=True, use_container_width=True)

# ─── PARADO TÁCTICO ───────────────────────────────────────────────────────────
elif menu == "Parado Táctico":
    page_header("📋", "PARADO TÁCTICO", "Formación del partido")
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    img = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 0)
    if img: st.image(img, use_container_width=True)
    else: st.info("No hay imagen táctica disponible.")

# ─── MAPA DE TIROS ────────────────────────────────────────────────────────────
elif menu == "Mapa de Tiros":
    page_header("🎯", "MAPA DE TIROS", "Distribución de disparos")
    hojas = df_raw.drop_duplicates('Partido')[['Partido', 'Hoja_Original']].set_index('Partido').to_dict()['Hoja_Original']
    partido = st.selectbox("Fecha:", list(hojas.keys()))
    c1, c2 = st.columns(2)
    with c1:
        img_r = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 1)
        if img_r: st.image(img_r, use_container_width=True, caption="River Plate")
    with c2:
        img_v = extraer_imagen_incrustada(str(EXCEL_ACTUAL), hojas[partido], 2)
        if img_v: st.image(img_v, use_container_width=True, caption="Rival")

# ─── CARA A CARA ──────────────────────────────────────────────────────────────
elif menu == "Cara a Cara":
    page_header("⚔️", "CARA A CARA", "Comparación de perfiles P90")
    # Simplificado para restaurar estabilidad
    st.info("Seleccioná jugadores en el menú lateral para comparar sus perfiles de rendimiento.")

# ─── HISTORIAL GENERAL (NUEVO EN HERRAMIENTAS) ────────────────────────────────
elif menu == "Historial General":
    page_header("🌍", "HISTORIAL GENERAL", "Historial acumulado vs todos los rivales")
    
    condicion_sel = st.radio("Condición:", ["Total", "Local", "Visitante"], horizontal=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    df_historial = generar_historial_completo(condicion_sel)
    
    if df_historial.empty:
        st.info(f"No hay partidos registrados bajo la condición '{condicion_sel}'.")
    else:
        total_pj = df_historial['PJ'].sum()
        total_pg = df_historial['PG'].sum()
        total_pe = df_historial['PE'].sum()
        total_pp = df_historial['PP'].sum()
        efectividad = (total_pg * 3 + total_pe) / (total_pj * 3) * 100 if total_pj > 0 else 0
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Partidos", int(total_pj))
        c2.metric("Victorias", int(total_pg))
        c3.metric("Empates", int(total_pe))
        c4.metric("Derrotas", int(total_pp))
        c5.metric("Efectividad", f"{efectividad:.1f}%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df_historial, hide_index=True, use_container_width=True, height=600)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("<div class='footer'>Data CARP · Club Atlético River Plate · Análisis de Rendimiento</div>", unsafe_allow_html=True)
