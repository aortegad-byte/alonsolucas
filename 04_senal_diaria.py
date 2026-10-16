"""Señal del día (entregable 1): dirección, probabilidad y posición del modelo congelado.

Aplica sin cambios el modelo congelado de metodologia_v2 §8: núcleo con HG1, logística Ridge
(C = 0,01) con reentreno cada 20 jornadas, Platt en línea y banda con histéresis (q = 0,20,
solo ±1). Usa las mismas funciones que 03_modelos_decision.py, así que en el tramo de desarrollo
reproduce la estrategia M1_ridge|DH_histeresis_q0.2 de resultados/senales_desarrollo.csv.

La decisión se toma al cierre de la última jornada de la base y se aplica al retorno del
USD/CLP de esa jornada a la siguiente. El script no calcula retornos ni resultados: no evalúa
nada, así que tampoco mira el tramo fuera de muestra.

Dirección y posición pueden no coincidir. La dirección sale de la probabilidad calibrada
(> 0,5 = alza); la posición, del percentil de la probabilidad cruda entre las últimas 63
predicciones. Una probabilidad de 0,49 puede ser alta comparada con las semanas anteriores.

Uso:
  python 04_senal_diaria.py "base_usdclp (2).xlsx"
  python 04_senal_diaria.py "base_usdclp (2).xlsx" --hasta 2024-09-27   # como si la base terminara ese día
"""
import argparse
import importlib
import json
from pathlib import Path

import pandas as pd

etapa2a = importlib.import_module("02_seleccion_variables")
etapa2b = importlib.import_module("03_modelos_decision")
NUCLEO = etapa2b.NUCLEO
Q_HISTERESIS = 0.20                 # metodologia_v2 §8
DIAS_MOSTRAR = 10


def preparar_datos(xlsx, hasta=None):
    """Mismas jornadas que 03_modelos_decision.py, más la última, que todavía no tiene objetivo."""
    panel = etapa2a.construir_panel(xlsx, fin=None, hasta=hasta)
    cols = NUCLEO + ["up_next", "ret_next", "x_fedl01", "x_chni1m", "dias_next"]
    historia, hoy = panel[cols].iloc[:-1].dropna(), panel[cols].iloc[[-1]]
    faltan = [c for c in NUCLEO if pd.isna(hoy[c].iloc[0])]
    if faltan:
        raise SystemExit(f"ERROR: sin dato al {hoy.index[0].date()} para {faltan} "
                         f"(el relleno cubre hasta 5 días calendario); no se puede emitir la señal")
    return pd.concat([historia, hoy])


def predecir(d):
    pred = pd.DataFrame(index=d.index)
    pred["p_cruda"] = etapa2b.walk_forward(d, etapa2b.ridge, escalar=True)
    pred["p_calibrada"] = etapa2b.platt_en_linea(pred["p_cruda"], d["up_next"])
    pred["percentil_63"] = etapa2b.percentil_movil(pred["p_cruda"])
    pred["posicion"] = etapa2b.posiciones(pred["p_cruda"], "DH", Q_HISTERESIS)
    return pred


def senal_del_dia(pred):
    fecha, ultima = pred.index[-1], pred.iloc[-1]
    return {"fecha_decision": str(fecha.date()),
            "aplica_a": "retorno del USD/CLP desde el cierre de fecha_decision hasta la próxima jornada",
            "direccion": "alza" if ultima["p_calibrada"] > 0.5 else "baja",
            "prob_alza_calibrada": round(float(ultima["p_calibrada"]), 4),
            "prob_alza_cruda": round(float(ultima["p_cruda"]), 4),
            "percentil_63": round(float(ultima["percentil_63"]), 4),
            "posicion": int(ultima["posicion"]),
            "posicion_anterior": int(pred["posicion"].iloc[-2]),
            "modelo": f"M1_ridge|DH_histeresis_q{Q_HISTERESIS} (metodologia_v2 §8)"}


def main():
    ap = argparse.ArgumentParser(description="Señal del día del modelo congelado")
    ap.add_argument("xlsx", nargs="?", default="base_usdclp (2).xlsx")
    ap.add_argument("--hasta", help="trunca la base en esta fecha (AAAA-MM-DD)")
    a = ap.parse_args()

    pred = predecir(preparar_datos(a.xlsx, a.hasta))
    senal = senal_del_dia(pred)

    salida = Path("resultados")
    salida.mkdir(exist_ok=True)
    (salida / "senal_del_dia.json").write_text(json.dumps(senal, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(senal, indent=2, ensure_ascii=False))
    print(f"\nÚltimas {DIAS_MOSTRAR} jornadas:")
    print(pred.tail(DIAS_MOSTRAR).round(4).to_string())


if __name__ == "__main__":
    main()
