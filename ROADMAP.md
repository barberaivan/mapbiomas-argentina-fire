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

### Terminar el análisis 6 y los dos mapas nuevos (17 sep)

**Análisis 6 hecho y verificado**, con control y prueba de persistencia
(`docs/09-statistics.md` §5.7/§5.7.1/§5.7.2, `docs/10-factsheet_design.md` §6). El diseño es
el de Ferro et al. (2026) rehecho a 30 m para todo el país: q = 3,74 nacional, 10,9 para
bosque → agropecuario, y el control reordena las regiones (Pampa baja al tercer puesto,
Campos y Malezales y Altos Andes quedan por debajo de 1). Las dos compuertas cierran: área
quemada 0,00 % contra el toolkit los 26 años, y 280,72 Mha/año de cobertura espacial.

Los mapas de frecuencia en veces (promedio y máximo) también están bajados y dibujados.

**Falta**: el ráster del año del último fuego, que sigue corriendo en GEE
(`arg_last_fire_480m_mean`, >1 h — la cuenta gmail). Cuando aterrice:

```bash
$PYTHON collection-01/statistics/last_fire_export.py --fetch   # corre su compuerta
quarto render collection-01/notebooks/factsheet.qmd
```

Y tres decisiones que sólo se pueden tomar mirando la figura:

- **Los cortes de clase del mapa del año del último fuego** — siete períodos puestos a ojo
  antes de ver la distribución, hay que ajustarlos al histograma real.
- **Si la magma invertida del mapa de frecuencia reemplaza a la naranja** en la lámina de
  apertura: el cero blanco deja 60 % del país en blanco y es un cambio grande.
- **Del análisis 6, qué figura va a la slide**: el dumbbell del control (la honesta) o la
  matriz de q (la que tiene el 10,9). Las dos, nacionales, en nivel 1.

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
- **Borrar las dos reducciones muertas** `collection-01/workflow/11-burnable_area.py` y
  `11-burned_area_stats.py`: el área quemada la calcula el toolkit y los dos denominadores los
  calculan `statistics/{burnable,lulc_area}_export.py`, así que ninguna de las dos corre ya.
