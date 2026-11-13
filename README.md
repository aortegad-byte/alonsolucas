# Desafío USD/CLP · Torneo Banco Itaú y FEN

Predicción de la dirección del USD/CLP del día siguiente y su traducción a una exposición sobre el nocional. Entrega del jueves 12 de noviembre de 2026.

**Estrategia entregada:** logística Ridge (M1) con calibración Platt y banda con histéresis (DH, q = 0,20). Posiciones −1, 0 y +1.

## Qué mirar primero

| Archivo | Contenido |
|---|---|
| [`Backtest_USDCLP.ipynb`](Backtest_USDCLP.ipynb) | **Notebook de la entrega**: resumen del backtesting, gráficos, estadísticas de trading y verificaciones |
| [`metodologia_v2.md`](metodologia_v2.md) | Modelos, supuestos, mecanismo de ejecución, pruebas realizadas y pendientes (modelo congelado en §8) |

## Resultados principales (validación 2018-01-02 a 2024-09-27, 1.714 jornadas, 2 pb por unidad de cambio de posición)

| | M1 · DH (q 0,20) | Comprar siempre (+1) |
|---|---|---|
| Retorno anual neto de carry y costos | 6,98 % | 3,42 % |
| Volatilidad anual | 9,93 % | 14,05 % |
| Sharpe | 0,70 | 0,24 |
| Drawdown máximo | −15,2 % | −35,2 % |
| Acierto en días con posición | 54,4 % | 50,6 % |
| Operaciones (suma de \|Δposición\|) | 1.014 | 1 |

Reservas (detalle en la sección 7 del notebook): el costo de 2 pb y el carry (FEDL01 rezagada − TPM) son supuestos propios porque aún no se tienen los del kit; q = 0,20 se eligió con datos del mismo período, así que las cifras son una cota superior; **el tramo fuera de muestra (desde 2024-10-01) no se ha evaluado**. Ninguna estrategia sobrevive a la corrección por comparaciones múltiples (metodología §7).

## Modelos y supuestos (resumen; detalle en la metodología §8)

- **Variables:** 13 series del núcleo (cobre HG1, DXY, VIX, UST2Y, FEDL01, BRL, MXN, CHNI, volatilidad implícita del USD/CLP, etc.), con información hasta el cierre de la jornada *t*. Datos de Bloomberg hasta el 2026-11-06, panel limpio de jornadas con cotización del USD/CLP.
- **Modelo (M1):** regresión logística con regularización L2 (C = 0,01), estandarizada solo con datos de entrenamiento. Ventana expansiva desde 2000-08-01 y reentreno cada 20 jornadas. Predice la probabilidad de que el USD/CLP suba al día siguiente.
- **Calibración:** Platt en línea, ajustada solo con predicciones fuera de muestra previas.
- **Regla de exposición (DH):** percentil de la probabilidad cruda entre las últimas 63 predicciones. Entra en +1 si el percentil es ≥ 0,80 y en −1 si es ≤ 0,20. Mantiene la posición hasta que el percentil cruza 0,50 y entonces pasa a 0 (o a la posición contraria si llega al otro extremo). Filtro de calidad: 0 si la desviación de las últimas 63 predicciones es < 10⁻⁴.
- **Descartados** tras pruebas con reglas fijadas de antemano: LightGBM y el promedio de modelos (M2, M3, sin mejora robusta frente a costos) y las posiciones ±3 (metodología §8.2 y §8.4; la mentoría respondió de forma verbal que ±3 no es lo más importante).
- **Costos y carry:** 2 pb por unidad de cambio de posición. Carry overnight = FEDL01 rezagada − TPM (metodología §8.3), devengado por días reales / 360.

## Mecanismo de ejecución

- **Cuándo se decide:** con la información disponible al cierre de la jornada *t* (valores `PX_LAST` de cada serie; FEDL01 rezagada un día).
- **Qué se opera y a qué precio:** la posición decidida en *t* se mantiene de *t* a *t*+1 y gana el retorno cierre a cierre del USD/CLP (`PX_LAST`). No se usa apertura ni el dólar observado como precio de ejecución.
- **Qué gatilla una operación:** un cambio del percentil de la probabilidad según la regla DH de arriba. El costo se cobra por cada unidad de cambio de posición; el de salir a 0 se imputa al último día con posición activa.
- **Lunes y feriados:** los retornos se calculan sobre la secuencia de jornadas (el retorno del lunes cubre el fin de semana), con una prueba automática en `01_panel.py`.
- **Supuesto del torneo sobre los horarios:** el diccionario de datos de los organizadores indica asumir que el modelo corre al cierre de cada sesión, con todos los cierres de una misma fecha disponibles, y usarlos tal como vienen; se sigue esa regla. **Salvedad** (metodología §9): VIX, DXY y UST2Y cierran en Nueva York, normalmente después de la fijación del USD/CLP; si en la práctica el USD/CLP se fija antes, las cifras serían algo optimistas y esas series se rezagarían un día, reentrenando con el cambio declarado.
- **Monitoreo en vivo:** `04_senal_diaria.py` entrega la señal al cierre de la última jornada de la base (dirección según el signo de la posición, "abstención" si es 0, probabilidad calibrada y percentil).

## Cómo ejecutar

Probado con Python 3.14 (las versiones de `requirements.txt` están fijadas para ese entorno).

```
git clone https://github.com/aortegad-byte/alonsolucas.git
cd alonsolucas
python -m venv .venv
.venv\Scripts\activate          # Windows;  en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Reproducir el notebook (no necesita la base de Bloomberg)

El notebook lee solo los archivos ya generados en `resultados/`, que están en el repositorio. Desde la raíz del repositorio:

```
jupyter nbconvert --to notebook --execute --inplace Backtest_USDCLP.ipynb
```

o abrirlo en Jupyter / VS Code y ejecutar todas las celdas **con la raíz del repositorio como directorio de trabajo** (el notebook busca `resultados/`).

### 2. Regenerar los resultados desde los datos (opcional)

La base de Bloomberg (`base_usdclp_actualizada.xlsx`, datos hasta el 2026-11-06) **no se incluye en el repositorio** por ser un dato licenciado; es la base `base_usdclp` que entregaron los organizadores del torneo. Copiarla a la raíz del repositorio y ejecutar en orden:

```
python 01_panel.py --xlsx "base_usdclp_actualizada.xlsx" --variante core
python 02_seleccion_variables.py "base_usdclp_actualizada.xlsx"
python 03_modelos_decision.py "base_usdclp_actualizada.xlsx"
python 04_senal_diaria.py "base_usdclp_actualizada.xlsx"
python 07_conviccion_diaria.py "base_usdclp_actualizada.xlsx"
```

Los scripts escriben en `resultados/` (y `01_panel.py` en `data/`, ignorado por git). Los modelos usan semilla fija. `01_panel.py` usa por defecto el carry overnight; con `--carry ndf` usa FEDL01 − CHNI1M. `04_senal_diaria.py` guarda la decisión en `resultados/senal_del_dia.json`; con `--hasta AAAA-MM-DD` calcula la señal como si la base terminara ese día.

## Archivos

| Archivo | Contenido |
|---|---|
| `Backtest_USDCLP.ipynb` | Notebook de la entrega (resumen de backtesting, gráficos, estadísticas) |
| `metodologia_v2.md` | Metodología vigente, resultados y modelo congelado (§8); pendientes en §9 |
| `Resumen_tecnico_desafio_USDCLP.pdf` | Resumen técnico de la etapa 1 (10 oct 2026) |
| `Tabla Comparativa Variables Núcleo USD CLP.pdf` | Tabla anterior; reemplazada (metodología §2) |
| `01_panel.py` | Panel limpio, objetivo, chequeos (look-ahead y lunes) y referencias provisionales |
| `02_seleccion_variables.py` | Panel y selección de variables (etapa 2a) |
| `03_modelos_decision.py` | Modelos, calibración y capa de decisión (etapa 2b); define el modelo congelado |
| `04_senal_diaria.py` | Señal del día con el modelo congelado |
| `05_prueba_tres.py`, `06_prueba_e.py` | Pruebas de ±3 (descartadas, metodología §8.2 y §8.4) |
| `07_conviccion_diaria.py` | Lectura de la convicción y del riesgo sobre el desarrollo (genera los CSV que usa el notebook) |
| `resultados/` | Salidas de los scripts |
