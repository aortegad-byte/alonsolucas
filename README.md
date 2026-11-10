# Desafío USD/CLP · Torneo Banco Itaú y FEN

Predicción de la dirección del USD/CLP del día siguiente y su traducción a una exposición de −3, −1, 0, 1 o 3 veces el nocional.

## Estado (9 de noviembre de 2026)

- Núcleo de variables congelado (13 series, cobre HG1).
- Modelo congelado: logística Ridge calibrada con Platt y banda con histéresis, solo ±1.
- Señal del día automatizada (`04_senal_diaria.py`).
- ±3 probado con reglas fijadas de antemano y descartado (metodología §8.2), y de nuevo con restricciones de riesgo estrictas (prueba E, §8.4): rechazado. Cerrado el 10 nov 2026: la mentoría respondió de forma verbal que ±3 no es lo más importante, sino que el valor neto después de costos sea positivo y que las señales sean buenas. Se mantiene ±1 sin incluir la regla E; falta la respuesta por escrito (metodología §9).
- Carry proxy overnight (FEDL01 rezagada − TPM) en lugar del NDF 1M, declarado en metodología §8.3; no cambia señales ni posiciones.
- El tramo fuera de muestra (desde 2024-10-01) todavía no se ha evaluado.
- La especificación y todas las decisiones están en [`metodologia_v2.md`](metodologia_v2.md). **Los pendientes para la próxima sesión están en su §9.**

## Archivos

| Archivo | Contenido |
|---|---|
| `metodologia_v2.md` | Metodología vigente, resultados y modelo congelado (§8) |
| `Resumen_tecnico_desafio_USDCLP.pdf` | Resumen técnico de la etapa 1 (10 oct 2026) |
| `Tabla Comparativa Variables Núcleo USD CLP.pdf` | Tabla anterior; reemplazada (ver metodología §2) |
| `01_panel.py` | Panel limpio, objetivo, chequeos (look-ahead y lunes) y referencias provisionales (etapa 1) |
| `02_seleccion_variables.py` | Panel y selección de variables (etapa 2a) |
| `03_modelos_decision.py` | Modelos, calibración y capa de decisión (etapa 2b) |
| `04_senal_diaria.py` | Señal del día con el modelo congelado: dirección, probabilidad y posición (entregable 1) |
| `05_prueba_tres.py` | Prueba de ±3 con señal clara (descartada, metodología §8.2) |
| `06_prueba_e.py` | Prueba E: ±3 con restricciones de riesgo (registrada antes de correr, metodología §8.4) |
| `resultados/` | Salidas de los scripts |

## Uso

La base de Bloomberg (`base_usdclp_actualizada.xlsx`, datos hasta el 2026-11-06) no se incluye en el repositorio. Copiarla a la raíz y ejecutar:

```
pip install -r requirements.txt
python 01_panel.py --xlsx "base_usdclp_actualizada.xlsx" --variante core
python 02_seleccion_variables.py "base_usdclp_actualizada.xlsx"
python 03_modelos_decision.py "base_usdclp_actualizada.xlsx"
python 04_senal_diaria.py "base_usdclp_actualizada.xlsx"
```

`01_panel.py` usa por defecto el carry overnight; con `--carry ndf` usa FEDL01 − CHNI1M.

`04_senal_diaria.py` imprime la decisión al cierre de la última jornada de la base y la guarda en `resultados/senal_del_dia.json`. Con `--hasta AAAA-MM-DD` calcula la señal como si la base terminara ese día.
