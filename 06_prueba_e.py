"""Prueba E (declarada, metodologia_v2 §8.4): ±3 con restricciones de riesgo estrictas.

Parte del modelo congelado (metodologia_v2 §8: M1 Ridge, banda con histéresis q = 0,20, ±1).
Las bases exigen que ±3 esté entre las posiciones posibles en el monitoreo en vivo. Las pruebas
anteriores (D3 en §7, reglas A-D en §8.2) mostraron que los días de señal "más clara" no ganan más
por unidad, así que esta prueba no busca más acierto: limita el daño de triplicar la exposición.

Todo lo que sigue se fijó y se registró en git antes de correr el script por primera vez.

Principio. El ±3 solo amplifica: se aplica cuando el modelo congelado ya está en +1 (o −1) y la
señal apunta en la misma dirección. Nunca abre una posición que el modelo congelado no tiene.

Restricciones (todas, con información hasta el cierre de t):
  1 señal extrema   percentil de M1 (63 predicciones) >= 0,95 para +3, <= 0,05 para −3
  2 régimen calmo   vol. implícita 1M del USD/CLP <= su mediana de las últimas 252 jornadas
                    (incluida la de hoy)
  3 duración        como máximo 3 jornadas seguidas en ±3; la cuarta vuelve a ±1
  4 freno           si una jornada en ±3 pierde más de 1 % del nominal (retorno + carry, sin costo),
                    no hay ±3 en las 20 jornadas siguientes. La pérdida de la posición decidida en t
                    se conoce al cierre de t+1, que es cuando se toma la decisión siguiente.
  5 frecuencia      tope duro: como máximo 5 jornadas en ±3 dentro de las últimas 100 decisiones
                    (incluida la de hoy). Primera versión: "si en selección hay ±3 en más del 5 % de
                    las jornadas, la regla no se acepta"; se cambió antes de correr la selección porque
                    dejaba al ±3 fuera de las posiciones posibles, y después de ver que en 2010-2011
                    (antes de selección) la regla daba ±3 en el 5,1 % de las jornadas.

Criterios en selección (2012-2017, costo 2 pb):
  ventaja  los cuatro de §8.2: >= 30 días en ±3; acierto ±3 >= acierto ±1 + 3 puntos; resultado por
           unidad ±3 > ±1; Sharpe con ±3 > Sharpe del congelado
  riesgo   máximo drawdown no peor que el del congelado, y peor día no peor que 1,5 veces el peor
           día del congelado

Decisión (fijada antes de correr):
  ventaja y riesgo              -> aprobada
  solo riesgo                   -> incluida por cumplimiento de las bases (declarado como tal)
  falla riesgo                  -> rechazada: solo ±1
Si se adopta (aprobada o incluida), la validación (2018 a sep 2024) se mira una sola vez y solo
exige el criterio de riesgo; si lo falla, se queda ±1. La validación no es una muestra virgen
(ya se miró en la etapa 2b), y se declara en el informe.

Uso: python 06_prueba_e.py "base_usdclp_actualizada.xlsx"
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

etapa2a = importlib.import_module("02_seleccion_variables")
etapa2b = importlib.import_module("03_modelos_decision")
prueba_tres = importlib.import_module("05_prueba_tres")

Q_HISTERESIS = 0.20
PCT_EXTREMO = 0.95
VENTANA_VOL = 252
MAX_RACHA = 3
FRENO_PERDIDA = 0.01
FRENO_JORNADAS = 20
TOPE_TRES, VENTANA_TOPE = 5, 100
FACTOR_PEOR_DIA = 1.5
COSTO = etapa2b.COSTO_SELECCION
SELECCION, VALIDACION = etapa2b.SELECCION, etapa2b.VALIDACION


def resultado_unitario(d):
    """Retorno + carry de una unidad comprada en USD, sin costo (insumo del freno)."""
    return etapa2b.pnl(pd.Series(1.0, index=d.index), d, 0.0)


def posiciones_e(base, pct, vol, unidad):
    """Aplica las restricciones 1 a 5 sobre las posiciones ±1 del modelo congelado.
    Devuelve las posiciones y un registro de por qué cada candidato a ±3 quedó o no en ±3."""
    calma = vol <= vol.rolling(VENTANA_VOL).median()
    candidato = (((base == 1) & (pct >= PCT_EXTREMO)) | ((base == -1) & (pct <= 1 - PCT_EXTREMO))) & calma
    pos = base.copy()
    motivo = pd.Series("", index=base.index)
    racha, bloqueado_hasta = 0, -1
    dias_tres = []                                              # índices de jornadas en ±3
    for i in range(len(base)):
        if not candidato.iloc[i]:
            racha = 0
            continue
        if i <= bloqueado_hasta:
            motivo.iloc[i] = "freno"
            racha = 0
            continue
        if racha >= MAX_RACHA:
            motivo.iloc[i] = "duracion"
            racha = 0
            continue
        if sum(j > i - VENTANA_TOPE for j in dias_tres) >= TOPE_TRES:
            motivo.iloc[i] = "tope"
            racha = 0
            continue
        pos.iloc[i] = 3.0 * base.iloc[i]
        motivo.iloc[i] = "tres"
        dias_tres.append(i)
        racha += 1
        r = pos.iloc[i] * unidad.iloc[i]
        if pd.notna(r) and r < -FRENO_PERDIDA:
            bloqueado_hasta = i + FRENO_JORNADAS
    return pos, motivo


def riesgo(base, pos, d, tramo):
    s = slice(*tramo)
    r_e = etapa2b.pnl(pos.loc[s], d.loc[s], COSTO)
    r_b = etapa2b.pnl(base.loc[s], d.loc[s], COSTO)
    dd = lambda r: float((r.cumsum() - r.cumsum().cummax()).min())
    fila = {"dd_e": dd(r_e), "dd_congelado": dd(r_b), "peor_dia_e": float(r_e.min()),
            "peor_dia_congelado": float(r_b.min())}
    fila["riesgo_ok"] = bool(fila["dd_e"] >= fila["dd_congelado"]
                             and fila["peor_dia_e"] >= FACTOR_PEOR_DIA * fila["peor_dia_congelado"])
    return fila


def decidir(fila):
    if fila["califica"] and fila["riesgo_ok"]:
        return "aprobada"
    if fila["riesgo_ok"]:
        return "incluida_por_bases"
    return "rechazada_riesgo"


def preparar(xlsx):
    panel = etapa2a.construir_panel(xlsx)
    d, pred = etapa2b.predicciones(panel)
    base = etapa2b.posiciones(pred["M1_ridge"], "DH", Q_HISTERESIS)
    pct = etapa2b.percentil_movil(pred["M1_ridge"])
    vol = panel.loc[d.index, "x_vol1m"]
    pos, motivo = posiciones_e(base, pct, vol, resultado_unitario(d))
    return d, base, pos, motivo


def main(xlsx):
    d, base, pos, motivo = preparar(xlsx)
    s = slice(*SELECCION)
    fila = prueba_tres.evaluar_seleccion(base, pos, d)
    fila["frac_dias_tres"] = fila["dias_tres"] / len(d.loc[s])
    fila |= riesgo(base, pos, d, SELECCION)
    fila["bloqueos_freno"] = int((motivo.loc[s] == "freno").sum())
    fila["cortes_duracion"] = int((motivo.loc[s] == "duracion").sum())
    fila["cortes_tope"] = int((motivo.loc[s] == "tope").sum())
    fila["decision"] = decidir(fila)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    sel = pd.DataFrame([fila])
    print("Selección 2012-2017:")
    print(sel.T.to_string(header=False))

    hojas = {"seleccion": sel, "parametros": pd.DataFrame([{
        "pct_extremo": PCT_EXTREMO, "ventana_vol": VENTANA_VOL, "max_racha": MAX_RACHA,
        "freno_perdida": FRENO_PERDIDA, "freno_jornadas": FRENO_JORNADAS, "tope_tres": TOPE_TRES, "ventana_tope": VENTANA_TOPE,
        "factor_peor_dia": FACTOR_PEOR_DIA, "costo_pb": COSTO * 1e4}])}

    if fila["decision"] in ("aprobada", "incluida_por_bases"):
        print(f"\nDecisión en selección: {fila['decision']}. Validación 2018 a sep 2024 (una sola vez):")
        val, boot = prueba_tres.evaluar_validacion("E", base, pos, d)
        rv = riesgo(base, pos, d, VALIDACION)
        rv["decision_final"] = fila["decision"] if rv["riesgo_ok"] else "rechazada_en_validacion"
        print(val.round(4).to_string(index=False))
        print(boot.round(4).to_string(index=False))
        print(pd.Series(rv).to_string())
        hojas |= {"validacion": val, "bootstrap": boot, "riesgo_validacion": pd.DataFrame([rv])}
    else:
        print(f"\nDecisión en selección: {fila['decision']}. Se queda ±1; la validación no se mira.")

    salida = Path("resultados")
    salida.mkdir(exist_ok=True)
    with pd.ExcelWriter(salida / "prueba_e.xlsx") as w:
        for nombre, t in hojas.items():
            t.to_excel(w, sheet_name=nombre, index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base_usdclp_actualizada.xlsx")
