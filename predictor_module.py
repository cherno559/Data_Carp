import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y LISTA OFICIAL 30 EQUIPOS
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
# MÓDULO 1 ── DATA LIGA (WEB SCRAPING)
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
        df_fb = pd.DataFrame(data)
        df_fb.loc[df_fb["equipo"] == "River Plate", ["GF", "GC"]] = [32, 14]
        df_fb.loc[df_fb["equipo"] == "Boca Juniors", ["GF", "GC"]] = [28, 18]
        return df_fb, False

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── DATA PLANTILLA (TU EXCEL)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def extraer_plantilla_river(ruta_excel_str: str) -> pd.DataFrame:
    ruta = Path(ruta_excel_str)
    if not ruta.exists(): return pd.DataFrame()
    xl = pd.ExcelFile(ruta)
    hojas_omitir = {"Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"}
    filas = []

    for hoja in xl.sheet_names:
        if hoja in hojas_omitir: continue
        try:
            df_h = pd.read_excel(ruta, sheet_name=hoja)
            df_h.columns = df_h.columns.astype(str).str.strip()
            if "Jugador" not in df_h.columns: continue
            df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
            df_h["Minutos"] = pd.to_numeric(df_h.get("Minutos", 0), errors="coerce").fillna(0)
            df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
            df_h["Partido"] = hoja
            filas.append(df_h)
        except: continue

    if not filas: return pd.DataFrame()
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
    agg = agg[agg["Minutos"] >= 1].copy() # Aparecen todos
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.8, 1.2) 
    return agg.reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── LÓGICA DE SIMULACIÓN
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

def generar_cronica_partido(sim, titulares, df_plantilla, rival):
    top = sim["df_resultados"].sort_values("prob", ascending=False).iloc[0]
    gr, gv = int(top["River"]), int(top["Rival"])
    cronica = []
    if gr > 0:
        df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
        df_xi["p"] = (df_xi["xG_p90"] + 0.05) / (df_xi["xG_p90"] + 0.05).sum()
        gols = np.random.choice(df_xi["Jugador"], size=gr, p=df_xi["p"])
        mins = sorted(np.random.randint(2, 89, size=gr))
        for m, j in zip(mins, gols): cronica.append({"Min": m, "Txt": f"🔴 ¡GOL de River! {j}."})
    if gv > 0:
        mins = sorted(np.random.randint(2, 89, size=gv))
        for m in mins: cronica.append({"Min": m, "Txt": f"⚽ Gol de {rival}."})
    return gr, gv, sorted(cronica, key=lambda x: x["Min"])

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── GRÁFICOS (ESTILO ORIGINAL)
# ─────────────────────────────────────────────────────────────────────────────

_ST = dict(font=dict(family="Rajdhani", size=13), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)

def fig_barras_1x2(sim, rival, style_fn):
    fig = go.Figure()
    cats, vals, cols = ["Victoria River", "Empate", "Derrota River"], [sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100], [RED, "#9CA3AF", "#1A4A8B"]
    for cat, val, col in zip(cats, vals, cols):
        fig.add_trace(go.Bar(x=[val], y=[cat], orientation="h", marker_color=col, text=[f"{val:.1f}%"], textposition="outside", textfont=dict(family="Bebas Neue", size=18)))
    fig.update_layout(**_ST, title=f"Probabilidades vs {rival}", height=260, showlegend=False)
    if style_fn: style_fn(fig)
    return fig

def fig_heatmap(sim, rival, style_fn):
    z = np.zeros((7,7))
    for _, r in sim["df_resultados"].iterrows(): 
        if r.River < 7 and r.Rival < 7: z[int(r.Rival)][int(r.River)] = r.prob * 100
    fig = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale="Reds"))
    fig.update_layout(**_ST, title="Marcadores Probables", xaxis_title="River", yaxis_title=rival, height=450)
    if style_fn: style_fn(fig)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 5 ── RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""<style>
    .pred-kpi { background: #111827; border-left: 4px solid #D0021B; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 10px; }
    .pred-kpi .label { font-family: 'Rajdhani'; font-size: 10px; color: #9CA3AF; letter-spacing: 1px; }
    .pred-kpi .valor { font-family: 'Bebas Neue'; font-size: 38px; color: #D0021B; }
    .pred-kpi.empate .valor { color: #9CA3AF; } .pred-kpi.derrota .valor { color: #1A4A8B; }
    </style>""", unsafe_allow_html=True)

    df_liga, _ = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))
    
    col1, col2 = st.columns([2,1])
    rival_sel = col1.selectbox("🆚 Rival", sorted([e for e in df_liga["equipo"] if e != "River Plate"]))
    es_local = col2.radio("📍 Estadio", ["Monumental 🏟️", "Visitante ✈️"], horizontal=True) == "Monumental 🏟️"

    df_p = df_plantilla.sort_values("Minutos", ascending=False)
    titulares_raw = st.multiselect("👥 Seleccioná el XI Titular:", [f"{r.Jugador} ({r.Posicion})" for _, r in df_p.iterrows()], default=[f"{r.Jugador} ({r.Posicion})" for _, r in df_p.head(11).iterrows()], max_selections=11)
    titulares = [t.split(" (")[0] for t in titulares_raw]

    if st.button("🚀 SIMULAR PARTIDO", use_container_width=True, type="primary", disabled=len(titulares)!=11):
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"### 📊 River Plate vs {rival_sel}")
        k1, k2, k3, k4, k5 = st.columns(5)
        for c, l, v, t in [(k1,"VICTORIA",f"{sim['prob_victoria']*100:.1f}%",""), (k2,"EMPATE",f"{sim['prob_empate']*100:.1f}%","empate"), (k3,"DERROTA",f"{sim['prob_derrota']*100:.1f}%","derrota"), (k4,"λ RIVER",f"{lr:.2f}",""), (k5,"λ RIVAL",f"{lv:.2f}","")]:
            c.markdown(f'<div class="pred-kpi {t}"><div class="label">{l}</div><div class="valor">{v}</div></div>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["🎯 Probabilidades", "📈 Distribución", "📋 XI Titular", "🔮 Crónica"])
        with t1: st.plotly_chart(fig_barras_1x2(sim, rival_sel, apply_plotly_style_fn), use_container_width=True)
        with t2: st.plotly_chart(fig_heatmap(sim, rival_sel, apply_plotly_style_fn), use_container_width=True)
        with t3: st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)][["Jugador","Posicion","Nota","xG_p90"]], use_container_width=True, hide_index=True)
        with t4:
            gr, gv, cron = generar_cronica_partido(sim, titulares, df_plantilla, rival_sel)
            st.markdown(f"<h3 style='text-align:center'>{gr} - {gv}</h3>", unsafe_allow_html=True)
            for e in cron: st.write(f"**{e['Min']}'** | {e['Txt']}")
