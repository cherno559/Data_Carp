import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y LISTA OFICIAL
# ─────────────────────────────────────────────────────────────────────────────

MONTECARLO_N = 10_000

EQUIPOS_PRIMERA_2026 = [
    "River Plate", "Boca Juniors", "Racing Club", "Independiente", "San Lorenzo",
    "Huracán", "Vélez Sársfield", "Talleres (C)", "Estudiantes (LP)", "Lanús",
    "Rosario Central", "Newell's Old Boys", "Argentinos Juniors", "Defensa y Justicia",
    "Godoy Cruz", "Platense", "Belgrano", "Instituto", "Unión", "Banfield",
    "Gimnasia (LP)", "Atlético Tucumán", "Central Córdoba", "Barracas Central",
    "Tigre", "Sarmiento", "Independiente Rivadavia", "Deportivo Riestra",
    "San Martín (T)", "Aldosivi"
]

RED     = "#D0021B"
GRAY    = "#374151"
GOLD    = "#C9A84C"
LIGHT_B = "rgba(249,250,251,1)"

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── DATA LIGA Y PLANTILLA
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga() -> tuple[pd.DataFrame, bool]:
    URL = "https://fbref.com/es/comps/21/Liga-Argentina-Stats"
    try:
        tablas = pd.read_html(URL, attrs={"id": "results"})
        df = tablas[0]
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(c).strip() for c in df.columns]
        
        col_map = {}
        for col in df.columns:
            c_low = col.lower()
            if any(k in c_low for k in ["squad", "equipo"]): col_map["equipo"] = col
            elif any(k in c_low for k in ["mp", "pj"]): col_map["PJ"] = col
            elif any(k in c_low for k in ["gf", "f"]): col_map["GF"] = col
            elif any(k in c_low for k in ["ga", "gc"]): col_map["GC"] = col

        df_liga = df[[col_map["equipo"], col_map["PJ"], col_map["GF"], col_map["GC"]]].copy()
        df_liga.columns = ["equipo", "PJ", "GF", "GC"]
        df_liga = df_liga[df_liga["equipo"].isin(EQUIPOS_PRIMERA_2026)]
        
        for c in ["PJ", "GF", "GC"]: 
            df_liga[c] = pd.to_numeric(df_liga[c], errors="coerce")
        
        return df_liga.reset_index(drop=True), True
    except:
        data = [{"equipo": e, "PJ": 20, "GF": 20, "GC": 20} for e in EQUIPOS_PRIMERA_2026]
        return pd.DataFrame(data), False

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
        Nota     = ("Nota SofaScore", lambda x: x[x>0].mean() if not x[x>0].empty else 6.5),
        Goles    = ("Goles", "sum"),
        Inter    = ("Intercepciones", "sum")
    )
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.8, 1.2) 
    return agg[agg["Minutos"] >= 1].reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── LÓGICA DE CÁLCULO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    riv_base = df_liga[df_liga["equipo"] == "River Plate"].iloc[0]
    
    fa_rival = (r_data["GF"] / r_data["PJ"]) / mgf
    fd_rival = (r_data["GC"] / r_data["PJ"]) / mgf
    fa_river = (riv_base["GF"] / riv_base["PJ"]) / mgf
    fd_river = (riv_base["GC"] / riv_base["PJ"]) / mgf
    
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    mult_atk = 1.0 + ((df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() - 1.0) * 0.4)
    mult_def = 1.0 + ((df_xi["xGA_p90"].mean() / df_plantilla["xGA_p90"].mean() - 1.0) * 0.4)
    forma    = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.4)

    V = 1.15
    lam_r = fa_river * mult_atk * fd_rival * mgf * forma * (V if es_local else 1.0)
    lam_v = fa_rival * (fd_river / max(mult_def, 0.2)) * mgf * (1/forma) * (1.0 if es_local else V)
    return round(float(np.clip(lam_r, 0.2, 6.0)), 3), round(float(np.clip(lam_v, 0.2, 6.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr = rng.poisson(lam_r, MONTECARLO_N)
    gv = rng.poisson(lam_v, MONTECARLO_N)
    for i in range(MONTECARLO_N):
        if ((gr[i]==1 and gv[i]==0) or (gr[i]==0 and gv[i]==1)) and rng.random() < 0.28:
            gr[i], gv[i] = 1, 1
    
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": float(np.mean((gr==r) & (gv==v)))})
            
    return {"prob_victoria": float(np.mean(gr > gv)), "prob_empate": float(np.mean(gr == gv)), 
            "prob_derrota": float(np.mean(gr < gv)), "df_resultados": pd.DataFrame(res), 
            "goles_river": gr, "goles_rival": gv, "lambda_r": lam_r, "lambda_v": lam_v, "n": MONTECARLO_N}

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── VISUALIZACIONES Y CRÓNICA
# ─────────────────────────────────────────────────────────────────────────────

def fig_barras_1x2(sim, rival, style_fn):
    cats, vals, cols = ["Victoria River", "Empate", "Derrota River"], [sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100], [RED, "#9CA3AF", "#1A4A8B"]
    fig = go.Figure(go.Bar(x=vals, y=cats, orientation="h", marker_color=cols, text=[f"{v:.1f}%" for v in vals], textposition="outside", textfont=dict(family="Bebas Neue", size=18)))
    fig.update_layout(font=dict(family="Rajdhani"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B, height=260, showlegend=False, title=f"Probabilidades vs {rival}")
    if style_fn: style_fn(fig)
    return fig

def obtener_tabla_goleadores(titulares, df_plantilla, lam_r):
    """Calcula la probabilidad individual de gol de cada titular."""
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
    
    # Probabilidad individual basada en xG_p90 respecto al Lambda esperado de River
    total_xg = df_xi["xG_p90"].sum() if df_xi["xG_p90"].sum() > 0 else 1
    
    df_xi["Prob. Gol"] = (df_xi["xG_p90"] / total_xg) * (1 - np.exp(-lam_r))
    df_xi["Prob. Gol"] = (df_xi["Prob. Gol"] * 100).round(1)
    
    return df_xi[["Jugador", "Posicion", "xG_p90", "Prob. Gol"]].sort_values("Prob. Gol", ascending=False)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""<style>
    .pred-kpi { background: #111827; border-left: 4px solid #D0021B; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 10px; }
    .pred-kpi .label { font-family: 'Rajdhani'; font-size: 10px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1.5px; }
    .pred-kpi .valor { font-family: 'Bebas Neue'; font-size: 42px; color: #D0021B; line-height: 1; }
    .pred-kpi.empate .valor { color: #9CA3AF; } .pred-kpi.derrota .valor { color: #1A4A8B; }
    </style>""", unsafe_allow_html=True)

    df_liga, _ = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))
    
    c1, c2 = st.columns([2,1])
    rival_sel = c1.selectbox("🆚 Seleccioná el Rival", sorted([e for e in df_liga["equipo"] if e != "River Plate"]))
    es_local = c2.radio("📍 Condición", ["Monumental 🏟️", "Visitante ✈️"], horizontal=True) == "Monumental 🏟️"

    df_p = df_plantilla.sort_values("Minutos", ascending=False)
    opciones = [f"{r.Jugador} ({r.Posicion})" for _, r in df_p.iterrows()]
    titulares_raw = st.multiselect("👥 Elegí el XI Titular:", opciones, default=opciones[:11], max_selections=11)
    titulares = [t.split(" (")[0] for t in titulares_raw]

    if st.button("🚀 INICIAR SIMULACIÓN", use_container_width=True, type="primary", disabled=len(titulares)!=11):
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"### 📊 Análisis Predictivo: River vs {rival_sel}")
        k1, k2, k3, k4, k5 = st.columns(5)
        for c, l, v, t in [(k1,"Victoria",f"{sim['prob_victoria']*100:.1f}%",""), (k2,"Empate",f"{sim['prob_empate']*100:.1f}%","empate"), (k3,"Derrota",f"{sim['prob_derrota']*100:.1f}%","derrota"), (k4,"λ River",f"{lr:.2f}",""), (k5,"λ Rival",f"{lv:.2f}","")]:
            c.markdown(f'<div class="pred-kpi {t}"><div class="label">{l}</div><div class="valor">{v}</div></div>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["📊 Probabilidades", "🎯 Resultados Exactos", "⚽ Posibles Goleadores", "🔬 Detalle XI"])
        
        with t1: 
            st.plotly_chart(fig_barras_1x2(sim, rival_sel, apply_plotly_style_fn), use_container_width=True)
            
        with t2:
            z = np.zeros((7,7))
            for _, r in sim["df_resultados"].iterrows(): 
                if r.River < 7 and r.Rival < 7: z[int(r.Rival)][int(r.River)] = r.prob * 100
            fig_h = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale="Reds"))
            fig_h.update_layout(title="Mapa de Marcadores", xaxis_title="River", yaxis_title=rival_sel, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)
            if apply_plotly_style_fn: apply_plotly_style_fn(fig_h)
            st.plotly_chart(fig_h, use_container_width=True)
            
        with t3:
            st.markdown("<div style='font-family:Bebas Neue,cursive;font-size:20px;color:#1F2937;letter-spacing:2px;margin-bottom:12px;'>🏆 PROBABILIDAD INDIVIDUAL DE GOL</div>", unsafe_allow_html=True)
            df_goles = obtener_tabla_goleadores(titulares, df_plantilla, lr)
            st.dataframe(df_goles.rename(columns={"xG_p90": "xG/90", "Prob. Gol": "% Prob. Gol"}), use_container_width=True, hide_index=True)
            st.info("💡 Calculado en base al xG/90 histórico de cada jugador y la debilidad defensiva del rival.")

        with t4:
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)][["Jugador","Posicion","Nota","xG_p90","xGA_p90"]].sort_values("Posicion"), use_container_width=True, hide_index=True)
