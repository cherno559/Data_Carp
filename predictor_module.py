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
# MÓDULO 1 ── DATA MACRO (LIGA)
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
        
        if len(df_liga) > 15:
            return df_liga.reset_index(drop=True), True
        else:
            raise ValueError()
    except:
        data = [{"equipo": e, "PJ": 20, "GF": 24, "GC": 24} for e in EQUIPOS_PRIMERA_2026]
        df_fb = pd.DataFrame(data)
        df_fb.loc[df_fb["equipo"] == "River Plate", ["GF", "GC"]] = [32, 14]
        df_fb.loc[df_fb["equipo"] == "Boca Juniors", ["GF", "GC"]] = [28, 18]
        return df_fb, False

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1B ── DATA MICRO (RIVER - TU EXCEL)
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

    agg = agg[agg["Minutos"] >= 1].copy() 
    
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.8, 1.2) 
    
    return agg.reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── CÁLCULO DE FUERZAS Y SIMULACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    fa_rival = (r_data["GF"] / r_data["PJ"]) / mgf
    fd_rival = (r_data["GC"] / r_data["PJ"]) / mgf
    
    riv_base = df_liga[df_liga["equipo"] == "River Plate"].iloc[0]
    fa_river = (riv_base["GF"] / riv_base["PJ"]) / mgf
    fd_river = (riv_base["GC"] / riv_base["PJ"]) / mgf
    
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    mult_atk = (df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() + 1) / 2
    mult_def = (df_xi["xGA_p90"].mean() / df_plantilla["xGA_p90"].mean() + 1) / 2
    forma    = 1.0 + ((df_xi["forma"].mean() - 1.0) * 0.5)

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
# MÓDULO 3 ── GRÁFICOS ORIGINALES PLOTLY
# ─────────────────────────────────────────────────────────────────────────────

_PLOTLY_BASE = dict(
    font=dict(family="Rajdhani, Inter, sans-serif", size=13, color="#1F2937"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=LIGHT_B,
    margin=dict(l=16, r=16, t=40, b=16),
    title_font=dict(family="Bebas Neue, cursive", size=22, color="#1F2937"),
    hoverlabel=dict(bgcolor="#111827", bordercolor=RED, font_color="white", font_family="Rajdhani", font_size=13),
)

def fig_barras_1x2(sim: dict, rival: str) -> go.Figure:
    cats  = [f"Victoria River", "Empate", f"Derrota River"]
    vals  = [sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100]
    cols  = [RED, "#9CA3AF", "#1A4A8B"]

    fig = go.Figure()
    for cat, val, col in zip(cats, vals, cols):
        fig.add_trace(go.Bar(
            x=[val], y=[cat],
            orientation="h",
            marker_color=col,
            text=[f"{val:.1f}%"],
            textposition="outside",
            textfont=dict(family="Bebas Neue", size=18, color=col),
            hovertemplate=f"<b>{cat}</b>: {val:.1f}%<extra></extra>",
        ))

    fig.add_vline(x=33.3, line_dash="dot", line_color="#D1D5DB", line_width=1)
    fig.update_layout(
        **_PLOTLY_BASE,
        title=f"PROBABILIDADES 1X2 — River vs {rival}",
        showlegend=False,
        barmode="stack",
        xaxis=dict(range=[0, 105], showgrid=False, zeroline=False, ticksuffix="%", gridcolor="#E5E7EB"),
        yaxis=dict(showgrid=False, linecolor="#E5E7EB"),
        height=260,
    )
    return fig

def fig_heatmap(sim: dict, rival: str) -> go.Figure:
    MAX_G = 6
    df    = sim["df_resultados"]
    z     = np.zeros((MAX_G + 1, MAX_G + 1))
    texto = [[""] * (MAX_G + 1) for _ in range(MAX_G + 1)]

    for _, row in df.iterrows():
        r, v = int(row["River"]), int(row["Rival"])
        if r <= MAX_G and v <= MAX_G:
            z[v][r] = row["prob"] * 100
            texto[v][r] = f"{row['prob']*100:.1f}%"

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[str(i) for i in range(MAX_G + 1)],
        y=[str(i) for i in range(MAX_G + 1)],
        text=texto,
        texttemplate="%{text}",
        colorscale=[[0, "#F9FAFB"], [0.5, "#FECACA"], [1, RED]],
        showscale=True,
        colorbar=dict(title="Prob %", ticksuffix="%", title_font=dict(family="Rajdhani"), tickfont=dict(family="Rajdhani")),
        hovertemplate=("River %{x} - %{y} " + rival + "<br>Probabilidad: %{z:.2f}%<extra></extra>"),
    ))
    fig.update_layout(
        **_PLOTLY_BASE,
        title=f"RESULTADOS EXACTOS — River (cols) vs {rival} (filas)",
        xaxis=dict(title="Goles River", title_font=dict(family="Rajdhani", color=RED)),
        yaxis=dict(title=f"Goles {rival}", title_font=dict(family="Rajdhani")),
        height=480,
    )
    return fig

def fig_distribucion(sim: dict, rival: str) -> go.Figure:
    fig = go.Figure()

    for datos, nombre, color in [(sim["goles_river"], "River Plate", RED), (sim["goles_rival"], rival, GRAY)]:
        vals, cnts = np.unique(datos, return_counts=True)
        probs = cnts / sim["n"] * 100
        fig.add_trace(go.Bar(
            x=vals, y=probs,
            name=nombre,
            marker_color=color,
            opacity=0.85,
            hovertemplate=f"<b>{nombre}</b><br>%{{x}} goles: %{{y:.1f}}%<extra></extra>",
        ))

    for lam, nombre, color in [(sim["lambda_r"], "River", RED), (sim["lambda_v"], rival, GRAY)]:
        fig.add_vline(x=lam, line_dash="dot", line_color=color, line_width=2, annotation_text=f"λ {nombre} = {lam:.2f}", annotation_font=dict(family="Rajdhani", size=11, color=color), annotation_position="top right")

    fig.update_layout(
        **_PLOTLY_BASE,
        title=f"DISTRIBUCIÓN DE GOLES SIMULADOS (N={sim['n']:,})",
        barmode="group",
        xaxis=dict(title="Goles por partido", gridcolor="#E5E7EB", dtick=1, title_font=dict(family="Rajdhani")),
        yaxis=dict(title="Frecuencia (%)", gridcolor="#E5E7EB", ticksuffix="%", title_font=dict(family="Rajdhani")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family="Rajdhani", size=13)),
        height=360,
    )
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── INTERFAZ STREAMLIT ORIGINAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    # CSS ORIGINAL PARA LAS TARJETAS GRANDES
    st.markdown("""
    <style>
    .pred-kpi {
        background: #111827;
        border: 1px solid #2A2A2A;
        border-left: 4px solid #D0021B;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .pred-kpi .label {
        font-family: 'Rajdhani', sans-serif;
        font-size: 10px;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 700;
    }
    .pred-kpi .valor {
        font-family: 'Bebas Neue', cursive;
        font-size: 44px;
        line-height: 1;
        color: #D0021B;
    }
    .pred-kpi .lambda-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 28px;
        line-height: 1;
        color: #C9A84C;
    }
    .pred-kpi.empate .valor { color: #9CA3AF; }
    .pred-kpi.derrota .valor { color: #1A4A8B; }
    .pred-info {
        background: rgba(208,2,27,0.06);
        border-left: 3px solid #D0021B;
        border-radius: 0 6px 6px 0;
        padding: 10px 16px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 13px;
        color: #4B5563;
        font-weight: 500;
        margin-bottom: 12px;
    }
    .badge-datos {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 12px;
        font-weight: 700;
        background: #1a4d1a;
        color: #66ff66;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Conectando con la base de datos y la liga..."):
        df_liga, es_real = obtener_estadisticas_liga()
        df_plantilla = extraer_plantilla_river(str(ruta_excel))

    if df_liga.empty or df_plantilla.empty:
        st.error("⚠️ Faltan datos para ejecutar el simulador.")
        return

    st.markdown('<span class="badge-datos">✅ Datos Cargados · Inteligencia CARP Activa</span>', unsafe_allow_html=True)

    col_conf1, col_conf2 = st.columns([2, 1])
    with col_conf1:
        rivales_lista = sorted([e for e in df_liga["equipo"].tolist() if "River" not in e])
        rival_sel = st.selectbox("🆚 Seleccioná el rival", rivales_lista)
    with col_conf2:
        condicion = st.radio("📍 Condición de River", ["Local 🏟️", "Visitante ✈️"], horizontal=True)
        es_local = condicion == "Local 🏟️"

    st.markdown("---")
    st.markdown(
        "<div style='font-family:Bebas Neue,cursive;font-size:22px;color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>"
        "👥 ARMAR XI TITULAR</div>", unsafe_allow_html=True
    )
    
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

    st.markdown("---")
    btn_disabled = n_sel != 11
    simular = st.button("🚀 SIMULAR PARTIDO (10.000 iteraciones)", disabled=btn_disabled, use_container_width=True, type="primary")

    if not simular:
        if btn_disabled: st.info(f"👆 Seleccionaste {n_sel}/11 jugadores. Faltan {11-n_sel}.")
        return

    with st.spinner("Calculando fuerzas y ejecutando simulación..."):
        λ_r, λ_v = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(λ_r, λ_v)

    st.markdown(
        f"<div style='font-family:Bebas Neue,cursive;font-size:28px;color:#1F2937;letter-spacing:2px;margin:16px 0 8px;'>"
        f"📊 RESULTADO — RIVER vs {rival_sel.upper()}</div>", unsafe_allow_html=True
    )
    
    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_data = [
        (k1, "Victoria River", f"{sim['prob_victoria']*100:.1f}%", "victory"),
        (k2, "Empate", f"{sim['prob_empate']*100:.1f}%", "empate"),
        (k3, "Derrota River", f"{sim['prob_derrota']*100:.1f}%", "derrota"),
        (k4, f"λ River", f"{λ_r:.3f}", "lambda"),
        (k5, f"λ {rival_sel[:14]}", f"{λ_v:.3f}", "lambda"),
    ]
    for col, label, valor, tipo in kpi_data:
        val_cls  = "lambda-val" if tipo == "lambda" else "valor"
        card_cls = f"pred-kpi {tipo}" if tipo in ("empate","derrota") else "pred-kpi"
        col.markdown(f"""
        <div class="{card_cls}">
            <div class="label">{label}</div>
            <div class="{val_cls}">{valor}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Probabilidades 1X2", "🎯 Resultados Exactos", "📈 Distribución Goles", "🔬 Análisis del XI"])

    with tab1:
        st.plotly_chart(fig_barras_1x2(sim, rival_sel), use_container_width=True)
    with tab2:
        st.plotly_chart(fig_heatmap(sim, rival_sel), use_container_width=True)
        top = sim["df_resultados"].sort_values("prob", ascending=False).head(10).copy()
        top["Marcador"] = top.apply(lambda r: f"River {int(r.River)} – {int(r.Rival)} {rival_sel}", axis=1)
        top["Probabilidad"] = (top["prob"] * 100).map("{:.2f}%".format)
        st.markdown("<div style='font-family:Bebas Neue,cursive;font-size:20px;color:#1F2937;letter-spacing:2px;margin-top:8px;'>🏆 TOP 10 RESULTADOS MÁS PROBABLES</div>", unsafe_allow_html=True)
        st.dataframe(top[["Marcador", "Probabilidad"]].reset_index(drop=True), hide_index=True, use_container_width=True)
    with tab3:
        st.plotly_chart(fig_distribucion(sim, rival_sel), use_container_width=True)
    with tab4:
        df_xi_display = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
        st.markdown("<div style='font-family:Bebas Neue,cursive;font-size:18px;color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>📋 STATS DEL XI TITULAR</div>", unsafe_allow_html=True)
        cols_show = ["Jugador", "Posicion", "Nota", "xG_p90", "xGA_p90"]
        df_show = df_xi_display[cols_show].rename(columns={"Posicion": "Pos.", "Nota": "⭐ Nota", "xG_p90": "xG/90", "xGA_p90": "xGA/90"}).sort_values("Pos.").reset_index(drop=True)
        st.dataframe(df_show, hide_index=True, use_container_width=True)
