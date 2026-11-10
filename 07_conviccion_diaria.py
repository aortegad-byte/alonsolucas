"""Convicción por día (entregable 3, parte descriptiva): ¿separa el percentil jornadas con mejor acierto?

Lee resultados/senales_desarrollo.csv (tramo de desarrollo, hasta 2024-09-30) y arma, para el modelo
congelado M1_ridge|DH_histeresis_q0.2, una fila por jornada con probabilidad cruda y calibrada,
percentil de 63 predicciones, posición, acierto y resultado en pb. No reentrena nada ni mira el
tramo fuera de muestra.

Acierto = el signo de la posición coincide con el signo de ret_next (solo posición ≠ 0 y ret_next ≠ 0).
Resultado: se calcula con la función pnl de 03_modelos_decision.py, es decir con el carry overnight de
metodologia_v2 §8.3 (FEDL01 rezagada − TPM; las columnas salen del panel de la base, no del CSV) y 2 pb
por unidad de cambio de posición. El costo de entrar o invertir se cobra el día del cambio; el de salir
a 0 se imputa al último día con posición activa, de modo que los promedios sobre jornadas con
posición ≠ 0 lo incluyen. Los promedios por tramo usan esas jornadas; el valor total usa todas.
Los intervalos son bootstrap estacionario (95 %, el de 03_modelos_decision.py) sobre las jornadas en
orden de fecha. El percentil usa la misma función que el modelo (03_modelos_decision.percentil_movil).

Uso:
  python 07_conviccion_diaria.py "base_usdclp_actualizada.xlsx"
Salidas: resultados/conviccion_diaria.csv, conviccion_tramos.csv, conviccion_valor_total.csv,
conviccion_descomposicion.csv (señal contra carry), conviccion_subperiodos.csv y conviccion_riesgo.csv
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

etapa2a = importlib.import_module("02_seleccion_variables")
etapa2b = importlib.import_module("03_modelos_decision")
ESTRATEGIA = "M1_ridge|DH_histeresis_q0.2"
TRAMOS = [0, 0.10, 0.20, 0.50, 0.80, 0.90, 1.0]
FIN = pd.Timestamp("2024-09-30")
COSTO = etapa2b.COSTO_SELECCION     # 2 pb por unidad de cambio de posición (metodologia_v2 §8.2)
COLS_CARRY = ["x_fedl01", "x_tpm", "dias_next"]


def tabla_diaria(d, carry):
    t = pd.DataFrame({"ret_next": d["ret_next"], "p_cruda": d["M1_ridge"], "p_calibrada": d["M1_ridge_cal"],
                      "posicion": d[ESTRATEGIA]})
    t["percentil_63"] = etapa2b.percentil_movil(d["M1_ridge"])
    t = t.dropna(subset=["percentil_63"]).join(carry)
    opera = (t["posicion"] != 0) & (t["ret_next"] != 0)
    t["acierto"] = np.where(opera, (np.sign(t["posicion"]) == np.sign(t["ret_next"])).astype(float), np.nan)

    bruto = etapa2b.pnl(t["posicion"], t, 0.0)
    costo = (bruto - etapa2b.pnl(t["posicion"], t, COSTO)) * 1e4
    salida = (t["posicion"] == 0) & (t["posicion"].shift(1, fill_value=0) != 0)
    imputado = costo.where(salida, 0.0)
    t["carry_pb"] = (t["x_fedl01"] - t["x_tpm"]) / 100 * t["dias_next"] / 360 * 1e4
    t["pnl_bruto_pb"] = bruto * 1e4
    t["costo_pb"] = costo - imputado + imputado.shift(-1, fill_value=0.0)
    t["pnl_neto_pb"] = t["pnl_bruto_pb"] - t["costo_pb"]
    return t


def intervalo_boot(x, rng):
    """IC 95 % de la media por bootstrap estacionario (x en orden de fecha)."""
    x = x.dropna().to_numpy()
    if len(x) < 2:
        return np.nan, np.nan
    medias = x[etapa2b.indices_bootstrap(len(x), rng)].mean(axis=1)
    return tuple(np.percentile(medias, [2.5, 97.5]))


def resumen_tramos(t):
    rng = np.random.default_rng(etapa2b.SEMILLA)
    t = t.assign(tramo=pd.cut(t["percentil_63"], TRAMOS, include_lowest=True))
    filas = []
    for tramo, g in t.groupby("tramo", observed=True):
        op = g[g["posicion"] != 0]
        a_lo, a_hi = intervalo_boot(g["acierto"], rng)
        n_lo, n_hi = intervalo_boot(op["pnl_neto_pb"], rng)
        filas.append({"tramo": tramo, "dias": len(g), "dias_operados": g["acierto"].count(),
                      "dias_posicion": len(op),
                      "acierto": g["acierto"].mean(), "acierto_ic95_lo": a_lo, "acierto_ic95_hi": a_hi,
                      "pnl_bruto_medio_pb": op["pnl_bruto_pb"].mean(),
                      "pnl_neto_medio_pb": op["pnl_neto_pb"].mean(),
                      "costo_medio_pb": op["costo_pb"].mean(),
                      "pnl_neto_ic95_lo": n_lo, "pnl_neto_ic95_hi": n_hi,
                      "aporte_total_pb": g["pnl_neto_pb"].sum(),
                      "aporte_por_jornada_pb": g["pnl_neto_pb"].sum() / len(t)})
    return pd.DataFrame(filas).set_index("tramo")


def valor_total(t):
    """Modelo, comprar siempre (+1) y no operar sobre las mismas jornadas y con el mismo costo."""
    rng = np.random.default_rng(etapa2b.SEMILLA)
    siempre = etapa2b.pnl(pd.Series(1.0, index=t.index), t, COSTO) * 1e4
    nunca = pd.Series(0.0, index=t.index)
    series = {"modelo": t["pnl_neto_pb"], "comprar_siempre": siempre, "no_operar": nunca,
              "modelo_menos_siempre": t["pnl_neto_pb"] - siempre}
    filas = []
    for nombre, s in series.items():
        lo, hi = intervalo_boot(s, rng)
        filas.append({"estrategia": nombre, "jornadas": len(s), "total_pb": s.sum(),
                      "media_por_jornada_pb": s.mean(), "ic95_lo": lo, "ic95_hi": hi})
    return pd.DataFrame(filas).set_index("estrategia")


SUBPERIODOS = [("2010-04-01", "2017-12-31"), ("2018-01-01", "2024-09-27")]


def pnl_pb(pos, t, con_carry, costo=COSTO):
    """pnl en pb con la función pnl de 03; sin carry se anulan FEDL01 y TPM, y queda posición × ret_next − costo."""
    dd = t if con_carry else t.assign(x_fedl01=0.0, x_tpm=0.0)
    return etapa2b.pnl(pos, dd, costo) * 1e4


def riesgo(t):
    """Drawdown, peores jornadas, rotación y costo de equilibrio del modelo, comprar siempre y vender siempre (con carry)."""
    pos = referencias(t)
    anios = (t.index[-1] - t.index[0]).days / 365.25
    filas = {}
    for k in ("modelo", "comprar_siempre", "vender_siempre"):
        p, r = pos[k], pnl_pb(pos[k], t, True)
        curva = pd.concat([pd.Series([0.0], index=[t.index[0] - pd.Timedelta(days=1)]), r.cumsum()])
        caida = curva - curva.cummax()
        fin = caida.idxmin()
        inicio = curva.loc[:fin].idxmax()
        cambios = p.diff().abs().fillna(p.abs()).sum()
        bruto = pnl_pb(p, t, True, costo=0.0).sum()
        fila = {"total_neto_pb": r.sum(), "max_drawdown_pb": caida.min(),
                "dd_inicio": (t.index[0] if inicio < t.index[0] else inicio).date(), "dd_fin": fin.date(),
                "rotacion_anual": cambios / anios, "cambios_totales": cambios,
                "total_bruto_pb": bruto,
                # total neto = bruto − costo × cambios, lineal en el costo; sin equilibrio si el bruto no es positivo
                "costo_equilibrio_pb": bruto / cambios if cambios > 0 and bruto > 0 else np.nan}
        for i, (fecha, valor) in enumerate(r.nsmallest(5).items(), 1):
            fila.update({f"peor{i}_fecha": fecha.date(), f"peor{i}_pb": valor, f"peor{i}_posicion": p.loc[fecha]})
        filas[k] = fila
    return pd.DataFrame(filas).T.rename_axis("estrategia")


def referencias(t):
    """Posición diaria del modelo y de cada referencia sobre las mismas jornadas."""
    constante = lambda v: pd.Series(float(v), index=t.index)
    seguir = pd.Series(np.where(t["x_tpm"] > t["x_fedl01"], -1.0, 1.0), index=t.index)
    return {"modelo": t["posicion"], "comprar_siempre": constante(1), "vender_siempre": constante(-1),
            "no_operar": constante(0), "seguir_carry": seguir, "exposicion_uno": constante(1)}


def descomposicion(t):
    """Total, media y distribución de posiciones por estrategia, con y sin carry; más la diferencia contra seguir_carry."""
    rng = np.random.default_rng(etapa2b.SEMILLA)
    pos = referencias(t)
    con = {k: pnl_pb(p, t, True) for k, p in pos.items()}
    sin = {k: pnl_pb(p, t, False) for k, p in pos.items()}
    filas = [{"estrategia": k, "pct_mas1": (p == 1).mean(), "pct_cero": (p == 0).mean(), "pct_menos1": (p == -1).mean(),
              "total_con_carry_pb": con[k].sum(), "total_sin_carry_pb": sin[k].sum(),
              "carry_pb": con[k].sum() - sin[k].sum(),
              "media_con_carry_pb": con[k].mean(), "media_sin_carry_pb": sin[k].mean()}
             for k, p in pos.items()]
    tabla = pd.DataFrame(filas).set_index("estrategia")
    dif = []
    for nombre, serie in (("con_carry", con), ("sin_carry", sin)):
        x = serie["modelo"] - serie["seguir_carry"]
        lo, hi = intervalo_boot(x, rng)
        dif.append({"base": nombre, "total_pb": x.sum(), "media_por_jornada_pb": x.mean(), "ic95_lo": lo, "ic95_hi": hi})
    sub = []
    for ini, fin in SUBPERIODOS:
        m = (t.index >= ini) & (t.index <= fin)
        fila = {"subperiodo": f"{ini} a {fin}", "jornadas": int(m.sum())}
        for k in ("modelo", "seguir_carry"):
            fila[f"{k}_con_carry_pb"] = con[k][m].mean()
            fila[f"{k}_sin_carry_pb"] = sin[k][m].mean()
        sub.append(fila)
    return tabla, pd.DataFrame(dif).set_index("base"), pd.DataFrame(sub).set_index("subperiodo"), con["modelo"]


def main(xlsx):
    d = pd.read_csv("resultados/senales_desarrollo.csv", index_col=0, parse_dates=True)
    d = d.loc[d.index <= FIN]
    carry = etapa2a.construir_panel(xlsx).loc[d.index, COLS_CARRY]
    t = tabla_diaria(d, carry)
    resultados = Path("resultados")
    t.round(6).to_csv(resultados / "conviccion_diaria.csv", encoding="utf-8")
    r = resumen_tramos(t)
    r.round(4).to_csv(resultados / "conviccion_tramos.csv", encoding="utf-8")
    v = valor_total(t)
    v.round(4).to_csv(resultados / "conviccion_valor_total.csv", encoding="utf-8")

    con_pos = t["posicion"] != 0
    print(f"Fecha mínima: {t.index.min().date()}  Fecha máxima: {t.index.max().date()}  Jornadas: {len(t)}")
    print(f"Jornadas con posición ≠ 0: {int(con_pos.sum())}; de ellas con ret_next = 0 (sin acierto): "
          f"{int((con_pos & (t['ret_next'] == 0)).sum())}; con acierto definido: {t['acierto'].count()} "
          f"(acierto global {t['acierto'].mean():.4f})")
    pd.set_option("display.width", 250, "display.max_columns", 50)
    print("\nPor tramo de percentil (en los tramos medios la posición viene de la histéresis):")
    print(r.round(4).to_string())
    print(f"\nValor total (todas las jornadas, incluidas las de posición 0; costo de salida imputado):")
    print(v.round(4).to_string())
    print(f"\nTotal acumulado del modelo: {v.loc['modelo', 'total_pb']:.1f} pb; "
          f"comprar siempre: {v.loc['comprar_siempre', 'total_pb']:.1f} pb; "
          f"diferencia: {v.loc['modelo_menos_siempre', 'total_pb']:.1f} pb "
          f"({v.loc['modelo_menos_siempre', 'media_por_jornada_pb']:.3f} pb por jornada)")

    dc, dif, sub, modelo_con = descomposicion(t)
    dc.round(4).to_csv(resultados / "conviccion_descomposicion.csv", encoding="utf-8")
    sub.round(4).to_csv(resultados / "conviccion_subperiodos.csv", encoding="utf-8")
    print(f"\nDescomposición señal / carry (control: total del modelo con carry {modelo_con.sum():.1f} pb "
          f"contra {t['pnl_neto_pb'].sum():.1f} pb de la tabla diaria):")
    print(dc.round(4).to_string())
    print("\nModelo menos seguir_carry (IC95 por bootstrap estacionario, bloque medio "
          f"{etapa2b.BLOQUE_MEDIO}):")
    print(dif.round(4).to_string())
    print("\nPnl por jornada en cada subperíodo (pb):")
    print(sub.round(4).to_string())
    rk = riesgo(t)
    rk.to_csv(resultados / "conviccion_riesgo.csv", encoding="utf-8")
    print("\nRiesgo (con carry, 2 pb por unidad de cambio):")
    print(rk.T.to_string())
    print(f"\nCosto de equilibrio del modelo: {rk.loc['modelo', 'costo_equilibrio_pb']:.2f} pb por unidad de cambio "
          f"(supuesto: {COSTO * 1e4:.0f} pb)")

    sup = {b: dif.loc[b, "media_por_jornada_pb"] > 0 for b in dif.index}
    sig = {b: dif.loc[b, "ic95_lo"] > 0 or dif.loc[b, "ic95_hi"] < 0 for b in dif.index}
    print(f"\nModelo > seguir_carry: sin carry {sup['sin_carry']} (IC excluye cero: {sig['sin_carry']}); "
          f"con carry {sup['con_carry']} (IC excluye cero: {sig['con_carry']})")

    positivo = (r["pnl_neto_medio_pb"] > 0)
    excluye = (r["pnl_neto_ic95_lo"] > 0) | (r["pnl_neto_ic95_hi"] < 0)
    print(f"pnl_neto_medio_pb positivo en {int(positivo.sum())} de {len(r)} tramos; "
          f"el IC95 excluye cero en: {[str(i) for i in r.index[excluye]] or 'ninguno'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "base_usdclp_actualizada.xlsx")
