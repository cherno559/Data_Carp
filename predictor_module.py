import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

MONTECARLO_N = 10_000

POS_GRUPO = {
    "Arquero":       "GK",
    "Defensor":      "DEF",
    "Mediocampista": "MID",
    "Delantero":     "FWD",
}

RED     = "#D0021B"
GRAY    = "#374151"
GOLD    = "#C9A84C"
LIGHT_B = "rgba(249,250,251,1)"

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── DATA MACRO: EXTRACCIÓN DESDE INTERNET (WEB SCRAPING)
# ─────────────────────────────────────────────────────────────────────────────

# Promedios históricos por si falla la conexión a internet (Fallback)
FALLBACK_LIGA = {
    "River Plate": {"PJ": 20, "GF": 32, "GC": 14}, "Boca Juniors": {"PJ": 20, "GF": 28, "GC": 18},
    "Racing Club": {"PJ": 20, "GF": 26, "GC": 20}, "Independiente": {"PJ": 20, "GF": 22, "GC": 24},
    "San Lorenzo": {"PJ": 20, "GF": 20, "GC": 25}, "Estudiantes": {"PJ": 20, "GF": 21, "GC": 19},
    "Vélez Sársfield": {"PJ": 20, "GF": 24, "GC": 22}, "Talleres": {"PJ": 20, "GF": 23, "GC": 21},
    "Huracán": {"PJ": 20, "GF": 18, "GC": 23}, "Lanús": {"PJ": 20, "GF": 17, "GC": 22},
    "Argentinos Juniors": {"PJ": 20, "GF": 19, "GC": 20}, "Defensa y Justicia": {"PJ": 20, "GF": 16, "GC": 21},
    "Rosario Central": {"PJ": 20, "GF": 20, "GC": 22}, "Newell's Old Boys": {"PJ": 20, "GF": 18, "GC": 23},
    "Godoy Cruz": {"PJ": 20, "GF": 17, "GC": 24}, "Platense": {"PJ": 20, "GF": 14, "GC": 26},
    "Belgrano": {"PJ": 20, "GF": 18, "GC": 20}, "Instituto": {"PJ": 20, "GF": 19, "GC": 21},
    "Banfield": {"PJ": 20, "GF": 15, "GC": 22}, "Barracas Central": {"PJ": 20, "GF": 14, "GC": 25},
    "Tigre": {"PJ": 20, "GF": 12, "GC": 28}, "Sarmiento": {"PJ": 20, "GF": 15, "GC": 24}
}

@st.cache_data(ttl=86400) # Se actualiza una vez al día para evitar bloqueos
def obtener_estadisticas_liga() -> tuple[pd.DataFrame, bool]:
    """Descarga la tabla de la liga desde internet para conocer la fuerza real de los rivales."""
    URLS_CANDIDATAS = [
        "https://fbref.com/es/comps/21/Liga-Argentina-Stats",
        "https://fbref.com/en/comps/21/Argentine-Primera-Division-Stats",
    ]
    
    for url in URLS_CANDIDATAS:
        try:
            tablas = pd.read_html(url, attrs={"id": "results"})
            if not tablas: continue
            
            df_raw = tablas[0]
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = [" ".join(c).strip() for c in df_raw.columns]
                
            col_map = {}
            for col in df_raw.columns:
                col_lower = col.lower()
                if any(k in col_lower for k in ["squad", "club", "equipo", "team"]): col_map["equipo"] = col
                elif col_lower in ["mp", "pj", "pl", "played"]: col_map["PJ"] = col
                elif col_lower in ["gf", "f", "for"]: col_map["GF"] = col
                elif col_lower in ["ga", "gc", "against", "en contra"]: col_map["GC"] = col
                
            if len(col_map) < 4: continue
            
            df_liga = df_raw[[col_map["equipo"], col_map["PJ"], col_map["GF"], col_map["GC"]]].copy()
            df_liga.columns = ["equipo", "PJ", "GF", "GC"]
            df_liga = df_liga.dropna()
            for c in ["PJ", "GF", "GC"]: df_liga[c] = pd.to_numeric(df_liga[c], errors="coerce")
            df_liga = df_liga.dropna().reset_index(drop=True)
            
            if len(df_liga) >= 10:
                return df_liga, True # Conexión exitosa
        except Exception:
            continue

    # Si no hay internet o falla la página, usa los promedios guardados
    registros = [{"equipo": eq, "PJ": v["PJ"], "GF": v["GF"], "GC": v["GC"]} for eq, v in FALLBACK_LIGA.items()]
    return pd.DataFrame(registros), False

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1B ── DATA MICRO: EXTRACCIÓN DE LA PLANTILLA DE RIVER (TU EXCEL)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def extraer_plantilla_river(ruta_excel_str: str) -> pd.DataFrame:
    """Lee tu Excel SOLO para armar el perfil de rendimiento de los jugadores de River."""
    ruta = Path(ruta_excel_str)
    if not ruta.exists(): return pd.DataFrame()
    try: xl = pd.ExcelFile(ruta)
    except: return pd.DataFrame()

    hojas_omitir = {"Promedios Generales", "Goleadores", "Asistidores", "Resumen Estadísticas"}
    filas_jugadores = []

    for hoja in xl.sheet_names:
        if hoja in hojas_omitir: continue
        try:
            df_hoja = pd.read_excel(ruta, sheet_name=hoja)
            df_hoja.columns = df_hoja.columns.astype(str).str.strip()
        except: continue

        if "Jugador" not in df_hoja.columns: continue

        df_hoja["Jugador"] = df_hoja["Jugador"].fillna("").astype(str).str.strip().str.title()
        df_hoja["Jugador"] = df_hoja["Jugador"].apply(lambda x: re.sub(r"\s+", " ", x))
        df_hoja["Minutos"] = pd.to_numeric(df_hoja.get("Minutos", 0), errors="coerce").fillna(0)

        df_hoja = df_hoja[(df_hoja["Jugador"] != "") & (df_hoja["Jugador"].str.lower() != "nan") & (df_hoja["Minutos"] > 0)].copy()
        df_hoja["Partido"] = hoja
        filas_jugadores.append(df_hoja)

    if not filas_jugadores: return pd.DataFrame()

    df_todos = pd.concat(filas_jugadores, ignore_index=True)
    cols_num = ["Goles", "Asistencias", "Pases Clave", "Quites (Tackles)", "Intercepciones", "Tiros Totales", "Tiros al Arco"]
    for col in cols_num:
        df_todos[col] = pd.to_numeric(df_todos.get(col, 0), errors="coerce").fillna(0)

    if "Nota SofaScore" in df_todos.columns:
        df_todos["Nota SofaScore"] = pd.to_numeric(df_todos["Nota SofaScore"], errors="coerce")
        df_todos = df_todos[df_todos["Nota SofaScore"] != 0]

    agg = df_todos.groupby("Jugador", as_index=False).agg(
        Posicion    = ("Posición", lambda x: x.mode()[0] if not x.mode().empty else "—"),
        Minutos     = ("Minutos", "sum"),
        Partidos    = ("Partido", "nunique"),
        Nota        = ("Nota SofaScore", "mean"),
        Goles       = ("Goles", "sum"),
        Asistencias = ("Asistencias", "sum"),
        PasesClave  = ("Pases Clave", "sum"),
        Quites      = ("Quites (Tackles)", "sum"),
        Intercepciones = ("Intercepciones", "sum")
    )

    agg = agg[agg["Minutos"] >= 90].copy()
    mins = agg["Minutos"].replace(0, 1)
    agg["xG_p90"]  = (agg["Goles"] / mins * 90).round(3)
    agg["xGA_p90"] = (agg["Intercepciones"] / mins * 90).round(3)
    agg["forma"]   = (agg["Nota"].fillna(7.0) / 7.0).round(3)
    agg["forma"]   = agg["forma"].clip(0.6, 1.5)

    return agg.reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── CÁLCULO DE FUERZAS (Poisson)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_medias(df_liga: pd.DataFrame) -> dict:
    df = df_liga[df_liga["PJ"] > 0].copy()
    df["gf_pp"] = df["GF"] / df["PJ"]
    df["gc_pp"] = df["GC"] / df["PJ"]
    return {"mgf": float(df["gf_pp"].mean()), "mgc": float(df["gc_pp"].mean())}

def calcular_fuerzas(df_liga: pd.DataFrame, rival: str, medias: dict) -> dict:
    fila_rival = df_liga[df_liga["equipo"].str.contains(rival, case=False, na=False)]
    if fila_rival.empty:
        fa_rival, fd_rival = 1.0, 1.0
    else:
        r = fila_rival.iloc[0]
        pj = max(r["PJ"], 1)
        fa_rival = (r["GF"] / pj) / max(medias["mgf"], 0.01)
        fd_rival = (r["GC"] / pj) / max(medias["mgc"], 0.01)

    fila_river = df_liga[df_liga["equipo"].str.contains("River", case=False, na=False)]
    if fila_river.empty:
        fa_river, fd_river = 1.15, 0.80
    else:
        rv = fila_river.iloc[0]
        pj = max(rv["PJ"], 1)
        fa_river = (rv["GF"] / pj) / max(medias["mgf"], 0.01)
        fd_river = (rv["GC"] / pj) / max(medias["mgc"], 0.01)

    return {"fa_rival": float(fa_rival), "fd_rival": float(fd_rival), "fa_river": float(fa_river), "fd_river": float(fd_river)}

def calcular_multiplicador(titulares: list[str], df_plantilla: pd.DataFrame) -> dict:
    if not titulares or df_plantilla.empty: return {"mult_atk": 1.0, "mult_def": 1.0, "forma_prom": 1.0}
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
    if df_xi.empty: return {"mult_atk": 1.0, "mult_def": 1.0, "forma_prom": 1.0}

    def media_segura(serie):
        val = serie.replace(0, np.nan).mean()
        return val if not pd.isna(val) else 0.001

    ref_xg  = media_segura(df_plantilla[df_plantilla["Posicion"].isin(["Delantero", "Mediocampista"])]["xG_p90"])
    ref_xga = media_segura(df_plantilla[df_plantilla["Posicion"].isin(["Defensor", "Arquero"])]["xGA_p90"])

    xi_atk = df_xi[df_xi["Posicion"].isin(["Delantero", "Mediocampista"])]
    xi_def = df_xi[df_xi["Posicion"].isin(["Defensor", "Arquero"])]

    mult_atk = media_segura(xi_atk["xG_p90"]) / ref_xg if not xi_atk.empty else 1.0
    mult_def = media_segura(xi_def["xGA_p90"]) / ref_xga if not xi_def.empty else 1.0
    forma_prom = float(df_xi["forma"].mean()) if not df_xi["forma"].isna().all() else 1.0

    return {"mult_atk": float(np.clip(mult_atk * forma_prom, 0.55, 1.65)), "mult_def": float(np.clip(mult_def * forma_prom, 0.55, 1.65)), "forma_prom": forma_prom}

def calcular_lambdas(fuerzas: dict, mults: dict, medias: dict, es_local: bool) -> tuple[float, float]:
    FACTOR_LOCAL = 1.08 if es_local else 1.00
    fa_river_adj = fuerzas["fa_river"] * mults["mult_atk"]
    fd_river_adj = fuerzas["fd_river"] * (1 / max(mults["mult_def"], 0.1))

    lambda_r = fa_river_adj * (1 / max(fuerzas["fd_rival"], 0.4)) * medias["mgf"] * FACTOR_LOCAL
    lambda_v = fuerzas["fa_rival"] * (1 / max(fd_river_adj, 0.4)) * medias["mgf"]

    return round(float(np.clip(lambda_r, 0.2, 6.0)), 4), round(float(np.clip(lambda_v, 0.2, 6.0)), 4)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── SIMULACIÓN MONTECARLO (vectorizada)
# ─────────────────────────────────────────────────────────────────────────────

def simular_montecarlo(lambda_r: float, lambda_v: float, n: int = MONTECARLO_N, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    goles_r = rng.poisson(lam=lambda_r, size=n)
    goles_v = rng.poisson(lam=lambda_v, size=n)

    wins = int(np.sum(goles_r > goles_v)); draws = int(np.sum(goles_r == goles_v)); losses = int(np.sum(goles_r < goles_v))

    MAX_G = 6
    resultados = [{"River": r, "Rival": v, "prob": float(np.mean((goles_r == r) & (goles_v == v)))} for r in range(MAX_G + 1) for v in range(MAX_G + 1)]

    return {"prob_victoria": wins/n, "prob_empate": draws/n, "prob_derrota": losses/n, "goles_river": goles_r, "goles_rival": goles_v, "df_resultados": pd.DataFrame(resultados), "lambda_r": lambda_r, "lambda_v": lambda_v, "n": n}

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── GRÁFICOS PLOTLY
# ─────────────────────────────────────────────────────────────────────────────
_PLOTLY_BASE = dict(
    font=dict(family="Rajdhani, Inter, sans-serif", size=13, color="#1F2937"),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B,
    margin=dict(l=16, r=16, t=40, b=16),
    title_font=dict(family="Bebas Neue, cursive", size=22, color="#1F2937"),
    hoverlabel=dict(bgcolor="#111827", bordercolor=RED, font_color="white", font_family="Rajdhani", font_size=13),
)

def fig_barras_1x2(sim: dict, rival: str) -> go.Figure:
    cats = [f"Victoria River", "Empate", f"Derrota River"]
    vals = [sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100]
    cols = [RED, "#9CA3AF", "#1A4A8B"]
    fig = go.Figure()
    for cat, val, col in zip(cats, vals, cols):
        fig.add_trace(go.Bar(x=[val], y=[cat], orientation="h", marker_color=col, text=[f"{val:.1f}%"], textposition="outside", textfont=dict(family="Bebas Neue", size=18, color=col), hovertemplate=f"<b>{cat}</b>: {val:.1f}%<extra></extra>"))
    fig.add_vline(x=33.3, line_dash="dot", line_color="#D1D5DB", line_width=1)
    fig.update_layout(**_PLOTLY_BASE, title=f"PROBABILIDADES 1X2 — River vs {rival}", showlegend=False, barmode="stack", xaxis=dict(range=[0, 105], showgrid=False, zeroline=False, ticksuffix="%", gridcolor="#E5E7EB"), yaxis=dict(showgrid=False, linecolor="#E5E7EB"), height=260)
    return fig

def fig_heatmap(sim: dict, rival: str) -> go.Figure:
    df = sim["df_resultados"]
    z = np.zeros((7, 7)); texto = [[""] * 7 for _ in range(7)]
    for _, row in df.iterrows():
        r, v = int(row["River"]), int(row["Rival"])
        if r <= 6 and v <= 6:
            z[v][r] = row["prob"] * 100
            texto[v][r] = f"{row['prob']*100:.1f}%"
    fig = go.Figure(go.Heatmap(z=z, x=[str(i) for i in range(7)], y=[str(i) for i in range(7)], text=texto, texttemplate="%{text}", colorscale=[[0, "#F9FAFB"], [0.5, "#FECACA"], [1, RED]], showscale=True, colorbar=dict(title="Prob %", ticksuffix="%"), hovertemplate="River %{x} - %{y} " + rival + "<br>Probabilidad: %{z:.2f}%<extra></extra>"))
    fig.update_layout(**_PLOTLY_BASE, title=f"RESULTADOS EXACTOS — River (cols) vs {rival} (filas)", xaxis=dict(title="Goles River", title_font=dict(color=RED)), yaxis=dict(title=f"Goles {rival}"), height=480)
    return fig

def fig_distribucion(sim: dict, rival: str) -> go.Figure:
    fig = go.Figure()
    for datos, nombre, color in [(sim["goles_river"], "River Plate", RED), (sim["goles_rival"], rival, GRAY)]:
        vals, cnts = np.unique(datos, return_counts=True)
        fig.add_trace(go.Bar(x=vals, y=cnts/sim["n"]*100, name=nombre, marker_color=color, opacity=0.85, hovertemplate=f"<b>{nombre}</b><br>%{{x}} goles: %{{y:.1f}}%<extra></extra>"))
    for lam, nombre, color in [(sim["lambda_r"], "River", RED), (sim["lambda_v"], rival, GRAY)]:
        fig.add_vline(x=lam, line_dash="dot", line_color=color, line_width=2, annotation_text=f"λ {nombre} = {lam:.2f}", annotation_font=dict(color=color))
    fig.update_layout(**_PLOTLY_BASE, title=f"DISTRIBUCIÓN DE GOLES SIMULADOS (N={sim['n']:,})", barmode="group", xaxis=dict(title="Goles por partido", dtick=1), yaxis=dict(title="Frecuencia (%)", ticksuffix="%"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=360)
    return fig

def fig_radar_xi(df_xi: pd.DataFrame) -> go.Figure:
    if df_xi.empty: return go.Figure()
    metricas = ["xG_p90", "xGA_p90", "forma", "Goles", "Asistencias"]
    labels   = ["xG/90", "Interc./90", "Forma", "Goles", "Asistencias"]
    vals_xi = [float(df_xi[m].mean()) if m in df_xi.columns else 0.0 for m in metricas]
    fig = go.Figure(go.Scatterpolar(r=vals_xi + [vals_xi[0]], theta=labels + [labels[0]], fill="toself", fillcolor=f"rgba(208,2,27,0.15)", line=dict(color=RED, width=2), marker=dict(color=RED, size=7), hovertemplate="%{theta}: %{r:.3f}<extra></extra>"))
    fig.update_layout(polar=dict(bgcolor=LIGHT_B, radialaxis=dict(visible=True, showticklabels=True), angularaxis=dict(tickfont=dict(color=GRAY))), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=50, r=50, t=30, b=30), height=300)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 5 ── INTERFAZ STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""
    <style>
    .pred-kpi { background: #111827; border: 1px solid #2A2A2A; border-left: 4px solid #D0021B; border-radius: 10px; padding: 16px 20px; text-align: center; }
    .pred-kpi .label { font-family: 'Rajdhani', sans-serif; font-size: 10px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 2px; font-weight: 700; }
    .pred-kpi .valor { font-family: 'Bebas Neue', cursive; font-size: 44px; line-height: 1; color: #D0021B; }
    .pred-kpi .lambda-val { font-family: 'JetBrains Mono', monospace; font-size: 28px; line-height: 1; color: #C9A84C; }
    .pred-kpi.empate .valor { color: #9CA3AF; }
    .pred-kpi.derrota .valor { color: #1A4A8B; }
    .pred-info { background: rgba(208,2,27,0.06); border-left: 3px solid #D0021B; border-radius: 0 6px 6px 0; padding: 10px 16px; font-family: 'Rajdhani', sans-serif; font-size: 13px; color: #4B5563; font-weight: 500; margin-bottom: 12px; }
    .badge-ok { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; background: #1a4d1a; color: #66ff66; margin-bottom: 12px; }
    .badge-warn { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; background: #4d3300; color: #ffaa00; margin-bottom: 12px; }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Conectando con la base de datos y la liga..."):
        df_liga, es_real = obtener_estadisticas_liga()
        df_plantilla = extraer_plantilla_river(str(ruta_excel))

    if df_liga.empty or df_plantilla.empty:
        st.error("⚠️ Faltan datos para ejecutar el simulador.")
        return

    if es_real:
        st.markdown('<span class="badge-ok">🌐 Datos en vivo (Internet) + 📂 Excel Local</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-warn">⚠️ Sin internet. Usando promedios históricos + 📂 Excel Local</span>', unsafe_allow_html=True)

    medias = calcular_medias(df_liga)
    rivales_lista = sorted([e for e in df_liga["equipo"].tolist() if "River" not in e])

    col_conf1, col_conf2 = st.columns([2, 1])
    with col_conf1:
        rival_sel = st.selectbox("🆚 Seleccioná el rival", rivales_lista, help="Ahora puedes elegir a CUALQUIER equipo de la liga, aunque River no haya jugado contra ellos este año.")
    with col_conf2:
        condicion = st.radio("📍 Condición de River", ["Local 🏟️", "Visitante ✈️"], horizontal=True)
        es_local = condicion == "Local 🏟️"

    st.markdown("---")
    st.markdown("<div style='font-family:Bebas Neue,cursive;font-size:22px;color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>👥 ARMAR XI TITULAR</div>", unsafe_allow_html=True)
    
    pos_orden = {"Arquero": 0, "Defensor": 1, "Mediocampista": 2, "Delantero": 3}
    df_plant_ord = df_plantilla.copy()
    df_plant_ord["_ord"] = df_plant_ord["Posicion"].map(pos_orden).fillna(9)
    df_plant_ord = df_plant_ord.sort_values(["_ord", "Minutos"], ascending=[True, False])

    pos_emoji = {"Arquero": "🧤", "Defensor": "🛡️", "Mediocampista": "⚙️", "Delantero": "⚡"}
    opciones = [f"{pos_emoji.get(row.Posicion,'')} {row.Jugador}  ({row.Nota:.2f}⭐)" for _, row in df_plant_ord.iterrows()]
    jugadores_ord = df_plant_ord["Jugador"].tolist()

    xi_default_nombres = []
    for pos, cupo in [("Arquero", 1), ("Defensor", 4), ("Mediocampista", 4), ("Delantero", 2)]:
        subset = df_plant_ord[df_plant_ord["Posicion"] == pos].head(cupo)
        xi_default_nombres.extend(subset["Jugador"].tolist())

    titulares_raw = st.multiselect("Jugadores:", options=opciones, default=[op for op, nombre in zip(opciones, jugadores_ord) if nombre in xi_default_nombres][:11], max_selections=11)

    def limpiar_nombre(opt: str) -> str:
        return re.sub(r"\s*\(.*\)$", "", re.sub(r"^[^\w]+", "", opt).strip()).strip()

    titulares = [limpiar_nombre(t) for t in titulares_raw]
    n_sel = len(titulares)

    if n_sel != 11:
        st.warning(f"⚠️ Seleccionaste {n_sel}/11 jugadores. El simulador requiere exactamente 11.")
        return

    st.markdown("---")
    if st.button("🚀 SIMULAR PARTIDO (10.000 iteraciones)", use_container_width=True, type="primary"):
        with st.spinner("Simulando..."):
            fuerzas = calcular_fuerzas(df_liga, rival_sel, medias)
            mults   = calcular_multiplicador(titulares, df_plantilla)
            λ_r, λ_v = calcular_lambdas(fuerzas, mults, medias, es_local)
            sim     = simular_montecarlo(λ_r, λ_v)

        st.markdown(f"<div style='font-family:Bebas Neue,cursive;font-size:28px;color:#1F2937;letter-spacing:2px;margin:16px 0 8px;'>📊 RESULTADO — RIVER vs {rival_sel.upper()}</div>", unsafe_allow_html=True)
        st.caption("🏟️ Local · Monumental" if es_local else "✈️ Visitante")

        k1, k2, k3, k4, k5 = st.columns(5)
        for col, label, valor, tipo in [(k1, "Victoria", f"{sim['prob_victoria']*100:.1f}%", "victory"), (k2, "Empate", f"{sim['prob_empate']*100:.1f}%", "empate"), (k3, "Derrota", f"{sim['prob_derrota']*100:.1f}%", "derrota"), (k4, f"λ River", f"{λ_r:.3f}", "lambda"), (k5, f"λ Rival", f"{λ_v:.3f}", "lambda")]:
            col.markdown(f'<div class="pred-kpi {tipo if tipo in ("empate","derrota") else ""}"><div class="label">{label}</div><div class="{"lambda-val" if tipo=="lambda" else "valor"}">{valor}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["📊 Probabilidades 1X2", "🎯 Resultados Exactos", "📈 Distribución Goles", "🔬 Análisis del XI"])
        with tab1: st.plotly_chart(fig_barras_1x2(sim, rival_sel), use_container_width=True)
        with tab2:
            st.plotly_chart(fig_heatmap(sim, rival_sel), use_container_width=True)
            top = sim["df_resultados"].sort_values("prob", ascending=False).head(10).copy()
            top["Marcador"] = top.apply(lambda r: f"River {int(r.River)} – {int(r.Rival)} {rival_sel}", axis=1)
            top["Probabilidad"] = (top["prob"] * 100).map("{:.2f}%".format)
            st.dataframe(top[["Marcador", "Probabilidad"]].reset_index(drop=True), hide_index=True, use_container_width=True)
        with tab3: st.plotly_chart(fig_distribucion(sim, rival_sel), use_container_width=True)
        with tab4:
            df_xi_display = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
            c_radar, c_tabla = st.columns([1, 1.5])
            with c_radar: st.plotly_chart(fig_radar_xi(df_xi_display), use_container_width=True)
            with c_tabla:
                cols_show = ["Jugador", "Posicion", "Nota", "xG_p90", "xGA_p90"]
                st.dataframe(df_xi_display[cols_show].sort_values("Posicion").reset_index(drop=True), hide_index=True, use_container_width=True)

        st.markdown(f"<div style='text-align:center;font-size:11px;color:#9CA3AF;margin-top:24px;'>Montecarlo N={MONTECARLO_N:,} · Red de Inteligencia de Scouting CARP</div>", unsafe_allow_html=True)
