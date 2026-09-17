# ROADMAP

**What to do next, in order.** This file is the *when*; `collection-01/docs/NN-*.md` are the *how*.
Read it at the start of every session, before planning anything.

**How to use it**

- Work top-down. `Now` is in flight, `Next` is ordered and its blockers are named, `Later` is
  scheduled but not yet startable.
- Each item says whether it is **run** (execute what exists) or **edit → run** (code must change
  first). That distinction is the whole point of the file — several things below look like a re-run
  and are not.
- **Update this file as you go**: tick an item when it lands, and delete it on the next pass. Git
  history is the archive; a long done-list costs every future session context it could spend on the
  work.
- [`BACKLOG.md`](BACKLOG.md) is the *unscheduled* pile, per topic, with the post-mortems. An item
  moves BACKLOG → ROADMAP when it is scheduled, never the other way.

**Dates.** MapBiomas Argentina col-3 (with fire col-1) launches **24 Sep 2026**. The factsheet is
drawn by graphic designers, so its **data is due ~Wed 16 Sep**. Ideally, assets sould be ready 
at **15 Sep 2026** for Brazil to copy them to `mapbiomas-public`.

## Next

### Análisis 6: decidir ventana y figura (17 sep)

**Hecho**: el análisis 6 completo con control, en su propio cuaderno
(`notebooks/factsheet_veg.qmd`, renderiza en ~2 min), más los dos mapas de píxel nuevos y las
Malvinas en todos los mapas. q = 3,74 nacional, 10,9 para bosque → agropecuario.

**Hecho también, y es la mitad de la decisión de abajo**: la **versión de slide**
(`notebooks/factsheet_veg_short.qmd`, ~10 s; docs/09 §5.8, docs/10 §6.5) — tres frases
nacionales con **cada porcentaje acompañado de su superficie**, más dos Sankeys (nivel 2 y
nivel 1) y la figura de las dos barras de denominador distinto. Los números: de las **61,4 Mha
quemadas (1999-2024, hectárea-año)** cambian de clase **12,5 Mha / 20 %** (nivel 2) y **9,1 Mha
/ 15 %** (nivel 1); el país cambia **10,4 Mha/año, el 4,1 %** de sus 252 Mha de superficie
vegetal; y **el 3,4 % de ese cambio ocurre donde ardió**, contra un 0,9 % de superficie —
**3,6 veces**, que es q = 3,74 por otro camino. Escribe `fig06c_*`.

**Hecho, 17 sep**: **el bloque de bosques** (`factsheet_veg_short.qmd` §4, docs/09 §5.9,
docs/10 §6.6) y las dos tablas que lo alimentan (`factsheet_bosques{,_destinos}.csv`).
Y **sí tenemos Y+4 e Y+5 nacionales**: los `_n44` son país entero con un bit norte/sur de
más, así que los cuatro lags están exportados y no hace falta ninguna corrida nueva.

**Lo que hay que decidir, y sólo se decide mirando**:

- **Qué número de bosque se dice, porque hay cuatro y sólo uno responde a cada frase**: la
  familia deja de ser bosque **q = 6,4**; el **bosque cerrado, q = 14,0**; bosque →
  agropecuario (esa transición sola) **10,9**. ⚠️ El promedio de la familia **no describe a
  ninguna de sus clases** — bosque inundable da **q = 1,0**, el fuego no le hace nada—, así
  que si va un solo número de bosque tiene que ser **el de una clase**. La recomendación:
  *"cuando se quema un bosque cerrado, el 44 % deja de ser bosque al año siguiente; sin
  fuego, el 3 %"*.

- **Qué ventana se reporta.** Y+1 es la de Ferro et al., calibrada en el Chaco donde el fuego
  despeja. En Patagonia el bosque quemado que deja de ser bosque va de 49 % (Y+1) a 78 % (Y+5)
  — la arbustalización llega al mapa tres años tarde (docs/09 §5.7.3). Si se reporta a un año
  se subestiman todos los sistemas donde el fuego mata pero no despeja.
- **Qué figura va a la slide**: el dumbbell del control (la honesta), la matriz de q (la que
  tiene el 10,9), o las del cuaderno corto (el Sankey + las dos barras, que es la historia sin
  q). Todas nacionales, en nivel 1. **Si va el Sankey de nivel 2, el porcentaje que lo acompaña
  es 20 %, no 15 %** — "cambió de cobertura" depende del nivel de leyenda (docs/10 §6.5).
- **Los cortes de clase del mapa del año del último fuego** y **si la magma invertida
  reemplaza a la naranja** en la lámina de apertura (el cero blanco deja 60 % del país en
  blanco).

**Pendiente si se quiere cerrar el 17 % que falta en Patagonia** (docs/09 §5.7.3): partir el
bosque quemado por tamaño de incendio o por severidad propia. No está hecho ni es necesario
para el lanzamiento.

### ⚠️ Los tres cuadernos no tienen el mismo estatus

**Sólo `factsheet.qmd` alimenta el lanzamiento de septiembre** (análisis 1–5). Los otros dos
—`factsheet_veg.qmd` y `factsheet_veg_short.qmd`, todo el análisis 6— son **exploratorios**: no
se publican ahora, y son el material del **lanzamiento de fuego de diciembre (Bariloche, 7-11
dic)** y del **paper**. No se borran ni se dejan de documentar. Está escrito en docs/09 §5.0 y
en el encabezado de docs/10.

**Lo próximo: el cuaderno que especifica la lámina.** Una entrada por slide de septiembre —
figura, epígrafe, número, archivo de origen— que reemplace a la prosa de docs/10 como fuente de
verdad y que sea lo que recibe el diseñador gráfico. Iván está diseñando el factsheet real
ahora; el cuaderno se escribe sobre esa decisión, no antes.

### Revisar el factsheet y elegir qué va a las slides

Los seis análisis están hechos, con sus tablas y sus 170 figuras
(`collection-01/docs/09-statistics.md`; `quarto render collection-01/notebooks/factsheet.qmd`).
Lo que falta es **decidir**:

- **Qué regiones se destacan en cada slide.** Las variantes `all_regions` están para eso; hay
  12 focales de cada análisis ya escritas, así que cambiar de región no cuesta nada.
- **Las frases de equivalencia**, del peor año (2001, 5,08 Mha) y del **total de la serie**
  (63,23 Mha con recurrencias = 2,06 provincias de Buenos Aires): la tabla de candidatas, con
  las tres cuentas hechas, está en la sección 0 del notebook.
- **Selva Paranense: 60 % de lo quemado es agropecuario** (análisis 4). Mirarlo antes de que
  vaya a una slide.
- **Los análisis 4 y 5 se invierten entre sí** y hay que elegir cuál va (o los dos, juntos):
  Bosques Patagónicos es 55 % bosque de lo quemado pero quema 0,16 % de su bosque por año.
  Citar uno sin el otro da la lectura opuesta (docs/09 §5.3.1).
- **Si el Delta aparece**, su epígrafe tiene que decir que el 27 % de la región es "no
  observado" en col-3 y queda fuera del denominador (docs/09 §3.1).
- **Del análisis 6, qué va**: lo más probable es sólo lo nacional en nivel 1. El epígrafe
  **tiene** que decir que es observacional — los píxeles que arden no son una muestra al azar
  del país, y el fuego como herramienta de un desmonte ya decidido es la lectura más probable
  de bosque → agropecuario (docs/10 §6.4).

### Entregar los números y las figuras al diseñador (~mié 16 sep)

`collection-01/data/statistics/figures/` — 170 figuras, PNG y PDF de cada una.

## After

- **El cruce contra *staging***, cuando Brasil copie los assets (gate 8, docs/09 §9).
- **El ingest manual de los 27 paquetes de cicatrices**, que destraba `toDrive-area-scar-size`.
- **Registro en Workspace** (subtemas, leyendas, capas territoriales) — docs/09 §11.
- **El ATBD de Argentina**, que nadie más puede escribir por nosotros.
- **El cuaderno lámina por lámina** de la versión de septiembre: qué figura va en cada una,
  con qué epígrafe y qué número, y de qué archivo sale. Es lo que se le entrega al diseñador
  gráfico, y hoy esa selección vive en prosa en docs/10. **Es lo próximo** (ver abajo).
