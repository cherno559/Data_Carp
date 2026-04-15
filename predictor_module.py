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

# Mapeo de posición (tu app usa español)
POS_GRUPO = {
    "Arquero":       "GK",
    "Defensor":      "DEF",
    "Mediocampista": "MID",
    "Delantero":     "FWD",
}

# Colores reutilizados de tu app
RED     = "#D0021B"
GRAY    = "#374151"
GOLD    = "#C9A84C"
LIGHT_B = "rgba(249,250,251,1)"

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── EXTRACCIÓN DE DATOS REALES DESDE EL EXCEL
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def extraer_datos_liga_desde_excel(ruta_excel_str: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Lee TODOS los partidos del Excel y construye:
      1. df_rivales : stats agregadas por rival (GF/GC/PJ) → fuerzas base
      2. df_plantilla: stats P90 reales de los jugadores de River

    Usa los mismos datos que ya cargaste, sin scraping externo.
    Retorna (df_rivales, df_plantilla).
    """
    ruta = Path(ruta_excel_str)
    if not ruta.exists():
        return pd.DataFrame(), pd.DataFrame()

    try:
        xl = pd.ExcelFile(ruta)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

    hojas_omitir = {
        "Promedios Generales", "Goleadores",
        "Asistidores", "Resumen Estadísticas"
    }

    partidos_meta = []   # info de resultado por partido
    filas_jugadores = [] # filas individuales de jugadores River

    for hoja in xl.sheet_names:
        if hoja in hojas_omitir:
            continue

        # ── Leer hoja de datos de jugadores ────────────────────────────────
        try:
            df_hoja = pd.read_excel(ruta, sheet_name=hoja)
            df_hoja.columns = df_hoja.columns.astype(str).str.strip()
        except Exception:
            continue

        if "Jugador" not in df_hoja.columns:
            continue

        # Limpieza igual a tu cargar_datos_completos
        df_hoja["Jugador"] = (
            df_hoja["Jugador"].fillna("").astype(str).str.strip().str.title()
        )
        df_hoja["Jugador"] = df_hoja["Jugador"].apply(
            lambda x: re.sub(r"\s+", " ", x)
        )
        if "Minutos" in df_hoja.columns:
            df_hoja["Minutos"] = pd.to_numeric(
                df_hoja["Minutos"], errors="coerce"
            ).fillna(0)
        else:
            df_hoja["Minutos"] = 0

        df_hoja = df_hoja[
            (df_hoja["Jugador"] != "")
            & (df_hoja["Jugador"].str.lower() != "nan")
            & (df_hoja["Minutos"] > 0)
        ].copy()

        df_hoja["Partido"] = hoja
        filas_jugadores.append(df_hoja)

        # ── Leer resultado del partido desde la misma hoja (header=None) ──
        try:
            df_raw = pd.read_excel(ruta, sheet_name=hoja, header=None)
        except Exception:
            continue

        local, rival, g_local, g_rival = None, None, None, None
        for r in range(min(130, len(df_raw))):
            for c in range(min(20, len(df_raw.columns))):
                val = str(df_raw.iloc[r, c]).strip().lower()
                if val in ["métrica", "metrica"]:
                    try:
                        local = str(df_raw.iloc[r, c + 1]).strip()
                        rival = str(df_raw.iloc[r, c + 2]).strip()
                    except Exception:
                        pass
                if val == "resultado":
                    try:
                        m1 = re.match(r"^(\d+)", str(df_raw.iloc[r, c + 1]).strip())
                        m2 = re.match(r"^(\d+)", str(df_raw.iloc[r, c + 2]).strip())
                        if m1 and m2:
                            g_local = int(m1.group(1))
                            g_rival = int(m2.group(1))
                    except Exception:
                        pass

        if local and rival and g_local is not None and g_rival is not None:
            is_river_local = "River" in local
            rival_nombre   = rival if is_river_local else local
            gf_river       = g_local if is_river_local else g_rival
            gc_river       = g_rival if is_river_local else g_local
            gf_rival_pdo   = g_rival if is_river_local else g_local
            gc_rival_pdo   = g_local if is_river_local else g_rival

            partidos_meta.append({
                "hoja":          hoja,
                "rival_nombre":  rival_nombre,
                "river_local":   is_river_local,
                "gf_river":      gf_river,
                "gc_river":      gc_river,
                "gf_rival":      gf_rival_pdo,
                "gc_rival":      gc_rival_pdo,
            })

    # ── df_rivales ─────────────────────────────────────────────────────────
    if not partidos_meta:
        df_rivales = pd.DataFrame()
    else:
        df_meta = pd.DataFrame(partidos_meta)
        df_rivales = (
            df_meta.groupby("rival_nombre")
            .agg(
                PJ=("hoja", "count"),
                GF=("gf_rival", "sum"),
                GC=("gc_rival", "sum"),
            )
            .reset_index()
            .rename(columns={"rival_nombre": "equipo"})
        )
        # Agregar River mismo (para calcular media de "liga interna")
        river_row = pd.DataFrame([{
            "equipo": "River Plate",
            "PJ": len(df_meta),
            "GF": int(df_meta["gf_river"].sum()),
            "GC": int(df_meta["gc_river"].sum()),
        }])
        df_rivales = pd.concat([river_row, df_rivales], ignore_index=True)

    # ── df_plantilla ────────────────────────────────────────────────────────
    if not filas_jugadores:
        df_plantilla = pd.DataFrame()
    else:
        df_todos = pd.concat(filas_jugadores, ignore_index=True)

        cols_num = [
            "Goles", "Asistencias", "Pases Clave",
            "Quites (Tackles)", "Intercepciones",
            "Tiros Totales", "Tiros al Arco",
        ]
        for col in cols_num:
            if col in df_todos.columns:
                df_todos[col] = pd.to_numeric(
                    df_todos[col], errors="coerce"
                ).fillna(0)
            else:
                df_todos[col] = 0

        if "Nota SofaScore" in df_todos.columns:
            df_todos["Nota SofaScore"] = pd.to_numeric(
                df_todos["Nota SofaScore"], errors="coerce"
            )
            df_todos = df_todos[df_todos["Nota SofaScore"] != 0]

        if "Efectividad Pases" in df_todos.columns:
            df_todos["Efectividad Pases"] = pd.to_numeric(
                df_todos["Efectividad Pases"], errors="coerce"
            ).replace(0, np.nan)

        agg = df_todos.groupby("Jugador", as_index=False).agg(
            Posicion    = ("Posición", lambda x: x.mode()[0] if not x.mode().empty else "—"),
            Minutos     = ("Minutos",        "sum"),
            Partidos    = ("Partido",        "nunique"),
            Nota        = ("Nota SofaScore", "mean"),
            Goles       = ("Goles",          "sum"),
            Asistencias = ("Asistencias",    "sum"),
            PasesClave  = ("Pases Clave",    "sum"),
            Quites      = ("Quites (Tackles)","sum"),
            Intercepciones = ("Intercepciones","sum"),
            TirosTotal  = ("Tiros Totales",  "sum"),
            EfectPases  = ("Efectividad Pases","mean"),
        )

        # Solo jugadores con al menos 90 minutos (1 partido completo)
        agg = agg[agg["Minutos"] >= 90].copy()

        mins = agg["Minutos"].replace(0, 1)
        agg["xG_p90"]      = (agg["Goles"]       / mins * 90).round(3)
        agg["xGA_p90"]     = (agg["Intercepciones"] / mins * 90).round(3)
        agg["forma"]       = (agg["Nota"].fillna(7.0) / 7.0).round(3)  # normalizada: 7.0 = 1.0
        agg["forma"]       = agg["forma"].clip(0.6, 1.5)

        df_plantilla = agg.reset_index(drop=True)

    return df_rivales, df_plantilla


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── CÁLCULO DE FUERZAS (Poisson)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_medias(df_rivales: pd.DataFrame) -> dict:
    """Media de goles/partido de todos los equipos en el dataset."""
    df = df_rivales[df_rivales["PJ"] > 0].copy()
    df["gf_pp"] = df["GF"] / df["PJ"]
    df["gc_pp"] = df["GC"] / df["PJ"]
    return {
        "mgf": float(df["gf_pp"].mean()),
        "mgc": float(df["gc_pp"].mean()),
    }


def calcular_fuerzas(
    df_rivales: pd.DataFrame,
    rival: str,
    medias: dict,
) -> dict:
    """
    FA = (GF/PJ) / media_gf  → ataque relativo al promedio
    FD = (GC/PJ) / media_gc  → defensa relativa (mayor = peor defensa)
    """
    fila_rival = df_rivales[df_rivales["equipo"] == rival]
    if fila_rival.empty:
        fa_rival = 1.0
        fd_rival = 1.0
    else:
        r = fila_rival.iloc[0]
        pj = max(r["PJ"], 1)
        fa_rival = (r["GF"] / pj) / max(medias["mgf"], 0.01)
        fd_rival = (r["GC"] / pj) / max(medias["mgc"], 0.01)

    fila_river = df_rivales[df_rivales["equipo"] == "River Plate"]
    if fila_river.empty:
        fa_river = 1.15
        fd_river = 0.80
    else:
        rv = fila_river.iloc[0]
        pj = max(rv["PJ"], 1)
        fa_river = (rv["GF"] / pj) / max(medias["mgf"], 0.01)
        fd_river = (rv["GC"] / pj) / max(medias["mgc"], 0.01)

    return {
        "fa_rival":  float(fa_rival),
        "fd_rival":  float(fd_rival),
        "fa_river":  float(fa_river),
        "fd_river":  float(fd_river),
    }


def calcular_multiplicador(
    titulares: list[str],
    df_plantilla: pd.DataFrame,
) -> dict:
    """
    Multiplica las fuerzas base de River según el XI elegido.
    Basado en xG/90 (ataque) y nota promedio (forma general).
    """
    if not titulares or df_plantilla.empty:
        return {"mult_atk": 1.0, "mult_def": 1.0, "forma_prom": 1.0}

    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()
    if df_xi.empty:
        return {"mult_atk": 1.0, "mult_def": 1.0, "forma_prom": 1.0}

    # Referencia: promedio de toda la plantilla (mínimo 90 minutos)
    def media_segura(serie):
        val = serie.replace(0, np.nan).mean()
        return val if not pd.isna(val) else 0.001

    ref_xg  = media_segura(
        df_plantilla[df_plantilla["Posicion"].isin(["Delantero", "Mediocampista"])]["xG_p90"]
    )
    ref_xga = media_segura(
        df_plantilla[df_plantilla["Posicion"].isin(["Defensor", "Arquero"])]["xGA_p90"]
    )

    xi_atk = df_xi[df_xi["Posicion"].isin(["Delantero", "Mediocampista"])]
    xi_def = df_xi[df_xi["Posicion"].isin(["Defensor", "Arquero"])]

    mult_atk = (
        media_segura(xi_atk["xG_p90"]) / ref_xg
        if not xi_atk.empty else 1.0
    )
    mult_def = (
        media_segura(xi_def["xGA_p90"]) / ref_xga
        if not xi_def.empty else 1.0
    )

    forma_prom = float(df_xi["forma"].mean()) if not df_xi["forma"].isna().all() else 1.0

    mult_atk   = float(np.clip(mult_atk * forma_prom, 0.55, 1.65))
    mult_def   = float(np.clip(mult_def * forma_prom, 0.55, 1.65))

    return {"mult_atk": mult_atk, "mult_def": mult_def, "forma_prom": forma_prom}


def calcular_lambdas(
    fuerzas: dict,
    mults: dict,
    medias: dict,
    es_local: bool,
) -> tuple[float, float]:
    """
    λ_River = FA_river_ajustado × (1/FD_rival) × media_liga × factor_local
    λ_Rival = FA_rival          × (1/FD_river_ajustado) × media_liga
    """
    FACTOR_LOCAL = 1.08 if es_local else 1.00

    fa_river_adj = fuerzas["fa_river"] * mults["mult_atk"]
    fd_river_adj = fuerzas["fd_river"] * (1 / max(mults["mult_def"], 0.1))

    lambda_r = (
        fa_river_adj
        * (1 / max(fuerzas["fd_rival"], 0.4))
        * medias["mgf"]
        * FACTOR_LOCAL
    )
    lambda_v = (
        fuerzas["fa_rival"]
        * (1 / max(fd_river_adj, 0.4))
        * medias["mgf"]
    )

    lambda_r = float(np.clip(lambda_r, 0.2, 6.0))
    lambda_v = float(np.clip(lambda_v, 0.2, 6.0))

    return round(lambda_r, 4), round(lambda_v, 4)


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── SIMULACIÓN MONTECARLO (vectorizada)
# ─────────────────────────────────────────────────────────────────────────────

def simular_montecarlo(
    lambda_r: float,
    lambda_v: float,
    n: int = MONTECARLO_N,
    seed: int = 42,
) -> dict:
    """Genera N partidos virtuales con numpy vectorizado (sin bucles Python)."""
    rng = np.random.default_rng(seed)

    goles_r   = rng.poisson(lam=lambda_r, size=n)  # shape (N,)
    goles_v   = rng.poisson(lam=lambda_v, size=n)  # shape (N,)

    wins   = int(np.sum(goles_r > goles_v))
    draws  = int(np.sum(goles_r == goles_v))
    losses = int(np.sum(goles_r < goles_v))

    # Matriz de resultados exactos (0–6)
    MAX_G = 6
    resultados = []
    for r in range(MAX_G + 1):
        for v in range(MAX_G + 1):
            prob = float(np.mean((goles_r == r) & (goles_v == v)))
            resultados.append({"River": r, "Rival": v, "prob": prob})

    return {
        "prob_victoria": wins   / n,
        "prob_empate":   draws  / n,
        "prob_derrota":  losses / n,
        "goles_river":   goles_r,
        "goles_rival":   goles_v,
        "df_resultados": pd.DataFrame(resultados),
        "lambda_r":      lambda_r,
        "lambda_v":      lambda_v,
        "n":             n,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── GRÁFICOS (usando Plotly igual que tu app)
# ─────────────────────────────────────────────────────────────────────────────

_PLOTLY_BASE = dict(
    font=dict(family="Rajdhani, Inter, sans-serif", size=13, color="#1F2937"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=LIGHT_B,
    margin=dict(l=16, r=16, t=40, b=16),
    title_font=dict(family="Bebas Neue, cursive", size=22, color="#1F2937"),
    hoverlabel=dict(
        bgcolor="#111827", bordercolor=RED,
        font_color="white", font_family="Rajdhani", font_size=13,
    ),
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

    fig.add_vline(
        x=33.3, line_dash="dot", line_color="#D1D5DB",
        line_width=1,
    )
    fig.update_layout(
        **_PLOTLY_BASE,
        title=f"PROBABILIDADES 1X2 — River vs {rival}",
        showlegend=False,
        barmode="stack",
        xaxis=dict(range=[0, 105], showgrid=False, zeroline=False,
                   ticksuffix="%", gridcolor="#E5E7EB"),
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
        colorbar=dict(title="Prob %", ticksuffix="%",
                      title_font=dict(family="Rajdhani"),
                      tickfont=dict(family="Rajdhani")),
        hovertemplate=(
            "River %{x} - %{y} " + rival +
            "<br>Probabilidad: %{z:.2f}%<extra></extra>"
        ),
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

    for datos, nombre, color in [
        (sim["goles_river"], "River Plate", RED),
        (sim["goles_rival"], rival,         GRAY),
    ]:
        vals, cnts = np.unique(datos, return_counts=True)
        probs = cnts / sim["n"] * 100
        fig.add_trace(go.Bar(
            x=vals, y=probs,
            name=nombre,
            marker_color=color,
            opacity=0.85,
            hovertemplate=f"<b>{nombre}</b><br>%{{x}} goles: %{{y:.1f}}%<extra></extra>",
        ))

    for lam, nombre, color in [
        (sim["lambda_r"], "River", RED),
        (sim["lambda_v"], rival,   GRAY),
    ]:
        fig.add_vline(
            x=lam, line_dash="dot", line_color=color, line_width=2,
            annotation_text=f"λ {nombre} = {lam:.2f}",
            annotation_font=dict(family="Rajdhani", size=11, color=color),
            annotation_position="top right",
        )

    fig.update_layout(
        **_PLOTLY_BASE,
        title=f"DISTRIBUCIÓN DE GOLES SIMULADOS (N={sim['n']:,})",
        barmode="group",
        xaxis=dict(title="Goles por partido", gridcolor="#E5E7EB",
                   dtick=1, title_font=dict(family="Rajdhani")),
        yaxis=dict(title="Frecuencia (%)", gridcolor="#E5E7EB",
                   ticksuffix="%", title_font=dict(family="Rajdhani")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1,
                    font=dict(family="Rajdhani", size=13)),
        height=360,
    )
    return fig


def fig_radar_xi(df_xi: pd.DataFrame) -> go.Figure:
    """Radar del XI seleccionado vs promedio plantilla."""
    if df_xi.empty:
        return go.Figure()

    metricas = ["xG_p90", "xGA_p90", "forma", "Goles", "Asistencias"]
    labels   = ["xG/90", "Interc./90", "Forma", "Goles", "Asistencias"]

    vals_xi  = []
    for m in metricas:
        if m in df_xi.columns:
            vals_xi.append(float(df_xi[m].mean()))
        else:
            vals_xi.append(0.0)

    fig = go.Figure(go.Scatterpolar(
        r=vals_xi + [vals_xi[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor=f"rgba(208,2,27,0.15)",
        line=dict(color=RED, width=2),
        marker=dict(color=RED, size=7),
        name="XI Elegido",
        hovertemplate="%{theta}: %{r:.3f}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=LIGHT_B,
            radialaxis=dict(
                visible=True,
                showticklabels=True,
                tickfont=dict(size=9, color="#9CA3AF", family="Rajdhani"),
                gridcolor="#E5E7EB", linecolor="#E5E7EB",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, family="Rajdhani", color=GRAY),
                gridcolor="#E5E7EB", linecolor="#E5E7EB",
            ),
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=50, t=30, b=30),
        height=300,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 5 ── INTERFAZ STREAMLIT (se llama desde la app principal)
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    """
    Renderiza la página completa del Predictor.

    Parámetros
    ----------
    ruta_excel          : Path al Excel activo (ya lo tenés como EXCEL_ACTUAL)
    apply_plotly_style_fn: tu función apply_plotly_style (opcional, para consistencia)
    """

    # ── Estilos locales complementarios ─────────────────────────────────────
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

    # ── Carga de datos ───────────────────────────────────────────────────────
    with st.spinner("Cargando datos del Excel..."):
        df_rivales, df_plantilla = extraer_datos_liga_desde_excel(str(ruta_excel))

    if df_rivales.empty or df_plantilla.empty:
        st.error("⚠️ No se pudieron extraer los datos del Excel. Verificá que el archivo tiene el formato correcto.")
        return

    st.markdown(
        '<span class="badge-datos">✅ Datos extraídos del Excel · Sin conexión externa</span>',
        unsafe_allow_html=True,
    )

    medias = calcular_medias(df_rivales)

    # Lista de rivales disponibles (excluyendo River)
    rivales_lista = sorted([
        e for e in df_rivales["equipo"].tolist()
        if "River" not in e
    ])

    # ── Controles en columnas ────────────────────────────────────────────────
    col_conf1, col_conf2 = st.columns([2, 1])

    with col_conf1:
        rival_sel = st.selectbox(
            "🆚 Seleccioná el rival",
            rivales_lista,
            help="Rivales basados en los partidos registrados en tu Excel",
        )

    with col_conf2:
        condicion = st.radio(
            "📍 Condición de River",
            ["Local 🏟️", "Visitante ✈️"],
            horizontal=True,
        )
        es_local = condicion == "Local 🏟️"

    st.markdown("---")

    # ── Selección de XI titular ──────────────────────────────────────────────
    st.markdown(
        "<div style='font-family:Bebas Neue,cursive;font-size:22px;"
        "color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>"
        "👥 ARMAR XI TITULAR</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="pred-info">Seleccioná exactamente 11 jugadores. '
        "El modelo ajusta las fuerzas de River según el rendimiento real "
        "(xG/90 y nota SofaScore) de los titulares elegidos.</div>",
        unsafe_allow_html=True,
    )

    # Organizar plantilla por posición para mostrar ordenada
    pos_orden = {"Arquero": 0, "Defensor": 1, "Mediocampista": 2, "Delantero": 3}
    df_plant_ord = df_plantilla.copy()
    df_plant_ord["_ord"] = df_plant_ord["Posicion"].map(pos_orden).fillna(9)
    df_plant_ord = df_plant_ord.sort_values(["_ord", "Minutos"], ascending=[True, False])

    pos_emoji = {"Arquero": "🧤", "Defensor": "🛡️", "Mediocampista": "⚙️", "Delantero": "⚡"}

    # Opciones con emoji + nota
    opciones = [
        f"{pos_emoji.get(row.Posicion,'')} {row.Jugador}  ({row.Nota:.2f}⭐)"
        for _, row in df_plant_ord.iterrows()
    ]
    jugadores_ord = df_plant_ord["Jugador"].tolist()

    # XI sugerido automáticamente: mejor XI por nota × minutos
    xi_default_nombres = []
    for pos, cupo in [("Arquero", 1), ("Defensor", 4), ("Mediocampista", 4), ("Delantero", 2)]:
        subset = df_plant_ord[df_plant_ord["Posicion"] == pos].head(cupo)
        xi_default_nombres.extend(subset["Jugador"].tolist())

    xi_default_opts = [
        op for op, nombre in zip(opciones, jugadores_ord)
        if nombre in xi_default_nombres
    ]

    titulares_raw = st.multiselect(
        "Jugadores (ordenados por posición y minutos jugados):",
        options=opciones,
        default=xi_default_opts[:11],
        max_selections=11,
        help="Máximo 11 jugadores. El orden sugerido es por minutos jugados en la temporada.",
    )

    # Extraer nombres limpios (quitar emoji y nota)
    def limpiar_nombre(opt: str) -> str:
        # Formato: "🧤 Nombre Apellido  (7.20⭐)"
        sin_emoji = re.sub(r"^[^\w]+", "", opt).strip()
        nombre    = re.sub(r"\s*\(.*\)$", "", sin_emoji).strip()
        return nombre

    titulares = [limpiar_nombre(t) for t in titulares_raw]
    n_sel     = len(titulares)

    col_cnt1, col_cnt2 = st.columns([1, 3])
    with col_cnt1:
        if n_sel == 11:
            st.success(f"✅ {n_sel}/11 jugadores")
        elif n_sel < 11:
            st.warning(f"⚠️ {n_sel}/11 — faltan {11-n_sel}")
        else:
            st.error(f"❌ {n_sel}/11 — máximo 11")

    st.markdown("---")

    # ── Botón de simulación ──────────────────────────────────────────────────
    btn_disabled = n_sel != 11
    simular      = st.button(
        "🚀 SIMULAR PARTIDO (10.000 iteraciones)",
        disabled=btn_disabled,
        use_container_width=True,
        type="primary",
    )

    if btn_disabled and not simular:
        st.info("👆 Completá la selección de 11 jugadores y presioná **Simular**.")
        return

    if not simular:
        return  # espera al click

    # ── Pipeline de cálculo ──────────────────────────────────────────────────
    with st.spinner("Calculando fuerzas y ejecutando simulación..."):
        fuerzas = calcular_fuerzas(df_rivales, rival_sel, medias)
        mults   = calcular_multiplicador(titulares, df_plantilla)
        λ_r, λ_v = calcular_lambdas(fuerzas, mults, medias, es_local)
        sim     = simular_montecarlo(λ_r, λ_v)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-family:Bebas Neue,cursive;font-size:28px;"
        f"color:#1F2937;letter-spacing:2px;margin:16px 0 8px;'>"
        f"📊 RESULTADO — RIVER vs {rival_sel.upper()}</div>",
        unsafe_allow_html=True,
    )
    condicion_txt = "🏟️ Local · Monumental" if es_local else "✈️ Visitante"
    st.caption(condicion_txt)

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_data = [
        (k1, "Victoria River",     f"{sim['prob_victoria']*100:.1f}%", "victory"),
        (k2, "Empate",             f"{sim['prob_empate']*100:.1f}%",   "empate"),
        (k3, "Derrota River",      f"{sim['prob_derrota']*100:.1f}%",  "derrota"),
        (k4, f"λ River",           f"{λ_r:.3f}",                       "lambda"),
        (k5, f"λ {rival_sel[:14]}", f"{λ_v:.3f}",                     "lambda"),
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

    # ── Tabs de gráficos ─────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Probabilidades 1X2",
        "🎯 Resultados Exactos",
        "📈 Distribución Goles",
        "🔬 Análisis del XI",
    ])

    with tab1:
        st.plotly_chart(fig_barras_1x2(sim, rival_sel), use_container_width=True)
        st.markdown(
            '<div class="pred-info">La línea punteada vertical representa el umbral '
            "de equilibrio (33.3%). Barras que superan ese límite indican ventaja.</div>",
            unsafe_allow_html=True,
        )

    with tab2:
        st.plotly_chart(fig_heatmap(sim, rival_sel), use_container_width=True)

        # Top 10 resultados
        st.markdown(
            "<div style='font-family:Bebas Neue,cursive;font-size:20px;"
            "color:#1F2937;letter-spacing:2px;margin-top:8px;'>🏆 TOP 10 RESULTADOS MÁS PROBABLES</div>",
            unsafe_allow_html=True,
        )
        top = (
            sim["df_resultados"]
            .sort_values("prob", ascending=False)
            .head(10)
            .copy()
        )
        top["Marcador"] = top.apply(
            lambda r: f"River {int(r.River)} – {int(r.Rival)} {rival_sel}", axis=1
        )
        top["Probabilidad"] = (top["prob"] * 100).map("{:.2f}%".format)
        top["Resultado"]    = top.apply(
            lambda r: "✅ Victoria" if r.River > r.Rival
            else ("⚖️ Empate" if r.River == r.Rival else "❌ Derrota"),
            axis=1,
        )
        st.dataframe(
            top[["Marcador", "Resultado", "Probabilidad"]].reset_index(drop=True),
            hide_index=True,
            use_container_width=True,
        )

    with tab3:
        st.plotly_chart(fig_distribucion(sim, rival_sel), use_container_width=True)
        st.markdown(
            f'<div class="pred-info">Basado en {sim["n"]:,} partidos simulados con '
            f"distribución de Poisson. λ River = <b>{λ_r:.3f}</b> · "
            f"λ {rival_sel} = <b>{λ_v:.3f}</b>. "
            f"Un λ mayor indica mayor expectativa de gol por partido.</div>",
            unsafe_allow_html=True,
        )

    with tab4:
        df_xi_display = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()

        c_radar, c_tabla = st.columns([1, 1.5])

        with c_radar:
            st.markdown(
                "<div style='font-family:Bebas Neue,cursive;font-size:18px;"
                "color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>"
                "🛡️ PERFIL DEL XI</div>",
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig_radar_xi(df_xi_display), use_container_width=True)

        with c_tabla:
            st.markdown(
                "<div style='font-family:Bebas Neue,cursive;font-size:18px;"
                "color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>"
                "📋 STATS DEL XI TITULAR</div>",
                unsafe_allow_html=True,
            )
            cols_show = ["Jugador", "Posicion", "Partidos", "Nota",
                         "xG_p90", "xGA_p90", "forma", "Goles", "Asistencias"]
            cols_ok   = [c for c in cols_show if c in df_xi_display.columns]
            df_show   = df_xi_display[cols_ok].rename(columns={
                "Posicion": "Pos.", "Nota": "⭐ Nota", "xG_p90": "xG/90",
                "xGA_p90": "Inter/90", "forma": "Forma",
            }).sort_values("Pos.").reset_index(drop=True)
            st.dataframe(df_show, hide_index=True, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Tabla de fuerzas
        st.markdown(
            "<div style='font-family:Bebas Neue,cursive;font-size:18px;"
            "color:#1F2937;letter-spacing:2px;margin-bottom:8px;'>"
            "⚙️ FUERZAS CALCULADAS</div>",
            unsafe_allow_html=True,
        )
        df_fuerzas = pd.DataFrame({
            "Parámetro": [
                "FA River (base)", "FA River (ajustado por XI)",
                "FD River (base)", "FD River (ajustado por XI)",
                "FA Rival", "FD Rival",
                "Mult. Ataque XI", "Mult. Defensa XI", "Forma Promedio XI",
                "Media GF/partido (liga interna)",
                "λ River", f"λ {rival_sel}",
            ],
            "Valor": [
                f"{fuerzas['fa_river']:.4f}",
                f"{fuerzas['fa_river']*mults['mult_atk']:.4f}",
                f"{fuerzas['fd_river']:.4f}",
                f"{fuerzas['fd_river']*(1/max(mults['mult_def'],0.1)):.4f}",
                f"{fuerzas['fa_rival']:.4f}",
                f"{fuerzas['fd_rival']:.4f}",
                f"{mults['mult_atk']:.4f}",
                f"{mults['mult_def']:.4f}",
                f"{mults['forma_prom']:.4f}",
                f"{medias['mgf']:.4f}",
                f"{λ_r:.4f}",
                f"{λ_v:.4f}",
            ],
        })
        st.dataframe(df_fuerzas, hide_index=True, use_container_width=True)

    # ── Footer del módulo ────────────────────────────────────────────────────
    st.markdown(
        f"<div style='text-align:center;font-family:Rajdhani,sans-serif;"
        f"font-size:11px;color:#9CA3AF;margin-top:24px;'>"
        f"Motor de Predicción · Poisson + Montecarlo N={MONTECARLO_N:,} · "
        f"Datos: {ruta_excel.name}</div>",
        unsafe_allow_html=True,
    )
