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

# Lista maestra para evitar equipos "fantasma" de internet
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
        
        # FILTRO CRÍTICO: Solo equipos de nuestra lista oficial
        df_liga = df_liga[df_liga["equipo"].isin(EQUIPOS_PRIMERA_2026)].dropna()
        
        for c in ["PJ", "GF", "GC"]: df_liga[c] = pd.to_numeric(df_liga[c], errors="coerce")
        return df_liga.reset_index(drop=True), True
    except:
        # Fallback ultra-completo
        data = [{"equipo": e, "PJ": 20, "GF": 25, "GC": 25} for e in EQUIPOS_PRIMERA_2026]
        return pd.DataFrame(data), False

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
        df_h = pd.read_excel(ruta, sheet_name=hoja)
        df_h.columns = df_h.columns.astype(str).str.strip()
        if "Jugador" not in df_h.columns: continue
        
        df_h["Jugador"] = df_h["Jugador"].fillna("").astype(str).str.strip().str.title()
        df_h["Minutos"] = pd.to_numeric(df_h.get("Minutos", 0), errors="coerce").fillna(0)
        df_h = df_h[(df_h["Jugador"] != "") & (df_h["Minutos"] > 0)].copy()
        df_h["Partido"] = hoja
        filas.append(df_h)

    if not filas: return pd.DataFrame()
    df_todos = pd.concat(filas, ignore_index=True)
    
    # Convertir métricas
    for c in ["Goles", "Intercepciones", "Nota SofaScore"]:
        df_todos[c] = pd.to_numeric(df_todos.get(c, 0), errors="coerce").fillna(0)

    agg = df_todos.groupby("Jugador", as_index=False).agg(
        Posicion = ("Posición", lambda x: x.mode()[0] if not x.mode().empty else "MID"),
        Minutos  = ("Minutos", "sum"),
        Nota     = ("Nota SofaScore", lambda x: x[x>0].mean() if not x[x>0].empty else 6.5),
        Goles    = ("Goles", "sum"),
        Inter    = ("Intercepciones", "sum")
    )

    # CORRECCIÓN: Filtro de minutos casi inexistente para que aparezcan todos
    agg = agg[agg["Minutos"] >= 1].copy() 
    
    m90 = agg["Minutos"] / 90
    agg["xG_p90"]  = (agg["Goles"] / m90).round(3)
    agg["xGA_p90"] = (agg["Inter"] / m90).round(3)
    agg["forma"]   = (agg["Nota"] / 7.0).clip(0.7, 1.3) # Balanceado
    
    return agg.reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 2 ── CÁLCULO DE FUERZAS Y SIMULACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def calcular_lambdas(df_liga, rival, titulares, df_plantilla, es_local):
    # Medias liga
    mgf = (df_liga["GF"] / df_liga["PJ"]).mean()
    
    # Fuerza Rival
    r_data = df_liga[df_liga["equipo"] == rival].iloc[0]
    fa_rival = (r_data["GF"] / r_data["PJ"]) / mgf
    fd_rival = (r_data["GC"] / r_data["PJ"]) / mgf
    
    # Fuerza River Base
    riv_base = df_liga[df_liga["equipo"] == "River Plate"].iloc[0]
    fa_river = (riv_base["GF"] / riv_base["PJ"]) / mgf
    fd_river = (riv_base["GC"] / riv_base["PJ"]) / mgf
    
    # Ajuste por XI (Suavizado para balance)
    df_xi = df_plantilla[df_plantilla["Jugador"].isin(titulares)]
    mult_atk = (df_xi["xG_p90"].mean() / df_plantilla["xG_p90"].mean() + 1) / 2
    mult_def = (df_xi["xGA_p90"].mean() / df_plantilla["xGA_p90"].mean() + 1) / 2
    forma    = df_xi["forma"].mean()

    # Localía 15%
    f_river = 1.15 if es_local else 1.0
    f_rival = 1.0 if es_local else 1.15

    lam_r = fa_river * mult_atk * (1/max(fd_rival, 0.5)) * mgf * forma * f_river
    lam_v = fa_rival * (1/max(fd_river * mult_def, 0.5)) * mgf * (1/forma) * f_rival
    
    return round(float(np.clip(lam_r, 0.5, 5.0)), 3), round(float(np.clip(lam_v, 0.5, 5.0)), 3)

def simular_montecarlo(lam_r, lam_v):
    rng = np.random.default_rng(42)
    gr = rng.poisson(lam_r, MONTECARLO_N)
    gv = rng.poisson(lam_v, MONTECARLO_N)
    
    # Ajuste Dixon-Coles para empates (30% de realismo)
    for i in range(MONTECARLO_N):
        if ((gr[i]==1 and gv[i]==0) or (gr[i]==0 and gv[i]==1)) and rng.random() < 0.25:
            gr[i], gv[i] = 1, 1

    prob_w = np.mean(gr > gv)
    prob_d = np.mean(gr == gv)
    prob_l = np.mean(gr < gv)
    
    res = []
    for r in range(7):
        for v in range(7):
            res.append({"River": r, "Rival": v, "prob": np.mean((gr==r) & (gv==v))})
            
    return {"prob_victoria": prob_w, "prob_empate": prob_d, "prob_derrota": prob_l, "df_res": pd.DataFrame(res), "gr": gr, "gv": gv}

# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO 3 ── RENDER (STREAMLIT)
# ─────────────────────────────────────────────────────────────────────────────

def render_predictor(ruta_excel: Path, apply_style=None):
    df_liga, real = obtener_estadisticas_liga()
    df_plantilla = extraer_plantilla_river(str(ruta_excel))
    
    if df_plantilla.empty:
        st.error("No se detectaron jugadores en el Excel.")
        return

    st.markdown(f'<span style="color:#66ff66">✔ {len(df_plantilla)} jugadores cargados</span>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        rival_sel = st.selectbox("Rival", sorted([e for e in df_liga["equipo"] if e != "River Plate"]))
    with c2:
        es_local = st.radio("Condición", ["Local", "Visitante"], horizontal=True) == "Local"

    st.markdown("### Seleccioná tus 11")
    # Ordenar para que sea fácil elegir
    df_p = df_plantilla.sort_values("Minutos", ascending=False)
    opciones = [f"{row.Jugador} ({row.Posicion})" for _, row in df_p.iterrows()]
    seleccionados_raw = st.multiselect("Titulares", opciones, default=opciones[:11], max_selections=11)
    
    titulares = [s.split(" (")[0] for s in seleccionados_raw]

    if len(titulares) == 11:
        lr, lv = calcular_lambdas(df_liga, rival_sel, titulares, df_plantilla, es_local)
        sim = simular_montecarlo(lr, lv)

        st.divider()
        k1, k2, k3 = st.columns(3)
        k1.metric("Victoria River", f"{sim['prob_victoria']*100:.1f}%")
        k2.metric("Empate", f"{sim['prob_empate']*100:.1f}%")
        k3.metric("Derrota River", f"{sim['prob_derrota']*100:.1f}%")
        
        # Tabla técnica rápida abajo
        with st.expander("Ver detalles del cálculo"):
            st.write(f"Lambda River: {lr} | Lambda Rival: {lv}")
            st.dataframe(df_plantilla[df_plantilla["Jugador"].isin(titulares)])
    else:
        st.warning("Faltan elegir jugadores para el XI.")
