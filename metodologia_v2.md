# Desafío USD/CLP · Metodología v2

Actualización del *Resumen técnico* (10 de octubre de 2026). Fecha: 16 de octubre de 2026.
Mismas marcas: **[Decidido]** acordado o implementado; **[Propuesta]** sugerido y por confirmar.
Este documento reemplaza o agrega a las secciones indicadas; lo no mencionado sigue igual.

---

## 1. Lo que confirman las bases (reemplaza parte de §2 y §7.4)

| Aspecto | Antes | Ahora |
|---|---|---|
| Tres referencias | "+1, 0 y −1" (supuesto) | **Comprar siempre (+1), no operar nunca (0) y operar siempre con exposición uno.** Las bases nombran las referencias en el entregable 2. "Comprar siempre" y "exposición uno" podrían ser la misma estrategia o distinguirse por el carry o el rebalanceo; **se confirma con el código de evaluación**. |
| Carry | Proxy propio (FEDL01 rezagada − CHNI1M) | Las bases dicen que la base del kit trae el carry ya calculado y que lo calcula el laboratorio "bajo una regla única". La base que tenemos viene en bruto: **se mantiene el proxy hasta recibir el del kit**. |
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

Script: `04_senal_diaria.py`. Aplica el modelo de §8 con las mismas funciones de `03_modelos_decision.py` y entrega, para la última jornada de la base: dirección (probabilidad calibrada > 0,5 = alza), probabilidad calibrada y cruda, percentil de 63 predicciones y posición. No calcula retornos, así que no evalúa el tramo fuera de muestra.

- **Dirección y posición pueden diferir:** la dirección usa la probabilidad calibrada; la posición, su percentil frente a las últimas 63 predicciones.
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

## 9. Pendientes (actualizado al cierre de la sesión del 16 oct 2026)

**Hecho en la sesión del 16 oct 2026**
- `01_panel.py` en el repo, con prueba de lunes (§3.3): `prueba_lunes_ok` exige que tanto las jornadas como las jornadas con retorno sean lunes en 17–23 %. Da 20,1 % en las tres variantes; si el retorno se calcula sobre el calendario continuo, los lunes con retorno caen a 0 % y la prueba falla. Nota: `01_panel.py` todavía usa el cobre LME (LMCADS03); los scripts 02 a 05 arman su propio panel con HG1, así que no afecta al modelo congelado.
- Etapa C (§5) reproducida con HG1: el script 02 da resultados idénticos a los guardados.
- Señal del día (§8.1, `04_senal_diaria.py`), verificada contra el script 03 y sin look-ahead.
- Prueba de ±3 con señal clara (§8.2, `05_prueba_tres.py`): descartada, se mantiene ±1.

**Decisiones abiertas**
1. **Dirección que reporta la señal del día.** Hoy sale de la probabilidad calibrada (> 0,5 = alza), mientras que la posición sale del percentil, y pueden contradecirse (ejemplo: probabilidad 0,49 con posición +1). Alternativa: reportar como dirección el signo de la posición y "sin señal" cuando es 0.
2. **Alinear `01_panel.py` con HG1**, o declararlo solo como panel de la etapa 1.

**Trabajo siguiente**
- **Lectura de la convicción (entregable 3):** jornadas de máxima exposición y de abstención.
- **Curva de resultado (entregable 2)** frente a comprar siempre, no operar nunca y operar siempre con exposición uno; espera el código de evaluación del kit.
- **Reducir la rotación** sin abrir muchas pruebas nuevas (hoy ~149 veces el nominal al año con M1·DH).
- **Monitoreo en vivo (13 nov–1 dic):** usar `04_senal_diaria.py` con la base actualizada cada día; definir cómo llegan los datos nuevos.

**Depende del kit o de la mentoría**
- Respuestas de la mentoría (§10 del resumen): retorno, carry, costos, período fuera de muestra, datos en vivo, rezagos de publicación.
- **Costo de transacción del kit:** es lo que hoy decide qué estrategia elegir (§7).
- Evaluar **una sola vez** en el tramo fuera de muestra (desde 2024-10-01), después de conocer costo y carry.

**Para retomar el entorno**
- Crear el entorno: `python -m venv .venv` y `.venv\Scripts\pip install -r requirements.txt`.
- Copiar `base_usdclp (2).xlsx` a la raíz (no se publica).
- Las salidas de prueba conviene generarlas fuera del repo, porque los scripts escriben en `resultados/` del directorio actual.
