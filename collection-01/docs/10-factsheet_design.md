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

> **Plan de producción: [`09-statistics.md`](09-statistics.md)** (de dónde sale cada
> número: el área quemada del toolkit, el denominador quemable, el conteo de incendios) y

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
**Resuelto**: el cálculo corre sobre el asset de **16 clases** y el factsheet reporta
las **13**. La agregación 16 → 13 es exacta (medida: cada clase de 16 cae 100 % dentro
de una de 13), así que una sola tabla sirve para las dos — ver `09-statistics.md` §5.2.
**Septiembre es sólo a nivel de ecorregión**: provincia y departamento quedan para el
lanzamiento de diciembre en Bariloche (`09-statistics.md` §1.2).

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

**Todo el factsheet es por AÑO CALENDARIO**, en las tres fuentes: el área quemada
del toolkit, el denominador quemable y el conteo de incendios. El año de fuego
(1 mayo → 30 abril) es cómo está organizado el *mapeo*, no cómo se reporta nada.
En el conteo, cada incendio se archiva en el año y mes calendario de su fecha
mediana (`date_median` o `date_med`), así que un incendio entero cae en un solo año 
y un solo mes.

Las regiones también pueden ser las clases de LULC de MapBiomas.
El concepto aplica igual, pero el análisis es muy distinto, ya que esas 
regiones no se trabajan de forma vectorial sino por pixel. Si hay análisis
que usan la base de datos vectorial de fuego, esto puede traer inconvenientes.
Tiene sentido evitar esos casos (e.g., cantidad de incendios).

### Convenciones para gráficos multi-región

Varios análisis (2, 3 y 4) terminan en un gráfico de líneas donde cada línea
es una región. Conviene fijar de una vez cómo se presentan, así todo el
factsheet se lee como una familia y no como gráficos sueltos.

**Color por región, estable en todo el factsheet.** Cada ecorregión tiene su
color y lo mantiene en todos los gráficos. Si el lector aprende un color en la
slide 2, le sirve en la 4.

**El mapa es la leyenda.** En vez de (o además de) la leyenda de cuadraditos al
costado, va un mapita chico de Argentina con cada polígono relleno del color de
su línea. Se exporta como un plot aparte, para que el diseñador lo ubique donde
quiera. La ventaja sobre la leyenda clásica es que no sólo dice qué color es
cada región, sino *dónde* está: el lector no tiene que saberse las ecorregiones
de memoria.

**Paleta ordenada por latitud**, de tonos cálidos en el norte a fríos en el sur.
Con 13 clases no hay paleta cualitativa que alcance — ninguna da 13 colores
realmente distinguibles entre sí. Pero si el tono codifica latitud, el problema
cambia de naturaleza: el lector infiere "esta línea es del norte" sin ir al
mapa, y el mapa se ve como un degradé coherente en vez de un mosaico arbitrario.
Además la identidad fina la carga el mapa, así que los colores no necesitan ser
máximamente separables; alcanza con que lo sean entre regiones que se comparan.

OJO: en la mayor parte de las slides, el mapa de ARG con ecorregiones dibujadas
tendrá el color asociado a un escalar para cada ecorregión. Ahí no aplica esto 
de "un color fijo por región". En los factsheets se suele sacar una línea desde
el mapa para indicar que un plot pertenece a una región.

**Área quemable** no varía entre años, se toma como una constante por píxel.
Es sensato y ya fue pensado, no discutirlo.

**Dos variantes de cada gráfico:**

- `all_regions`: todas las líneas coloreadas en un solo panel. Sirve para ver el
  conjunto y detectar quién se sale de la norma.
- *focal*, una por región: las demás regiones en gris claro de fondo, y la focal
  en su color y con trazo grueso. Acompañada de su mapa, también en gris claro,
  con sólo el polígono focal relleno. Así se resalta una región sin perder la
  distribución de las otras como referencia visual — se ve si la focal es rara o
  si hace lo mismo que todas.

La variante focal es la que probablemente use el factsheet (una región por
slide, o una destacada por gráfico), y la `all_regions` sirve para el análisis
interno y para decidir a quién destacar.

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
**El quemable es una constante por región, no un número por año**.
Se toma el modo 1998–2024 de quemable/no quemable por píxel
y se suma por ecorregión. Son 13 números, calculados una vez. 

Consecuencia para el epígrafe: el `%` se lee como "del área que es quemable la mayor
parte del tiempo", así que la serie temporal es señal de **fuego**, no de cambio de uso
del suelo. Decirlo así. 

Lo quemable/no quemable **se define sobre la leyenda de col 3**, no sobre nuestra
reclass de fuego: la lista de clases está en `09-statistics.md` (agua, urbano,
suelo desnudo, hielo y "otras áreas no vegetadas" son no quemables). La clase
**no observado se ignora**: no suma ni al numerador ni al denominador.

### 2. Serie temporal de proporción quemada: cómo cambió en el tiempo

La proporción quemada anual en función del año calendario. 
Ajustar un modelo que suavice el patrón en función del tiempo.
Lo más simple es una recta, pero preferiría una GAM de pocas bases 
(k = 5 en mgcv, modelo normal).
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

**Variante normalizada por región.** El gráfico de arriba, con todas las regiones
juntas, tiene el problema de siempre: el Chaco aplasta a la Patagonia y no se ve
la forma de las series chicas. Para comparar *formas* interanuales —qué años
fueron pico en cada región, si los picos coinciden entre regiones— conviene
dividir la serie de cada región por su propia media. El eje Y pasa a leer "veces
el año típico de esa región": 1 es un año normal, 4 es un año que quemó cuatro
veces lo habitual.

Elegimos "veces la media" y no "% del total quemado en la serie" (que es la
normalización del análisis 4) porque acá hay 28 años: si sumaran 100 %, cada año
promediaría ~3,6 %, un número que no le dice nada a nadie. En cambio "2020 quemó
4 veces lo típico" se entiende sin explicación. En el eje mensual, con 12 bins y
un pico estacional claro, el % sí funciona bien; por eso las dos normalizaciones
son distintas a propósito.

Este gráfico usa las convenciones multi-región de más arriba (color por región,
mapa-leyenda, variantes `all_regions` y focal).

### 3. Pirograma: en qué meses ocurre el fuego?

La versión completa del pirograma es % quemada y nro de incendios >= 10 ha
(o elegir umbral de tamaño) en función del mes, en un gráfico con doble eje Y. 
Seguir modelo en Barberá et al. 2025, figura 2C [https://link.springer.com/article/10.1186/s42408-025-00353-8].
Si es demasiado, se quita el número de incendios.

La cantidad de incendios se juzga sobre la base de datos vectorial de fuego. El
**año y el mes son los calendario de la fecha mediana del polígono**
(`date_median`): la base está *guardada* por año de fuego, pero se reporta por año
calendario como todo lo demás. Un incendio que cruza el 31 de diciembre cae entero
en uno de los dos años acá, y se parte en el área de los rásters.

**Cada incendio puede contar más de una vez**, porque cruza regiones. 
El incendio corresponde a todas las regiones que intersecta.

La versión escalar de estas variables es el mes de mayor actividad de fuego, 
juzgado por % quemado, pero también podría ser el mes con más eventos. 

Sería ideal ajustar un GAM cíclico para acompañar los puntos. 
En el gráfico, quizás convenga que el eje x corra de mayo a abril, como
nuestro año de fuego, así no se corta la temporada por el medio. Es una
convención de *display* del eje de meses: los datos siguen siendo por año
calendario. 

El número medio de incendios, si se muestra, quizás debería expresarse como
densidad cada 10000 km2, o de alguna manera que deje números agradables,
pero relativizado al área.
Otra es no relativizar porque igual cada región tendrá su gráfico, entonces
los gráficos pueden vivir en escalas diferentes, siempre estirados de cero al 
máximo de la variable. 

Poner varias regiones en un mismo panel trae el problema de la magnitud, y ese
caso se trata aparte, en el análisis 4: ahí está definida la normalización que
usamos para comparar formas intraanuales entre regiones. Este análisis 3 se
queda con lo que sólo él hace — el pirograma por región, con doble eje Y y el
conteo de incendios. Como las imágenes previas ya muestran magnitud e
intensidad, lo valioso acá es la forma intraanual, y de eso se ocupa el 4.

En caso de mostrar GAMs que sigan los puntos (en vez de líneas), ajustarlo con 
k = 12 para que sigan bien los datos, base cíclica, y siempre ajustarlo
sobre la variable resumida final (Barberá et al. lo ajusta sobre datos 
por año crudos, pero acá queremos que siga bien el promedio, es algo
meramente estético).

### 4. Distribución intraanual comparada: cuándo se quema cada región

Mismo formato que el análisis 2 (líneas multi-región), pero el eje X es el año
calendario en vez de la serie de años: muestra *cuándo*, dentro del año, se
quema cada región.

El problema que resuelve: la Patagonia se quema poco y el Chaco mucho. Si las
dos son líneas en un mismo panel con un eje Y de % quemado, la Patagonia es una
línea plana planchada contra el cero y no se ve nada de su estacionalidad. Para
comparar la distribución temporal hay que sacarle la magnitud a cada región.

**Cómo se normaliza.** Por región y por mes, se suma el área quemada de toda la
serie, y después se divide por el total de esa región, de modo que los 12 meses
sumen 100 %. El eje Y lee "qué porcentaje de lo que se quema en esta región
ocurre en cada mes". Ojo que es % de *lo que se quema*, no % del área total de
la región ni % de lo quemable — son cosas distintas y conviene decirlo en el
epígrafe.

Como la normalización es por región, da igual trabajar en hectáreas o en
proporción quemada: el cociente final es el mismo. Entonces trabajamos con
área, que es lo que ya tenemos.

**Por qué % y no una densidad.** Un % es interpretable de entrada, mientras que
una unidad de densidad genérica ("fuego por unidad de tiempo") no le dice nada a
nadie. El costo es que el % depende de la resolución del eje X: si en vez de
meses usáramos quincenas, todos los números se parten al medio. Por eso el
binning mensual no es un detalle de implementación sino parte de la definición
del gráfico, y va dicho en el epígrafe.

**Eje X de mayo a abril**, el orden del año de fuego (ver `utils/constants.py`:
el FY va del 1 de mayo al 30 de abril siguiente, y se nombra por el año de
inicio). Es sólo el **orden del eje de meses** — los datos se agregan por año
calendario, como todo el factsheet — y evita cortar la temporada de fuego por el
medio.

La misma lógica aplica a la cantidad de incendios: qué % de los incendios de una
región ocurre en cada mes. Sumar o promediar los años da lo mismo, porque la
normalización lo cancela.

Valen las convenciones multi-región de más arriba: color por región, mapa como
leyenda, y las variantes `all_regions` y focal. La focal es especialmente útil
acá — permite decir "el Chaco quema en invierno tardío, a contramano del resto"
mostrando el resto en gris de fondo.

### 5. Composición de lo quemado: qué se quema en cada región

De todo lo que se quemó en una ecorregión, qué porcentaje era bosque, qué porcentaje
vegetación natural herbácea y arbustiva, qué porcentaje campo agrícola. Permite decir
"en Yungas dos tercios de lo quemado es bosque; en la Estepa Patagónica, el 1 %".

**No hace falta ningún cálculo nuevo**: el producto `annual_burned_coverage` del toolkit ya
es área quemada × cobertura × ecorregión × año, y nuestra copia de la app ya cruza la
cobertura del **año anterior** al fuego — que es justamente la capa correcta acá: lo que
había para quemarse, no en qué quedó clasificado el píxel después de quemarse.
Ver `09-statistics.md` §5.2.

**OJO, y va en el epígrafe: esto NO es "qué porcentaje del bosque se quemó".** Son dos
preguntas con el mismo par de palabras y distinto denominador. Acá el denominador es el área
quemada de la región, que la tenemos. El de la otra pregunta sería el área de cada clase en la
región, que el quemable constante no tiene — necesitaría un export más, y hay que decidirlo
antes de prometer ese panel, no después (`09-statistics.md` §3.3).

El gráfico es una barra apilada horizontal por ecorregión, ordenadas por proporción de
bosque, con Argentina arriba como referencia, y los colores del lenguaje visual de MapBiomas
(verde bosque, tostado herbácea y arbustiva, ámbar agropecuario). Acá **no** aplica el color
por región: el color codifica la clase de cobertura, no el territorio. La variante de slide es
el mapa pintado por un solo escalar — el % de lo quemado que era bosque.

### 6. Qué porcentaje de cada cobertura se quema

La otra mitad de la pregunta del análisis 5, y conviene tenerlas juntas porque se confunden
con facilidad. El 5 dice **qué se quemó** (de lo quemado en el Chaco, el 43 % era bosque);
el 6 dice **qué proporción de cada clase se quemó** (del bosque del Chaco, tanto por ciento
por año). Denominadores distintos, números distintos, y en el epígrafe hay que decir cuál es.

El caso que lo deja claro (medido): **Bosques Patagónicos es 55 % bosque de lo que se quema**
y quema **0,16 % de su bosque por año**. Casi todo lo que se quema ahí es bosque porque casi
todo lo que hay ahí *es* bosque, no porque su bosque se queme mucho. Campos y Malezales es el
espejo: sólo 0,3 % de lo quemado es bosque, y sin embargo tiene la tasa herbácea más alta del
país (5,15 % por año). Citar uno de estos números sin decir cuál es le da al lector lo
contrario de lo que pasa.

**Esto sí necesitó un cálculo nuevo**, el único de este bloque: el área de cada clase de
cobertura por ecorregión y por año (`statistics/lulc_area_export.py`). El toolkit no lo puede
dar, porque todos sus productos están enmascarados al fuego: sabe cuánto bosque se quemó y no
cuánto bosque había.

Dos cosas definen el número y las dos van dichas (`09-statistics.md` §5.3):

- **El desfasaje de un año**: el numerador cruza el fuego del año Y con la cobertura de Y−1,
  así que el denominador tiene que ser el área de la clase en Y−1.
- **El promedio se toma al final**: se calcula el `%` año por año y después se promedia, nunca
  `suma(quemado)/suma(área)`. Un cociente de sumas no es el promedio de los cocientes, y sumar
  27 años de área quemada vuelve a contar cada requema.

El gráfico es un *heatmap* ecorregión × clase (nivel 1) con el valor escrito en cada celda —
una matriz se lee mejor así que como doce gráficos de barras — y la variante de slide es el
mapa de un solo escalar: qué porcentaje del bosque se quema por año.

Los números de referencia, promedio anual 1999–2025: a nivel país se quema **1,38 % del
bosque**, 0,94 % de la vegetación herbácea y arbustiva y 0,43 % del área agropecuaria. Los
máximos por clase son Espinal (2,96 % del bosque), Campos y Malezales (5,15 % de la herbácea)
y Campos y Malezales otra vez (2,37 % de lo agropecuario). Tabla completa en
`data/statistics/factsheet_lulc_pct_mean.csv`.
