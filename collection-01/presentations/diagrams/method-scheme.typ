// The Collection-1 method scheme — slide 13 of taller_mayo_2026_col_01.
//
// ONE definition, three consumers:
//   * the deck, final state        -> method-scheme()
//   * the deck, built up in steps  -> method-scheme(pause: pause) in a slide
//   * the paper figure             -> figures/method-scheme.typ
//
// Layout is fletcher's elastic grid — not one absolute coordinate. Columns:
//   0  stage label (left gutter)     3  right-hand box column
//   1  left-hand box column          4  "Resolución …" label (right gutter)
//   2  empty, widens the gap between the two box columns so the "Resumen"
//      label fits between them (as it does in the original)
//
// Same trick vertically: empty rows open the gaps between stages, one per unit
// of gap. An empty row or column costs nothing but one extra grid gap.
//
//   row  0  Landsat            | Clasificador probabilístico
//   row  1  MapBiomas          | Probabilidad de quema
//   row  3  Métricas anuales   | Serie temporal por píxel
//   row  7  Semillas           | Algoritmo SNIC
//   row  8  Candidatos         | Polígonos
//   row 12  Productos internos | Productos oficiales
// (spacer rows: 2 | 4,5,6 | 9,10,11 — one per unit of inter-stage gap)
//
// The grouping brackets `enclose` the named boxes rather than being positioned,
// so moving a box moves its bracket.

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
#import "../lib/style.typ": *

// `render` is the diagram constructor. It defaults to fletcher's own `diagram`,
// which draws the finished scheme in one page. To build it up over subslides,
// pass touying's fletcher reducer and its `pause` marker:
//
//   #let fletcher-diagram = touying-reducer.with(
//     reduce: fletcher.diagram, cover: fletcher.hide)
//   #method-scheme(render: fletcher-diagram, pause: pause)
//
// The `..brk` splices below are the only trace of it in the layout: with
// `pause: none` they splice nothing and every step collapses, which is what the
// finished slide and the paper figure want.
#let method-scheme(render: diagram, pause: none) = {
  let brk = if pause == none { () } else { (pause,) }

  render(
    spacing: (24pt, 7pt),

    // ================================================== análisis espectral ===
    stage-label(c-spectral, (0, 0.5), [Análisis \ espectral]),

    stage-box(c-spectral, (1, 0), name: <landsat>, lines-left(
      [*Landsat*],
      [\- 6 bandas ópticas],
      [\- 11 índices espectrales],
    )),
    stage-box(c-spectral, (1, 1), name: <mapbiomas>, lines-left(
      [*MapBiomas*],
      [\- Land cover del año previo],
      [\- Mosaico del año previo],
      [\- Regiones],
    )),
    group-bracket((<landsat>, <mapbiomas>)),

    ..brk,

    stage-box(c-spectral, (3, 0), name: <clasificador>, lines-centre(
      [Clasificador probabilístico],
      [(regresión logística)],
    )),
    arr(<landsat>, <clasificador>),
    arr(<mapbiomas>, <clasificador>),

    ..brk,

    stage-box(c-spectral, (3, 1), name: <prob>, lines-centre(
      [*Probabilidad de quema*],
      [para cada píxel-fecha],
      [(observación)],
    )),
    arr(<clasificador>, <prob>),

    group-bracket((<clasificador>, <prob>), dir: right, colour: c-bracket),
    side-label((4, 0.5), [Resolución \ sub-anual]),

    ..brk,

    // ================================================== análisis temporal ===
    stage-label(c-temporal, (0, 3), [Análisis \ temporal]),

    stage-box(c-temporal, (3, 3), name: <serie>, lines-centre(
      [Serie temporal por píxel],
      [(prob. de quema)],
    )),
    arr(<prob>, <serie>),

    ..brk,

    stage-box(c-temporal, (1, 3), name: <metricas>, lines-left(
      [*Métricas anuales*],
      [\- Probabilidad de quema alta],
      [\- Aumento abrupto],
      [\- Persistencia],
    )),
    arr(<serie>, <metricas>, label: tag[Resumen], label-side: right),
    group-bracket((<metricas>,)),

    ..brk,

    // =================================================== análisis espacial ===
    stage-label(c-spatial, (0, 7.5), [Análisis \ espacial]),

    stage-box(c-spatial, (1, 7), name: <semillas>, lines-left(
      [*Semillas*],
      [Píxeles claramente quemados],
    )),
    stage-box(c-spatial, (1, 8), name: <candidatos>, lines-left(
      [*Candidatos*],
      [Píxeles plausiblemente quemados],
    )),
    arr(<metricas>, <semillas>, label: tag[Umbrales], label-side: right),
    group-bracket((<semillas>, <candidatos>)),

    ..brk,

    stage-box(c-spatial, (3, 7), name: <snic>, lines-centre(
      [Algoritmo de crecimiento],
      [de región (SNIC)],
    )),
    arr(<semillas>, <snic>),
    arr(<candidatos>, <snic>),

    ..brk,

    stage-box(c-spatial, (3, 8), name: <poligonos>, [*Polígonos*], width: auto),
    arr(<snic>, <poligonos>),

    ..brk,

    // ============================================================ productos ===
    stage-label(c-product, (0, 12), [Productos]),

    stage-box(c-product, (1, 12), name: <internos>, lines-left(
      [*Productos internos* (vectorial)],
      [\- ID del objeto],
      [\- Fechas: año, fecha min.,],
      [#h(0.85em) fecha med., fecha max.],
      [\- Métricas de calidad:],
      [#h(0.85em) Densidad de semillas, N obs.],
    )),
    // Long label on a shallow diagonal: sits above the line, as in the original.
    arr(<poligonos>, <internos>,
        label: tag[Procesamiento a nivel de objetos], label-side: right,
        label-sep: 4pt),
    group-bracket((<internos>,)),

    ..brk,

    stage-box(c-product, (3, 12), name: <oficiales>, lines-left(
      [*Productos oficiales* (raster)],
      [\- Mes de quema],
      [\- Tamaño de la cicatriz],
      [\- Frecuencia],
      [\- Acumulado],
      [\- Año del último incendio],
    )),
    arr(<internos>, <oficiales>),

    // The right-hand "Resolución anual" bracket spans everything below the
    // spectral block, so it is declared last.
    group-bracket((<serie>, <snic>, <poligonos>, <oficiales>),
                  dir: right, colour: c-bracket),
    side-label((4, 7.5), [Resolución \ anual]),
  )
}
