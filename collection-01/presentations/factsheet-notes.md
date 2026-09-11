# Ideas y documentación para el factsheet de fuego col 1

## Generalidades

El factsheed es una serie de imágenes/infografías que contienen los 
principales hallazgos relacionados a un producto de MapBiomas.

Para el lanzamiento general (Argentina Col3, 24/08/2026) haremos un 
factsheet pequeño, limitado. Luego extenderemos el análisis para 
mostrar más detalles en un segundo lanzamiento propio de fuego, que 
probablemente tenga lugar en Bariloche, en la semana del 7-11/12/2026.

Por ahora trabajamos en la versión reducida, que consiste en 3-4 
imágenes (slides). Estas serán parte de la presentación de fuego (~15 min)
en el lanzamiento general, donde también se hará una breve descripción
de la metodología de mapeo desarrollada.

En este documento se detallan enlaces/datos relevantes, e ideas para 
el factsheet. Puede también servir como hoja de ruta/bitácora, para estar al
tanto de qué se hizo y qué falta.

> **Plan de producción: [`../docs/09-statistics.md`](../docs/09-statistics.md)** (de dónde sale cada
> número: las tablas de área, el toolkit de la red, el denominador quemable) y
> **[`../docs/07-vector_to_raster.md` §1.1](../docs/07-vector_to_raster.md)** (los filtros de
> polígonos que resuelven la sobre-estimación en agricultura y en el pastizal pampeano).
> **El orden de trabajo está en [`../../ROADMAP.md`](../../ROADMAP.md).**
> Este archivo tiene el *contenido* del factsheet: qué gráficos, qué mensaje.

## Enlaces/archivos relevantes

- Carpeta de Drive de Argentina para el factsheet col 3: 
  `https://drive.google.com/drive/folders/1yGf9Kvv-bW8sLDuOOBLC0LoVcDw4pv3o`
- Factsheets de ejemplo: 
  Perú: `https://drive.google.com/file/d/17QOdf0zKoLDrVaCVrePdSPT5LESoZDP9/view?usp=drive_link` 
  Brasil: `https://drive.google.com/file/d/1KDZeqRvEinWQDAfpln6T9FVlHl_S5bgq/view?usp=drive_link`
- PPT de trabajo para nuestro factsheet de fuego:
  `https://docs.google.com/presentation/d/1OEkZipoZGzFkNU6bzdLaOvdyKS2F9tMYXuTQJwuNwEs/edit?usp=sharing`
  Aquí trabajamos como borrador, pero al diseño final lo agarrará un 
  diseñador gráfico.
- Carpeta con fotos de fuego:
  `https://drive.google.com/drive/folders/1J072ZOqP4WWvUISLceLW5EmywnSunV-m?usp=drive_link`. Necesitamos elegir una para la portada; Luna sugiere
  `https://drive.google.com/file/d/1j7XaIncKvfXdtYtkqUDn1IDZEY2Gr344/view?usp=sharing`
- Asset de ecorregiones (Burkart et al. 1999), usaremos el de 13 clases
  porque es lo que se hace en land cover, 
  pero se listan los dos para futuras aplicaciones:
  `projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`, y
  `projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-16Ecorregiones_3857`.
- Repo de Barberá et al. 2025 (para robar código de GAM y gráficos):
  `https://github.com/barberaivan/patagonian_fires.git`
- Asset final de land cover col 3:
  `projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`.
  IMPORTANTE: en el postprocesamiento de fuego exportamos varias cosas basadas 
  en una versión preliminar. Hay que correlas de nuevo. Revisar si eso debe 
  actualizarse manualmente en la plataforma.
- Informe de Ecosistemas Argentinos, una regionalización alternativa:
  `https://asaeargentina.com.ar/docs/recursos/Informe_ecosistemas_argentinos.pdf`


## Generalidades del análisis

En general analizaremos patrones de fuego a nivel nacional y a nivel
de territorios/regiones. Estos territorios son los que probablemente se
mencionan en docs/08- y 09-, que había que definir, ya los tenemos definidos.

En general, planeamos mostrar el mismo resultado a nivel nacional y a nivel
de cada región. La región puede ser una ecorregión (elección por defecto, ver abajo)
o una provincia política, pero para el segundo caso se pedirá explícitamente. 

Decidimos que los principales territorios de interés serán
las ecorregiones de Burkart et al. 1999 
[Burkart, R., Bárbaro, N. O., Sánchez, R. O., & Gómez, D. A. (1999). 
Eco-regiones de la Argentina.].
Tenemos que elegir qué asset usar (13 vs. 16, me inclino por 13).

A continuación se describen los principales análisis. 
El procedimiento que se describe aplica tanto a nivel de todo ARG como
a nivel de cada región. 

Cuando el análisis devuelve un escalar (e.g., % quemado anual medio),
para el nivel nacional sólo se reporta como un número, no con un mapa,
pero a nivel de regiones, sería ideal mostrar el mapa de ARG con las regiones 
pintadas (sólido) con el color variando por este escalar. 

Cuando el análisis devuelve un vector o tabla (e.g., serie temporal de 
% quemada anual), se puede mostrar el gráfico de ARG resaltado, con más 
jerarquía, y los gráficos de algunas regiones (por separado). Idealmente
las slides tienen al menos un mapa, entonces estos subgráficos, como 
serie temporal, tienen una línea que conecta la ecorregión con el gráfico
correspondiente.

Las regiones resaltadas con algún subgráfico no tienen que ser siempre 
las mismas. En un caso podemos resaltar cuál tiene el mayor aumento 
relativo, cuál el mayor aumento absoluto, y en otra slide, resaltar otras
regiones, según qué nos parezca relevante de cada variable. 

Todas las proporciones se expresan en porcentaje, 
aunque las llamemos proporción... es más fácil leerlo.

Las regiones también pueden ser las clases de LULC de MapBiomas.
El concepto aplica igual, pero el análisis es muy distinto, ya que esas 
regiones no se trabajan de forma vectorial sino por pixel. Si hay análisis
que usan la base de datos vectorial de fuego, esto puede traer inconvenientes.
Tiene sentido evitar esos casos (e.g., cantidad de incendios).

## Propuesta de análisis / resultados a presentar

(Para el lanzamiento general, resultados acotados.)

### 1. Proporción quemada anual media: cuánto se quema

La proporción quemada anual media es el cociente área quemada / área quemable
en una región y momento de interés. 
La región será el país/ecorregión, y el momento será año calendario. 
La media se calcula reduciendo los años de la serie.

Esta puede ser la primera imagen. Mapa de ARG con cada región pintada según 
esta métrica, y un globito mostrando cuánto se quema en proporción el total 
de ARG. También reportar los absolutos, e.g.: 4.2 Mha quemadas de 100 Mha quemables. 
El quemable también se calcula por año, según las capas de MapBiomas del año
previo. Este cálculo es costoso a nivel nacional creo, así que vale la pena
revisar si ya está calculado para otras cosas, como validación.
Lo quemable/no quemable se define según nuestro método de mapeo; con la 
reclass de LULC para fuego tenemos esos números. La clase no observado se ignora,
no suma a lo quemable.

Quizás este sea el único resultado que también se analizaría por unidad de LULC.
Acá el área quemable es el área de cada LULC class en cada año. Ojo que esta es 
una reducción a nivel nacional y puede ser pesada.

### 2. Serie temporal de proporción quemada: cómo cambió en el tiempo

La proporción quemada anual en función del año calendario. 
Ajustar un modelo que suavice el patrón en función del tiempo.
Lo más simple es una recta, pero preferiría una GAM de pocas bases.
Esta tendencia se puede resumir en escalar como la pendiente promedio (b):
se evalúa la pendiente en cada año y se promedia sobre años. Si es una 
recta, esta cuenta se omite, ya que la pendiente es ese valor.
Acá sería ideal mostrar una pendiente relativizada o estandarizada por
magnitud. Por ejemplo, b / mean(prop quemada anual), 
o b / sd(prop quemada anual). Si no, al comparar entre regiones, los b
más grandes serán quizás regiones que se queman mucho pero que presentan 
bajo cambio relativo. Pensar qué métrica sería la más clara.

El mapa de ARG debería mostrar las ecorregiones pintadas por b,
y de ahí deberían salir algunos paneles mostrando la serie de algunas ecorreg.

Resaltar el año que tuvo más y menos fuego. En el de más, proponer un equivalente
tangible de tamaño (e.g., equivalente casi a la provincia de bs as).

### 3. Pirograma: en qué meses ocurre el fuego?

La versión completa del pirograma es % quemada y nro de incendios >= 10 ha
(o elegir umbral de tamaño) en función del mes, en un gráfico con doble eje Y. 
Seguir modelo en Barberá et al. 2025, figura 2C [https://link.springer.com/article/10.1186/s42408-025-00353-8].
Si es demasiado, se quita el número de incendios.

La cantidad de incendios debería juzgarse en base a la base de datos vectorial
de fuego, basada en años de fuego, no años calendario. Ahí, es mes corresponde 
al mes de la fecha mediana del polígono. El conteo por región consiste en 
todos los polígonos que intersectan la región, no importa si sólo tocan un extremo.
Esto implica que muchos fuegos serán contados más de una vez, pero no es problema.

La versión escalar de estas variables es el mes de mayor actividad de fuego, 
juzgado por % quemado, pero también podría ser el mes con más eventos. 

Sería ideal ajustar un GAM cíclico para acompañar los puntos. 
En el gráfico, quizás convenga que el eje x corra de mayo a abril, como
nuestro año de fuego, así no se corta nada. 

El número medio de incendios, si se muestra, quizás debería expresarse como
densidad cada 10000 km2, o de alguna manera que deje números agradables,
pero relativizado al área.
Otra es no relativizar porque igual cada región tendrá su gráfico, entonces
los gráficos pueden vivir en escalas diferentes, siempre estirados de cero al 
máximo de la variable. 

En caso de querer poner en un mismo panel distintas regiones, tenemos el problema
de la magnitud. En ese caso, quizás todo debería relativizarse a su máximo
por región, para estar en [0, 1], y así poder comparar las formas más que las 
magnitudes. 

Como las imágenes previas ya muestran magnitud/intensidad, creo que acá
lo más valioso es mostrar la forma intraanual, así que iría por cualquier
estrategia que priorice eso. 

En cuando a proporción quemada mensual, me gustaría mostrar lo siguiente:
por mes, calcular el promedio de proporción quemada a lo largo de los años.
relativizar eso para que sumen 100 %. Así, el eje lee "qué porcentaje de 
lo que se quema en un año, en promedio, se quema en cada mes". 
La misma lógica puede aplicarse a la cantidad de incendios.
En ambos casos, reducir años con suma o promedio da lo mismo.

En caso de mostrar GAMs que sigan los puntos (en vez de líneas), ajustarlo con 
k = 12 para que sigan bien los datos, base cíclica, y siempre ajustarlo
sobre la variable resumida final (Barberá et al. lo ajusta sobre datos 
por año crudos, pero acá queremos que siga bien el promedio, es algo
meramente estético).