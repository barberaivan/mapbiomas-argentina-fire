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

---

## ⚠️ Qué entra al lanzamiento de septiembre, y qué es exploratorio

**Hay tres cuadernos `factsheet_*` y NO tienen el mismo estatus.** Confundirlos es el error
caro de este momento del proyecto: son 306 figuras y sólo un puñado se publica el 24 de
septiembre.

| Cuaderno | Estatus | Para qué |
|---|---|---|
| **`factsheet.qmd`** | **EL ÚNICO QUE ALIMENTA LA VERSIÓN DE SEPTIEMBRE** | Análisis 1–5. De acá salen las 3–4 láminas del lanzamiento general |
| `factsheet_veg.qmd` | **Exploratorio** | Análisis 6 entero: control, `q`, 12 ecorregiones, dos ventanas, el caso patagónico |
| `factsheet_veg_short.qmd` | **Exploratorio** | El análisis 6 recortado + el bloque de bosques; el ensayo de cómo se diría en una lámina |

**Exploratorio no quiere decir descartado — quiere decir que no se publica en septiembre.**
Los dos cuadernos de vegetación son material de trabajo para:

1. **el lanzamiento propio de fuego (Bariloche, 7-11/12/2026)**, donde el factsheet se
   extiende y el análisis 6 es candidato natural a lámina propia; y
2. **el paper**, donde el control, `q`, la trayectoria por ventana y el corte por clase de
   bosque son el material que sostiene un resultado publicable.

Por eso **no se borra nada y se sigue documentando con el mismo cuidado**, aunque no vaya a
imprenta ahora.

**Lo que falta, y es lo próximo**: un cuaderno que **especifique lámina por lámina** la
versión de septiembre — qué figura va en cada una, con qué epígrafe, qué número se dice y de
qué archivo sale. Hoy la selección vive en la cabeza y en este documento en prosa; ahí va a
vivir explícita, y es lo que se le entrega al diseñador gráfico. Mientras no exista, **la
fuente de verdad de qué se publica es esta tabla más las decisiones del `ROADMAP.md`**.

---

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

**Va al principio, y una vez con los nombres escritos.** Si el mapa es la
leyenda, tiene que aparecer *antes* del primer resultado que lo use —en el
factsheet y en el cuaderno—, con una línea que diga que ése es el corte
territorial de todo lo que sigue y la cita de Burkart et al. (1999). Hay dos
variantes: `map_legend()`, el mapa solo, que es lo que acompaña a un gráfico
multi-región (los nombres sobran: la identidad la carga la posición), y
`map_legend(labels = TRUE)`, **el mapa con la leyenda en texto al lado** en orden
norte → sur. La segunda se usa una sola vez, la primera vez que el mapa aparece,
para que el lector que no se sabe las ecorregiones las aprenda ahí; después ya no
hace falta repetir los nombres.

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

### 0. La apertura: las ecorregiones y dónde se quema

La primera lámina son dos mapas del mismo país. A la izquierda el **mapa-leyenda con los
nombres escritos** (el único lugar donde se escriben: de ahí en adelante el color ya
significa algo). A la derecha, **el % de los años en que se quemó cada píxel**, con las
ecorregiones dibujadas encima en blanco.

Es a propósito el **mismo número del análisis 1**, píxel a píxel en vez de por ecorregión:
el promedio del mapa de la derecha es la proporción quemada media anual del país. La
lámina, entonces, enseña a leer el resto del factsheet — dónde está cada región, y que
"proporción quemada media anual" es una cosa que se ve en un mapa.

**No es el conteo de años del subproducto de frecuencia**, que depende del largo de la
serie y significará otra cosa en la colección 2: es ese conteo dividido por los 27 años.
De dónde sale el ráster, a qué escala y por qué se agrega promediando y no con el máximo:
`09-statistics.md` §5.5.

**La versión de tres paneles** (`fig00_tres_mapas`) agrega en el medio el mapa del análisis 1
—la proporción quemada anual media, pintada por ecorregión— y va de lo general a lo fino:
quién es quién, cuánto se quema cada región, dónde se quema cada píxel. Los dos porcentajes
tienen denominadores distintos y conviene decirlo en el epígrafe, porque la relación entre
ellos es exacta y es lo que hace honesta a la lámina: **el promedio del mapa de píxeles sobre
una región es el valor que pinta el mapa del medio**.

#### Las Islas Malvinas van en TODOS los mapas, sin pintar

**Todo mapa de la Argentina de este factsheet dibuja las Islas Malvinas**, y las dibuja
**sin pintar**: contorno y nada más, en los coropletas, en los mapas de píxel y en el
mapa-leyenda de las ecorregiones.

Que estén vacías no es una omisión: es lo que dicen los datos. La ecorregión 13 (Islas del
Atlántico Sur) está **fuera de la grilla de procesamiento** —ninguna de las 248 cartas la
toca—, así que no hay mapeo de fuego ahí. Su "0 % quemado" sería un agujero del mapeo
presentado como un hecho sobre el fuego, y por eso no entra en ninguna tabla ni en el
denominador nacional (`09-statistics.md` §3.2). Dibujarlas vacías dice las dos cosas a la
vez: **el territorio está, el dato no**.

Si un epígrafe habla de cobertura nacional, esa es la frase: *las Malvinas se muestran como
territorio; la colección 1 no las mapea*.

Tres detalles de implementación, en `factsheet_style.R`:

- **`ECO_SF` sigue siendo las 12 reportadas** —es la geometría de los DATOS, a la que se unen
  los escalares y con la que se recortan los rásters— y las islas son una capa aparte
  (`MALVINAS_SF`, `geom_malvinas()`) que se suma a cada mapa.
- **La capa va dentro del `ggplot`, nunca después de `coord_sf`**: al ser una capa más, es lo
  que extiende el lienzo hacia el sudeste. Agregarla afuera dibuja el mapa con el encuadre
  continental y recorta las islas — el modo de fallar que no se nota, porque el resto del
  mapa sigue bien.
- **El trazo va más fino que el del continente** (0,1 contra 0,18–0,25). El archipiélago son
  451 partes en ~250 km: al grosor del continente los islotes se tocan y el conjunto se
  imprime como una mancha gris. A 0,1 se lee la silueta de Soledad y Gran Malvina. No se
  descarta ningún islote — el problema es el trazo, no la geometría.

Verificado sobre la capa (17 sep 2026): la ecorregión 13 de este asset es **sólo las
Malvinas** (bbox −61,46/−52,95 a −57,72/−51,00). No trae Georgias ni Sandwich del Sur, que a
−36° de longitud habrían estirado el lienzo de todos los mapas por un archipiélago que no se
vería.

#### 0.1 El cero es blanco, y es una clase aparte (vale para los tres rásters)

Convención de todos los mapas de píxel del factsheet, decidida el 17/9/2026: **"no se quemó
nunca" va en blanco y no es el primer tono de la rampa**. Son dos lecturas distintas —"acá no
hubo fuego" y "acá hubo poco fuego"— y una rampa continua las pega en el mismo crema. No es un
detalle de gusto: el 60 % de las celdas dibujadas son ese cero, así que la decisión *es* el
mapa. La rampa empieza en el primer valor mayor que cero, con un tono claramente distinto del
blanco.

Hay una tercera cosa, que tampoco es 0: las celdas **sin nada quemable** (lagos, salares,
glaciares) quedan fuera de la máscara y no se dibujan. "No es quemable", "es quemable y nunca
se quemó" y "se quemó" son tres estados y el mapa los muestra como tres.

Las paletas son **viridis**, y son dos porque son dos variables:

| mapa | paleta | sentido |
|---|---|---|
| frecuencia / veces | **magma** invertida, recortada en `end = 0,84` | más fuego = más oscuro; lo quemado termina en negro, que es lo que es. El recorte evita que la primera clase se confunda con el blanco del cero |
| año del último fuego | **viridis C (plasma)** invertida, `begin = 0,05`, `end = 0,92` | más reciente = más oscuro. Distinta a propósito: compartir paleta haría leer dos variables como una |

Sobre papel blanco lo oscuro es lo que salta, y en los dos casos lo que tiene que saltar es el
valor alto. Invertir cualquiera de las dos es un argumento (`direction`) en
`factsheet_style.R`.

#### 0.2 El mismo mapa en veces, y la versión de conteos enteros

"El 3 % de los años" no se lee solo. **El mismo dato × 27/100** es "cuántas veces ardió el
píxel promedio de la celda", con los mismos cortes y los mismos tonos: lo único que cambia es
la leyenda, así que las dos figuras no pueden contradecirse. Va la que se prefiera.

El número es **fraccionario**, porque la celda de 480 m promedia sus 256 píxeles: 0,54 veces
es "un píxel típico de esa celda ardió una vez cada dos series". Por eso esa escala **no
empieza en 1**.

La versión que sí empieza en 1 necesita el **máximo** de la celda ("en algún lugar de estos
480 m hubo un píxel que ardió N veces"), que es un segundo archivo y **otra cuenta**:
exagera a propósito — el peor píxel pinta sus 23 hectáreas. Está escrita y exportada
(`09-statistics.md` §5.5.1) como alternativa; **la lámina de apertura usa la del promedio**.

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

#### 2.1 El mapa del año del último fuego — la figura de la sección

La figura principal del análisis 2 no es un escalar de tendencia pintado por ecorregión: es
**el año del último fuego, píxel a píxel**. Dónde ardió hace poco y dónde hace veinte años.

Es el complemento exacto de la lámina de apertura. Aquél dice **cuánto** ardió cada lugar en
27 años; éste dice **cuándo fue la última vez**. Juntos son las dos preguntas que un lector le
hace a un mapa de fuego, y salen del mismo conjunto de productos (`09-statistics.md` §5.6).

Tres cosas para el epígrafe, y las tres son la figura:

- **Blanco es "no ardió nunca"** en los 27 años, no una clase baja de la rampa (§0.1). Es el
  60 % del país.
- **La clase es un período, no un año.** La celda de 480 m promedia el año de los píxeles que
  ardieron, así que el valor es fraccionario: una celda "2009 – 2013" puede ser una que ardió
  entera en 2011 o una que ardió mitad en 2004 y mitad en 2017. Se eligió el promedio y no el
  máximo porque el máximo satura — en el Chaco casi toda celda tiene algún píxel quemado en
  los últimos dos años y el mapa queda plano (§5.6 de `09-statistics.md` tiene la tabla de las
  tres opciones).
- **Lo oscuro es lo reciente**, en plasma (§0.1).

Una decisión más, que se puede revertir con un argumento: **no se esconde nada**. Una celda
donde ardió el 0,4 % de la superficie lleva su año igual que una que ardió entera, y eso
ensancha visualmente la huella. Se deja así porque acá el color codifica una **fecha**, no una
magnitud: esa celda no miente sobre *cuánto* ardió — de eso habla el mapa de al lado — sólo
dice *cuándo*. `map_last_fire(min_denom = ...)` sube el umbral si alguna vez se prefiere lo
contrario.

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

**El equivalente tangible se pide tres veces, y una de ellas es el total de la serie.**
La sección 0 del cuaderno (`notebooks/factsheet.qmd`) tiene la tabla de candidatas con las
tres cuentas hechas —año medio, peor año y **total acumulado**— contra diez superficies de
referencia (las provincias grandes están ahí sólo por el total, que es un orden de magnitud
mayor que un año). El total es la **suma de los 27 años**, así que cada hectárea está contada
tantas veces como se quemó: son 63,23 Mha, el 25,2 % del área quemable y el equivalente a
2,06 provincias de Buenos Aires. **No es la huella quemada** —cuánto del país se quemó
*alguna vez*—, que es menor y sale del producto `accumulated_burned_coverage`, no de estas
tablas. El epígrafe tiene que decir "el equivalente a", nunca "se quemó el 23 % del país".

**Variante normalizada por región.** El gráfico de arriba, con todas las regiones
juntas, tiene el problema de siempre: el Chaco aplasta a la Patagonia y no se ve
la forma de las series chicas. Para comparar *formas* interanuales —qué años
fueron pico en cada región, si los picos coinciden entre regiones— conviene
dividir la serie de cada región por su propia media. El eje Y pasa a leer "veces
el año típico de esa región": 1 es un año normal, 4 es un año que quemó cuatro
veces lo habitual.

Elegimos "veces la media" y no "% del total quemado en la serie" (que es la
normalización del análisis 3.3) porque acá hay 28 años: si sumaran 100 %, cada año
promediaría ~3,6 %, un número que no le dice nada a nadie. En cambio "2020 quemó
4 veces lo típico" se entiende sin explicación. En el eje mensual, con 12 bins y
un pico estacional claro, el % sí funciona bien; por eso las dos normalizaciones
son distintas a propósito.

**Pero la normalización no es gratis, así que el multipanel va también sin
normalizar.** "Veces el año típico" saca la magnitud a propósito, y con eso se
pierde justamente lo que el lector quiere saber de una región: cuánto se quema.
Cuando las series por región se muestran como *multipanel* —un panel por
ecorregión— la normalización deja de ser necesaria, porque cada panel tiene su
propia escala Y y ninguna región aplasta a otra. Entonces se dibujan las dos: la
grilla normalizada (comparar formas) y la grilla en **% quemado anual**, con el
**mismo GAM k = 5 ajustado a esa variable** —el de `factsheet_trend_fits.csv`, el
mismo que pinta el mapa de tendencia y la serie nacional— y su banda. El epígrafe
de la segunda tiene que decir que los paneles no son comparables en altura entre
sí, que es el precio de que cada uno se lea bien.

Este gráfico usa las convenciones multi-región de más arriba (color por región,
mapa-leyenda, variantes `all_regions` y focal).

### 3. Patrón intraanual: cuándo se quema

Cuatro gráficos sobre el mismo eje de 12 meses y, por eso, un solo análisis: **el mes pico
en el mapa** (3.1), el **pirograma** en unidades absolutas (3.2), el **reparto mensual
comparado entre regiones** (3.3) y el **pirograma normalizado**, que junta las dos repartijas
en un panel y devuelve la magnitud como texto (3.4). Todos dibujan el eje de mayo a abril.

#### 3.1 El mes pico, en el mapa

El máximo del reparto mensual (3.3) pintado sobre las ecorregiones: en qué mes se quema la
mayor parte del área de cada una. Es el resumen de la sección en una imagen, y la que abre
la slide.

**La paleta tiene que ser cíclica.** Un mes no es una magnitud: diciembre y enero son
vecinos, y una rampa secuencial los manda a las dos puntas opuestas, inventando una
distancia que no existe. Se usa la rueda de tonos completa, 30° por mes, a luminancia y
croma constantes, anclada de modo que **enero caiga en rojo y julio en cian** — con lo cual,
en el hemisferio sur, el color se lee solo: cálido es pico de verano, frío de invierno.

La leyenda nombra los meses en **tres letras, nunca en número** (un número obliga a traducir
mentalmente, que es justo lo que un mapa no debe pedir) y se ordena de mayo a abril, como el
eje de todo el análisis. Al lado va la tabla con el mismo dato y, además, el pico por
**cantidad de incendios**, que no siempre cae en el mismo mes: el área la manda el incendio
grande y el conteo, el chico.

#### 3.2 Pirograma: en qué meses ocurre el fuego?

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
caso se trata aparte, en el 3.3: ahí está definida la normalización que
usamos para comparar formas intraanuales entre regiones. Este 3.2 se
queda con lo que sólo él hace — el pirograma por región, con doble eje Y y el
conteo de incendios. Como las imágenes previas ya muestran magnitud e
intensidad, lo valioso acá es la forma intraanual, y de eso se ocupa el 3.3.

En caso de mostrar GAMs que sigan los puntos (en vez de líneas), ajustarlo con 
k = 12 para que sigan bien los datos, base cíclica, y siempre ajustarlo
sobre la variable resumida final (Barberá et al. lo ajusta sobre datos 
por año crudos, pero acá queremos que siga bien el promedio, es algo
meramente estético).

#### 3.3 Distribución intraanual comparada: cuándo se quema cada región

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

#### 3.4 Pirograma normalizado: las dos repartijas juntas, y los totales en el panel

El 3.2 y el 3.3 dicen lo mismo en dos unidades y obligan a mirar dos figuras. El 3.4 es el
pirograma **en las unidades del 3.3**: las barras son el % del área quemada de toda la serie
que ocurrió en cada mes, la línea es el % de los incendios ≥ 10 ha, y **cada serie suma
100 %**.

**Lo que gana: un solo eje.** Con las dos series en la misma unidad desaparecen el segundo eje
y el factor de escala que lo define — que es arbitrario y hace que "la línea está por encima
de la barra" no signifique nada en el 3.2. Acá sí significa: un mes donde la línea supera a
la barra concentra **más incendios que área**, o sea muchos fuegos chicos; al revés, pocos y
grandes. Es la lectura que el doble eje no permite.

**Lo que pierde, y cómo se devuelve.** Normalizar borra la magnitud, así que cada panel la
lleva escrita: el **área quemada total** de la serie (suma de los años, con recurrencias) y la
**cantidad de incendios** (total y ≥ 10 ha, que es la que dibuja la línea). Son de fuentes
distintas a propósito —el área sale de los rásters, los incendios de los polígonos— y un
incendio se cuenta en cada ecorregión que toca, así que los totales regionales suman más que
el nacional. La etiqueta se ubica sola en la mitad floja del año, para no taparle el pico a
ninguna región.

Se dibuja para el país y para las 12 ecorregiones, con las mismas convenciones de color.

### 4. Composición de lo quemado: qué se quema en cada región

> **Sólo clases quemables.** Agua, glaciar, ciudad y suelo desnudo no arden: el área quemada
> que cae ahí es error de mapeo (0,09 % de lo quemado en el país, 1,6 % en el peor caso) y
> queda afuera de este análisis y del 5. Con eso la composición **suma 100 % sobre lo que
> puede arder**, que es lo que un lector entiende cuando lee "el 30 % de lo quemado era
> bosque". El corte va por familia de nivel 1 y es exacto (`09-statistics.md` §5.2.1).

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

**Qué leyenda, y en qué nivel: se dice explícitamente, y las nativas van primero.** Esto lo
va a leer gente que conoce la leyenda de cobertura de memoria, así que no alcanza con mostrar
las familias. La cobertura es siempre la **integración nacional de la colección 3**
(`LAND-COVER/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`), **nunca** las
clasificaciones por región de MapBiomas —donde el mismo nombre puede querer decir cosas
distintas según la región—, y la leyenda es la de la red (`00_Tools/Legends.js`,
`lulc_argentina_nivel{0,1,2}`), con sus tres niveles anidados. Los análisis 4 y 5 se dibujan
**dos veces**: primero por **clase nativa (nivel 2)**, que son pocas —17 con fuego— y son las
que el lector reconoce, y después por **familia (nivel 1)**, que es la versión de slide. La
agregación nivel 2 → nivel 1 → nivel 0 **es de la leyenda, no nuestra**, y el cuaderno imprime
la tabla completa (código col-3 → los tres niveles) para que se pueda auditar de un vistazo.
Cada figura dice en el subtítulo qué nivel está mostrando. Los colores de nivel 2 sí son
nuestros —la leyenda de la red trae nombres y no paleta—: cada familia conserva su color de
nivel 1 y sus clases son tonos de ése, así que la barra detallada se sigue leyendo como las
mismas cinco familias.

### 5. Qué porcentaje de cada cobertura se quema

La otra mitad de la pregunta del análisis 4, y conviene tenerlas juntas porque se confunden
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

### 6. Cómo cambia la cobertura alrededor del fuego

El último análisis, y el único que mira **dos** mapas de cobertura por cada hectárea quemada:
el del año **anterior** al fuego y el del año **siguiente**. De dónde salen los números:
`09-statistics.md` §5.7. **Las figuras las dibuja `notebooks/factsheet_veg.qmd`**, no
`factsheet.qmd`: el análisis 6 se mudó a un cuaderno propio para poder iterarlo en segundos
en vez de en minutos. Escribe con el mismo prefijo `fig06_`, así que para el diseñador no
cambia nada.

⚠️ **La ventana no es neutral.** Y+1 es la de Ferro et al., calibrada en el Chaco, donde el
fuego DESPEJA. Donde el fuego **mata pero no despeja** —los bosques andino-patagónicos— un
año no alcanza: el bosque quemado que deja de ser bosque pasa de 49 % en Y+1 a 78 % en Y+5,
y la arbustalización llega al mapa unos tres años tarde (`09-statistics.md` §5.7.3). Para
vegetación natural leñosa, **Y+3 como mínimo**; para cualquier afirmación sobre bosque,
**Y+4–5**.

**El diseño es el de Ferro et al. (2026)** —el trabajo del grupo sobre el Chaco Seco— rehecho
a 30 m y para todo el país. De ahí vienen la ventana Y−1 → Y+1, la regla de exclusión y el
cociente q.

#### 6.1 La figura es el CONTROL, no el porcentaje

La tentación es la barra de "el 15 % de lo quemado cambió de cobertura". **Sola, esa barra no
se puede leer**: el país cambia un 3,9 % sin fuego alguno. El análisis existe por el
cociente

> **q = P(cambió | ardió) / P(cambió | no ardió)**

y la figura que va a la slide es la que muestra **los dos números juntos**: un punto gris (lo
que cambia sin fuego) y uno rojo (lo que cambia con fuego) por ecorregión, unidos por un
segmento. El segmento ES el efecto del fuego; el punto gris dice cuánto habría pasado igual.

Por qué importa, con los números medidos:

- **Pampa tiene el porcentaje más alto del país (33,9 %) y cae al tercer puesto por q**,
  porque es además donde más cambia todo lo demás (6,9 % sin fuego).
- **Campos y Malezales (q = 0,7) y Altos Andes (q = 0,8) quedan por debajo de 1**: ahí lo
  quemado cambia MENOS que lo no quemado. Con el porcentaje solo, la lectura era "casi no
  cambia"; con el control, es "menos que nada" — el fuego no es una vía de conversión en esas
  regiones.
- **Bosques Patagónicos pasa a primero (q = 7,3)** con un porcentaje del medio de la tabla.

q va en **escala logarítmica** siempre: es un cociente, y 0,5 y 2 tienen que estar a la misma
distancia de 1. En lineal, todo el lado "el fuego limita el cambio" se aplasta contra el eje.

#### 6.2 La prueba de la cicatriz (Y+3)

La objeción de fondo: la colección de cobertura se construye con las mismas imágenes que ven
la quemadura, así que un bosque quemado puede clasificarse como herbáceas en Y+1 sin que el
bosque haya desaparecido. Si eso dominara, a tres años la tasa de lo quemado caería hacia el
control. **No pasa**: sube de 14,5 % a 17,6 % mientras el control sube de 3,9 % a 5,8 %, y q
se mantiene en ~3. Las transiciones son persistentes.

Esto no va a una slide del factsheet; va al epígrafe, en una línea, porque es la respuesta a
la primera pregunta que hace cualquiera que conozca los datos.

#### 6.3 Las otras tres vistas

- **q por transición** (matriz antes × después, color log(q)): donde el promedio deja de
  servir. Nacional, nivel 1: bosque → agropecuario **q = 10,9**, bosque que sigue siendo
  bosque **q = 0,7**. Ahí está todo el análisis en dos números.
- **De lo que NO cambió, qué es**: barra apilada que suma 100 %, con la paleta del análisis 4.
- **De lo que SÍ cambió, de qué a qué**: el **Sankey** (aluvial), ancho = área sumada de la
  serie. Se dibujan las transiciones que llegan al 1 % de lo que cambió y el subtítulo dice
  qué porcentaje quedó dibujado; no se las junta en una categoría "otras", porque una clase
  inventada en el eje de una leyenda anidada es peor que una ausencia.

  ⚠️ **De un Sankey con umbral NO se lee el área de llegada de una clase.** El umbral se aplica
  **por transición**, así que un destino alimentado por muchos flujos chicos se dibuja mucho más
  flaco de lo que es, y uno alimentado por un flujo grande se dibuja entero. Medido, nacional,
  Y+1: a bosque llegan **0,891 Mha desde fuera de la familia**, y ese número es **idéntico en los
  dos niveles** —es la misma hectárea con dos leyendas—, pero en nivel 1 viene en **2 bandas**
  (se dibuja el 100 %) y en nivel 2 se reparte entre **37** (con umbral 1,5 % sobrevive **una**,
  el 24 %). De ahí la impresión, falsa, de que en nivel 2 llega menos bosque que en nivel 1. Dos
  consecuencias: **el nivel 2 pide umbrales bajos** (0,5 % en la versión corta, que sube la
  cobertura de 72 a 87 % y hace aparecer las tres clases de bosque), y **el subtítulo tiene que
  imprimir la cobertura siempre**. Para área de llegada, el análisis 4.

#### 6.4 Lo que hay que decir en el epígrafe

> **Con fuego la cobertura cambia 3,7 veces más que sin fuego, y 10,9 veces más para bosque →
> agropecuario.** Pero es observacional: los píxeles que arden no son una muestra al azar del
> país. Parte de q puede ser que el fuego ocurre donde el cambio ya iba a ocurrir — el fuego
> como herramienta de un desmonte decidido de antemano es, de hecho, la lectura más probable
> de bosque → agropecuario. Y q es un cociente de superficies, sin intervalo de confianza.

Cuatro decisiones de método más, todas visibles en las figuras:

1. **"Cambió" depende del nivel de leyenda.** Bosque cerrado → bosque abierto cambia en nivel
   2 y no en nivel 1. Se muestran los dos; **para la slide, nivel 1** — con 20+ clases el
   Sankey se vuelve ilegible.
2. **El filtro del lado "antes" va en los cuatro estados, control incluido.** Si el
   tratamiento se filtra y el control no, q compara dos poblaciones distintas.
3. **El lado "después" no se filtra**: herbácea inundable → agua es una transición legítima.
   Consecuencia deliberada: el Sankey tiene más categorías a la derecha que a la izquierda.
4. **La serie llega a 2024 (Y+1) y a 2022 (Y+3)**, así que los totales de esta sección no
   coinciden con los del resto del factsheet. Decirlo si aparece un absoluto.

**Qué va al factsheet.** Está todo escrito para el país y para las 12 ecorregiones, en los dos
niveles; lo más probable es que a la slide vaya **sólo lo nacional en nivel 1** — el dumbbell
del control y la matriz de q, o el Sankey si se prefiere la historia de las transiciones. La
versión ya recortada a eso es **§6.5**.

#### 6.5 La versión de slide: tres frases y dos figuras

`notebooks/factsheet_veg_short.qmd` (docs/09 §5.8) es este mismo análisis dicho en lo que entra
en una lámina: **nacional, sin regiones, sin `q`, sin la trayectoria patagónica**. No recalcula
nada —lee las mismas tablas y llama al mismo `sankey_change()`— y escribe con prefijo propio
`fig06c_`. Existe porque la versión larga no se puede podar en la sala: hay que decidir antes qué
frase se dice.

**Regla de esta sección, y vale para toda la lámina: cada porcentaje va con su superficie.** Un
porcentaje solo no se puede chequear contra nada y "¿cuántas hectáreas son?" es lo primero que
pregunta cualquiera. Dos unidades, y hay que decir cuál es cuál: lo **quemado** se dice como
**total de la serie** (26 años, recurrencias incluidas), lo que es **superficie del país** se dice
**por año**.

**Frase 1 — de lo que ardió, cuánto figura con otra cobertura.** De las **61,4 Mha quemadas**
entre 1999 y 2024, **12,5 Mha (20 %)** aparecen con otra clase un año después; en familias,
**9,1 Mha (15 %)**. Va con el **Sankey** de ese mismo nivel. ⚠️ **El número y el Sankey tienen que
ser del mismo nivel de leyenda**: bosque cerrado → bosque abierto cambia en nivel 2 y no en nivel
1, y poner el Sankey de nivel 2 con el 15 % de nivel 1 es el error fácil de esta lámina.

**Frase 2 — cuánto cambia el país.** La superficie vegetal argentina son **252 Mha**, y cambian
de familia **10,4 Mha por año (4,1 %)** en una ventana de dos años (17,4 Mha / 6,9 % por clase).
Es el contexto sin el cual la frase 1 no se puede leer, y es lo más parecido al control que esta
lámina se puede permitir.

**Frase 3 — cuánto pesa el fuego en ese cambio.** Se queman **2,4 Mha/año, el 0,9 %** de esa
superficie, pero de las 10,4 Mha que cambian cada año **0,35 Mha ardieron: el 3,4 % del cambio,
3,6 veces** lo que le tocaría por tamaño. **La figura son dos barras con denominadores
distintos** —superficie arriba, cambio abajo— y ésa es la comparación: si el fuego fuera
indiferente al cambio, las dos medirían lo mismo. (3,4 / 0,9 = 3,6 y q = 3,7 son dos caminos al
mismo hecho, no dos hallazgos; si en la sala preguntan "¿y eso es mucho?", la respuesta larga es
q y está en §6.1.)

**Variante, si se la quiere decir más ancha**: contando el fuego en cualquier año de la ventana
—no sólo en el del medio— el 3,4 % sube a 8,0 %. Las dos son verdaderas; la estricta es la que se
puede atribuir a un fuego con fecha, y es la que conviene poner.

**El Sankey completo, con la permanencia** (`keep_unchanged = TRUE`): la misma figura sin sacar
la diagonal. Sale **plana a propósito** —de lo quemado, el **85 %** sigue siendo lo que era en
nivel 1, el 80 % en nivel 2— y ése es el punto: las figuras de la frase 1 son un **zoom** sobre la
cinta fina del 15 %, y conviene mostrarlas después de la completa, no en lugar de ella. En nivel 1
entran las 17 transiciones (umbral 0,1 % sólo para que las clases de área ~0 no apilen etiquetas
sobre el eje; cuesta el 0,14 %), así que **el alto total es el área quemada y las proporciones se
leen del dibujo**. Es la figura que contesta "¿y el fuego no transforma casi nada?" con el número
correcto y no con una impresión: 15 % es mucho o poco **contra el 3,9 % que cambia sin fuego**, no
contra cero.

**Lo que esta versión NO puede decir**, y por eso el epígrafe de §6.4 sigue siendo obligatorio:
no es "el fuego transformó 9,1 Mha" (es asociación, no causa), un año subestima la vegetación
leñosa (§6 ⚠️), y parte del cambio a un año puede ser la cicatriz y no la conversión (§6.2).

#### 6.6 Si la lámina es sólo de bosques

La variante más fuerte del análisis 6, y la que más fácil se dice mal. Números en
`09-statistics.md` §5.9; figuras en `factsheet_veg_short.qmd` §4.

**Hay CUATRO números de bosque y no son intercambiables** (nacional, Y+1):

| lo que se afirma | q |
|---|---|
| el **bosque** (familia) deja de ser bosque | **6,4** |
| el **bosque cerrado** deja de ser bosque | **14,0** |
| **bosque → agropecuario** (esa transición sola) | **10,9** |
| el bosque cerrado deja de ser *bosque cerrado* (incluye pasar a bosque abierto) | 11,7 |

La frase "la transformación de bosques a otras clases es N veces más probable" es **la primera
fila: 6,4**. El 10,9 es *una* transición (el 61 % de lo que sale, no todo) y el 11,7 cuenta como
transformación un cambio que **sigue siendo bosque**.

⚠️ **El promedio de la familia no describe a ninguna de sus clases, y ésa es la razón para bajar
a nivel 2 acá.** Bosque cerrado q = 14,0; bosque abierto 2,2; **bosque inundable q = 1,0 — el
fuego no le hace nada medible**. El 6,4 promedia tres sistemas distintos. **Si va un solo número
de bosque a la lámina, que sea el de una clase.**

**La frase recomendada**, que es la más fuerte y a la vez la más defendible:

> **Cuando se quema un bosque cerrado, el 44 % deja de ser bosque al año siguiente. Sin fuego, el
> 3 %: 14 veces más probable.** (8,1 Mha de bosque cerrado quemadas entre 1999 y 2024.)

**Las dos figuras**: el *dumbbell* de las tres clases (ardió vs no ardió, con `q` escrito al lado
y la línea del promedio de la familia — es la figura que hace visible por qué el promedio no
sirve), y el **Sankey del bosque quemado con su permanencia**: 18,6 Mha de bosque quemado, el
70 % sigue siendo bosque y el 30 % se reparte 61 % agropecuario / 38 % herbácea-arbustiva. Desde
bosque cerrado y en clases nativas, **la mitad de lo que sale va a cultivos temporarios**.

**La ventana mueve los dos números en direcciones opuestas** y hay que saber cuál se dice: el
porcentaje **sube** (bosque cerrado 44 % en Y+1 → 51 % en Y+5, la conversión tarda) y `q` **baja**
(14,0 → 9,1, el control acumula su propio fondo). Y+4 e Y+5 nacionales **ya están exportados**
(§5.9), así que reportar a cinco años no cuesta una corrida nueva.
