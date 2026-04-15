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

# Lista maestra para asegurar que siempre aparezcan los 30 de Primera
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
# MÓDULO 1 ── DATA LIGA (WEB SCRAPING + FALLBACK)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga() -> tuple[pd.DataFrame, bool]:
    """Obtiene la tabla de posiciones de internet o usa el backup de 30 equipos."""
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
        
        # Filtramos para que solo queden los 30 oficiales
        df_liga = df_liga[df_liga["equipo"].isin(EQUIPOS_PRIMERA_2026)]
        
        for c in ["PJ", "GF", "GC"]: 
            df_liga[c] = pd.to_numeric(df_liga[c], errors="coerce")
        
        if len(df_liga) > 15:
            return df_liga.reset_index(drop=True), True
        else:
            raise ValueError("Tabla incompleta")
    except:
        # Plan B: Datos estimados para los 30 equipos si falla internet
        data = [{"equipo": e, "PJ": 20, "GF": 24, "GC": 24} for e in EQUIPOS_PRIMERA_2026]
        df_fb = pd.DataFrame(data)
        # Ajuste manual rápido de potencias para el fallback
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

    # Filtro de 1 minuto para que aparezcan TODOS
    agg = agg[agg["Minutos"] >= 1].copy() 
    
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    # Suavizamos la forma para que no inflote tanto los porcentajes
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.8, 1.2) 
    
    return agg.reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── LÓGICA MATEMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    
    # Datos Rival
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    fa_rival = (r_data["GF"] / r_data["PJ"]) / mgf
    fd_rival = (r_data["GC"] / r_data["PJ"]) / mgf
    
    # Datos River
    riv_base = df_liga[df_liga["equipo"] == "River Plate"].iloc[0]
    fa_river = (riv_base["GF"] / riv_base["PJ"]) / mgf
    fd_river = (riv_base["GC"] / riv_base["PJ"]) / mgf
    
    # Ajuste por XI
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    # Suavizado de impacto del XI para realismo
    mult_atk = (df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() + 1) / 2
    mult_def = (df_xi["xGA_p90"].mean() / df_plantilla["xGA_p90"].mean() + 1) / 2
    forma    = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.5)

    # Localía 15% (Equilibrada)
    VENTAJA = 1.15
    f_river = VENTAJA if es_local else 1.0
    f_rival = 1.0 if es_local else VENTAJA

    lam_r = fa_river * mult_atk * (1/max(fd_rival, 0.4)) * mgf * forma * f_river
    lam_v = fa_rival * (1/max(fd_river * mult_def, 0.4)) * mgf * (1/forma) * f_rival
    
    return round(float(np.clip(lam_r, 0.4, 5.0)), 3), round(float(np.clip(lam_v, 0.4, 5.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr = rng.poisson(lam_r, MONTECARLO_N)
    gv = rng.poisson(lam_v, MONTECARLO_N)
    
    # Parche Dixon-Coles (Ajuste de Empates al 30%)
    for i in range(MONTECARLO_N):
        if ((gr[i]==1 and gv[i]==0) or (gr[i]==0 and gv[i]==1)) and rng.random() < 0.28:
            gr[i], gv[i] = 1, 1

    prob_w = float(np.mean(gr > gv))
    prob_d = float(np.mean(gr == gv))
    prob_l = float(np.mean(gr < gv))
    
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": float(np.mean((gr==r) & (gv==v)))})
            
    return {
        "prob_victoria": prob_w, 
        "prob_empate": prob_d, 
        "prob_derrota": prob_l, 
        "df_resultados": pd.DataFrame(res), 
        "goles_river": gr, 
        "goles_rival": gv,
        "lambda_r": lam_r,
        "lambda_v": lam_v,
        "n": MONTECARLO_N
    }

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── VISUALIZACIONES (PLOTLY)
# ─────────────────────────────────────────────────────────────────────────────

def fig_barras_1x2(sim, rival):
    cats = ["Victoria River", "Empate", f"Victoria {rival}"]
    vals = [sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100]
    cols = [RED, "#9CA3AF", "#1A4A8B"]
    fig = go.Figure(go.Bar(x=vals, y=cats, orientation='h', marker_color=cols, text=[f"{v:.1f}%" for v in vals], textposition='outside'))
    fig.update_layout(title="Probabilidades 1X2", margin=dict(l=20, r=20, t=40, b=20), height=250, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def fig_heatmap(sim, rival):
    z = np.zeros((7, 7))
    for _, row in sim["df_resultados"].iterrows():
        r, v = int(row["River"]), int(row["Rival"])
        if r < 7 and v < 7: z[v][r] = row["prob"] * 100
    fig = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], colorscale="Reds"))
    fig.update_layout(title="Resultados Exactos (River en columnas)", height=400, xaxis_title="Goles River", yaxis_title=f"Goles {rival}")
    return fig

def fig_distribucion(sim, rival):
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=sim["goles_river"], name="River", marker_color=RED, histnorm='percent'))
    fig.add_trace(go.Histogram(x=sim["goles_rival"], name=rival, marker_color=GRAY, histnorm='percent'))
    fig.update_layout(title="Distribución de Goles", barmode='group', height=350)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 5 ── RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    with st.spinner("Analizando datos..."):
        df_liga, real = obtener_estadisticas_liga()
        df_plantilla = extraer_plantilla_river(str(ruta_excel))
    
    if df_plantilla.empty:
        st.error("No se encontraron jugadores en el Excel.")
        return

    st.markdown(f'<div class="badge-datos">✅ {len(df_plantilla)} jugadores disponibles · {"🌐 Datos en vivo" if real else "📂 Modo Local"}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        rival_sel = st.selectbox("🆚 Seleccioná el rival", sorted([e for e in df_liga["equipo"] if e != "River Plate"]))
    with col2:
        es_local = st.radio("📍 Condición de River", ["Local", "Visitante"], horizontal=True) == "Local"

    st.markdown("### 👥 Armar XI Titular")
    df_p = df_plantilla.sort_values("Minutos", ascending=False)
    opciones = [f"{row.Jugador} ({row.Posicion})" for _, row in df_p.iterrows()]
    
    # XI Sugerido
    seleccionados_raw = st.multiselect("Jugadores:", opciones, default=opciones[:11], max_selections=11)
    titulares = [s.split(" (")[0] for s in seleccionados_raw]

    if len(titulares) == 11:
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"#### 📊 Probabilidades: River vs {rival_sel}")
        st.plotly_chart(fig_barras_1x2(sim, rival_sel), use_container_width=True)
        
        t1, t2, t3 = st.tabs(["🎯 Marcadores", "📈 Goles", "🔬 XI Titular"])
        with t1:
            st.plotly_chart(fig_heatmap(sim, rival_sel), use_container_width=True)
        with t2:
            st.plotly_chart(fig_distribucion(sim, rival_sel), use_container_width=True)
        with t3:
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)], hide_index=True)
            st.write(f"**Goles Esperados (λ):** River {lr:.2f} - {rival_sel} {lv:.2f}")
    else:
        st.info("👆 Seleccioná exactamente 11 jugadores para activar la simulación.")
