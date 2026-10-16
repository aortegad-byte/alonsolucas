# Desafío USD/CLP · Torneo Banco Itaú y FEN

Predicción de la dirección del USD/CLP del día siguiente y su traducción a una exposición de −3, −1, 0, 1 o 3 veces el nocional.

## Estado (16 de octubre de 2026)

- Núcleo de variables congelado (13 series, cobre HG1).
- Modelo congelado: logística Ridge calibrada con Platt y banda con histéresis, solo ±1.
- El tramo fuera de muestra (desde 2024-10-01) todavía no se ha evaluado.
- La especificación y todas las decisiones están en [`metodologia_v2.md`](metodologia_v2.md).

## Archivos

| Archivo | Contenido |
|---|---|
| `metodologia_v2.md` | Metodología vigente, resultados y modelo congelado (§8) |
| `Resumen_tecnico_desafio_USDCLP.pdf` | Resumen técnico de la etapa 1 (10 oct 2026) |
| `Tabla Comparativa Variables Núcleo USD CLP.pdf` | Tabla anterior; reemplazada (ver metodología §2) |
| `01_panel.py` | Panel limpio, objetivo, chequeos (look-ahead y lunes) y referencias provisionales (etapa 1) |
| `02_seleccion_variables.py` | Panel y selección de variables (etapa 2a) |
| `03_modelos_decision.py` | Modelos, calibración y capa de decisión (etapa 2b) |
| `resultados/` | Salidas de ambos scripts |

## Uso

La base de Bloomberg (`base_usdclp (2).xlsx`) no se incluye en el repositorio. Copiarla a la raíz y ejecutar:

```
pip install -r requirements.txt
python 01_panel.py --xlsx "base_usdclp (2).xlsx" --variante core
python 02_seleccion_variables.py "base_usdclp (2).xlsx"
python 03_modelos_decision.py "base_usdclp (2).xlsx"
```
