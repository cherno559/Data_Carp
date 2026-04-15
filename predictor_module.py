import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE POSICIONES 2026 (J 13)
# ─────────────────────────────────────────────────────────────────────────────

MONTECARLO_N = 10_000

EQUIPOS_PRIMERA_2026 = [
    "Ind. Rivadavia", "River", "Vélez", "Estudiantes", "Argentinos", "Lanús", 
    "Belgrano", "Boca Jrs.", "Central", "Talleres", "Huracán", "Unión", 
    "Defensa", "Barracas", "Tigre", "Independiente", "Racing", "San Lorenzo", 
    "Instituto", "Gimnasia", "Platense", "Sarmiento", "Banfield", "Gimnasia (M)", 
    "Central Córdoba", "Atl. Tucumán", "Newell's", "Riestra", "Aldosivi", "Estudiantes RC"
]

DATOS_LIGA_MANUAL = {
    "Ind. Rivadavia":  {"PJ": 13, "GF": 23, "GC": 13}, "River": {"PJ": 13, "GF": 19, "GC": 9},
    "Vélez": {"PJ": 13, "GF": 15, "GC": 9}, "Estudiantes": {"PJ": 13, "GF": 16, "GC": 7},
    "Argentinos": {"PJ": 13, "GF": 14, "GC": 10}, "Lanús": {"PJ": 13, "GF": 18, "GC": 14},
    "Belgrano": {"PJ": 13, "GF": 13, "GC": 12}, "Boca Jrs.": {"PJ": 13, "GF": 15, "GC": 8},
    "Central": {"PJ": 13, "GF": 15, "GC": 13}, "Talleres": {"PJ": 13, "GF": 14, "GC": 12},
    "Huracán": {"PJ": 13, "GF": 15, "GC": 10}, "Unión": {"PJ": 13, "GF": 19, "GC": 14},
    "Defensa": {"PJ": 13, "GF": 16, "GC": 12}, "Barracas": {"PJ": 13, "GF": 13, "GC": 12},
    "Tigre": {"PJ": 13, "GF": 16, "GC": 12}, "Independiente": {"PJ": 13, "GF": 19, "GC": 16},
    "Racing": {"PJ": 13, "GF": 15, "GC": 13}, "San Lorenzo": {"PJ": 13, "GF": 12, "GC": 12},
    "Instituto": {"PJ": 13, "GF": 14, "GC": 15}, "Gimnasia": {"PJ": 13, "GF": 15, "GC": 19},
    "Platense": {"PJ": 13, "GF": 7,  "GC": 8}, "Sarmiento": {"PJ": 13, "GF": 11, "GC": 14},
    "Banfield": {"PJ": 13, "GF": 14, "GC": 17}, "Gimnasia (M)": {"PJ": 13, "GF": 10, "GC": 16},
    "Central Córdoba": {"PJ": 13, "GF": 6,  "GC": 16}, "Atl. Tucumán": {"PJ": 13, "GF": 13, "GC": 18},
    "Newell's": {"PJ": 13, "GF": 10, "GC": 23}, "Riestra": {"PJ": 13, "GF": 3,  "GC": 10},
    "Aldosivi": {"PJ": 13, "GF": 3,  "GC": 14}, "Estudiantes RC": {"PJ": 13, "GF": 4,  "GC": 19}
}

RED, GRAY, LIGHT_B = "#D0021B", "#374151", "rgba(249,250,251,1)"
_ST = dict(font=dict(family="Rajdhani", size=13), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── DATA LIGA Y PLANTILLA
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga():
    registros = [{"equipo": eq, "PJ": s["PJ"], "GF": s["GF"], "GC": s["GC"]} for eq, s in DATOS_LIGA_MANUAL.items()]
    return pd.DataFrame(registros)

@st.cache_data(ttl=3600)
def extraer_plantilla_river(ruta_excel_str):
    ruta = Path(ruta_excel_str)
    xl = pd.ExcelFile(ruta)
    filas = []
    for hoja in xl.sheet_names:
        if "Promedios" in hoja or "Resumen" in hoja: continue
        try:
            df_h = pd.read_excel(ruta, sheet_name=hoja)
            df_h.columns = df_h.columns.astype(str).str.strip()
            df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
            df_h["Minutos"] = pd.to_numeric(df_h.get("Minutos", 0), errors="coerce").fillna(0)
            df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
            filas.append(df_h)
        except: continue
    df_todos = pd.concat(filas, ignore_index=True)
    agg = df_todos.groupby("Jugador", as_index=False).agg(
        Posicion = ("Posición", lambda x: x.mode()[0] if not x.mode().empty else "Mediocampista"),
        Minutos  = ("Minutos", "sum"),
        Nota     = ("Nota SofaScore", lambda x: x[x>0].mean() if not x[x>0].empty else 6.8),
        Goles    = ("Goles", "sum")
    )
    agg["xG_p90"] = (agg["Goles"] / (agg["Minutos"]/90)).round(3)
    agg["forma"] = (agg["Nota"] / 7.0).clip(0.85, 1.15)
    return agg[agg["Minutos"] >= 1].reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── LÓGICA DE SIMULACIÓN Y GOLEADORES (CON SMOOTHING)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    riv_base = df_liga[df_liga["equipo"] == "River"].iloc[0]
    fa_rival, fd_rival = (r_data["GF"]/r_data["PJ"])/mgf, (r_data["GC"]/r_data["PJ"])/mgf
    fa_river, fd_river = (riv_base["GF"]/riv_base["PJ"])/mgf, (riv_base["GC"]/riv_base["PJ"])/mgf
    
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    # Aumentamos un poco la sensibilidad del XI (de 0.4 a 0.5)
    mult_atk = 1.0 + ((df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() - 1.0) * 0.5)
    forma = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.5)
    
    V = 1.15
    lam_r = fa_river * mult_atk * fd_rival * mgf * forma * (V if es_local else 1.0)
    lam_v = fa_rival * fd_river * mgf * (1/forma) * (1.0 if es_local else V)
    return round(float(np.clip(lam_r, 0.2, 5.0)), 3), round(float(np.clip(lam_v, 0.2, 5.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr, gv = rng.poisson(lam_r, MONTECARLO_N), rng.poisson(lam_v, MONTECARLO_N)
    # Ajuste Dixon-Coles suavizado (0.18 en vez de 0.28) para que la victoria pese más
    for i in range(MONTECARLO_N):
        if ((gr[i]==1 and gv[i]==0) or (gr[i]==0 and gv[i]==1)) and rng.random() < 0.18:
            gr[i], gv[i] = 1, 1
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": float(np.mean((gr==r) & (gv==v)))})
    return {"prob_victoria": float(np.mean(gr > gv)), "prob_empate": float(np.mean(gr == gv)), "prob_derrota": float(np.mean(gr < gv)), "df_resultados": pd.DataFrame(res), "lambda_r": lam_r, "lambda_v": lam_v, "n": MONTECARLO_N}

def obtener_tabla_goleadores(titulares, df_plantilla, lam_r):
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
    
    # LAPLACE SMOOTHING: Les damos una chance mínima a todos para que nadie tenga 0.0%
    def amenaza_base(pos):
        if "Delantero" in pos: return 0.05
        if "Mediocampista" in pos: return 0.03
        return 0.015 # Defensores (mínima chance de córner/rebote)
    
    # Peso de posición para priorizar visualmente a los atacantes
    def peso_pos(p):
        if "Delantero" in p: return 1.3
        if "Mediocampista" in p: return 1.0
        return 0.7 
    
    df_xi["amenaza"] = (df_xi["xG_p90"] + df_xi["Posicion"].apply(amenaza_base)) * df_xi["Posicion"].apply(peso_pos)
    total = df_xi["amenaza"].sum() if df_xi["amenaza"].sum() > 0 else 1
    
    # Probabilidad de que el jugador marque al menos un gol
    df_xi["% Prob. Gol"] = ((df_xi["amenaza"] / total) * (1 - np.exp(-lam_r)) * 100).round(1)
    
    return df_xi[["Jugador", "Posicion", "xG_p90", "% Prob. Gol"]].sort_values("% Prob. Gol", ascending=False)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── VISUALIZACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fig_heatmap(sim, rival, style_fn):
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
    fig = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(MAX_G + 1)], y=[str(i) for i in range(MAX_G + 1)], text=texto, texttemplate="%{text}", colorscale=[[0, "#F9FAFB"], [0.2, "#FEE2E2"], [1, RED]], showscale=False))
    fig.update_layout(**_ST, title=f"MAPA DE MARCADORES (vs {rival})", xaxis=dict(title="Goles River", tickfont=dict(color=RED)), yaxis=dict(title=f"Goles {rival}"), height=450)
    if style_fn: style_fn(fig)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""<style>
    .pred-kpi { background: #111827; border-left: 4px solid #D0021B; border-radius: 10px; padding: 16px 20px; text-align: center; }
    .pred-kpi .label { font-family: 'Rajdhani', sans-serif; font-size: 10px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 2px; font-weight: 700; }
    .pred-kpi .valor { font-family: 'Bebas Neue', cursive; font-size: 44px; color: #D0021B; line-height: 1; }
    .pred-kpi.empate .valor { color: #9CA3AF; } .pred-kpi.derrota .valor { color: #1A4A8B; }
    .badge-datos { display: inline-block; padding: 3px 12px; border-radius: 20px; font-family: 'Rajdhani'; font-size: 12px; font-weight: 700; background: #1a4d1a; color: #66ff66; margin-bottom: 15px; }
    </style>""", unsafe_allow_html=True)

    df_liga = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))
    st.markdown('<span class="badge-datos">✅ Torneo 2026 Sincronizado (J 13)</span>', unsafe_allow_html=True)

    c1, c2 = st.columns([2,1])
    rival_sel = c1.selectbox("🆚 Seleccioná el Rival", sorted([e for e in EQUIPOS_PRIMERA_2026 if e != "River"]))
    es_local = c2.radio("📍 Condición", ["Monumental 🏟️", "Visitante ✈️"], horizontal=True) == "Monumental 🏟️"

    opciones = [f"{r.Jugador} ({r.Posicion})" for _, r in df_plantilla.sort_values("Minutos", ascending=False).iterrows()]
    titulares_raw = st.multiselect("👥 Armá tu XI Titular:", opciones, default=opciones[:11], max_selections=11)
    titulares = [re.sub(r"\s*\(.*\)$", "", t).strip() for t in titulares_raw]

    if st.button("🚀 SIMULAR PARTIDO", use_container_width=True, type="primary", disabled=len(titulares)!=11):
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"### 📊 Resultado Probable: River vs {rival_sel}")
        k1, k2, k3, k4, k5 = st.columns(5)
        for c, l, v, t in [(k1,"Victoria",f"{sim['prob_victoria']*100:.1f}%",""), (k2,"Empate",f"{sim['prob_empate']*100:.1f}%","empate"), (k3,"Derrota",f"{sim['prob_derrota']*100:.1f}%","derrota"), (k4,"λ River",f"{lr:.2f}",""), (k5,"λ Rival",f"{lv:.2f}","")]:
            c.markdown(f'<div class="pred-kpi {t}"><div class="label">{l}</div><div class="valor">{v}</div></div>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["📊 Probabilidades", "⚽ Goleadores", "🎯 Marcadores", "🔬 Análisis XI"])
        with t1:
            fig = go.Figure(go.Bar(x=[sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100], y=["Victoria River", "Empate", "Derrota River"], orientation="h", marker_color=[RED, "#9CA3AF", "#1A4A8B"], text=[f"{v*100:.1f}%" for v in [sim["prob_victoria"], sim["prob_empate"], sim["prob_derrota"]]], textposition="outside"))
            fig.update_layout(**_ST, height=260, showlegend=False)
            if apply_plotly_style_fn: apply_plotly_style_fn(fig)
            st.plotly_chart(fig, use_container_width=True)
        with t2:
            st.dataframe(obtener_tabla_goleadores(titulares, df_plantilla, lr).rename(columns={"xG_p90": "xG/90"}), use_container_width=True, hide_index=True)
        with t3:
            st.plotly_chart(fig_heatmap(sim, rival_sel, apply_plotly_style_fn), use_container_width=True)
        with t4:
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)][["Jugador","Posicion","Nota","xG_p90"]].sort_values("Posicion"), use_container_width=True, hide_index=True)
