import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y TABLA POSICIONES 2026 (CORREGIDA SEGÚN IMAGEN)
# ─────────────────────────────────────────────────────────────────────────────

MONTECARLO_N = 10_000

# Nombres exactos de tu torneo
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

RED, GRAY, LIGHT_B = "#D0021B", "#374151", "rgba(249,250,251,1)"

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── DATA LIGA Y PLANTILLA
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga() -> pd.DataFrame:
    registros = []
    for eq, stats in DATOS_LIGA_MANUAL.items():
        registros.append({"equipo": eq, "PJ": stats["PJ"], "GF": stats["GF"], "GC": stats["GC"]})
    return pd.DataFrame(registros)

@st.cache_data(ttl=3600)
def extraer_plantilla_river(ruta_excel_str: str) -> pd.DataFrame:
    ruta = Path(ruta_excel_str)
    xl = pd.ExcelFile(ruta)
    hojas_omitir = {"Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"}
    filas = []
    for hoja in xl.sheet_names:
        if hoja in hojas_omitir: continue
        try:
            df_h = pd.read_excel(ruta, sheet_name=hoja)
            df_h.columns = df_h.columns.astype(str).str.strip()
            df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
            df_h["Minutos"] = pd.to_numeric(df_h.get("Minutos", 0), errors="coerce").fillna(0)
            df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
            filas.append(df_h)
        except: continue
    
    df_todos = pd.concat(filas, ignore_index=True)
    for c in ["Goles", "Intercepciones", "Nota SofaScore"]:
        df_todos[c] = pd.to_numeric(df_todos.get(c, 0), errors="coerce").fillna(0)

    agg = df_todos.groupby("Jugador", as_index=False).agg(
        Posicion = ("Posición", lambda x: x.mode()[0] if not x.mode().empty else "Mediocampista"),
        Minutos  = ("Minutos", "sum"),
        Nota     = ("Nota SofaScore", lambda x: x[x>0].mean() if not x[x>0].empty else 6.8),
        Goles    = ("Goles", "sum"),
        Inter    = ("Intercepciones", "sum")
    )
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.85, 1.15) 
    return agg[agg["Minutos"] >= 1].reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── CÁLCULO Y GOLEADORES (FILTRO DE POSICIÓN)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    riv_base = df_liga[df_liga["equipo"] == "River"].iloc[0]
    
    fa_rival, fd_rival = (r_data["GF"]/r_data["PJ"])/mgf, (r_data["GC"]/r_data["PJ"])/mgf
    fa_river, fd_river = (riv_base["GF"]/riv_base["PJ"])/mgf, (riv_base["GC"]/riv_base["PJ"])/mgf
    
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    mult_atk = 1.0 + ((df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() - 1.0) * 0.4)
    mult_def = 1.0 + ((df_xi["xGA_p90"].mean() / df_plantilla["xGA_p90"].mean() - 1.0) * 0.4)
    forma    = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.5)

    V = 1.15
    lam_r = fa_river * mult_atk * fd_rival * mgf * forma * (V if es_local else 1.0)
    lam_v = fa_rival * (fd_river / max(mult_def, 0.3)) * mgf * (1/forma) * (1.0 if es_local else V)
    return round(float(np.clip(lam_r, 0.2, 5.0)), 3), round(float(np.clip(lam_v, 0.2, 5.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr, gv = rng.poisson(lam_r, MONTECARLO_N), rng.poisson(lam_v, MONTECARLO_N)
    for i in range(MONTECARLO_N):
        if ((gr[i]==1 and gv[i]==0) or (gr[i]==0 and gv[i]==1)) and rng.random() < 0.28:
            gr[i], gv[i] = 1, 1
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": float(np.mean((gr==r) & (gv==v)))})
    return {"prob_victoria": float(np.mean(gr > gv)), "prob_empate": float(np.mean(gr == gv)), "prob_derrota": float(np.mean(gr < gv)), "df_resultados": pd.DataFrame(res), "lambda_r": lam_r, "lambda_v": lam_v, "n": MONTECARLO_N}

def obtener_tabla_goleadores(titulares, df_plantilla, lam_r):
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
    
    # AJUSTE POSICIÓN: Penalizamos a los defensores (aunque tengan xG por penales)
    def peso_pos(p):
        if "Delantero" in p: return 1.3
        if "Mediocampista" in p: return 1.0
        return 0.6 # Defensores (Efecto Montiel corregido)
    
    df_xi["p_pos"] = df_xi["Posicion"].apply(peso_pos)
    df_xi["p_final"] = df_xi["xG_p90"] * df_xi["p_pos"]
    total = df_xi["p_final"].sum() if df_xi["p_final"].sum() > 0 else 1
    df_xi["% Prob. Gol"] = ((df_xi["p_final"] / total) * (1 - np.exp(-lam_r)) * 100).round(1)
    return df_xi[["Jugador", "Posicion", "xG_p90", "% Prob. Gol"]].sort_values("% Prob. Gol", ascending=False)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── INTERFAZ STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""<style>
    .pred-kpi { background: #111827; border: 1px solid #2A2A2A; border-left: 4px solid #D0021B; border-radius: 10px; padding: 16px 20px; text-align: center; }
    .pred-kpi .label { font-family: 'Rajdhani', sans-serif; font-size: 10px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 2px; font-weight: 700; }
    .pred-kpi .valor { font-family: 'Bebas Neue', cursive; font-size: 44px; line-height: 1; color: #D0021B; }
    .pred-kpi.empate .valor { color: #9CA3AF; } .pred-kpi.derrota .valor { color: #1A4A8B; }
    .badge-datos { display: inline-block; padding: 3px 12px; border-radius: 20px; font-family: 'Rajdhani'; font-size: 12px; font-weight: 700; background: #1a4d1a; color: #66ff66; margin-bottom: 15px; }
    </style>""", unsafe_allow_html=True)

    df_liga = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))
    
    st.markdown(f'<span class="badge-datos">✅ Torneo 2026: Tabla Sincronizada (J 13)</span>', unsafe_allow_html=True)

    c1, c2 = st.columns([2,1])
    rival_sel = c1.selectbox("🆚 Seleccioná el Rival", sorted([e for e in EQUIPOS_PRIMERA_2026 if e != "River"]))
    es_local = c2.radio("📍 Condición", ["Monumental 🏟️", "Visitante ✈️"], horizontal=True) == "Monumental 🏟️"

    df_p = df_plantilla.sort_values("Minutos", ascending=False)
    opciones = [f"{r.Jugador} ({r.Posicion})" for _, r in df_p.iterrows()]
    titulares_raw = st.multiselect("👥 Armá tu XI Titular:", opciones, default=opciones[:11], max_selections=11)
    titulares = [re.sub(r"\s*\(.*\)$", "", t).strip() for t in titulares_raw]

    if st.button("🚀 SIMULAR PARTIDO", use_container_width=True, type="primary", disabled=len(titulares)!=11):
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"### 📊 Resultado Probable: River vs {rival_sel}")
        k1, k2, k3, k4, k5 = st.columns(5)
        for c, l, v, t in [(k1,"Victoria",f"{sim['prob_victoria']*100:.1f}%",""), (k2,"Empate",f"{sim['prob_empate']*100:.1f}%","empate"), (k3,"Derrota",f"{sim['prob_derrota']*100:.1f}%","derrota"), (k4,"λ River",f"{lr:.2f}",""), (k5,"λ Rival",f"{lv:.2f}","")]:
            c.markdown(f'<div class="pred-kpi {t}"><div class="label">{l}</div><div class="valor">{v}</div></div>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["📊 Probabilidades", "⚽ Posibles Goleadores", "🎯 Marcadores", "🔬 Análisis XI"])
        
        with t1:
            fig = go.Figure(go.Bar(x=[sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100], y=["Victoria River", "Empate", "Derrota River"], orientation="h", marker_color=[RED, "#9CA3AF", "#1A4A8B"], text=[f"{v*100:.1f}%" for v in [sim["prob_victoria"], sim["prob_empate"], sim["prob_derrota"]]], textposition="outside"))
            fig.update_layout(height=260, showlegend=False, font=dict(family="Rajdhani"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)
            if apply_plotly_style_fn: apply_plotly_style_fn(fig)
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            st.markdown("<div style='font-family:Bebas Neue;font-size:22px;color:#1F2937;margin-bottom:12px;'>🏆 PROBABILIDAD DE GOL POR JUGADOR</div>", unsafe_allow_html=True)
            df_g = obtener_tabla_goleadores(titulares, df_plantilla, lr)
            st.dataframe(df_g.rename(columns={"xG_p90": "xG/90"}), use_container_width=True, hide_index=True)

        with t3:
            z = np.zeros((7,7))
            for _, r in sim["df_resultados"].iterrows(): 
                if r.River < 7 and r.Rival < 7: z[int(r.Rival)][int(r.River)] = r.prob * 100
            fig_h = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale="Reds"))
            fig_h.update_layout(title="Mapa de Marcadores", xaxis_title="River", yaxis_title=rival_sel, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)
            if apply_plotly_style_fn: apply_plotly_style_fn(fig_h)
            st.plotly_chart(fig_h, use_container_width=True)
            
        with t4:
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)][["Jugador","Posicion","Nota","xG_p90","xGA_p90"]].sort_values("Posicion"), use_container_width=True, hide_index=True)
