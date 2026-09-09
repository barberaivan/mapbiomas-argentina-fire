// The SAME slide 13, built up over subslides instead of shown at once.
// One source, ten pages — the reason for the whole migration. Build with
//   typst compile --root . taller_mayo_2026_col_01-steps.typ out/taller_mayo_2026_col_01-steps.pdf
// The only difference from taller_mayo_2026_col_01.typ is the last two lines:
// the diagram is rendered through touying's reducer and given the `pause`
// marker. Adding or moving a step is one `..brk` in diagrams/method-scheme.typ.

#import "@preview/touying:0.7.4": *
#import "@preview/touying:0.7.4": themes
#import themes.simple: simple-theme, slide
#import "@preview/fletcher:0.5.8" as fletcher: diagram
#import "/lib/style.typ": *
#import "/diagrams/method-scheme.typ": method-scheme

#show: simple-theme.with(
  header: none, footer: none, footer-right: none,
  config-page(width: slide-width, height: slide-height, margin: 12pt),
  config-common(show-strong-with-alert: false),
  config-methods(init: (self: none, body) => {
    set text(font: font-sans, size: size-body, fill: c-ink)
    set par(leading: leading)
    body
  }),
)

#let fletcher-diagram = touying-reducer.with(reduce: diagram, cover: fletcher.hide)

#slide[
  #set align(center + horizon)
  #method-scheme(render: fletcher-diagram, pause: pause)
]
