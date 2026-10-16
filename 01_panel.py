#!/usr/bin/env python3
"""
Etapa 1 - Panel limpio, objetivo y referencias provisionales (USD/CLP)
======================================================================

Que hace
--------
1. Lee la hoja `datos` de base_usdclp.xlsx (formato ancho, indice = dias calendario).
2. Se queda con las series decididas en la matriz de disponibilidad (grupos `core`,
   `probar`, `swaps`, `cnh`).
3. Relleno acotado hacia adelante (FFILL_DIAS dias calendario) SOLO para feriados de
   otros mercados; nada mas se rellena.
4. Rezago de publicacion: las series en LAG_1D se desplazan un dia (FEDL01 se publica
   al dia siguiente). Es una precaucion; el rezago exacto esta por confirmar.
5. Transforma: retornos logaritmicos (precios), diferencias (tasas y volatilidades) y
   niveles de las variables de estado. Todo mira hacia atras.
6. Construye el objetivo: retorno del USD/CLP de la proxima jornada (cierre a cierre).
   Es lo UNICO que usa informacion futura y va en columnas separadas (TARGET_COLS).
7. Chequeos de calidad + prueba anti look-ahead por truncamiento + prueba de lunes
   (el panel debe tener lunes en proporcion ~1/5; si faltan, las diferencias se
   calcularon sobre el calendario continuo y no sobre la secuencia de jornadas).
8. Referencias provisionales (siempre largo, plano, siempre corto) con un carry proxy.

IMPORTANTE - supuestos provisionales (reemplazar con el kit del laboratorio)
----------------------------------------------------------------------------
* Retorno = cierre a cierre del USD/CLP (PX_LAST). Confirmar con el codigo de evaluacion.
* Carry proxy = (FEDL01 rezagado - CHNI1M) / 100 * dias / 360 por unidad de exposicion.
  El laboratorio entrega su propio carry; usar ese.
* Costos: COSTO_BPS = 0 por defecto (el kit define los costos reales).
* Periodo fuera de muestra: OOS_INICIO es un valor de trabajo, no el del laboratorio.
* Las "tres referencias" del torneo no estan definidas sin ambiguedad en las bases;
  aqui se usan +1, 0 y -1 como referencias de trabajo.

Uso
---
    python 01_panel.py --xlsx "base_usdclp (2).xlsx" --variante core --salida data/
    python 01_panel.py --xlsx "base_usdclp (2).xlsx" --variante swaps2003
    python 01_panel.py --xlsx "base_usdclp (2).xlsx" --variante full2010

Salidas (carpeta --salida): panel_<variante>.csv, referencias_<variante>.csv,
chequeos_<variante>.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- config
HOJA = "datos"
TARGET = "USDCLP Curncy|PX_LAST"
FFILL_DIAS = 5            # dias calendario: cubre fin de semana + feriado
STALE_DIAS = 7            # alerta si la ultima observacion de una serie es mas vieja
LAG_1D = {"fedl01"}       # publicadas al dia siguiente (por confirmar)
COSTO_BPS = 0.0           # por unidad de cambio de exposicion (placeholder)
OOS_INICIO = "2024-10-01" # placeholder de trabajo
DIAS_ANIO = 252
LUNES_RANGO = (0.17, 0.23) # proporcion aceptable de lunes en el panel (metodologia_v2 §3.3)

# alias, columna de la base, transformacion, grupo
#   log      -> retorno logaritmico  r_<alias>
#   diff     -> primera diferencia   d_<alias>
#   *+lvl    -> ademas el nivel      x_<alias>
SPEC = [
    ("usdclp",   TARGET,                          "log+lvl",  "core"),
    ("cobre",    "LMCADS03 Comdty|PX_LAST",       "log",      "core"),
    ("dxy",      "DXY Curncy|PX_LAST",            "log",      "core"),
    ("vix",      "VIX Index|PX_LAST",             "log+lvl",  "core"),
    ("ust2y",    "USGG2YR Index|PX_LAST",         "diff+lvl", "core"),
    ("fedl01",   "FEDL01 Index|PX_LAST",          "diff+lvl", "core"),
    ("chni1m",   "CHNI1M Curncy|PX_LAST",         "diff+lvl", "core"),
    ("chni3m",   "CHNI3M Curncy|PX_LAST",         "diff+lvl", "core"),
    ("chni6m",   "CHNI6M Curncy|PX_LAST",         "diff+lvl", "core"),
    ("usdbrl",   "USDBRL Curncy|PX_LAST",         "log",      "core"),
    ("usdmxn",   "USDMXN Curncy|PX_LAST",         "log",      "core"),
    ("clpv1m",   "USDCLPV1M Curncy|PX_LAST",      "diff+lvl", "core"),
    ("clpv3m",   "USDCLPV3M Curncy|PX_LAST",      "diff+lvl", "core"),
    # a probar
    ("hg1",      "HG1 Comdty|PX_LAST",            "log",      "probar"),
    ("move",     "MOVE Index|PX_LAST",            "log+lvl",  "probar"),
    ("mxef",     "MXEF Index|PX_LAST",            "log",      "probar"),
    ("brent",    "CO1 Comdty|PX_LAST",            "log",      "probar"),
    ("jpmvxy",   "JPMVXYEM Index|PX_LAST",        "diff+lvl", "probar"),
    ("usdzar",   "USDZAR Curncy|PX_LAST",         "log",      "probar"),
    # variante swaps / TPM
    ("chswp1",   "CHSWP1 Curncy|PX_LAST",         "diff+lvl", "swaps"),
    ("chswp10",  "CHSWP10 Curncy|PX_LAST",        "diff+lvl", "swaps"),
    ("tpm",      "CHOVCHOV Index|PX_LAST",        "diff+lvl", "swaps"),
    # variante 2010+
    ("usdcnh",   "USDCNH Curncy|PX_LAST",         "log",      "cnh"),
]
VARIANTES = {
    "core":      {"inicio": "2000-08-01", "grupos": {"core", "probar"}},
    "swaps2003": {"inicio": "2003-06-10", "grupos": {"core", "probar", "swaps"}},
    "full2010":  {"inicio": "2010-01-01", "grupos": {"core", "probar", "swaps", "cnh"}},
}
TARGET_COLS = ["ret_next", "up_next", "dias_next"]


# --------------------------------------------------------------------------- carga
def cargar_raw(xlsx):
    d = pd.read_excel(xlsx, sheet_name=HOJA)
    d["fecha"] = pd.to_datetime(d["fecha"])
    d = d.set_index("fecha").sort_index()
    if d.index.has_duplicates:
        raise ValueError("Fechas duplicadas en la hoja de datos")
    # el indice debe ser calendario diario continuo (asi viene la base)
    d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"))
    return d.apply(pd.to_numeric, errors="coerce")


# --------------------------------------------------------------------------- panel
def construir_panel(raw, variante="core"):
    """Solo mira hacia atras, salvo las columnas TARGET_COLS."""
    cfg = VARIANTES[variante]
    spec = [s for s in SPEC if s[3] in cfg["grupos"]]
    faltan = [s[1] for s in spec if s[1] not in raw.columns]
    if faltan:
        raise KeyError(f"Columnas no encontradas en la base: {faltan}")

    cols = [s[1] for s in spec]
    cal = raw[cols].copy()
    # 3. relleno acotado sobre el calendario completo (no inventa datos nuevos)
    cal = cal.ffill(limit=FFILL_DIAS)
    # 4. rezago de publicacion (sobre el calendario: el lunes ve el valor del viernes)
    for alias, col, _, _ in spec:
        if alias in LAG_1D:
            cal[col] = cal[col].shift(1)

    dias_mercado = raw[TARGET].notna()
    # el target no se rellena: solo jornadas con cotizacion
    base = cal.loc[dias_mercado]
    idx = base.index
    out = pd.DataFrame(index=idx)
    for alias, col, tr, _ in spec:
        s = base[col]
        if tr.startswith("log"):
            s_pos = s.where(s > 0)
            out[f"r_{alias}"] = np.log(s_pos).diff()
        if tr.startswith("diff"):
            out[f"d_{alias}"] = s.diff()
        if tr.endswith("+lvl"):
            out[f"x_{alias}"] = s

    # variables derivadas simples (estado), todas con informacion hasta t
    if {"x_fedl01", "x_chni1m"} <= set(out.columns):
        out["carry_usd_menos_clp"] = out["x_fedl01"] - out["x_chni1m"]   # % anual
    if variante == "full2010":
        h = raw.loc[dias_mercado, "USDCLP Curncy|PX_HIGH"]
        l = raw.loc[dias_mercado, "USDCLP Curncy|PX_LOW"]
        out["rango_hl"] = np.log(h / l).where((h > 0) & (l > 0) & (h >= l))

    # 6. objetivo (unico uso de informacion futura)
    out["dias"] = pd.Series(idx, index=idx).diff().dt.days
    out["ret_next"] = out["r_usdclp"].shift(-1)
    out["up_next"] = (out["ret_next"] > 0).astype(float).where(out["ret_next"].notna())
    out["dias_next"] = out["dias"].shift(-1)

    out = out.loc[cfg["inicio"]:]
    # core_completo: todas las series del grupo core con dato ese dia
    core_cols = [c for c in out.columns if c.split("_", 1)[-1] in
                 {s[0] for s in spec if s[3] == "core"} and c.startswith(("r_", "d_"))]
    out["core_completo"] = out[core_cols].notna().all(axis=1)
    return out


# --------------------------------------------------------------------------- chequeos
def prueba_look_ahead(raw, variante, fraccion=0.75):
    """Reconstruye el panel con datos truncados y verifica que las columnas de
    informacion (todas menos el objetivo) no cambian: si cambiaran, usarian futuro."""
    full = construir_panel(raw, variante)
    corte = full.index[int(len(full) * fraccion)]
    trunc = construir_panel(raw.loc[:corte], variante)
    feats = [c for c in full.columns if c not in TARGET_COLS]
    a = full.loc[:corte, feats]
    b = trunc.loc[:corte, feats]
    ok = a.shape == b.shape and np.allclose(
        a.astype(float).values, b.astype(float).values, equal_nan=True)
    return bool(ok), str(corte.date())


def chequeos(raw, panel, variante):
    r = {}
    r["variante"] = variante
    r["filas"] = int(len(panel))
    r["desde"], r["hasta"] = str(panel.index.min().date()), str(panel.index.max().date())
    r["indice_unico_y_creciente"] = bool(panel.index.is_unique and panel.index.is_monotonic_increasing)
    # prueba de lunes: con diferencias sobre la secuencia de jornadas no se pierde ningun lunes
    lunes = float((panel.index.dayofweek == 0).mean())
    lunes_con_retorno = float((panel["r_usdclp"].dropna().index.dayofweek == 0).mean())
    r["frac_lunes"] = round(lunes, 4)
    r["frac_lunes_con_retorno"] = round(lunes_con_retorno, 4)
    r["prueba_lunes_ok"] = bool(all(LUNES_RANGO[0] < f < LUNES_RANGO[1]
                                    for f in (lunes, lunes_con_retorno)))
    num = panel.select_dtypes("number")
    r["infinitos"] = int(np.isinf(num.values).sum())
    ret = panel["r_usdclp"].dropna()
    r["retornos_usdclp_mayores_6pct"] = [str(d.date()) for d in ret[ret.abs() > 0.06].index]
    r["frac_alza_dia_siguiente"] = round(float(panel["up_next"].mean()), 4)
    r["dias_retorno_cero"] = int((panel["ret_next"] == 0).sum())
    r["filas_core_completas"] = int(panel["core_completo"].sum())
    r["pct_core_completas"] = round(float(panel["core_completo"].mean()), 4)
    na = panel.drop(columns=TARGET_COLS + ["core_completo"]).isna().mean().round(4)
    r["columnas_con_mas_de_2pct_NA"] = {k: float(v) for k, v in na[na > 0.02].items()}
    # series desactualizadas al final de la base
    fin = raw[TARGET].last_valid_index()
    stale = {}
    for alias, col, _, g in SPEC:
        if g in VARIANTES[variante]["grupos"]:
            lv = raw[col].last_valid_index()
            if (fin - lv).days > STALE_DIAS:
                stale[col] = str(lv.date())
    r["series_desactualizadas"] = stale
    ok, corte = prueba_look_ahead(raw, variante)
    r["prueba_look_ahead_ok"] = ok
    r["prueba_look_ahead_corte"] = corte
    return r


# --------------------------------------------------------------------------- referencias
def metricas(pnl):
    pnl = pnl.dropna()
    if len(pnl) < 2:
        return dict(n=len(pnl))
    cum = pnl.cumsum()
    dd = (cum - cum.cummax()).min()
    vol = pnl.std() * np.sqrt(DIAS_ANIO)
    return dict(n=int(len(pnl)), pnl_total=round(float(cum.iloc[-1]), 4),
                media_anual=round(float(pnl.mean() * DIAS_ANIO), 4),
                vol_anual=round(float(vol), 4),
                sharpe=round(float(pnl.mean() * DIAS_ANIO / vol), 3) if vol > 0 else np.nan,
                max_drawdown=round(float(dd), 4))


def pnl_estrategia(panel, pos, costo_bps=COSTO_BPS):
    """pos[t]: exposicion decidida al cierre de t, aplicada al retorno t -> t+1.
    Resultado por unidad de nominal: bruto, carry y costo por cambio de exposicion."""
    bruto = pos * np.expm1(panel["ret_next"])
    carry = pos * panel["carry_usd_menos_clp"] / 100.0 * panel["dias_next"] / 360.0
    costo = pos.diff().abs().fillna(pos.abs()) * costo_bps / 1e4
    return pd.DataFrame({"bruto": bruto, "carry": carry, "costo": costo})


def referencias(panel):
    p = panel.dropna(subset=["ret_next", "carry_usd_menos_clp", "dias_next"])
    filas = []
    for nombre, v in [("siempre_largo_+1", 1.0), ("plano_0", 0.0), ("siempre_corto_-1", -1.0)]:
        pos = pd.Series(v, index=p.index)
        r = pnl_estrategia(p, pos)
        for tramo, sel in [("completo", slice(None)), ("oos_trabajo", slice(OOS_INICIO, None))]:
            rr = r.loc[sel]
            filas.append({"estrategia": nombre, "tramo": tramo, "serie": "bruto",
                          **metricas(rr["bruto"])})
            filas.append({"estrategia": nombre, "tramo": tramo, "serie": "bruto+carry",
                          **metricas(rr["bruto"] + rr["carry"])})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--xlsx", required=True, help="ruta a base_usdclp.xlsx")
    ap.add_argument("--variante", default="core", choices=list(VARIANTES))
    ap.add_argument("--salida", default="data")
    a = ap.parse_args()

    raw = cargar_raw(a.xlsx)
    panel = construir_panel(raw, a.variante)
    chk = chequeos(raw, panel, a.variante)
    ref = referencias(panel)

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out / f"panel_{a.variante}.csv", index_label="fecha")
    ref.to_csv(out / f"referencias_{a.variante}.csv", index=False)
    (out / f"chequeos_{a.variante}.json").write_text(json.dumps(chk, indent=2, ensure_ascii=False))

    print(json.dumps(chk, indent=2, ensure_ascii=False))
    print("\nReferencias provisionales (por unidad de nominal, carry proxy, sin costos):")
    print(ref.to_string(index=False))
    if not chk["prueba_look_ahead_ok"]:
        sys.exit("ERROR: la prueba anti look-ahead fallo")
    if not chk["prueba_lunes_ok"]:
        sys.exit(f"ERROR: proporcion de lunes anomala ({chk['frac_lunes']}, "
                 f"con retorno {chk['frac_lunes_con_retorno']}); esperado entre {LUNES_RANGO}")


if __name__ == "__main__":
    main()
