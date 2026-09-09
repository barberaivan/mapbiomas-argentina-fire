// Taller mayo 2026 — Colección 1.  Typst port of taller_mayo_2026_col_01.pptx.
//
// Pilot slide: nº 13, the method scheme.  Build with
//   typst compile --root . taller_mayo_2026_col_01.typ out/taller_mayo_2026_col_01.pdf
//
// `--root .` is required: the imports below reach into sibling directories, and
// Typst sandboxes file access to the root it is given.

#import "@preview/touying:0.7.4": *
#import "@preview/touying:0.7.4": themes
#import themes.simple: simple-theme, slide
#import "/lib/style.typ": *
#import "/diagrams/method-scheme.typ": method-scheme

#show: simple-theme.with(
  header: none,
  footer: none,
  footer-right: none,
  // The Google Slides original is exactly 720 x 405 pt; keep it, so that a
  // 10 pt font is the same 10 pt it was there.
  config-page(width: slide-width, height: slide-height, margin: 12pt),
  // simple-theme paints `strong` with the theme's accent colour; the deck's
  // bold text is plain black.
  config-common(show-strong-with-alert: false),
  config-methods(init: (self: none, body) => {
    set text(font: font-sans, size: size-body, fill: c-ink)
    set par(leading: leading)
    body
  }),
)

// ---------------------------------------------------------------- slide 13 ---
// No title in the original: the scheme is the whole slide.
#slide[
  #set align(center + horizon)
  #method-scheme()
]
