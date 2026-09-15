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

### Revisar el factsheet y elegir qué va a las slides

Los seis análisis están hechos, con sus tablas y sus 76 figuras
(`collection-01/docs/09-statistics.md`; `quarto render collection-01/notebooks/factsheet.qmd`).
Lo que falta es **decidir**:

- **Qué regiones se destacan en cada slide.** Las variantes `all_regions` están para eso; hay
  12 focales de cada análisis ya escritas, así que cambiar de región no cuesta nada.
- **La frase de equivalencia del peor año** (2001, 5,08 Mha): la tabla de candidatas está en la
  sección 0 del notebook.
- **Selva Paranense: 60 % de lo quemado es agropecuario** (análisis 5). Mirarlo antes de que
  vaya a una slide.
- **Los análisis 5 y 6 se invierten entre sí** y hay que elegir cuál va (o los dos, juntos):
  Bosques Patagónicos es 55 % bosque de lo quemado pero quema 0,16 % de su bosque por año.
  Citar uno sin el otro da la lectura opuesta (docs/09 §5.3.1).
- **Si el Delta aparece**, su epígrafe tiene que decir que el 27 % de la región es "no
  observado" en col-3 y queda fuera del denominador (docs/09 §3.1).

### Entregar los números y las figuras al diseñador (~mié 16 sep)

`collection-01/data/statistics/figures/` — 76 figuras, PNG y PDF de cada una.

## After

- **El cruce contra *staging***, cuando Brasil copie los assets (gate 8, docs/09 §9).
- **El ingest manual de los 27 paquetes de cicatrices**, que destraba `toDrive-area-scar-size`.
- **Registro en Workspace** (subtemas, leyendas, capas territoriales) — docs/09 §11.
- **El ATBD de Argentina**, que nadie más puede escribir por nosotros.
- **Borrar las dos reducciones muertas** `collection-01/workflow/11-burnable_area.py` y
  `11-burned_area_stats.py`: el área quemada la calcula el toolkit y los dos denominadores los
  calculan `statistics/{burnable,lulc_area}_export.py`, así que ninguna de las dos corre ya.
