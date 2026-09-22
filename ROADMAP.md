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

**Dates.** MapBiomas Argentina col-3 (with fire col-1) launches **24 Sep 2026**. 

## Next

**Ordenar y limpiar el repo — el plan vive en [`collection-01/docs/DOCS-CLEANUP.md`](collection-01/docs/DOCS-CLEANUP.md)**: el orden de las fases, la plantilla, a dónde va cada archivo y el protocolo de sesión.
El braindump que lo originó está absorbido en §1 de ese plan; la versión original queda en el
historial de git.

**Seed the `mapbiomas` remote** (run, when ready — no code change): force-push `main` to
`mapbiomas/argentina-fire` (`git push mapbiomas main:main --force`), replacing its placeholder
`Initial commit` history. Write access already confirmed (test branch pushed 22 Sep 2026). Iván
runs this himself — force-push is blocked for Claude Code's auto mode. See README's "Remotes"
section for the origin/mapbiomas split.

## After

- **El ATBD de Argentina Fuego Col1**, que nadie más puede escribir por nosotros.
    El **borrador está en [`collection-01/ATBD/`](collection-01/ATBD/)** (LaTeX, inglés, 27 pp.),
    revisado por Iván y con la portada al día. **Lo que falta está en
    [`ATBD/checklist.md`](collection-01/ATBD/checklist.md)**, tres ítems: el diagrama del
    algoritmo, las direcciones públicas de fuego (Gonza y Luna) y el snippet de GEE más el link de
    snapshot (Vera).
    ✅ Indexado (21 sep): `collection-01/README.md`, la tabla de documentos de `CLAUDE.md` y el
    README raíz apuntan al ATBD.
- **Seguir explorando análisis para el lanzamiento de diciembre**. 
    Ahí hay 4 factsheet-related notebooks; factsheet_sep2026 es el que soporta el factsheet
    del lanzamiento de Col3 ARG en septiembre.
- **Comunicar problema de leyenda**:

Arreglada la leyenda de nivel 2 de la red (17 sep). Falta avisarles.

`00_Tools/Legends.js::lulc_argentina_nivel2` **de la red** traía los valores de los códigos
11, 12 y 63 corridos un lugar respecto de sus claves, y `statistics/legends.py` lo copió
verbatim, así que estaba en **todas nuestras tablas de nivel 2**.

| código | decía | **es** | % de lo quemado |
|---|---|---|---|
| 11 | Mosaicos de arbustos y herbaceas | **Herbaceas Inundables** | 21,2 |
| 12 | Herbaceas Inundables | **Herbaceas** | 21,7 |
| 63 | Herbaceas | **Mosaicos de arbustos y herbaceas** | 4,1 |

**Hecho**: corregido **de los dos lados** (collection-01/statistics/docs/statistics.md §5.10.1), que es lo que importa, porque el
join numerador-denominador es POR NOMBRE y arreglar uno solo los habría emparejado mal sin que
ninguna compuerta lo viera. `legends.py` para el denominador (nuestro, decodifica por código)
y `factsheet_tables.R::fix_n2()` al leer los CSV del toolkit (que llegan con el nombre ya
decodificado por ese mismo archivo). **No se re-exportó nada de GEE**: los `_raw` estaban en
disco, los nueve `--check` re-decodifican sin red y pasan, `factsheet_tables.R` tarda 4,5 s.
Los cuatro cuadernos re-renderizados.

**Ningún número se movió, y el nivel 1 no se tocó** (las tres son la misma familia): el 25 % de
bosque del factsheet y todo el bloque de bosques de §5.9 están intactos. Cambió la etiqueta de
la mitad de nivel 2. Control después del arreglo: Pampa 62 % *Herbaceas*, Delta 75 %
*Herbaceas Inundables*, Puna 51 % *Mosaicos*.

**Lo que falta, y no es código**:

**Avisarle a la red.** El archivo es de ellos y lo lee todo país que decodifique la leyenda
argentina. Conviene mirar si la misma rotación está en el bloque de otro país.
**Revisar si algo ya publicado cita uno de los tres nombres**: el ATBD, láminas viejas, el
borrador del paper.