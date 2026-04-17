import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN Y CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Red-AI | River Plate Predictor", layout="wide")

MONTECARLO_N = 10_000
RED, GRAY, LIGHT_B = "#D0021B", "#374151", "rgba(249,250,251,1)"

# Estilo base para Plotly
_ST = {
    "font": {"family": "Rajdhani", "size": 13},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": LIGHT_B
}

EQUIPOS_PRIMERA_2026 = [
    "Ind. Rivadavia", "River", "Vélez", "Estudiantes", "Argentinos", "Lanús",
    "Belgrano", "Boca Jrs.", "Central", "Talleres", "Huracán", "Unión",
    "Defensa", "Barracas", "Tigre", "Independiente", "Racing", "San Lorenzo",
    "Instituto", "Gimnasia", "Platense", "Sarmiento", "Banfield", "Gimnasia (M)",
    "Central Córdoba", "Atl. Tucumán", "Newell's", "Riestra", "Aldosivi", "Estudiantes RC"
]

DATOS_LIGA_MANUAL = {
    "Ind. Rivadavia":  {"PJ": 13, "GF": 23, "GC": 13},
    "River":           {"PJ": 13, "GF": 19, "GC": 9},
    "Vélez":           {"PJ": 13, "GF": 15, "GC": 9},
    "Estudiantes":     {"PJ": 13, "GF": 16, "GC": 7},
    "Argentinos":      {"PJ": 13, "GF": 14, "GC": 10},
    "Lanús":           {"PJ": 13, "GF": 18, "GC": 14},
    "Belgrano":        {"PJ": 13, "GF": 13, "GC": 12},
    "Boca Jrs.":       {"PJ": 13, "GF": 15, "GC": 8},
    "Central":         {"PJ": 13, "GF": 15, "GC": 13},
    "Talleres":        {"PJ": 13, "GF": 14, "GC": 12},
    "Huracán":         {"PJ": 13, "GF": 15, "GC": 10},
    "Unión":           {"PJ": 13, "GF": 19, "GC": 14},
    "Defensa":         {"PJ": 13, "GF": 16, "GC": 12},
    "Barracas":        {"PJ": 13, "GF": 13, "GC": 12},
    "Tigre":           {"PJ": 13, "GF": 16, "GC": 12},
    "Independiente":   {"PJ": 13, "GF": 19, "GC": 16},
    "Racing":          {"PJ": 13, "GF": 15, "GC": 13},
    "San Lorenzo":     {"PJ": 13, "GF": 12, "GC": 12},
    "Instituto":       {"PJ": 13, "GF": 14, "GC": 15},
    "Gimnasia":        {"PJ": 13, "GF": 15, "GC": 19},
    "Platense":        {"PJ": 13, "GF": 7,  "GC": 8},
    "Sarmiento":       {"PJ": 13, "GF": 11, "GC": 14},
    "Banfield":        {"PJ": 13, "GF": 14, "GC": 17},
    "Gimnasia (M)":    {"PJ": 13, "GF": 10, "GC": 16},
    "Central Córdoba": {"PJ": 13, "GF": 6,  "GC": 16},
    "Atl. Tucumán":    {"PJ": 13, "GF": 13, "GC": 18},
    "Newell's":        {"PJ": 13, "GF": 10, "GC": 23},
    "Riestra":         {"PJ": 13, "GF": 3,  "GC": 10},
    "Aldosivi":        {"PJ": 13, "GF": 3,  "GC": 14},
    "Estudiantes RC":  {"PJ": 13, "GF": 4,  "GC": 19}
}

POSICION_MAP = {
    "DEL": "Delantero", "del": "Delantero", "Delantero": "Delantero",
    "MED": "Mediocampista", "med": "Mediocampista", "Mediocampista": "Mediocampista",
    "DEF": "Defensor", "def": "Defensor", "Defensor": "Defensor",
    "POR": "Arquero", "por": "Arquero", "Arquero": "Arquero",
}

# ─────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga():
    registros = [{"equipo": eq, "PJ": s["PJ"], "GF": s["GF"], "GC": s["GC"]} for eq, s in DATOS_LIGA_MANUAL.items()]
    return pd.DataFrame(registros)

@st.cache_data(ttl=3600)
def extraer_plantilla_river(archivo_excel):
    try:
        xl = pd.ExcelFile(archivo_excel)
        filas = []
        for hoja in xl.sheet_names:
            if any(x in hoja for x in ["Promedios", "Resumen"]): continue
            df_h = pd.read_excel(xl, sheet_name=hoja)
            df_h.columns = df_h.columns.astype(str).str.strip()
            if "Jugador" not in df_h.columns: continue
            
            df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
            df_h["Minutos"] = pd.to_numeric(df_h.get("Minutos", 0), errors="coerce").fillna(0)
            df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
            filas.append(df_h)

        if not filas: return pd.DataFrame()
        df_todos = pd.concat(filas, ignore_index=True)

        # Normalizar Posición
        pos_col = "Posición" if "Posición" in df_todos.columns else ("Posicion" if "Posicion" in df_todos.columns else None)
        df_todos["Pos_Norm"] = df_todos[pos_col].astype(str).str.strip().map(lambda p: POSICION_MAP.get(p, "Mediocampista")) if pos_col else "Mediocampista"
        
        df_todos["Goles"] = pd.to_numeric(df_todos.get("Goles", 0), errors="coerce").fillna(0)
        df_todos["Nota SofaScore"] = pd.to_numeric(df_todos.get("Nota SofaScore", 6.8), errors="coerce").fillna(6.8)

        agg = df_todos.groupby("Jugador", as_index=False).agg(
            Posicion=("Pos_Norm", lambda x: x.mode()[0] if not x.mode().empty else "Mediocampista"),
            Minutos=("Minutos", "sum"),
            Nota=("Nota SofaScore", lambda x: x[x > 0].mean() if not x[x > 0].empty else 6.8),
            Goles=("Goles", "sum")
        )

        agg["xG_p90"] = (agg["Goles"] / (agg["Minutos"].replace(0, 1) / 90)).round(3)
        agg["forma"] = (agg["Nota"] / 7.0).clip(0.85, 1.15)
        return agg[agg["Minutos"] >= 1].reset_index(drop=True)
    except Exception as e:
        st.error(f"Error procesando el Excel: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA DE SIMULACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    riv_base = df_liga[df_liga["equipo"] == "River"].iloc[0]

    fa_river, fd_river = (riv_base["GF"]/riv_base["PJ"])/mgf, (riv_base["GC"]/riv_base["PJ"])/mgf
    fa_rival, fd_rival = (r_data["GF"]/r_data["PJ"])/mgf, (r_data["GC"]/r_data["PJ"])/mgf

    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    mult_atk = 1.0 + ((df_xi["xG_p90"].mean() / max(df_plantilla["xG_p90"].mean(), 0.001) - 1.0) * 0.5)
    forma = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.5)

    V = 1.15
    lam_r = fa_river * mult_atk * fd_rival * mgf * forma * (V if es_local else 1.0)
    lam_v = fa_rival * fd_river * mgf * (1 / forma) * (1.0 if es_local else V)
    return round(float(np.clip(lam_r, 0.2, 5.0)), 3), round(float(np.clip(lam_v, 0.2, 5.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr, gv = rng.poisson(lam_r, MONTECARLO_N), rng.poisson(lam_v, MONTECARLO_N)
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": float(np.mean((gr == r) & (gv == v)))})
    return {
        "prob_victoria": float(np.mean(gr > gv)),
        "prob_empate": float(np.mean(gr == gv)),
        "prob_derrota": float(np.mean(gr < gv)),
        "df_resultados": pd.DataFrame(res)
    }

# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIONES (SOLUCIÓN AL VALUEERROR)
# ─────────────────────────────────────────────────────────────────────────────

def fig_heatmap(sim, rival):
    MAX_G = 5
    df = sim["df_resultados"]
    z = np.zeros((MAX_G + 1, MAX_G + 1))
    texto = [[""] * (MAX_G + 1) for _ in range(MAX_G + 1)]

    for _, row in df.iterrows():
        r, v = int(row["River"]), int(row["Rival"])
        if r <= MAX_G and v <= MAX_G:
            p = row["prob"] * 100
            z[v][r] = p
            texto[v][r] = f"{p:.1f}%" if p > 0.5 else ""

    fig = go.Figure(go.Heatmap(
        z=z, x=[str(i) for i in range(MAX_G + 1)], y=[str(i) for i in range(MAX_G + 1)],
        text=texto, texttemplate="%{text}",
        colorscale=[[0, "#F9FAFB"], [0.2, "#FEE2E2"], [1, RED]], showscale=False
    ))

    # SOLUCIÓN: Usar un diccionario unificado para evitar conflictos de tipos en Python 3.14
    ly = _ST.copy()
    ly.update({
        "title": {"text": f"MAPA DE MARCADORES — River vs {rival}"},
        "height": 500,
        "xaxis": {"title": "GOLES RIVER PLATE", "titlefont": {"color": RED}, "gridcolor": "#E5E7EB"},
        "yaxis": {"title": f"GOLES {rival.upper()}", "gridcolor": "#E5E7EB"},
    })
    fig.update_layout(ly)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZADO DE LA APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.markdown("""<style>
        .kpi-card { background: #111827; padding: 20px; border-radius: 10px; border-left: 5px solid #D0021B; text-align: center; }
        .kpi-val { font-size: 36px; font-weight: bold; color: #D0021B; }
        .kpi-lab { color: #9CA3AF; font-size: 12px; letter-spacing: 1px; }
    </style>""", unsafe_allow_html=True)

    st.title("⚪ Red-AI: River Plate Predictor 2026")
    
    archivo = st.file_uploader("📂 Cargá el Excel de Plantilla", type=["xlsx"])
    
    if not archivo:
        st.info("Esperando archivo Excel para iniciar...")
        return

    df_plantilla = extraer_plantilla_river(archivo)
    if df_plantilla.empty: return

    col1, col2 = st.columns([2, 1])
    with col1:
        rival = st.selectbox("🆚 Seleccioná el Rival", sorted([e for e in EQUIPOS_PRIMERA_2026 if e != "River"]))
    with col2:
        es_local = st.radio("📍 Localía", ["Monumental 🏟️", "Visitante ✈️"]) == "Monumental 🏟️"

    # Selección de XI
    opciones = [f"{r.Jugador} ({r.Posicion})" for _, r in df_plantilla.sort_values("Minutos", ascending=False).iterrows()]
    titulares_raw = st.multiselect("👥 Elegí tus 11 titulares:", opciones, default=opciones[:11], max_selections=11)
    
    if len(titulares_raw) < 11:
        st.warning(f"Faltan {11 - len(titulares_raw)} jugadores.")
        return

    if st.button("🚀 SIMULAR PARTIDO", use_container_width=True, type="primary"):
        titulares = [re.sub(r"\s*\(.*\)$", "", t).strip() for t in titulares_raw]
        df_liga = obtener_estadisticas_liga()
        
        lr, lv = calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="kpi-card"><div class="kpi-lab">VICTORIA</div><div class="kpi-val">{sim["prob_victoria"]*100:.1f}%</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="kpi-card"><div class="kpi-lab">EMPATE</div><div class="kpi-val" style="color:white">{sim["prob_empate"]*100:.1f}%</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="kpi-card"><div class="kpi-lab">DERROTA</div><div class="kpi-val" style="color:#1A4A8B">{sim["prob_derrota"]*100:.1f}%</div></div>', unsafe_allow_html=True)

        # Tabs
        t1, t2, t3 = st.tabs(["🎯 Marcadores Probables", "⚽ Goleadores", "📋 Análisis XI"])
        with t1:
            st.plotly_chart(fig_heatmap(sim, rival), use_container_width=True)
        with t2:
            from predictor_module import obtener_tabla_goleadores # Si querés usar la lógica de goles
            st.table(df_plantilla[df_plantilla["Jugador"].isin(titulares)][["Jugador", "Posicion", "xG_p90"]].sort_values("xG_p90", ascending=False))
        with t3:
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)], use_container_width=True)

if __name__ == "__main__":
    main()
