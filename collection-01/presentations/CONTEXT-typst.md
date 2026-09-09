# Context: methodological presentations in Typst

## Goal

Migrate presentations from Google Slides / PowerPoint to **Typst**, producing **PDF**
output. The PDF is the final deliverable: it renders identically on any platform and
does not depend on having the authoring software installed.

## Before starting

Two preliminary steps, in this order:

1. **Verify current versions.** The pins listed below may be out of date. Check
   https://typst.app/universe for Touying, Fletcher and CeTZ, and
   https://github.com/typst/typst/releases for the compiler, then **update the numbers
   in this file** before writing any code.
2. **Start with a single slide.** Pick the most representative one (ideally one with a
   box-and-arrow diagram) and reproduce it completely before touching the rest. Show it
   for approval. Only once it is validated, continue with the remaining slides. Do not
   attempt all 40 at once.

## Why

The motivation is maintenance, not aesthetics.

These presentations rely heavily on **box-and-arrow diagrams that build up
incrementally** — one slide per step, instead of animations, so the PDF is
self-contained. Edited by hand, changing one element means replicating that change
across 6-8 slides.

Typst solves this with a **single source of truth**: the diagram is written once, with
`pause` markers, and the compiler generates the N incremental pages. Adding an
intermediate step is one line; everything downstream recomputes automatically.

Secondary benefit: it is plain text, so it lives in git and can be edited by agents.

## Stack

These are not three programs. **Typst is the only binary**; the rest are packages that
download themselves from the registry (Typst Universe) on `#import`.

| Component | What it is | Role |
|---|---|---|
| **Typst** | Compiler (Rust, Apache-2.0) | Typesetting and layout engine → PDF |
| **Touying** | Package | Presentation framework: slides, themes, `#pause` |
| **Fletcher** | Package | Node-and-arrow diagrams (boxes + arrows) |
| **CeTZ** | Package | TikZ-style vector drawing; Fletcher is built on top of it |

### Versions

**Always pin the version in the `#import`.** Typst is pre-1.0 and so are the packages:
there are breaking changes between releases (see Gotchas). The pin is what guarantees
the project still compiles identically two years from now.

```typst
#import "@preview/touying:0.7.4": *
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
```

Checked 2026-09-09 against `https://packages.typst.org/preview/index.json` and
`github.com/typst/typst/releases`: compiler **0.15.1**, Touying **0.7.4**, Fletcher
**0.5.8** (0.5.9 does not exist in the registry), CeTZ **0.5.2**.

**Do not import CeTZ alongside Fletcher unless you actually need raw CeTZ.** Fletcher
0.5.8 depends internally on **cetz 0.3.4**; importing `cetz:0.5.2` puts a *second,
incompatible* CeTZ in scope, and anything drawn with it cannot be embedded in a Fletcher
diagram. Brackets, braces and polylines can be drawn with multi-vertex Fletcher `edge`s
instead — that is what `diagrams/method-scheme.typ` does.

Check the latest versions at https://typst.app/universe before changing these.

## Documentation (consult before inventing API)

- Typst: https://typst.app/docs
- Touying: https://touying-typ.github.io/docs/
- Touying (repo): https://github.com/touying-typ/touying
- Fletcher: https://typst.app/universe/package/fletcher/
- Fletcher (repo + example gallery): https://github.com/Jollywatt/typst-fletcher

## How it works

### Slides

Touying generates slides from headings, with no boilerplate. The mapping to Quarto is
direct:

| Quarto | Touying |
|---|---|
| `##` (new slide) | `==` |
| `. . .` (reveal) | `#pause` |
| manual control | `#slide[ ... ]` |

### Incremental diagrams

The core of the project: **`#pause` works inside the diagram**, not just in body text.

```typst
#let caja = (stroke: .08em, fill: rgb("#eef2ff"), corner-radius: 4pt)

#fletcher-diagram(
  spacing: 3em,
  node((0,0), [Raw data], ..caja),
  pause,
  edge("-|>"), node((1,0), [Cleaning], ..caja),
  pause,
  edge("-|>"), node((2,0), [Model], ..caja),
)
```

That produces three PDF pages from one definition, with nothing duplicated.

For long animations, use **waypoints** (named positions in the animation timeline)
instead of hard-coded subslide numbers, so inserting a step does not break what follows.

### Layout control

**There is no Mermaid-style auto-layout.** Nothing decides positions on its own.
Fletcher has a dual coordinate system:

- **Elastic**: unitless numbers, `(0,0)`, `(1,2)`. Row/column indices in a grid that
  expands to fit content. Handles alignment without manual work.
- **Absolute**: lengths, `(10mm, 20pt)`. Bypass the grid for exact placement.

Both can be mixed in the same diagram. When total unassisted control is needed, drop
down to raw CeTZ (which can be embedded inside a Fletcher diagram).

Available node shapes: rect, circle, diamond, pill, parallelogram, hexagon, trapezium,
cylinder, plus custom shapes.

Edges: `bend: 40deg` for arcs, `vertices` + `corner-radius` for polylines, relative
routing via strings (`"d,r,u,l"`), `snap-to`, `label-pos`, `label-side`.

### Page size

```typst
#set page(width: 254mm, height: 142.9mm, margin: 1cm)   // arbitrary
// or the Touying shortcut:
#show: simple-theme.with(aspect-ratio: "16-9")
```

## Working rules

1. **Centralize styles.** Define `#let caja = (...)`, `#let accent-color = ...` once, at
   the top, and reuse. Never hardcode a color or stroke in an individual slide. Changing
   the look of the whole deck must be a one-line edit.
2. **Compile often.** `typst compile deck.typ` takes milliseconds and errors carry line
   numbers. When unsure about a function: test it, do not assume.
3. **Do not invent API.** Typst postdates 2023 and training-data coverage is thin,
   especially for Fletcher. If a function is unclear, consult the docs linked above or
   the repo's example gallery.
4. **Prefer the elastic grid** for ~90% of cases; use absolute coordinates only where
   visual judgment demands it.

## Reproducing an existing presentation

Inputs provided:

- **`.pdf`** — visual reference. Rasterize pages to see how it should look.
- **`.pptx`** — machine-readable source. Use `python-pptx` to extract exact text, hex
  colors, fonts, sizes and positions. Avoids guessing values.

Both are **untracked** (see `.gitignore`): 21 MB of Google Slides export does not belong
in git history. Keep them in this folder locally; nothing in the build reads them.

Suggested order: extract content and palette from the PPTX → define the style `#let`s →
**rebuild a single pilot slide** → compare against the original PDF → iterate until it
is convincing → only then continue with the rest.

**Do not** produce `.pptx` output. The pipeline is `.typ` source → PDF, directly.

## Reusing diagrams in papers (LaTeX)

One of the main payoffs: the same diagram source serves both the slides and the paper.

Make a standalone file for the figure, with the page fitted to the content:

```typst
#set page(width: auto, height: auto, margin: 5pt)
#set text(font: "New Computer Modern", size: 9pt)

#import "diagram.typ": methodology-diagram
#methodology-diagram
```

`width: auto` is the equivalent of LaTeX's `standalone` class: the page shrinks to fit.
Then `typst compile figure.typ figure.pdf` yields a tightly cropped vector PDF.

**Export PDF for `.tex`, not PNG.** `\includegraphics{figure.pdf}` works natively with
pdflatex, stays vectorial, and scales without pixelating. The CLI also emits SVG (useful
for touch-ups in Inkscape) and PNG via `--ppi 300` if a journal demands raster.

Typst ships the New Computer Modern fonts — the same family LaTeX papers use — so
setting that font makes the box text match the article body typographically.

Two caveats:

- **Design the figure at final print width** (a single column is typically ~8.5cm) and
  include it at scale 1.0, rather than letting `\includegraphics[width=\columnwidth]`
  stretch it. Otherwise the box text ends up a different size than the caption.
- **The paper needs the final state, without pauses.** Either write the shared diagram
  without `pause` and let only the presentation add them, or use Touying's handout mode,
  which collapses all animation subslides into a single page per logical slide.

## Gotchas

- **Pre-1.0.** Typst 0.15.x, Touying 0.7.x, Fletcher 0.5.x. There are breaking changes
  between releases. Fletcher's changelog warns that some fixes alter diagram layout
  relative to previous versions (e.g. one release required halving `inset` values).
  **Pin versions.**
- **Fonts.** Typst uses system fonts. If the original uses a font that is not installed,
  the render changes. Verify availability or choose an explicit replacement.
- **Typst does not run R or Python.** Its scripting language is for document logic. It
  does read data natively (`csv()`, `json()`, `yaml()`, `toml()`), so tables and charts
  can be generated from files. For real computational chunks: Quarto with Typst output,
  or Calepin.
- **Not TeX-compatible.** It does not run LaTeX packages.

## Environment

- Typst runs natively on Linux, macOS and Windows (no WSL needed). Single binary.
- Editor: the **Tinymist** extension (language server + live preview), available on both
  the VS Code Marketplace and **Open VSX** — meaning it works in VS Code, VS Codium,
  Cursor and **Positron**. Tinymist has no built-in PDF viewer; add `vscode-pdf` or use
  its preview panel.

---

## Pilot: slide 13 (the method scheme) — done

```
presentations/
├── CONTEXT-typst.md                    this file
├── lib/style.typ                       palette, typography, node/edge/bracket presets
├── diagrams/method-scheme.typ          the diagram, once
├── figures/method-scheme.typ           standalone crop for the paper
├── taller_mayo_2026_col_01.typ         the deck — slide 13, final state
├── taller_mayo_2026_col_01-steps.typ   the same slide, built up over 10 subslides
└── out/                                the PDFs (build output)
```

The `.pptx` / `.pdf` originals also live here but are gitignored.

Build (**`--root .` is mandatory** — the imports cross directories and Typst
sandboxes file access to the root it is given):

```bash
cd collection-01/presentations
typst compile --root . taller_mayo_2026_col_01.typ       out/taller_mayo_2026_col_01.pdf
typst compile --root . taller_mayo_2026_col_01-steps.typ out/taller_mayo_2026_col_01-steps.pdf
typst compile --root . figures/method-scheme.typ         out/method-scheme.pdf
```

The compiler binary lives in `~/.local/bin/typst` (0.15.1, static musl build);
the packages self-download into `~/.cache/typst/packages/`.

### What was learned building it

- **The pptx is the source of truth for values, not the PDF.** `unzip` it and
  read `ppt/slides/slide13.xml` directly (`python-pptx` is not installed and is
  not needed): every shape carries `a:off`/`a:ext` in EMU (÷ 914400 × 72 = pt),
  its `a:srgbClr` line colour, `sz` in hundredths of a point, and `algn`. All
  boxes on slide 13 are `noFill` with a hairline coloured stroke — the pink
  wash they seem to have at low raster resolution is just the stroke bleeding.
- **`schemeClr` needs the theme.** Slide 13's product boxes and left brackets
  are `dk2`, which resolves through `slideLayout4` → `theme2.xml` ("Simple
  Dark") to `#303030`, *not* to `theme1.xml`'s `#158158`. Sampling the rendered
  PDF is the quick way to settle which.
- **Arial → Liberation Sans.** Metric-compatible and installed here. Keeping
  `"Arial"` as a fallback makes the deck portable but costs one
  `unknown font family` warning per compile; that warning is expected.
- **Escape the bullet dashes.** `[- 6 bandas ópticas]` is a real Typst list
  item, with list spacing; `[\- 6 bandas ópticas]` is the literal line the
  slides have.
- **Fletcher picks `circle` for squarish nodes.** Any multi-line box needs
  `shape: "rect"` explicitly, or it silently becomes a large circle.
- **Empty rows and columns are the way to control gaps.** The elastic grid has
  one spacing value; an unused row/column index inside the used range costs
  nothing but one extra grid gap. Slide 13 uses spacer rows 2 / 4,5,6 / 9,10,11
  for the inter-stage gaps, and an empty column 2 to open the gap the "Resumen"
  label needs between the two box columns.
- **Brackets: `node(enclose: (<a>, <b>), shape: fletcher.shapes.bracket)`.** No
  coordinates, no second CeTZ — the bracket tracks the boxes it groups.
- **Box widths in `em`, not `pt`.** `w-box = 17.1em` reproduces the original's
  171 pt at 10 pt *and* lets `figures/method-scheme.typ` shrink the whole
  diagram to 8 pt for the paper by changing one `#set text(size:)`.
- **`simple-theme` colours `strong` with its accent.** Turn it off with
  `config-common(show-strong-with-alert: false)`.
- **Page size**: `config-page(width: 720pt, height: 405pt)` passed *after* the
  theme's own args overrides its `paper: "presentation-16-9"` (841.89 pt wide),
  which matters because font sizes are absolute: 10 pt on a 720 pt page is the
  10 pt the slides had.

### Known, deliberate departures from the original

- Boxes are one uniform width per column. The original's are flush-left with
  hand-varied widths; uniform is what the elastic grid gives and it reads better.
- The scheme is centred on the page; the original sits ~24 pt right of centre.
