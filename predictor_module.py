import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y TABLA DE POSICIONES 2026 (J 13)
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
    "DEL": "Delantero", "del": "Delantero",
    "MED": "Mediocampista", "med": "Mediocampista",
    "DEF": "Defensor", "def": "Defensor",
    "POR": "Arquero", "por": "Arquero",
    "Delantero": "Delantero",
    "Mediocampista": "Mediocampista",
    "Defensor": "Defensor",
    "Arquero": "Arquero",
}

RED, GRAY, LIGHT_B = "#D0021B", "#374151", "rgba(249,250,251,1)"
_ST = dict(font=dict(family="Rajdhani", size=13), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=LIGHT_B)


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 1 ── DATA
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def obtener_estadisticas_liga():
    registros = [
        {"equipo": eq, "PJ": s["PJ"], "GF": s["GF"], "GC": s["GC"]}
        for eq, s in DATOS_LIGA_MANUAL.items()
    ]
    return pd.DataFrame(registros)


@st.cache_data(ttl=3600)
def extraer_plantilla_river(ruta_excel_str):
    ruta = Path(ruta_excel_str)
    try:
        xl = pd.ExcelFile(ruta)
        filas = []
        for hoja in xl.sheet_names:
            if "Promedios" in hoja or "Resumen" in hoja:
                continue
            df_h = pd.read_excel(ruta, sheet_name=hoja)
            df_h.columns = df_h.columns.astype(str).str.strip()
            if "Jugador" not in df_h.columns:
                continue

            df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
            if "Minutos" in df_h.columns:
                df_h["Minutos"] = pd.to_numeric(df_h["Minutos"], errors="coerce").fillna(0)
            else:
                df_h["Minutos"] = 0

            df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
            filas.append(df_h)

        if not filas:
            return pd.DataFrame(columns=["Jugador", "Posicion", "Minutos", "Nota", "Goles", "xG_p90", "forma"])

        df_todos = pd.concat(filas, ignore_index=True)

        if "Posición" in df_todos.columns:
            df_todos["Posición"] = df_todos["Posición"].astype(str).str.strip().map(
                lambda p: POSICION_MAP.get(p, "Mediocampista")
            )
        else:
            df_todos["Posición"] = "Mediocampista"

        if "Goles" not in df_todos.columns:
            df_todos["Goles"] = 0
        else:
            df_todos["Goles"] = pd.to_numeric(df_todos["Goles"], errors="coerce").fillna(0)

        if "Nota SofaScore" not in df_todos.columns:
            df_todos["Nota SofaScore"] = 6.8
        else:
            df_todos["Nota SofaScore"] = pd.to_numeric(df_todos["Nota SofaScore"], errors="coerce")

        agg = df_todos.groupby("Jugador", as_index=False).agg(
            Posicion=("Posición", lambda x: x.mode()[0] if not x.mode().empty else "Mediocampista"),
            Minutos=("Minutos", "sum"),
            Nota=("Nota SofaScore", lambda x: x[x > 0].mean() if not x[x > 0].empty else 6.8),
            Goles=("Goles", "sum")
        )

        minutos_seguros = agg["Minutos"].replace(0, 1)
        agg["xG_p90"] = (agg["Goles"] / (minutos_seguros / 90)).round(3)
        agg["forma"] = (agg["Nota"] / 7.0).clip(0.85, 1.15)

        return agg[agg["Minutos"] >= 1].reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame(columns=["Jugador", "Posicion", "Minutos", "Nota", "Goles", "xG_p90", "forma"])


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── LÓGICA DE SIMULACIÓN Y GOLEADORES
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    r_data = df_liga[df_liga["equipo"] == rival]
    riv_base = df_liga[df_liga["equipo"] == "River"]

    if r_data.empty or riv_base.empty:
        return 1.5, 1.0

    r_data = r_data.iloc[0]
    riv_base = riv_base.iloc[0]

    fa_rival = (r_data["GF"] / r_data["PJ"]) / mgf
    fd_rival = (r_data["GC"] / r_data["PJ"]) / mgf
    fa_river = (riv_base["GF"] / riv_base["PJ"]) / mgf
    fd_river = (riv_base["GC"] / riv_base["PJ"]) / mgf

    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    xg_promedio_equipo = df_plantilla["xG_p90"].mean()
    xg_promedio_xi = df_xi["xG_p90"].mean() if not df_xi.empty else xg_promedio_equipo

    mult_atk = 1.0 + ((xg_promedio_xi / max(xg_promedio_equipo, 0.001) - 1.0) * 0.5)
    forma_media = df_xi["forma"].mean() if not df_xi.empty else 1.0
    forma = 1.0 + ((forma_media - 1.0) * 0.5)

    V = 1.15
    lam_r = fa_river * mult_atk * fd_rival * mgf * forma * (V if es_local else 1.0)
    lam_v = fa_rival * fd_river * mgf * (1 / forma) * (1.0 if es_local else V)

    return round(float(np.clip(lam_r, 0.2, 5.0)), 3), round(float(np.clip(lam_v, 0.2, 5.0)), 3)


def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr = rng.poisson(lam_r, MONTECARLO_N)
    gv = rng.poisson(lam_v, MONTECARLO_N)

    penal_mask = ((gr == 1) & (gv == 0)) | ((gr == 0) & (gv == 1))
    penal_prob = rng.random(MONTECARLO_N)
    gr[penal_mask & (penal_prob < 0.18)] = 1
    gv[penal_mask & (penal_prob < 0.18)] = 1

    res = []
    for r in range(7):
        for v in range(7):
            res.append({
                "River": r,
                "Rival": v,
                "prob": float(np.mean((gr == r) & (gv == v)))
            })

    return {
        "prob_victoria": float(np.mean(gr > gv)),
        "prob_empate":   float(np.mean(gr == gv)),
        "prob_derrota":  float(np.mean(gr < gv)),
        "df_resultados": pd.DataFrame(res),
        "lambda_r": lam_r,
        "lambda_v": lam_v,
        "n": MONTECARLO_N
    }


def obtener_tabla_goleadores(titulares, df_plantilla, lam_r):
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)].copy()

    def amenaza_base(pos):
        if "Delantero" in pos: return 0.05
        if "Mediocampista" in pos: return 0.03
        return 0.015

    def peso_pos(pos):
        if "Delantero" in pos: return 1.3
        if "Mediocampista" in pos: return 1.0
        return 0.7

    df_xi["amenaza"] = (
        (df_xi["xG_p90"] + df_xi["Posicion"].apply(amenaza_base))
        * df_xi["Posicion"].apply(peso_pos)
    )
    total = df_xi["amenaza"].sum()
    if total == 0: total = 1

    df_xi["% Prob. Gol"] = (
        (df_xi["amenaza"] / total) * (1 - np.exp(-lam_r)) * 100
    ).round(1)

    return df_xi[["Jugador", "Posicion", "xG_p90", "% Prob. Gol"]].sort_values(
        "% Prob. Gol", ascending=False
    )


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── VISUALIZACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fig_heatmap(sim, rival, style_fn=None):
    MAX_G = 5
    df = sim["df_resultados"]

    z = np.zeros((MAX_G + 1, MAX_G + 1))
    texto = [[""] * (MAX_G + 1) for _ in range(MAX_G + 1)]

    for _, row in df.iterrows():
        r, v = int(row["River"]), int(row["Rival"])
        if r <= MAX_G and v <= MAX_G:
            p = row["prob"] * 100
            z[v][r] = p
            texto[v][r] = f"{p:.1f}%" if p > 1.0 else ""

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[str(i) for i in range(MAX_G + 1)],
        y=[str(i) for i in range(MAX_G + 1)],
        text=texto,
        texttemplate="<b>%{text}</b>",
        colorscale=[[0, "rgba(0,0,0,0)"], [0.1, "#FEE2E2"], [1, RED]],
        showscale=False
    ))

    fig.update_layout(
        font_family="Rajdhani",
        font_size=14,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=450,
        # SOLUCIÓN: Márgenes más grandes (b=60, l=60) para que los textos de los ejes no se corten
        margin=dict(t=20, b=60, l=60, r=20),
        
        xaxis_title_text="⚽ GOLES RIVER PLATE",
        xaxis_title_font_size=16,
        xaxis_title_font_family="Rajdhani",
        xaxis_title_font_color=RED,
        xaxis_tickfont_size=14,
        xaxis_side="bottom",
        
        yaxis_title_text=f"⚽ GOLES {rival.upper()}",
        yaxis_title_font_size=16,
        yaxis_title_font_family="Rajdhani",
        yaxis_title_font_color=GRAY,
        yaxis_tickfont_size=14,
        
        hoverlabel_bgcolor="#111827",
        hoverlabel_bordercolor=RED,
        hoverlabel_font_color="white",
    )

    if style_fn:
        try: style_fn(fig)
        except: pass

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 4 ── RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_plotly_style_fn=None):
    st.markdown("""<style>
    .pred-kpi { background: #111827; border-left: 4px solid #D0021B; border-radius: 10px;
                padding: 16px 20px; text-align: center; }
    .pred-kpi .label { font-family: 'Rajdhani', sans-serif; font-size: 10px; color: #9CA3AF;
                       text-transform: uppercase; letter-spacing: 2px; font-weight: 700; }
    .pred-kpi .valor { font-family: 'Bebas Neue', cursive; font-size: 44px; color: #D0021B; line-height: 1; }
    .pred-kpi.empate .valor  { color: #9CA3AF; }
    .pred-kpi.derrota .valor { color: #1A4A8B; }
    .badge-datos { display: inline-block; padding: 3px 12px; border-radius: 20px;
                   font-family: 'Rajdhani'; font-size: 12px; font-weight: 700;
                   background: #1a4d1a; color: #66ff66; margin-bottom: 15px; }
    </style>""", unsafe_allow_html=True)

    df_liga      = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))

    if df_plantilla.empty:
        st.error("No se pudo cargar la plantilla desde el Excel. Verificá el archivo.")
        return

    st.markdown('<span class="badge-datos">✅ Torneo 2026 Sincronizado (J 13)</span>', unsafe_allow_html=True)

    c1, c2 = st.columns([2, 1])
    rival_sel = c1.selectbox(
        "🆚 Seleccioná el Rival",
        sorted([e for e in EQUIPOS_PRIMERA_2026 if e != "River"])
    )
    es_local = (
        c2.radio("📍 Condición", ["Monumental 🏟️", "Visitante ✈️"], horizontal=True)
        == "Monumental 🏟️"
    )

    opciones = [
        f"{r.Jugador} ({r.Posicion})"
        for _, r in df_plantilla.sort_values("Minutos", ascending=False).iterrows()
    ]
    titulares_raw = st.multiselect(
        "👥 Armá tu XI Titular:",
        opciones,
        default=opciones[:11],
        max_selections=11
    )
    titulares = [re.sub(r"\s*\(.*\)$", "", t).strip() for t in titulares_raw]

    boton_disabled = len(titulares) != 11
    if boton_disabled:
        st.info(f"Seleccioná exactamente 11 titulares ({len(titulares)}/11 seleccionados).")

    if st.button("🚀 SIMULAR PARTIDO", use_container_width=True, type="primary", disabled=boton_disabled):
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.markdown(f"### 📊 Resultado Probable: River vs {rival_sel}")

        k1, k2, k3, k4, k5 = st.columns(5)
        kpis = [
            (k1, "Victoria",        f"{sim['prob_victoria']*100:.1f}%", ""),
            (k2, "Empate",          f"{sim['prob_empate']*100:.1f}%",   "empate"),
            (k3, "Derrota",         f"{sim['prob_derrota']*100:.1f}%",  "derrota"),
            (k4, "λ River",         f"{lr:.2f}",                        ""),
            (k5, "λ Rival",         f"{lv:.2f}",                        ""),
        ]
        for col, label, valor, clase in kpis:
            col.markdown(
                f'<div class="pred-kpi {clase}"><div class="label">{label}</div>'
                f'<div class="valor">{valor}</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.tabs(["📊 Probabilidades", "⚽ Goleadores", "🎯 Marcadores", "🔬 Análisis XI"])

        with t1:
            fig_prob = go.Figure(go.Bar(
                x=[sim["prob_victoria"]*100, sim["prob_empate"]*100, sim["prob_derrota"]*100],
                y=["Victoria River", "Empate", "Derrota River"],
                orientation="h",
                marker_color=[RED, "#9CA3AF", "#1A4A8B"],
                text=[f"{v*100:.1f}%" for v in [sim["prob_victoria"], sim["prob_empate"], sim["prob_derrota"]]],
                textposition="outside"
            ))
            fig_prob.update_layout(**_ST, height=260, showlegend=False)
            if apply_plotly_style_fn:
                try: apply_plotly_style_fn(fig_prob)
                except: pass
            st.plotly_chart(fig_prob, use_container_width=True)

        with t2:
            st.markdown("#### Jugadores con mayor probabilidad de anotar hoy")
            df_gol = obtener_tabla_goleadores(titulares, df_plantilla, lr)
            
            df_gol_top = df_gol.head(7).sort_values("% Prob. Gol", ascending=True)
            
            fig_gol = go.Figure(go.Bar(
                x=df_gol_top["% Prob. Gol"],
                y=df_gol_top["Jugador"],
                orientation="h",
                marker_color=RED,
                text=df_gol_top["% Prob. Gol"].apply(lambda x: f"{x}%"),
                textposition="auto",
                textfont=dict(color="white", size=14, family="Rajdhani")
            ))
            fig_gol.update_layout(
                font_family="Rajdhani",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="#374151", title="% Probabilidad de Gol"),
                yaxis=dict(showgrid=False, title=""),
                height=350,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig_gol, use_container_width=True)

        with t3:
            st.info("💡 **Guía:** El color más rojo indica el resultado exacto más probable. Se omiten resultados casi imposibles (< 1%) para mayor claridad.")
            st.plotly_chart(
                fig_heatmap(sim, rival_sel, apply_plotly_style_fn),
                use_container_width=True
            )

        with t4:
            st.markdown("#### Rendimiento y Métrica del XI Inicial")
            df_xi_display = df_plantilla[df_plantilla["Jugador"].isin(titulares)][
                ["Jugador", "Posicion", "Nota", "xG_p90"]
            ].sort_values("Nota", ascending=False)
            
            st.dataframe(
                df_xi_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Jugador": st.column_config.TextColumn("👤 Jugador", width="medium"),
                    "Posicion": st.column_config.TextColumn("📍 Posición", width="small"),
                    "Nota": st.column_config.ProgressColumn(
                        "⭐ Nota SofaScore Media",
                        help="Calificación promedio reciente en la app SofaScore",
                        format="%.2f",
                        min_value=6.0,
                        max_value=8.5,
                    ),
                    "xG_p90": st.column_config.NumberColumn(
                        "⚽ Goles Esperados (xG/90')",
                        help="Medida de probabilidad de gol por cada 90 minutos jugados",
                        format="%.2f",
                    )
                }
            )
