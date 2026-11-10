# Desafío USD/CLP · Metodología v2

Actualización del *Resumen técnico* (10 de octubre de 2026). Fecha: 16 de octubre de 2026.
Mismas marcas: **[Decidido]** acordado o implementado; **[Propuesta]** sugerido y por confirmar.
Este documento reemplaza o agrega a las secciones indicadas; lo no mencionado sigue igual.

---

## 1. Lo que confirman las bases (reemplaza parte de §2 y §7.4)

| Aspecto | Antes | Ahora |
|---|---|---|
| Tres referencias | "+1, 0 y −1" (supuesto) | **Comprar siempre (+1), no operar nunca (0) y operar siempre con exposición uno.** Las bases nombran las referencias en el entregable 2. "Comprar siempre" y "exposición uno" podrían ser la misma estrategia o distinguirse por el carry o el rebalanceo; **se confirma con el código de evaluación**. |
| Carry | Proxy propio (FEDL01 rezagada − CHNI1M); desde el 9 nov 2026, FEDL01 rezagada − TPM (§8.3) | Las bases dicen que la base del kit trae el carry ya calculado y que lo calcula el laboratorio "bajo una regla única". La base que tenemos viene en bruto: **se mantiene un proxy hasta recibir el del kit**. |
| Fuera de muestra | 2024-10-01 (valor de trabajo) | Lo define el código de evaluación. El jurado además mide el **monitoreo en vivo (13 nov–1 dic)**, que ningún modelo vio. |
| Criterios | — | Valor económico neto de costos, significancia (DM + bootstrap contra las tres referencias), rigor metodológico y defensa oral. |

Las preguntas de la mentoría (§10) siguen abiertas, salvo la 3, que queda respondida en parte.

## 2. Correcciones al resumen anterior

- **CHOVCHOV Index es la TPM** (desde el 9 de agosto de 2001, según el diccionario). Ya estaba considerada como "TPM" en las variantes. No se empalma con CHON (otra unidad, §6.3).
- **Error en la tabla comparativa de variables del núcleo** (documento aparte):
  1. **Objetivo equivocado.** La regresión explica el movimiento del USD/CLP **del mismo día** (R² 27–33 %), no el del día siguiente. Mide co-movimiento, no capacidad de predicción. Sus p-valores no sirven para decidir qué entra al modelo.
  2. **Muestra recortada.** Las diferencias se calcularon sobre el calendario continuo, que incluye fines de semana, y sin relleno. Así se pierden **todos los lunes** y cada día que sigue a un hueco: 4.117 observaciones desde 2000, contra 6.456 disponibles. Además, el lunes es justo el día que acumula la información del fin de semana.
  3. **Usa el período de prueba.** Llega hasta 2026, así que incluye el tramo fuera de muestra. Seleccionar variables mirando ese tramo es *data snooping* (§5.1, §6.4).
  4. **Lo que sí vale:** el diagnóstico de multicolinealidad (VIF y correlaciones entre cambios diarios) no depende del objetivo y se conserva (§4).

## 3. Protocolo de construcción del panel (precisa §7.1) [Decidido]

1. Relleno hacia adelante de hasta 5 días calendario **sobre el calendario completo, antes de filtrar jornadas**.
2. Se filtran las jornadas con cotización del USD/CLP.
3. **Toda diferencia o retorno se calcula sobre la secuencia de jornadas**, nunca sobre el calendario continuo. El retorno de un lunes cubre el fin de semana. *Regla de chequeo:* el panel debe contener lunes en proporción ~1/5. Se agrega como prueba automática a `01_panel.py`.
4. Rasgos con información hasta el cierre de t (FEDL01 rezagada un día). Objetivo: `ret_next` (t → t+1) y `up_next`.

## 4. Simplificación del núcleo por redundancia [Descartada: ver §6]

Con los VIF de la tabla comparativa (válidos porque son entre predictores):

| Bloque | Hoy | Propuesta | Motivo |
|---|---|---|---|
| Carry Chile (CHNI) | Δ1M, Δ3M, Δ6M | **ΔCHNI1M + pendiente (ΔCHNI6M − ΔCHNI1M)**; nivel de CHNI1M solo dentro del carry | ρ(Δ3M, Δ6M) = 0,89; VIF de CHNI3M = 5,1 |
| Vol. implícita USD/CLP | ΔV1M, ΔV3M | **ΔV1M**; la pendiente (V3M − V1M) pasa a candidata | ρ = 0,69; V3M sin aporte propio |
| Resto | Cobre, DXY, VIX, UST2Y, FEDL01, BRL, MXN | Sin cambios | VIF ≤ 1,6 |

La logística Ridge tolera colinealidad. Esta simplificación busca estabilidad e interpretabilidad, no mejorar el acierto. La validación de §5 confirma si el núcleo reducido rinde igual que el completo. Se usa la misma prueba anidada: el núcleo reducido se trata como el modelo base y CHNI3M y V3M se prueban como candidatas.

## 5. Protocolo para evaluar variables candidatas (reemplaza el método de §6.4) [Decidido]

Hay **dos preguntas distintas**, y cada una tiene su herramienta:

| Pregunta | Herramienta | Uso |
|---|---|---|
| ¿Repite información que ya está en el núcleo? | Regresión del Δ de la candidata sobre los Δ del núcleo, **mismo día** (R², VIF) | Filtro de redundancia; no decide la inclusión |
| ¿Ayuda a predecir el USD/CLP de **t+1**? | Etapas A–C | Decide la inclusión |

**Período.** Todo se calcula solo en el tramo de desarrollo: **2000-08-01 a 2024-09-30**. El tramo fuera de muestra no se mira hasta el final. Si el kit define otro corte, se ajusta y se rehace.

**Etapa A · Señal univariada.** `ret_next(t)` sobre `Δx(t)`, con errores HAC (Newey-West, 5 rezagos). Se reporta ρ, t-HAC y acierto teórico ≈ 0,5 + arcsin(ρ)/π. También se reporta la **estabilidad del signo por subperíodo** (2000–2009, 2010–2019 y 2020–sep 2024).

**Etapa B · Aporte por encima del núcleo.** `ret_next(t)` sobre el núcleo más la candidata, con errores HAC. Se reporta el coeficiente y el t-HAC de la candidata. Es dentro de la muestra y solo sirve para ordenar prioridades.

**Etapa C · Prueba fuera de muestra (decide).** Walk-forward con ventana expansiva, reentrenando cada 20 jornadas. Las predicciones se evalúan desde 2010 (primeros 10 años como calentamiento). Se comparan la logística Ridge del núcleo y la del núcleo más la candidata, con la misma C fijada de antemano.
- Métricas: diferencia en log-loss y en Brier score.
- Test: **Clark-West** (modelos anidados) y Diebold-Mariano sobre el diferencial de log-loss, con HAC de 5 rezagos.

**Comparaciones múltiples.** Se registran todas las candidatas probadas (k). A los p-valores de la etapa C se les aplica **Benjamini-Hochberg al 10 %**, y Bonferroni se reporta como referencia.

**Regla de inclusión, fijada antes de ver resultados.** Una candidata entra si cumple las dos condiciones:
1. Mejora la log-loss en la etapa C y sobrevive a Benjamini-Hochberg.
2. Su coeficiente mantiene el signo en al menos 2 de los 3 subperíodos.

Si una candidata no entra sola pero el bloque al que pertenece sí aporta (por ejemplo, un factor regional COP+PEN), se prueba el bloque como **una** candidata más.

**Candidatas.**
- Prioridad alta: USDZAR, HG1, MOVE, MXEF, CO1, JPMVXYEM.
- Prioridad baja: USDCOP, USDPEN o un factor regional.
- Del núcleo actual: CHNI3M y USDCLPV3M.
- Transformaciones: pendiente de vol. USD/CLP, pendiente EE.UU. (10a − 2a).
- Variantes por fecha de inicio, evaluadas en su propio período y declaradas aparte:
  - desde 2001: TPM (CHOVCHOV);
  - desde 2004: CHSWP1 y CHSWP10;
  - desde 2010: USDCNH.

**Advertencias.** Con una señal de ρ ≈ 0,1 se esperan mejoras de log-loss del orden de 10⁻³. Es normal que la mayoría de las candidatas no pase. Excluir es un resultado válido y defendible ante el jurado.

**Detalles de implementación** (`02_seleccion_variables.py`):
- C = 0,01, con C = 1 como sensibilidad.
- El p-valor que entra a Benjamini-Hochberg es el de **Clark-West unilateral**, porque los modelos son anidados.
- Para comparar modelos no anidados (por ejemplo, reemplazar una serie por otra) se usa Diebold-Mariano sobre la log-loss.

## 6. Resultados de la etapa 2a (16 oct 2026) [Decidido: regla adoptada; núcleo se mantiene]

El tramo de desarrollo tiene 6.025 jornadas; la etapa C evalúa entre 2010 y septiembre de 2024 (3.566 jornadas). Todos los números están en `resultados/seleccion_variables.xlsx`.

**Candidatas: ninguna entra.** El umbral de Benjamini-Hochberg para la mejor de 14 candidatas es p ≤ 0,0071.

| Candidata | Δ log-loss ×10⁴ | p Clark-West | Signo estable | Lectura |
|---|---|---|---|---|
| HG1 (cobre COMEX) | −1,4 | 0,024 | 3/3 | La más cercana a entrar; no pasa la corrección |
| USDZAR | −2,7 | 0,055 | 1/3 | Mayor mejora, pero el signo es inestable |
| CHSWP10, pendiente EE.UU. | −0,7 / −1,0 | 0,22 / 0,18 | 2/3 | Ruido |
| MOVE, MXEF, JPMVXYEM, Brent, TPM, CHSWP1, USDCNH, COP, PEN, factor regional | +0,2 a +3,8 | > 0,3 | — | Empeoran la log-loss |

La sensibilidad con C = 1 da los mismos signos.

**Núcleo:**
- **Contra la frecuencia histórica de alzas:** Δ log-loss −22,7 ×10⁻⁴; Clark-West p < 0,0001; acierto 52,9 % frente a 50,1 %. Pero Diebold-Mariano da p = 0,15, y DM es el test que exigen las bases.
- **Qué se pierde al quitar cada serie** (las que ayudan): CHNI3M −8,0 (p 0,012), USDMXN −6,1 (0,021), USDBRL −3,4 (0,054). Ninguna sobrevive a Benjamini-Hochberg con 13 pruebas.
- **Al quitar estas series, el modelo mejora** (hoy restan): cobre LME +8,6, VIX +6,5, vol. 3M +4,7, DXY +3,7, CHNI6M +3,2, CHNI1M +3,1. Ninguna diferencia es significativa.
- **El núcleo reducido de §4 rinde peor que el completo** (−4,4; Clark-West p 0,026): **se descarta la propuesta de §4.**
- **Prueba exploratoria fuera del protocolo:** reemplazar el cobre LME por HG1 da Δ −3,2 (Diebold-Mariano p 0,037) y mejora en los tres quinquenios (−5,1, −3,4, −1,0). Cuenta como una prueba adicional.

### 6.1 Núcleo con HG1 en lugar de LMCADS03 (16 oct 2026) [Decidido]

Se reemplazó el cobre LME por HG1 (COMEX, que cierra más tarde) y se repitió todo el protocolo. HG1 deja de ser candidata, así que quedan 13 candidatas y el umbral de Benjamini-Hochberg para la mejor pasa a 0,0077.

| Métrica (2010 a sep 2024, 3.566 jornadas) | Núcleo con LME | Núcleo con HG1 |
|---|---|---|
| Δ log-loss ×10⁴ vs frecuencia histórica | −22,7 | **−25,9** |
| p Clark-West / p Diebold-Mariano | < 0,0001 / 0,149 | < 0,0001 / **0,114** |
| Acierto direccional | 52,86 % | 52,89 % |
| Δ log-loss al quitar el cobre | +8,6 (resta) | +5,4 (sigue restando, menos) |
| Candidatas que entran | 0 de 14 | **0 de 13** |

Lectura:
- **El cambio mejora la calidad de la probabilidad**, no el acierto direccional.
- **El cobre sigue sin aportar** en este modelo lineal. Se mantiene por sentido económico (términos de intercambio) y porque podarlo mirando estos datos sería *data snooping*. Se revisará con LightGBM, que puede captar relaciones no lineales.
- **Las series que cargan la señal no cambian:** USDMXN, USDBRL y CHNI3M.
- **Ninguna candidata cambia de veredicto.** La mejor por p sigue siendo USDZAR (p 0,067), con signo inestable.
- **Pruebas acumuladas sobre el tramo de desarrollo:**
  - 14 candidatas;
  - 13 exclusiones (quitar una serie a la vez del núcleo);
  - 1 comparación de núcleo reducido contra completo;
  - 1 reemplazo del cobre.

## 7. Etapa 2b: modelos, calibración y capa de decisión (16 oct 2026) [Núcleo congelado]

Script: `03_modelos_decision.py`. Resultados: `resultados/modelos_decision.xlsx` y `resultados/senales_desarrollo.csv`.

**Diseño.** Todo se fijó antes de correr, salvo lo que se marca como corrección.

| Pieza | Elección |
|---|---|
| Predicción | Walk-forward expansivo desde 2010, reentreno cada 20 jornadas |
| M0 | Frecuencia histórica de alzas |
| M1 | Logística Ridge, C = 0,01 |
| M2 | LightGBM: profundidad 2, 300 árboles, tasa de aprendizaje 0,02, mínimo 200 por hoja, λ = 10 |
| M3 | Promedio de M1 y M2 |
| Calibración | Platt en línea, ajustado solo con predicciones fuera de muestra previas (mínimo 500) |
| Decisión | Percentil de la probabilidad entre las últimas 63 predicciones, más filtro de calidad |
| D1 | Siempre ±1 |
| D2 | Banda: ±1 fuera de [q, 1−q], 0 dentro |
| D3 | D2 más ±3 en el 5 % más extremo de cada lado, solo si en selección los extremos aciertan más que la banda |
| DH | Banda con histéresis: entra fuera de la banda y sale recién al cruzar la mediana |
| Tramos | Selección 2012–2017 (elige q con el Sharpe suavizado, costo 2 pb); validación 2018 a sep 2024 (1.714 jornadas) |
| Resultado | pos × (ret_next + carry proxy) − costo × \|Δpos\| |
| Significancia | Bootstrap estacionario (bloques de largo medio 10, 5.000 réplicas) contra +1, 0 y −1, con Benjamini-Hochberg sobre 36 pruebas |

**Correcciones hechas en el camino** (se declaran):
1. La primera versión de D3 ponía ±3 en la mitad de la banda, lo que daba ~45 % de los días en ±3. Esto contradecía §8.1 del resumen, que reserva ±3 para el 5–10 % de los días, y se corrigió a una cola fija del 5 %.
2. Se agregó DH después de ver que D1 y D2 rotan ~270 veces el nominal por año. Es una prueba adicional.

**Calidad de la probabilidad** (validación; Δ log-loss ×10⁴ frente a M0; p de Diebold-Mariano unilateral):

| Modelo | Crudo | Calibrado (Platt) |
|---|---|---|
| M1 Ridge | −8,6 (p 0,38) | −22,5 (p 0,13) |
| M2 LightGBM | −13,6 (p 0,30) | −25,1 (p 0,078) |
| M3 promedio | −20,2 (p 0,21) | −27,4 (p 0,081) |

Lectura:
- **Los modelos crudos se exceden en confianza:** la pendiente de calibración es 0,55–0,68, cuando un modelo bien calibrado da 1.
- **Platt corrige la calibración** (pendiente 0,73–0,85) y mejora todos los modelos. En 2012–2024, M1 y M3 calibrados llegan a p 0,064 y 0,058.
- **La señal del día debe reportar la probabilidad calibrada.**
- **La capa de decisión no cambia con la calibración:** usa percentiles, que no se alteran con una transformación monótona.

**Estrategias** (validación 2018 a sep 2024; Sharpe anual con costos de 0, 2 y 5 pb por unidad de cambio de exposición):

| Estrategia | Sharpe 0 pb | Sharpe 2 pb | Sharpe 5 pb | % días invertido | Rotación/año | p vs 0 (2 pb) |
|---|---|---|---|---|---|---|
| M1 · DH (q 0,20) | 1,00 | **0,70** | 0,25 | 53 % | 149 | 0,038 |
| M2 · D2 (q 0,35) | 0,82 | 0,41 | −0,20 | 71 % | 243 | 0,124 |
| M2 · D3 | 0,81 | 0,41 | −0,20 | 71 % | 347 | 0,114 |
| M2 · DH (q 0,25) | 0,79 | 0,48 | 0,01 | 64 % | 177 | 0,098 |
| M1, M3 · D1, D2, D3 | 0,19–0,32 | < 0 | < 0 | 90–100 % | 266–378 | > 0,5 |
| Referencia siempre +1 | 0,27 | 0,27 | 0,27 | 100 % | 0 | — |

Lectura:
1. **Ninguna estrategia sobrevive a Benjamini-Hochberg.** La mejor es M1·DH, con p 0,038 contra no operar nunca y 0,055 contra siempre −1.
2. **El costo de transacción decide el resultado.** Con rotaciones de 150–380 veces el nominal al año, 2 pb consumen 3–7 puntos de retorno anual. Hay que conocer el costo real del kit antes de elegir.
3. **La histéresis es la única mejora robusta a costos:** reduce la rotación a la mitad y es lo único positivo con 5 pb.
4. **±3 no paga.** En validación, los días extremos aciertan 52–57 %, apenas más que la banda, y suben la rotación. Se recomienda operar solo con ±1, como dice §8.3 del resumen.
5. **En selección, el Sharpe es casi plano frente a q** (0,9–1,3): el ancho de banda no está bien identificado.
6. **El Sharpe cae de ~1,2 en selección a ~0,5 en validación**, una degradación esperable.

**Pruebas acumuladas sobre el tramo de desarrollo:**
- 29 de la etapa 2a;
- 6 modelos de probabilidad;
- 12 estrategias contra 3 referencias.

## 8. Modelo congelado (16 oct 2026) [Decidido]

Desde aquí no se cambian ni las variables, ni el modelo, ni la regla de exposición, salvo por la información del kit (costos, carry, período fuera de muestra). Cualquier cambio posterior se declara como una prueba nueva.

| Componente | Especificación |
|---|---|
| Rasgos | Las 13 series del núcleo de §6.1, incluido el retorno del USD/CLP, con el cobre HG1 |
| Modelo | Logística Ridge (C = 0,01), estandarización ajustada solo con entrenamiento |
| Reentreno | Ventana expansiva desde 2000-08-01, cada 20 jornadas |
| Probabilidad reportada | Calibrada con Platt en línea, ajustado solo con predicciones fuera de muestra previas |
| Exposición | Percentil de la probabilidad cruda entre las últimas 63 predicciones. Entra en +1 si el percentil es ≥ 0,80 y en −1 si es ≤ 0,20. Mantiene la posición hasta que el percentil cruza 0,50; entonces pasa a 0 o a la posición contraria si llega al otro extremo. Filtro de calidad: 0 si la desviación de las últimas 63 predicciones es < 10⁻⁴ |
| Niveles | Solo −1, 0 y +1 (sin ±3) |
| Implementación | `03_modelos_decision.py`, estrategia `M1_ridge\|DH_histeresis_q0.2` |

### 8.1 Señal del día (16 oct 2026) [Implementado]

Script: `04_senal_diaria.py`. Aplica el modelo de §8 con las mismas funciones de `03_modelos_decision.py` y entrega, para la última jornada de la base: dirección, probabilidad calibrada y cruda, percentil de 63 predicciones y posición. No calcula retornos, así que no evalúa el tramo fuera de muestra.

- **Dirección (cambio de reporte del 9 nov 2026):** sale del signo de la posición: +1 = alza, −1 = baja, 0 = abstención. Las probabilidades calibrada y cruda se informan como contexto, no como decisión. Antes la dirección salía de la probabilidad calibrada (> 0,5 = alza) y podía contradecir a la posición. Es un cambio solo de reporte: el modelo y las posiciones no cambian.
- **Verificación:** en las 5.949 jornadas de desarrollo reproduce exactamente `M1_ridge|DH_histeresis_q0.2` de `senales_desarrollo.csv`. Truncando la base en cinco fechas (2012–2026), la señal de cada fecha es idéntica a la calculada con la base completa (sin look-ahead).
- **Si una serie del núcleo no tiene dato** dentro del relleno de 5 días, el script se detiene en vez de emitir una señal con datos rancios.
- Para extender el panel hasta la última jornada, `construir_panel` de `02_seleccion_variables.py` recibe ahora `fin` y `hasta` opcionales; con los valores por defecto el resultado de 02 y 03 no cambia.

### 8.2 Prueba de ±3 con señal clara (16 oct 2026) [Descartada: se mantiene ±1]

Script: `05_prueba_tres.py`; resultados en `resultados/prueba_tres.xlsx`. Las reglas y el criterio de elección se fijaron y se registraron en git (commit `e522232`) antes de correr.

- **Principio:** el ±3 solo amplifica una posición ±1 del modelo congelado en la misma dirección.
- **Reglas anidadas:** A acuerdo (percentil de M1 y de M2 ≥ 0,90, o ≤ 0,10); B + probabilidad calibrada a ≥ 0,068 de 0,5 (percentil 80 en selección); C + persistencia (acuerdo también el día anterior); D + vol. implícita 1M fuera del 20 % más alto del último año.
- **Criterio (selección 2012–2017, 2 pb):** ≥ 30 días en ±3, acierto ≥ 3 puntos sobre los días ±1, mayor resultado por unidad y mayor Sharpe que el modelo congelado.

| Regla | Días ±3 | Acierto ±3 / ±1 | Resultado por unidad ±3 / ±1 (pb) | Sharpe con ±3 / congelado |
|---|---|---|---|---|
| A acuerdo | 136 | 56,6 % / 54,5 % | 9,8 / 10,6 | 1,24 / 1,44 |
| B + probabilidad | 87 | 56,3 % / 54,7 % | 8,5 / 10,7 | 1,19 / 1,44 |
| C + persistencia | 2 | — | — | 1,42 / 1,44 |
| D + volatilidad | 2 | — | — | 1,42 / 1,44 |

Lectura:
- **Ninguna regla califica**, así que la validación no se miró y el modelo congelado no cambia.
- Los días de acuerdo aciertan algo más, pero **no ganan más por unidad** que los días ±1 y bajan el Sharpe: triplicar la exposición suma más riesgo y rotación que retorno.
- **La persistencia casi nunca se da:** el percentil de M1 tiene autocorrelación −0,17 (la señal viene de movimientos del día anterior que en parte se revierten).
- **Pruebas acumuladas:** 4 reglas de ±3 evaluadas en selección; ninguna prueba nueva en validación.

### 8.3 Carry overnight en el modelo congelado (9 nov 2026) [Decidido: cambio declarado]

El proxy de carry pasa de FEDL01 rezagada − CHNI1M (NDF 1M) a **FEDL01 rezagada − TPM (CHOVCHOV)**, diferencial estricto de tasas overnight. No viene del kit, así que se declara como cambio según §8. En `01_panel.py` la regla está en `calcular_carry_diario` (`--carry overnight`, por defecto, o `--carry ndf`), con `USAR_CARRY_OFICIAL_KIT` para cambiar al carry del kit cuando llegue.

- **Qué no cambia:** rasgos, modelo, filas de entrenamiento, probabilidades, posiciones, q elegidos (`seleccion_q`), activación de ±3 y convicción. `senales_desarrollo.csv` sale idéntico. `03_modelos_decision.py` mantiene `x_chni1m` en el filtro de filas para no recortar la muestra (la TPM parte el 2001-08-09; las predicciones, en 2010). La señal del día (§8.1) no usa el carry.
- **Qué cambia:** solo los resultados en pesos (carry en el resultado).

| Validación 2018 – sep 2024, 2 pb | Carry NDF | Carry overnight |
|---|---|---|
| M1·DH q0,20: media anual / Sharpe | 6,92 % / 0,696 | 6,98 % / 0,702 |
| Comprar siempre (+1): media anual | 3,78 % | 3,42 % |
| M1·DH − comprar siempre: diferencia / p bootstrap | 3,14 pts / 0,306 | 3,56 pts / 0,281 |
| M1·DH − no operar: p bootstrap | 0,038 | 0,036 |

- La elección de q en selección se mantiene (M1·DH: Sharpe 1,436 → 1,441 en q = 0,20) y la prueba de ±3 (§8.2) sigue sin reglas que califiquen.
- **Diferencia relevante en el tramo fuera de muestra:** la TPM (4,5 %) está casi un punto sobre CHNI1M (3,6 %) por la base onshore/offshore, así que con el carry overnight mantener un largo en USD cuesta ~0,7 puntos al año más que con el NDF (referencias de `01_panel.py` desde 2024-10-01: comprar siempre 3,71 % frente a 4,49 % anual con carry).
- **Pruebas acumuladas:** ninguna nueva; cambia la medición del resultado, no la estrategia.

### 8.4 Prueba E: ±3 con restricciones de riesgo (9 nov 2026) [Rechazada por riesgo: se mantiene ±1]

Script: `06_prueba_e.py`; resultados en `resultados/prueba_e.xlsx`. Las reglas, los criterios y la decisión se registraron en git (commit `6f213a8`) antes de correr la selección.

- **Por qué otra prueba:** las bases exigen que ±3 esté entre las posiciones posibles en el monitoreo en vivo. D3 (§7) y las reglas A–D (§8.2) mostraron que los días de señal "más clara" no ganan más por unidad, así que E no busca más acierto: **limita el daño** de triplicar la exposición.
- **Principio:** igual que en §8.2, el ±3 solo amplifica una posición ±1 del modelo congelado en la misma dirección.
- **Restricciones** (todas, con información hasta el cierre de t):
  1. **Señal extrema:** percentil de M1 ≥ 0,95 (o ≤ 0,05), la cola del 5 % del resumen técnico.
  2. **Régimen calmo:** vol. implícita 1M ≤ su mediana de las últimas 252 jornadas.
  3. **Duración:** como máximo 3 jornadas seguidas en ±3; la cuarta vuelve a ±1.
  4. **Freno:** si una jornada en ±3 pierde más de 1 % del nominal (retorno + carry), no hay ±3 en las 20 jornadas siguientes.
  5. **Tope de frecuencia:** como máximo 5 jornadas en ±3 dentro de las últimas 100 decisiones.
- **Criterios en selección (2012–2017, 2 pb):** *ventaja*, los cuatro de §8.2 (≥ 30 días en ±3, acierto ≥ 3 puntos sobre ±1, mayor resultado por unidad, mayor Sharpe que el congelado); *riesgo*, máximo drawdown no peor que el del congelado y peor día no peor que 1,5 veces el del congelado.
- **Decisión:** ventaja y riesgo → **aprobada**; solo riesgo → **incluida por cumplimiento de las bases** (se declara así); falla riesgo → solo ±1. Si se adopta, la validación (2018 – sep 2024) se mira una sola vez y solo exige el criterio de riesgo; si lo falla, solo ±1.
- **Cambio antes de correr la selección, declarado:** la restricción 5 decía primero "si en selección hay ±3 en más del 5 % de las jornadas, la regla no se acepta". Se cambió a un tope duro porque esa versión podía dejar al ±3 fuera de las posiciones posibles. El cambio se hizo **después de ver** que en 2010–2011 (antes de selección, al revisar la mecánica) la regla daba ±3 en el 5,1 % de las jornadas; con el tope, 3,3 %. No se miró ningún resultado de 2012 en adelante.
- **Advertencias:** la validación no es una muestra virgen (ya se miró en la etapa 2b). Con ~13 jornadas de monitoreo, un solo día en ±3 puede dominar el resultado en vivo.
- **Pruebas acumuladas:** 5 reglas de ±3 evaluadas en selección (4 en §8.2 + E); ninguna prueba nueva en validación.

**Resultado (selección 2012–2017, 2 pb), corrido una sola vez:**

| | Con ±3 (E) | Congelado ±1 |
|---|---|---|
| Jornadas en ±3 | 37 (2,7 %) | — |
| Acierto días ±3 / días ±1 | 51,4 % / 55,1 % | |
| Resultado por unidad días ±3 / días ±1 | −4,5 pb / +11,3 pb | |
| Sharpe | 1,12 | 1,44 |
| Máximo drawdown | −15,8 % | −9,5 % |
| Peor día | −4,65 % (límite 1,5 × = −2,87 %) | −1,91 % |

- **Falla en ventaja y en riesgo** → solo ±1; la validación no se miró. El tope cortó 21 candidatos y el freno, 27.
- **Lectura:** con restricciones de riesgo, los días de señal extrema aciertan *menos* que los ±1 y pierden por unidad. Junto con D3 y A–D, es la quinta vez que el ±3 no paga en este modelo: la cola extrema de M1 no concentra la señal.
- **Pendiente con las bases:** las bases exigen que ±3 esté entre las posiciones posibles en el monitoreo. Con este resultado, el modelo congelado no emite ±3. La mentoría respondió el 10 nov 2026, de forma verbal, que ±3 no es lo más importante (§9, decisión abierta 3, cerrada); no se abre una prueba nueva.

## 9. Pendientes (actualizado al cierre de la sesión del 10 nov 2026)

**Hecho en la sesión del 10 nov 2026**
- Dirección de la señal del día según el signo de la posición, con "abstención" cuando es 0 (§8.1); decisión abierta 1 resuelta.
- Decisión abierta 3 (±3 en el monitoreo) cerrada con la respuesta verbal de la mentoría; pendiente la respuesta por escrito.
- Lectura de la convicción y del riesgo del modelo congelado, descriptiva, sobre el tramo de desarrollo (§9.1, `07_conviccion_diaria.py`). No es una prueba nueva y no cambia el modelo.

**Hecho en la sesión del 9 nov 2026**
- Base actualizada (`base_usdclp_actualizada.xlsx`, datos hasta el 2026-11-06): mismas 77 columnas e historia idéntica a la anterior; solo agrega 31 jornadas. Pasa a ser la base por defecto de los scripts.
- Señal al cierre del 6 nov 2026: baja, probabilidad calibrada 0,495, posición 0 (cierra el +1 del día anterior).
- Carry overnight FEDL01 rezagada − TPM en `01_panel.py` y en el modelo congelado (§8.3): no cambia señales ni posiciones.
- Prueba E de ±3 con restricciones de riesgo (§8.4): rechazada por ventaja y por riesgo; se mantiene ±1.

**Hecho en la sesión del 16 oct 2026**
- `01_panel.py` en el repo, con prueba de lunes (§3.3): `prueba_lunes_ok` exige que tanto las jornadas como las jornadas con retorno sean lunes en 17–23 %. Da 20,1 % en las tres variantes; si el retorno se calcula sobre el calendario continuo, los lunes con retorno caen a 0 % y la prueba falla. Nota: `01_panel.py` todavía usa el cobre LME (LMCADS03); los scripts 02 a 05 arman su propio panel con HG1, así que no afecta al modelo congelado.
- Etapa C (§5) reproducida con HG1: el script 02 da resultados idénticos a los guardados.
- Señal del día (§8.1, `04_senal_diaria.py`), verificada contra el script 03 y sin look-ahead.
- Prueba de ±3 con señal clara (§8.2, `05_prueba_tres.py`): descartada, se mantiene ±1.

**Decisiones abiertas**
1. **Dirección que reporta la señal del día.** [Resuelta el 9 nov 2026] La dirección es el signo de la posición (+1 alza, −1 baja) y "abstención" cuando es 0 (§8.1). La probabilidad queda como contexto. El modelo y las posiciones no cambian.
2. **Alinear `01_panel.py` con HG1**, o declararlo solo como panel de la etapa 1.
3. **±3 en el monitoreo (urgente, antes del 13 nov).** Las bases exigen que ±3 esté entre las posiciones posibles, y el modelo congelado no lo emite tras la prueba E (§8.4). Según lo que responda la mentoría: (a) si basta con que la regla pueda emitir ±3, incluir la regla E por cumplimiento, declarando que en desarrollo no pagó; (b) si ±3 debe usarse efectivamente, lo mismo, con el resultado de §8.4 a la vista. No abrir una 6.ª regla elegida después de ver E. Si se incluye, hay que llevar la regla E a `04_senal_diaria.py`.
   **[Cerrada el 10 nov 2026]** La mentoría respondió el 10 nov 2026, de forma verbal y no escrita, que ±3 no es lo más importante: lo que importa es que el valor neto después de costos sea positivo y que las señales sean buenas. Se deja la regla E sin incluir por ahora; el modelo congelado sigue en ±1. Si se obtiene la respuesta por escrito, se anota aquí.
4. **`resultados/senal_del_dia.json`:** agregarlo al `.gitignore` o versionarlo para tener el historial de señales del monitoreo.

**Trabajo siguiente**
- **Lectura de la convicción (entregable 3):** hecha de forma descriptiva sobre el tramo de desarrollo (§9.1). Falta la lectura de las jornadas de máxima exposición y de abstención con la convicción en vivo.
- **Curva de resultado (entregable 2)** frente a comprar siempre, no operar nunca y operar siempre con exposición uno; espera el código de evaluación del kit.
- **Reducir la rotación** sin abrir muchas pruebas nuevas (hoy ~149 veces el nominal al año con M1·DH).
- **Monitoreo en vivo (13 nov–1 dic):** usar `04_senal_diaria.py` con la base actualizada cada día; definir cómo llegan los datos nuevos.

**Depende del kit o de la mentoría**
- Respuestas de la mentoría (§10 del resumen): retorno, carry, costos, período fuera de muestra, datos en vivo, rezagos de publicación.
- **±3 en el monitoreo:** decisión abierta 3 cerrada el 10 nov 2026 con respuesta verbal de la mentoría. Falta la respuesta por escrito; si llega, se anota en esa decisión.
- **Carry del kit:** confirmar sus unidades (% anual o resultado diario) antes de activar `USAR_CARRY_OFICIAL_KIT`, porque `pnl` divide por 100 y multiplica por días/360.
- **Texto de las bases:** `Bases.pdf` es un escaneo sin texto; conseguir una versión con texto o transcribir la parte de exposición y ±3.
- **Horarios de cierre:** confirmar si el `PX_LAST` del USD/CLP se fija antes que los cierres de Nueva York (VIX, DXY, UST2Y); si es así, esas series deberían rezagarse un día (riesgo de look-ahead que la prueba de truncamiento no detecta).
- **Costo de transacción del kit:** es lo que hoy decide qué estrategia elegir (§7).
- Evaluar **una sola vez** en el tramo fuera de muestra (desde 2024-10-01), después de conocer costo y carry.

**Para retomar el entorno**
- Clon local de trabajo: `Documents\alonsolucas`, con `.venv` ya creado y la base copiada en la raíz.
- Crear el entorno: `python -m venv .venv` y `.venv\Scripts\pip install -r requirements.txt`.
- Copiar `base_usdclp_actualizada.xlsx` a la raíz (no se publica).
- Las salidas de prueba conviene generarlas fuera del repo, porque los scripts escriben en `resultados/` del directorio actual.

### 9.1 Lectura de la convicción y del riesgo (10 nov 2026) [Descriptiva: sin cambios al modelo]

Análisis del modelo congelado `M1_ridge|DH_histeresis_q0.2` sobre el tramo de desarrollo, 2010-04-01 a 2024-09-27 (3.504 jornadas, desde que hay 63 predicciones para el percentil). No es una prueba nueva, no abre reglas y no mira el tramo fuera de muestra. Script: `07_conviccion_diaria.py "base_usdclp_actualizada.xlsx"`. El resultado se mide con la función `pnl` de `03_modelos_decision.py`, con el carry overnight de §8.3 y 2 pb por unidad de cambio de posición; el costo de salir a 0 se imputa al último día con posición activa. Los intervalos son bootstrap estacionario de bloque medio 10, el de `03_modelos_decision.py`.

**Acierto y resultado por tramo de percentil** (jornadas con posición ≠ 0; `resultados/conviccion_tramos.csv`)

| Percentil de 63 predicciones | Días con posición | Acierto | Neto (pb por jornada) | IC 95 % del neto |
|---|---|---|---|---|
| 0 – 0,10 | 342 | 0,584 | 9,4 | 2,7 a 16,2 |
| 0,10 – 0,20 | 319 | 0,564 | 6,6 | −2,2 a 14,5 |
| 0,20 – 0,50 | 245 | 0,469 | 1,8 | −8,0 a 11,6 |
| 0,50 – 0,80 | 246 | 0,508 | 5,0 | −3,2 a 13,2 |
| 0,80 – 0,90 | 369 | 0,567 | 8,8 | 2,1 a 15,8 |
| 0,90 – 1,00 | 387 | 0,559 | 9,3 | 1,4 a 18,0 |

- El neto es positivo en los seis tramos. El IC 95 % excluye cero en los tramos 0–0,10, 0,80–0,90 y 0,90–1,00.
- En los tramos 0,20–0,80 la posición viene de la histéresis (se mantiene hasta que el percentil cruza 0,50) y el acierto va de 0,469 a 0,508.
- Dentro de la zona extrema el acierto no sube con la convicción: 0,584 y 0,564 en la cola baja; 0,567 y 0,559 en la alta.

**Total sobre las 3.504 jornadas, con carry y 2 pb** (`conviccion_valor_total.csv`, `conviccion_riesgo.csv`)

| Estrategia | Total (pb) | Por jornada (pb) | IC 95 % |
|---|---|---|---|
| Modelo | 13.860 | 3,96 | 1,90 a 6,06 |
| Comprar siempre (+1) | 936 | 0,27 | −2,18 a 2,78 |
| Vender siempre (−1) | −940 | −0,27 | no calculado |
| No operar | 0 | 0 | — |

El modelo menos comprar siempre suma 12.923 pb (3,69 pb por jornada, IC 95 % de 0,44 a 6,81).

**Descomposición señal y carry** (`conviccion_descomposicion.csv`)
- Sin carry, el modelo suma 13.885 pb y comprar siempre 5.242 pb: el modelo la supera por unos 8.640 pb.
- El carry aporta −25 pb al modelo y −4.306 pb a comprar siempre.
- Posiciones del modelo: +1 en 28,6 % de las jornadas, 0 en 45,6 % y −1 en 25,9 %; la posición neta promedio es +0,027. La ganancia viene de la dirección y no del carry.
- Seguir el carry (−1 si TPM > FEDL01 rezagada, +1 en caso contrario) queda en −1 el 99,4 % de las jornadas: es casi vender siempre (−998 pb con carry, −5.306 pb sin carry). El modelo lo supera por 4,24 pb por jornada con carry (IC 95 % de 0,90 a 7,58) y por 5,48 sin carry (IC 95 % de 2,19 a 8,92).

**Subperíodos** (`conviccion_subperiodos.csv`)

| Subperíodo | Jornadas | Modelo, pb por jornada |
|---|---|---|
| 2010-04-01 a 2017-12-31 | 1.790 | 5,09 |
| 2018-01-01 a 2024-09-27 | 1.714 | 2,77 |

El segundo subperíodo coincide con la validación de §8.3: 2,77 × 252 = 698 pb, que son los 6,98 % de media anual del carry overnight.

**Riesgo** (`conviccion_riesgo.csv`)

| Métrica | Modelo | Comprar siempre | Vender siempre |
|---|---|---|---|
| Drawdown máximo (pb) | −1.516 | −3.518 | −5.805 |
| Período del drawdown | 2022-08-30 a 2023-05-26 | 2022-07-13 a 2023-06-07 | 2013-04-08 a 2022-07-13 |
| Rotación anual (veces el nocional) | 148 | 0,07 | 0,07 |
| Costo de equilibrio (pb por unidad de cambio) | 8,46 | 938 | sin equilibrio |

El costo de equilibrio del modelo es el costo con el que su total neto se hace cero: 18.150 pb de resultado bruto divididos entre 2.145 cambios de posición. Es mayor que los 2 pb del análisis y que los 5 pb que §7 usa como tercer escenario de costos.

**Días de cola** (los dos retornos más extremos de la revisión de datos; los precios son observados, sin relleno)
- **2011-01-03, retorno de +4,58 % hasta el 4 de enero.** El Banco Central anunció el lunes 3 de enero de 2011 un programa de compra de divisas para acumular US$ 12.000 millones en reservas durante 2011, con compras desde el 5 de enero. La nota, publicada a las 18:17 horas, informa que el dólar cerró ese día en su nivel más bajo en 31 meses (465,90 comprador y 466,40 vendedor). El modelo estaba en −1 (percentil 0,222) y perdió 457 pb, la peor jornada de su historia en el tramo. Fuente: [Cooperativa, 3 ene 2011](https://cooperativa.cl/banco-central-intervendra-el-dolar-con-programa-de-compra-de-divisas/prontus_nots/2011-01-03/182107.html).
- **2022-07-14, retorno de −7,37 % hasta el 15 de julio.** El Banco Central anunció el jueves 14 de julio de 2022 un programa de intervención cambiaria y provisión preventiva de liquidez en dólares por hasta US$ 25.000 millones, entre el 18 de julio y el 30 de septiembre de 2022: hasta US$ 10.000 millones en venta de dólares spot, hasta US$ 10.000 millones en instrumentos de cobertura cambiaria y hasta US$ 5.000 millones en swap de divisas. La nota de prensa se publicó a las 21:52 horas. El modelo estaba en posición 0 ese día, así que no ganó ni perdió; comprar siempre perdió 739 pb, su peor jornada. Fuentes: [comunicado del Banco Central](https://www.bcentral.cl/contenido/-/details/comunicado-14072022) y [Cooperativa, 14 jul 2022](https://www.cooperativa.cl/noticias/site/artic/20220714/pags-amp/20220714213947.html).
- Son riesgos de cola por decisiones de política monetaria que el modelo no anticipa. No se excluyen de ningún resultado de esta sección.

**Reservas**
- **Los tramos no son independientes:** una misma posición abierta aparece en varios tramos, porque el percentil cambia de un día a otro mientras la posición se mantiene. Los IC por tramo no deben sumarse ni compararse como muestras separadas.
- **Cota superior:** q = 0,20 se eligió con datos que se solapan con este período. Las cifras sobrestiman lo esperable fuera de muestra.
- **Pendientes del kit:** los resultados no usan el costo de transacción de la base del kit ni su regla de carry (`USAR_CARRY_OFICIAL_KIT` sigue pendiente).
- **Mismo período:** la rotación y el costo de equilibrio salen del mismo período de desarrollo.
- **Tramo fuera de muestra:** sigue sin evaluarse (desde 2024-10-01).
