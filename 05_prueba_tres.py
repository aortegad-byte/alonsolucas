"""Prueba nueva (declarada): ±3 solo cuando la señal es muy clara.

Parte del modelo congelado (metodologia_v2 §8: M1 Ridge, banda con histéresis q = 0,20, ±1) y
prueba si conviene llevar la exposición a ±3 en los días de señal más clara. Todo dentro del
tramo de desarrollo; el tramo fuera de muestra no se usa.

Todo lo que sigue se fijó antes de correr el script por primera vez.

Principio. El ±3 solo amplifica: se aplica cuando el modelo congelado ya está en +1 (o −1) y la
señal clara apunta en la misma dirección. Nunca abre una posición que el modelo congelado no tiene.

Criterios de señal clara (alza; la baja es simétrica):
  acuerdo       percentil de M1 Ridge >= 0,90 y percentil de M2 LightGBM >= 0,90 (63 predicciones)
  probabilidad  probabilidad calibrada de M1 >= 0,5 + u, con u el percentil 80 de |p_cal − 0,5|
                en el tramo de selección
  persistencia  el acuerdo también se cumplía la jornada anterior
  volatilidad   la vol. implícita 1M del USD/CLP no está en el 20 % más alto de las últimas 252
                jornadas (incluida la de hoy)

Reglas anidadas: A = acuerdo; B = A + probabilidad; C = B + persistencia; D = C + volatilidad.

Elección (solo con selección 2012-2017, costo 2 pb). Una regla califica si cumple todo:
  1. al menos 30 días en ±3;
  2. los días ±3 aciertan al menos 3 puntos más que los días ±1 del modelo congelado;
  3. el resultado por unidad de exposición de los días ±3 supera al de los días ±1;
  4. el Sharpe de la estrategia con ±3 supera al del modelo congelado.
Entre las que califican se elige la de mayor Sharpe. Si ninguna califica, se queda ±1.

Validación (2018 a sep 2024, una sola vez y solo para la regla elegida): Sharpe con 0, 2 y 5 pb,
máximo drawdown, peor día y bootstrap estacionario de la diferencia contra el modelo congelado y
contra las tres referencias, con Benjamini-Hochberg sobre esas 4 pruebas.
Advertencia: la validación ya se miró en la etapa 2b (incluida la convicción del D3), así que
no es una muestra virgen. Se declara en el informe.

Uso: python 05_prueba_tres.py "base_usdclp (2).xlsx"
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

etapa2a = importlib.import_module("02_seleccion_variables")
etapa2b = importlib.import_module("03_modelos_decision")

Q_HISTERESIS = 0.20
PCT_ACUERDO = 0.90
CUANTIL_PROB = 0.80
VENTANA_VOL, CUANTIL_VOL = 252, 0.80
MIN_DIAS_TRES = 30
VENTAJA_ACIERTO = 0.03
COSTO = etapa2b.COSTO_SELECCION
SELECCION, VALIDACION = etapa2b.SELECCION, etapa2b.VALIDACION


def condiciones(pred, vol):
    """Para cada regla, series booleanas de señal clara al alza y a la baja (solo información hasta t)."""
    pct1 = etapa2b.percentil_movil(pred["M1_ridge"])
    pct2 = etapa2b.percentil_movil(pred["M2_lgbm"])
    pcal = pred["M1_ridge_cal"]
    u = (pcal.loc[SELECCION[0]:SELECCION[1]] - 0.5).abs().quantile(CUANTIL_PROB)
    vol_ok = vol <= vol.rolling(VENTANA_VOL).quantile(CUANTIL_VOL)

    reglas = {}
    for lado, signo in (("alza", 1), ("baja", -1)):
        if signo > 0:
            acuerdo = (pct1 >= PCT_ACUERDO) & (pct2 >= PCT_ACUERDO)
            prob = pcal >= 0.5 + u
        else:
            acuerdo = (pct1 <= 1 - PCT_ACUERDO) & (pct2 <= 1 - PCT_ACUERDO)
            prob = pcal <= 0.5 - u
        persiste = acuerdo & acuerdo.shift(1, fill_value=False)
        reglas.setdefault("A_acuerdo", {})[signo] = acuerdo
        reglas.setdefault("B_+probabilidad", {})[signo] = acuerdo & prob
        reglas.setdefault("C_+persistencia", {})[signo] = persiste & prob
        reglas.setdefault("D_+volatilidad", {})[signo] = persiste & prob & vol_ok
    return reglas, u


def con_tres(base, regla):
    pos = base.copy()
    pos[(base == 1) & regla[1]] = 3.0
    pos[(base == -1) & regla[-1]] = -3.0
    return pos


def sharpe(r):
    return r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan


def evaluar_seleccion(base, pos, d):
    s = slice(*SELECCION)
    b, p, dd = base.loc[s], pos.loc[s], d.loc[s]
    unidad = etapa2b.pnl(np.sign(p), dd, 0.0)                    # resultado de una unidad en la dirección
    acierto = np.sign(p) == np.sign(dd["ret_next"])
    tres, uno = p.abs() == 3, p.abs() == 1
    fila = {"dias_tres": int(tres.sum()), "dias_uno": int(uno.sum()),
            "acierto_tres": acierto[tres].mean(), "acierto_uno": acierto[uno].mean(),
            "unidad_tres_pb": unidad[tres].mean() * 1e4, "unidad_uno_pb": unidad[uno].mean() * 1e4,
            "sharpe_tres": sharpe(etapa2b.pnl(p, dd, COSTO)), "sharpe_congelado": sharpe(etapa2b.pnl(b, dd, COSTO)),
            "rotacion_tres": p.diff().abs().sum() / len(p) * 252}
    fila["califica"] = bool(fila["dias_tres"] >= MIN_DIAS_TRES
                            and fila["acierto_tres"] >= fila["acierto_uno"] + VENTAJA_ACIERTO
                            and fila["unidad_tres_pb"] > fila["unidad_uno_pb"]
                            and fila["sharpe_tres"] > fila["sharpe_congelado"])
    return fila


def evaluar_validacion(nombre, base, pos, d):
    v = slice(*VALIDACION)
    b, p, dd = base.loc[v], pos.loc[v], d.loc[v]
    filas = []
    for etiqueta, x in ((nombre, p), ("congelado_±1", b)):
        for costo in etapa2b.COSTOS:
            r = etapa2b.pnl(x, dd, costo)
            filas.append({"estrategia": etiqueta, "costo_pb": costo * 1e4, **etapa2b.resumen_pnl(r, x, dd),
                          "peor_dia": r.min(), "dias_tres": int((x.abs() == 3).sum())})
    idx = etapa2b.indices_bootstrap(len(dd), np.random.default_rng(etapa2b.SEMILLA))
    r_tres = etapa2b.pnl(p, dd, COSTO)
    contra = {"congelado_±1": b, "REF_siempre_+1": 1.0, "REF_nunca_0": 0.0, "REF_siempre_-1": -1.0}
    boot = []
    for ref, x in contra.items():
        x = x if isinstance(x, pd.Series) else pd.Series(x, index=dd.index)
        dif = r_tres - etapa2b.pnl(x, dd, COSTO)
        boot.append({"contra": ref, "dif_media_anual": dif.mean() * 252,
                     "p_bootstrap": etapa2b.p_bootstrap(dif.to_numpy(), idx)})
    boot = pd.DataFrame(boot)
    boot["bh_10"] = etapa2b.benjamini_hochberg(boot["p_bootstrap"], etapa2b.ALFA_BH)
    return pd.DataFrame(filas), boot


def main(xlsx):
    panel = etapa2a.construir_panel(xlsx)
    d, pred = etapa2b.predicciones(panel)
    base = etapa2b.posiciones(pred["M1_ridge"], "DH", Q_HISTERESIS)
    reglas, u = condiciones(pred, panel.loc[d.index, "x_vol1m"])
    print(f"umbral de probabilidad calibrada: 0,5 ± {u:.4f}")

    posiciones = {n: con_tres(base, r) for n, r in reglas.items()}
    sel = pd.DataFrame([{"regla": n, **evaluar_seleccion(base, p, d)} for n, p in posiciones.items()])
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print("\nSelección 2012-2017:")
    print(sel.round(4).to_string(index=False))

    salida = Path("resultados")
    salida.mkdir(exist_ok=True)
    hojas = {"seleccion": sel, "parametros": pd.DataFrame([{
        "pct_acuerdo": PCT_ACUERDO, "umbral_prob_u": u, "cuantil_vol": CUANTIL_VOL, "ventana_vol": VENTANA_VOL,
        "min_dias_tres": MIN_DIAS_TRES, "ventaja_acierto": VENTAJA_ACIERTO, "costo_pb": COSTO * 1e4}])}

    califican = sel[sel["califica"]]
    if califican.empty:
        print("\nNinguna regla califica en selección: se mantiene solo ±1. La validación no se mira.")
    else:
        elegida = califican.loc[califican["sharpe_tres"].idxmax(), "regla"]
        print(f"\nRegla elegida en selección: {elegida}. Validación 2018 a sep 2024 (una sola vez):")
        val, boot = evaluar_validacion(elegida, base, posiciones[elegida], d)
        print(val.round(4).to_string(index=False))
        print(boot.round(4).to_string(index=False))
        hojas |= {"validacion": val, "bootstrap": boot}

    with pd.ExcelWriter(salida / "prueba_tres.xlsx") as w:
        for nombre, t in hojas.items():
            t.to_excel(w, sheet_name=nombre, index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base_usdclp (2).xlsx")
