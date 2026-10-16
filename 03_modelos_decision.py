"""Etapa 2b: modelos, calibración y capa de decisión (probabilidad -> exposición).

Núcleo congelado (metodologia_v2 §6.1, cobre HG1). Todo dentro del tramo de desarrollo
(2000-08-01 a 2024-09-30); el tramo fuera de muestra no se usa.

  Predicción    walk-forward expansivo desde 2010, reentreno cada 20 jornadas.
  Modelos       M0 frecuencia histórica · M1 logística Ridge · M2 LightGBM acotado · M3 promedio M1-M2.
  Calibración   Platt en línea, ajustado solo con predicciones fuera de muestra previas.
  Decisión      percentil móvil de 63 predicciones -> D1 siempre ±1 · D2 banda ±1 · D3 banda con ±3.
  Selección     2012-2017: ancho de banda q y activación de ±3.  Validación: 2018 a sep 2024.
  Significancia DM sobre log-loss vs M0; bootstrap estacionario vs referencias; Benjamini-Hochberg.

Uso: python 03_modelos_decision.py "base_usdclp (2).xlsx"
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from lightgbm import LGBMClassifier
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

etapa2a = importlib.import_module("02_seleccion_variables")
NUCLEO = list(etapa2a.NUCLEO)

INICIO_PRED = pd.Timestamp("2010-01-01")
SELECCION = ("2012-01-01", "2017-12-31")
VALIDACION = ("2018-01-01", etapa2a.FIN_DESARROLLO)
PASO = 20
C_RIDGE = 0.01
MIN_CALIB = 500                     # predicciones previas mínimas para ajustar Platt
VENTANA_PCT = 63
Q_GRILLA = np.round(np.arange(0.10, 0.46, 0.05), 2)
COLA_TRES = 0.05                    # ±3 solo en el 5 % más extremo de cada lado (metodología §8.1)
COSTO_SELECCION = 2e-4              # 2 pb por unidad de cambio de exposición (provisional)
COSTOS = [0.0, 2e-4, 5e-4]
HAC_LAGS = 5
N_BOOT, BLOQUE_MEDIO = 5000, 10
ALFA_BH = 0.10
SEMILLA = 0


def lgbm():
    return LGBMClassifier(n_estimators=300, learning_rate=0.02, max_depth=2, num_leaves=3,
                          min_child_samples=200, subsample=0.7, subsample_freq=1, colsample_bytree=0.7,
                          reg_lambda=10.0, random_state=SEMILLA, verbose=-1)


def ridge():
    return LogisticRegression(C=C_RIDGE, max_iter=1000)


# ---------------------------------------------------------------- predicción

def walk_forward(d, fabrica, escalar):
    X, y = d[NUCLEO].to_numpy(), d["up_next"].to_numpy()
    idx = np.flatnonzero(d.index >= INICIO_PRED)
    p = np.full(len(d), np.nan)
    for k in range(0, len(idx), PASO):
        bloque = idx[k:k + PASO]
        Xtr, Xte = X[:bloque[0]], X[bloque]
        if escalar:
            esc = StandardScaler().fit(Xtr)
            Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
        p[bloque] = fabrica().fit(Xtr, y[:bloque[0]]).predict_proba(Xte)[:, 1]
    return pd.Series(p, index=d.index)


def platt_en_linea(p, y):
    """Recalibra p con una logística sobre logit(p), ajustada solo con predicciones previas."""
    logit = np.log(p / (1 - p))
    out = pd.Series(np.nan, index=p.index)
    validas = np.flatnonzero(p.notna().to_numpy())
    for k in range(MIN_CALIB, len(validas), PASO):
        previas, bloque = validas[:k], validas[k:k + PASO]
        m = LogisticRegression(C=1e6, max_iter=1000).fit(logit.iloc[previas].to_frame(), y.iloc[previas])
        out.iloc[bloque] = m.predict_proba(logit.iloc[bloque].to_frame())[:, 1]
    return out


def predicciones(panel):
    d = panel[NUCLEO + ["up_next", "ret_next", "x_fedl01", "x_chni1m", "dias_next"]].dropna()
    y = d["up_next"]
    pred = pd.DataFrame(index=d.index)
    pred["M0_frecuencia"] = y.expanding().mean().shift(1).where(d.index >= INICIO_PRED)
    pred["M1_ridge"] = walk_forward(d, ridge, escalar=True)
    pred["M2_lgbm"] = walk_forward(d, lgbm, escalar=False)
    pred["M3_promedio"] = (pred["M1_ridge"] + pred["M2_lgbm"]) / 2
    for m in ["M1_ridge", "M2_lgbm", "M3_promedio"]:
        pred[m + "_cal"] = platt_en_linea(pred[m], y)
    return d, pred


# ---------------------------------------------------------------- calidad de la probabilidad

def logloss(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def hac_t(x):
    return sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}).tvalues[0]


def metricas_prob(pred, y, tramo, nombre_tramo):
    s = pred.loc[tramo[0]:tramo[1]].dropna()                # mismas jornadas para todos los modelos
    yy = y.loc[s.index].to_numpy()
    base = logloss(s["M0_frecuencia"].to_numpy(), yy)
    filas = []
    for m in s.columns:
        p = s[m].to_numpy()
        ll = logloss(p, yy)
        t = hac_t(base - ll) if m != "M0_frecuencia" else np.nan
        # pendiente de calibración: y ~ logit(p); 1 = bien calibrado, >1 = probabilidades tímidas
        pendiente = np.nan
        if m != "M0_frecuencia":                            # M0 es casi constante: pendiente no identificada
            pendiente = sm.Logit(yy, sm.add_constant(np.log(p / (1 - p)))).fit(disp=0).params[1]
        filas.append({"tramo": nombre_tramo, "modelo": m, "n": len(yy), "logloss": ll.mean(),
                      "d_logloss_vs_M0_x1e4": (ll - base).mean() * 1e4, "brier": ((yy - p) ** 2).mean(),
                      "acierto": ((p > 0.5) == yy).mean(), "p_media": p.mean(), "p_desv": p.std(),
                      "pendiente_calibracion": pendiente, "t_dm_vs_M0": t,
                      "p_dm_vs_M0": 1 - stats.norm.cdf(t) if m != "M0_frecuencia" else np.nan})
    return filas


# ---------------------------------------------------------------- capa de decisión

def percentil_movil(p):
    """Fracción de las últimas VENTANA_PCT predicciones (incluida la de hoy) menor o igual a la de hoy."""
    return p.rolling(VENTANA_PCT).apply(lambda w: (w <= w[-1]).mean(), raw=True)


def posiciones(p, diseño, q=None, con_tres=False):
    """D1: siempre ±1 según la mediana. D2: banda (±1 fuera de [q, 1-q], 0 dentro).
    DH: banda con histéresis (entra fuera de la banda, sale recién al cruzar la mediana).
    con_tres: ±3 en las colas fijas de COLA_TRES (5 % por lado, metodología §8.1)."""
    pct = percentil_movil(p)
    calidad = (p.rolling(VENTANA_PCT).std() > 1e-4) & pct.notna()   # filtro de calidad de señal (tesis)
    pos = pd.Series(0.0, index=p.index)
    if diseño == "D1":
        pos[pct > 0.5] = 1.0
        pos[pct <= 0.5] = -1.0
    elif diseño == "D2":
        pos[pct >= 1 - q] = 1.0
        pos[pct <= q] = -1.0
    elif diseño == "DH":
        actual = 0.0
        for i, (v, ok) in enumerate(zip(pct.to_numpy(), calidad.to_numpy())):
            if not ok:
                actual = 0.0
            elif v >= 1 - q:
                actual = 1.0
            elif v <= q:
                actual = -1.0
            elif (actual > 0 and v <= 0.5) or (actual < 0 and v > 0.5):
                actual = 0.0
            pos.iloc[i] = actual
    if con_tres:
        pos[pct >= 1 - COLA_TRES] = 3.0
        pos[pct <= COLA_TRES] = -3.0
    pos[~calidad] = 0.0
    return pos


def pnl(pos, d, costo):
    carry = (d["x_fedl01"] - d["x_chni1m"]) / 100 * d["dias_next"] / 360   # proxy: largo en USD paga el diferencial
    bruto = pos * (d["ret_next"] + carry)
    costos = costo * pos.diff().abs().fillna(pos.abs())
    return bruto - costos


def resumen_pnl(r, pos, d):
    eq = r.cumsum()
    activos = pos != 0
    acierto = (np.sign(pos[activos]) == np.sign(d.loc[activos[activos].index, "ret_next"])).mean()
    return {"n": len(r), "pnl_total": r.sum(), "media_anual": r.mean() * 252, "vol_anual": r.std() * np.sqrt(252),
            "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
            "max_drawdown": (eq - eq.cummax()).min(), "pct_dias_invertido": activos.mean(),
            "rotacion_anual": pos.diff().abs().sum() / len(pos) * 252, "acierto_dias_activos": acierto}


def elegir_q(p, d, tramo, diseño="D2"):
    """Ancho de banda: máximo del Sharpe suavizado (promedio con vecinos) en el tramo de selección."""
    filas = []
    for q in Q_GRILLA:
        pos = posiciones(p, diseño, q).loc[tramo[0]:tramo[1]]
        r = pnl(pos, d.loc[pos.index], COSTO_SELECCION)
        filas.append({"q": q, "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0.0})
    t = pd.DataFrame(filas)
    t["sharpe_suavizado"] = t["sharpe"].rolling(3, center=True, min_periods=2).mean()
    return t.loc[t["sharpe_suavizado"].idxmax(), "q"], t


def activar_tres(p, d, q, tramo):
    """±3 solo si, en selección, los días extremos aciertan más que los intermedios de la banda."""
    pct = percentil_movil(p).loc[tramo[0]:tramo[1]]
    ret = d.loc[pct.index, "ret_next"]
    direccion = np.where(pct >= 0.5, 1, -1)
    acierto = pd.Series(np.sign(ret) == direccion, index=pct.index)
    extremo = (pct >= 1 - COLA_TRES) | (pct <= COLA_TRES)
    banda = ((pct >= 1 - q) | (pct <= q)) & ~extremo
    a_ext, a_band = acierto[extremo].mean(), acierto[banda].mean()
    return bool(a_ext > a_band), a_ext, a_band, int(extremo.sum())


# ---------------------------------------------------------------- significancia

def indices_bootstrap(n, rng):
    """Matriz N_BOOT x n de índices del bootstrap estacionario (Politis-Romano), bloques de largo medio BLOQUE_MEDIO."""
    idx = np.empty((N_BOOT, n), np.int32)
    idx[:, 0] = rng.integers(n, size=N_BOOT)
    nuevos = rng.random((N_BOOT, n)) < 1 / BLOQUE_MEDIO
    saltos = rng.integers(n, size=(N_BOOT, n))
    for i in range(1, n):
        idx[:, i] = np.where(nuevos[:, i], saltos[:, i], (idx[:, i - 1] + 1) % n)
    return idx


def p_bootstrap(x, idx):
    """p unilateral de media(x) > 0: fracción de medias remuestreadas y centradas que superan la observada."""
    x = np.asarray(x)
    medias = x[idx].mean(axis=1)
    return ((medias - x.mean()) >= x.mean()).mean()


def benjamini_hochberg(p, alfa):
    p = np.asarray(p)
    orden = np.argsort(p)
    pasa = p[orden] <= alfa * np.arange(1, len(p) + 1) / len(p)
    k = np.max(np.flatnonzero(pasa)) + 1 if pasa.any() else 0
    rechaza = np.zeros(len(p), bool)
    rechaza[orden[:k]] = True
    return rechaza


# ---------------------------------------------------------------- principal

def main(xlsx):
    panel = etapa2a.construir_panel(xlsx)
    d, pred = predicciones(panel)
    y = d["up_next"]
    print(f"jornadas modeladas: {len(d)}; predicciones desde {pred['M1_ridge'].first_valid_index().date()}; "
          f"calibradas desde {pred['M1_ridge_cal'].first_valid_index().date()}")

    prob = pd.DataFrame(metricas_prob(pred, y, (SELECCION[0], VALIDACION[1]), "2012-2024")
                        + metricas_prob(pred, y, SELECCION, "seleccion")
                        + metricas_prob(pred, y, VALIDACION, "validacion"))

    # La capa de decisión usa percentiles, invariantes ante la recalibración monótona: se usan p crudas.
    modelos = ["M1_ridge", "M2_lgbm", "M3_promedio"]
    estrategias, grillas, tres = {}, [], []
    for m in modelos:
        p = pred[m]
        q, g = elegir_q(p, d, SELECCION)
        grillas.append(g.assign(modelo=m))
        activo, a_ext, a_band, n_ext = activar_tres(p, d, q, SELECCION)
        tres.append({"modelo": m, "q_elegido": q, "activa_tres": activo, "acierto_extremos": a_ext,
                     "acierto_banda": a_band, "n_extremos_seleccion": n_ext})
        estrategias[f"{m}|D1_siempre"] = posiciones(p, "D1")
        estrategias[f"{m}|D2_banda_q{q}"] = posiciones(p, "D2", q)
        estrategias[f"{m}|D3_banda_tres"] = posiciones(p, "D2", q, con_tres=activo)
        qh, gh = elegir_q(p, d, SELECCION, "DH")
        grillas.append(gh.assign(modelo=m + "|DH"))
        estrategias[f"{m}|DH_histeresis_q{qh}"] = posiciones(p, "DH", qh)

    val = slice(*VALIDACION)
    referencias = {"REF_siempre_+1": 1.0, "REF_nunca_0": 0.0, "REF_siempre_-1": -1.0}
    filas = []
    for costo in COSTOS:
        for nombre, pos in {**estrategias, **{k: pd.Series(v, index=d.index) for k, v in referencias.items()}}.items():
            pv = pos.loc[val]
            filas.append({"estrategia": nombre, "costo_pb": costo * 1e4,
                          **resumen_pnl(pnl(pv, d.loc[pv.index], costo), pv, d.loc[pv.index])})
    resultados = pd.DataFrame(filas)

    idx_boot = indices_bootstrap(len(d.loc[val]), np.random.default_rng(SEMILLA))
    boot = []
    for nombre, pos in estrategias.items():
        pv = pos.loc[val]
        r = pnl(pv, d.loc[pv.index], COSTO_SELECCION)
        for ref, nivel in referencias.items():
            r_ref = pnl(pd.Series(nivel, index=pv.index), d.loc[pv.index], COSTO_SELECCION)
            boot.append({"estrategia": nombre, "referencia": ref,
                         "dif_media_anual": (r - r_ref).mean() * 252,
                         "p_bootstrap": p_bootstrap((r - r_ref).to_numpy(), idx_boot)})
    boot = pd.DataFrame(boot)
    boot["bh_10"] = benjamini_hochberg(boot["p_bootstrap"], ALFA_BH)

    conviccion = []
    for nombre, pos in estrategias.items():
        pv = pos.loc[val]
        ret = d.loc[pv.index, "ret_next"]
        for nivel, g in pv.groupby(pv):
            conviccion.append({"estrategia": nombre, "posicion": nivel, "dias": len(g),
                               "acierto": (np.sign(ret[g.index]) == np.sign(nivel)).mean() if nivel != 0 else np.nan,
                               "ret_medio_pb": ret[g.index].mean() * 1e4})
    conviccion = pd.DataFrame(conviccion)

    salida = Path("resultados")
    salida.mkdir(exist_ok=True)
    with pd.ExcelWriter(salida / "modelos_decision.xlsx") as w:
        prob.to_excel(w, sheet_name="probabilidad", index=False)
        pd.concat(grillas).to_excel(w, sheet_name="seleccion_q", index=False)
        pd.DataFrame(tres).to_excel(w, sheet_name="activacion_tres", index=False)
        resultados.to_excel(w, sheet_name="estrategias_validacion", index=False)
        boot.to_excel(w, sheet_name="bootstrap", index=False)
        conviccion.to_excel(w, sheet_name="conviccion", index=False)
    pd.concat([d[["ret_next"]], pred, pd.DataFrame(estrategias)], axis=1).to_csv(salida / "senales_desarrollo.csv")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(prob.round(4).to_string())
    print(pd.concat(grillas).round(3).to_string())
    print(pd.DataFrame(tres).round(4).to_string())
    print(resultados.round(4).to_string())
    print(boot.round(4).to_string())
    print(conviccion.round(4).to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base_usdclp (2).xlsx")
