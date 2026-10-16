"""Etapa 2a: poder predictivo de las variables candidatas y diagnóstico del núcleo.

Implementa el protocolo de metodologia_v2.md (§3 y §5):
  - Panel por jornada del USD/CLP, relleno <= 5 días calendario, FEDL01 rezagada.
  - Solo tramo de desarrollo (2000-08-01 a 2024-09-30); el tramo fuera de muestra no se usa.
  - Etapa A: ret_next ~ Δx (HAC 5).  Etapa B: ret_next ~ núcleo + Δx (HAC 5).
  - Etapa C: walk-forward, logística Ridge núcleo vs núcleo + candidata; Clark-West y DM.
  - Benjamini-Hochberg al 10 % sobre los p de Clark-West de la etapa C.

Uso: python 02_seleccion_variables.py "base_usdclp (2).xlsx"
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

INICIO, FIN_DESARROLLO = "2000-08-01", "2024-09-30"
INICIO_EVAL = pd.Timestamp("2010-01-01")
AÑOS_CALENTAMIENTO = 5          # para variantes que parten tarde
PASO_REENTRENO = 20
C_RIDGE = 0.01                  # fijada de antemano (baseline del resumen técnico)
C_SENSIBILIDAD = 1.0
HAC_LAGS = 5
ALFA_BH = 0.10
SUBPERIODOS = [("2000-08-01", "2009-12-31"), ("2010-01-01", "2019-12-31"), ("2020-01-01", FIN_DESARROLLO)]

# Transformación: "r" retorno logarítmico (precios), "d" primera diferencia (tasas y volatilidades)
NUCLEO = {
    "r_usdclp": ("USDCLP Curncy|PX_LAST", "r"),
    "r_cobre": ("HG1 Comdty|PX_LAST", "r"),     # COMEX; reemplaza a LMCADS03 (metodologia_v2 §6)
    "r_dxy": ("DXY Curncy|PX_LAST", "r"),
    "d_vix": ("VIX Index|PX_LAST", "d"),
    "d_ust2y": ("USGG2YR Index|PX_LAST", "d"),
    "d_fedl01": ("FEDL01 Index|PX_LAST", "d"),
    "d_chni1m": ("CHNI1M Curncy|PX_LAST", "d"),
    "d_chni3m": ("CHNI3M Curncy|PX_LAST", "d"),
    "d_chni6m": ("CHNI6M Curncy|PX_LAST", "d"),
    "r_usdbrl": ("USDBRL Curncy|PX_LAST", "r"),
    "r_usdmxn": ("USDMXN Curncy|PX_LAST", "r"),
    "d_vol1m": ("USDCLPV1M Curncy|PX_LAST", "d"),
    "d_vol3m": ("USDCLPV3M Curncy|PX_LAST", "d"),
}
CANDIDATAS = {
    "r_usdzar": ("USDZAR Curncy|PX_LAST", "r"),
    "d_move": ("MOVE Index|PX_LAST", "d"),
    "r_mxef": ("MXEF Index|PX_LAST", "r"),
    "r_brent": ("CO1 Comdty|PX_LAST", "r"),
    "d_jpmvxyem": ("JPMVXYEM Index|PX_LAST", "d"),
    "r_usdcop": ("USDCOP Curncy|PX_LAST", "r"),
    "r_usdpen": ("USDPEN Curncy|PX_LAST", "r"),
    # variantes que parten después de 2000
    "d_tpm": ("CHOVCHOV Index|PX_LAST", "d"),
    "d_chswp1": ("CHSWP1 Curncy|PX_LAST", "d"),
    "d_chswp10": ("CHSWP10 Curncy|PX_LAST", "d"),
    "r_usdcnh": ("USDCNH Curncy|PX_LAST", "r"),
}
AUXILIARES = {"d_ust10y": ("USGG10YR Index|PX_LAST", "d")}
REZAGO_PUBLICACION = {"FEDL01 Index|PX_LAST"}


def construir_panel(xlsx, fin=FIN_DESARROLLO, hasta=None):
    """fin=None conserva hasta la última jornada, cuyo objetivo queda vacío (señal del día).
    hasta trunca la base en esa fecha, como si fuera la última disponible."""
    datos = pd.read_excel(xlsx, sheet_name="datos").set_index("fecha").sort_index()
    if hasta is not None:
        datos = datos.loc[:hasta]
    datos = datos.asfreq("D")                                   # calendario continuo
    jornada = datos["USDCLP Curncy|PX_LAST"].notna()            # el objetivo no se rellena
    lleno = datos.ffill(limit=5)                                # relleno sobre el calendario completo
    for col in REZAGO_PUBLICACION:
        lleno[col] = lleno[col].shift(1)
    lleno = lleno[jornada]                                      # secuencia de jornadas

    panel = pd.DataFrame(index=lleno.index)
    for nombre, (col, tipo) in {**NUCLEO, **CANDIDATAS, **AUXILIARES}.items():
        x = lleno[col]
        panel[nombre] = np.log(x).diff() if tipo == "r" else x.diff()
    panel["d_pend_us"] = panel.pop("d_ust10y") - panel["d_ust2y"]
    panel["r_regional"] = panel[["r_usdcop", "r_usdpen"]].mean(axis=1, skipna=False)

    px = lleno["USDCLP Curncy|PX_LAST"]
    panel["ret_next"] = np.log(px.shift(-1) / px)
    panel["up_next"] = (panel["ret_next"] > 0).astype(float).where(panel["ret_next"].notna())
    # insumos del carry proxy (niveles en % anual, información de t) y días hasta la próxima jornada
    panel["x_fedl01"] = lleno["FEDL01 Index|PX_LAST"]
    panel["x_chni1m"] = lleno["CHNI1M Curncy|PX_LAST"]
    panel["dias_next"] = pd.Series(panel.index, index=panel.index).diff().shift(-1).dt.days

    panel = panel.loc[INICIO:fin]
    if fin is not None:
        panel = panel.iloc[:-1]                                 # ret_next no puede cruzar el corte
    lunes = (panel.index.dayofweek == 0).mean()
    assert 0.17 < lunes < 0.23, f"proporción de lunes anómala: {lunes:.3f}"
    assert panel.index.is_unique and panel.index.is_monotonic_increasing
    return panel


def ols_hac(y, X):
    return sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})


def etapa_a(panel, var):
    d = panel[[var, "ret_next"]].dropna()
    fila = {"n_A": len(d)}
    res = ols_hac(d["ret_next"], d[[var]])
    rho = d[var].corr(d["ret_next"])
    fila.update(rho=rho, t_hac_A=res.tvalues[var], p_A=res.pvalues[var],
                acierto_teorico=0.5 + np.arcsin(rho) / np.pi)
    return fila


def signos_por_subperiodo(panel, var, base):
    """Signo del coeficiente de var (con el núcleo) en cada subperíodo con datos suficientes."""
    signos = []
    for ini, fin in SUBPERIODOS:
        d = panel.loc[ini:fin, base + [var, "ret_next"]].dropna()
        if len(d) < 500:
            continue
        signos.append(np.sign(ols_hac(d["ret_next"], d[base + [var]]).params[var]))
    return signos


def etapa_b(panel, var, base):
    d = panel[base + [var, "ret_next"]].dropna()
    res = ols_hac(d["ret_next"], d[base + [var]])
    signo = np.sign(res.params[var])
    sub = signos_por_subperiodo(panel, var, base)
    estables = sum(s == signo for s in sub)
    return {"n_B": len(d), "beta_B_std": res.params[var] * d[var].std() * 1e4,  # pb de ret_next por 1 desv. est.
            "t_hac_B": res.tvalues[var], "p_B": res.pvalues[var],
            "signo_estable": f"{estables}/{len(sub)}",
            "cumple_signo": len(sub) > 0 and estables >= max(2, int(np.ceil(2 * len(sub) / 3)))}


def walk_forward(d, feats, inicio_eval, C):
    """Probabilidades de alza fuera de muestra, ventana expansiva, reentreno cada PASO_REENTRENO jornadas."""
    X, y = d[feats].to_numpy(), d["up_next"].to_numpy()
    idx_eval = np.flatnonzero(d.index >= inicio_eval)
    p = np.full(len(d), np.nan)
    for k in range(0, len(idx_eval), PASO_REENTRENO):
        bloque = idx_eval[k:k + PASO_REENTRENO]
        fin_train = bloque[0]                                   # entrena con todo lo anterior
        esc = StandardScaler().fit(X[:fin_train])
        mod = LogisticRegression(C=C, max_iter=1000).fit(esc.transform(X[:fin_train]), y[:fin_train])
        p[bloque] = mod.predict_proba(esc.transform(X[bloque]))[:, 1]
    return p[idx_eval], y[idx_eval]


def hac_t(serie):
    """Estadístico t de la media de una serie con errores Newey-West."""
    res = sm.OLS(serie, np.ones(len(serie))).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    return res.tvalues[0]


def comparar(p_chico, p_grande, y):
    """Modelo grande (anida al chico) vs chico. p unilaterales: el grande es mejor."""
    eps = 1e-12
    ll = lambda p: -(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
    d_ll = ll(p_grande) - ll(p_chico)
    br_c, br_g = (y - p_chico) ** 2, (y - p_grande) ** 2
    cw = br_c - (br_g - (p_chico - p_grande) ** 2)               # Clark-West (2007) sobre el Brier
    t_cw, t_dm = hac_t(cw), hac_t(-d_ll)
    return {"n_C": len(y), "d_logloss_x1e4": d_ll.mean() * 1e4, "d_brier_x1e4": (br_g - br_c).mean() * 1e4,
            "t_cw": t_cw, "p_cw": 1 - stats.norm.cdf(t_cw), "t_dm": t_dm, "p_dm": 1 - stats.norm.cdf(t_dm),
            "acierto_chico": ((p_chico > 0.5) == y).mean(), "acierto_grande": ((p_grande > 0.5) == y).mean()}


def etapa_c(panel, base, grande, C=C_RIDGE):
    d = panel[grande + ["up_next"]].dropna()
    inicio = max(INICIO_EVAL, d.index[0] + pd.DateOffset(years=AÑOS_CALENTAMIENTO))
    p_c, y = walk_forward(d, base, inicio, C)
    p_g, _ = walk_forward(d, grande, inicio, C)
    out = comparar(p_c, p_g, y)
    out["eval_desde"] = inicio.date()
    return out


def benjamini_hochberg(p, alfa):
    p = np.asarray(p)
    orden = np.argsort(p)
    umbral = alfa * np.arange(1, len(p) + 1) / len(p)
    pasa = p[orden] <= umbral
    k = np.max(np.flatnonzero(pasa)) + 1 if pasa.any() else 0
    rechaza = np.zeros(len(p), bool)
    rechaza[orden[:k]] = True
    return rechaza


def evaluar_candidatas(panel):
    base = list(NUCLEO)
    candidatas = [c for c in CANDIDATAS if c not in ("r_usdcop", "r_usdpen")] + ["r_usdcop", "r_usdpen", "r_regional", "d_pend_us"]
    filas = []
    for var in candidatas:
        print("candidata", var, flush=True)
        fila = {"variable": var, "inicio": panel[var].first_valid_index().date()}
        fila |= etapa_a(panel, var) | etapa_b(panel, var, base) | etapa_c(panel, base, base + [var])
        fila["d_logloss_x1e4_C1"] = etapa_c(panel, base, base + [var], C_SENSIBILIDAD)["d_logloss_x1e4"]
        filas.append(fila)
    t = pd.DataFrame(filas)
    t["bh_10"] = benjamini_hochberg(t["p_cw"], ALFA_BH)
    t["bonferroni_10"] = t["p_cw"] <= ALFA_BH / len(t)
    t["incluir"] = (t["d_logloss_x1e4"] < 0) & t["bh_10"] & t["cumple_signo"]
    return t


def diagnosticar_nucleo(panel):
    base = list(NUCLEO)
    d = panel[base + ["ret_next", "up_next"]].dropna()
    res = ols_hac(d["ret_next"], d[base])
    filas = []
    for var in base:
        print("núcleo", var, flush=True)
        resto = [v for v in base if v != var]
        fila = {"variable": var} | etapa_a(panel, var)
        fila |= {"t_hac_B": res.tvalues[var], "p_B": res.pvalues[var],
                 "signo_estable": etapa_b(panel, var, resto)["signo_estable"]}
        fila |= {k + "_sin_var": v for k, v in etapa_c(panel, resto, base).items()
                 if k in ("d_logloss_x1e4", "t_cw", "p_cw")}
        filas.append(fila)
    t = pd.DataFrame(filas)

    # núcleo completo frente a referencias triviales en el mismo período de evaluación
    p_core, y = walk_forward(d, base, INICIO_EVAL, C_RIDGE)
    frecuencia = d["up_next"].expanding().mean().shift(1).loc[INICIO_EVAL:].to_numpy()  # tasa histórica de alzas
    p_usd, _ = walk_forward(d, ["r_usdclp"], INICIO_EVAL, C_RIDGE)
    global_ = pd.DataFrame([
        {"comparacion": "núcleo vs frecuencia histórica", **comparar(frecuencia, p_core, y)},
        {"comparacion": "núcleo vs solo r_usdclp", **comparar(p_usd, p_core, y)},
        {"comparacion": "núcleo completo vs reducido (§4)", **comparar(*_reducido_vs_completo(panel))},
    ])
    return t, global_


def _reducido_vs_completo(panel):
    """Núcleo reducido (§4 de la metodología) como 'chico' frente al completo como 'grande'."""
    panel = panel.copy()
    panel["d_pend_chni"] = panel["d_chni6m"] - panel["d_chni1m"]
    completo = list(NUCLEO)
    reducido = [v for v in completo if v not in ("d_chni3m", "d_chni6m", "d_vol3m")] + ["d_pend_chni"]
    d = panel[completo + ["d_pend_chni", "up_next"]].dropna()
    p_r, y = walk_forward(d, reducido, INICIO_EVAL, C_RIDGE)
    p_c, _ = walk_forward(d, completo, INICIO_EVAL, C_RIDGE)
    return p_r, p_c, y


def main(xlsx):
    panel = construir_panel(xlsx)
    print(f"panel: {len(panel)} jornadas, {panel.index[0].date()} a {panel.index[-1].date()}")
    cand = evaluar_candidatas(panel)
    nucleo, global_ = diagnosticar_nucleo(panel)
    salida = Path("resultados")
    salida.mkdir(exist_ok=True)
    with pd.ExcelWriter(salida / "seleccion_variables.xlsx") as w:
        cand.to_excel(w, sheet_name="candidatas", index=False)
        nucleo.to_excel(w, sheet_name="nucleo", index=False)
        global_.to_excel(w, sheet_name="nucleo_global", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(cand.round(4).to_string())
    print(nucleo.round(4).to_string())
    print(global_.round(4).to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base_usdclp (2).xlsx")
