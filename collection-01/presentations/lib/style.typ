// Deck-wide style: palette, typography and node/edge presets.
// Working rule #1 — nothing outside this file hardcodes a colour or a stroke.
// Values extracted from taller_mayo_2026_col_01.pptx (Google Slides export).

#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
#import fletcher.shapes: bracket as bracket-shape

// ---------------------------------------------------------------- palette ---
// The three analysis stages, in the order they run, then the products.
#let c-spectral = rgb("#FF67FF")   // Análisis espectral
#let c-temporal = rgb("#0CA5D0")   // Análisis temporal
#let c-spatial  = rgb("#7348E1")   // Análisis espacial
#let c-product  = rgb("#303030")   // Productos   (pptx schemeClr dk2)

#let c-ink      = rgb("#000000")   // box text
#let c-arrow    = rgb("#434343")   // connectors and their labels
#let c-muted    = rgb("#999999")   // "Resolución …" side labels
#let c-bracket  = rgb("#666666")   // right-hand grouping brackets

// ------------------------------------------------------------- typography ---
// The original is Arial; Liberation Sans is metric-compatible and is what is
// installed here. Keep the fallback chain so the deck still renders elsewhere.
#let font-sans = ("Liberation Sans", "Arial")

#let size-body  = 10pt    // box text and edge labels
#let size-stage = 11pt    // stage labels in the left gutter
#let leading    = 0.45em  // tight, as in the slides

#let hair = 0.75pt        // pptx w=9525 EMU == 0.75pt

// Box width, in `em` so the diagram scales with the font size instead of being
// pinned to the 10 pt slide. 17.1em == the 171 pt of the widest original box.
#let w-box = 17.1em

// ------------------------------------------------------------ box contents ---
// Stacked lines, left-aligned. The caller marks up its own emphasis: several
// titles in this deck are mixed weight ("*Productos internos* (vectorial)").
// Note the bullet dashes must be escaped (`\-`) or Typst makes a real list of
// them, which brings its own — much looser — spacing.
#let lines-left(..lines) = align(left, {
  set par(leading: leading)
  lines.pos().join(linebreak())
})

// Stacked lines, centred.
#let lines-centre(..lines) = align(center, {
  set par(leading: leading)
  lines.pos().join(linebreak())
})

// -------------------------------------------------------------- node preset ---
// One box style; the stage colour is the only thing that varies.
#let stage-box(colour, pos, body, ..args) = node(
  pos,
  body,
  shape: "rect",          // else fletcher auto-picks a circle for squarish boxes
  stroke: hair + colour,
  fill: none,
  corner-radius: 4pt,
  inset: 5pt,
  width: w-box,
  ..args,
)

// Gutter labels (no frame).
#let stage-label(colour, pos, body) = node(
  pos,
  align(right, text(fill: colour, size: size-stage, body)),
  stroke: none,
  inset: 0pt,
)
#let side-label(pos, body) = node(
  pos,
  align(left, text(fill: c-muted, size: size-body, body)),
  stroke: none,
  inset: 0pt,
)

// ------------------------------------------------------------ edge presets ---
// One arrow style for the whole deck.
#let arr(from, to, ..args) = edge(
  from, to, "-|>",
  stroke: hair + c-arrow,
  ..args,
)

// Edge label, in the connector colour.
#let tag(body) = text(fill: c-arrow, size: size-body, body)

// A square grouping bracket hugging one side of the nodes it encloses, using
// fletcher's own stretched-glyph shape. `enclose` takes the group's node names,
// so the bracket tracks the boxes: no coordinate is repeated.
#let group-bracket(names, dir: left, colour: c-product) = node(
  enclose: names,
  stroke: none,
  inset: 3pt,
  shape: bracket-shape.with(dir: dir, sep: 1pt, fill: colour, size: 7pt),
)

// ------------------------------------------------------------- page setup ---
// The Google Slides original is exactly 720 x 405 pt.
#let slide-width  = 720pt
#let slide-height = 405pt
