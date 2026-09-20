# ATBD — MapBiomas Argentina Fuego, Collection 1

The Algorithm Theoretical Basis Document for Collection 1, in English. It is the *conceptual*
description of the mapping algorithm: what each stage measures, why it measures it that way, and
what it hands to the next stage. It is deliberately **not** a full specification — the exact
parameters, thresholds, encodings and failure modes live in
[`../docs/`](../docs/), one note per workflow step, and the ATBD says so in §1.1.

It follows the Collection 0 ATBD (`collection-00/docs/documentation_pilot_latex/`) in structure,
preamble and style.

## Files

| file | what it is |
|---|---|
| `main.tex` | the document |
| `frontpage.tex` | title page (logo, collection, version, team) |
| `references.bib` | bibliography |
| `figures/` | the seven images, plus the two R scripts that regenerate the non-copied ones |
| `author_order.R` | the author-order draw between Lican Martínez and Ramón Peña Agrest: a public drand round fixes it, so the result is reproducible and nobody could have steered it. Its header comment is the documentation |
| `claude_comments.md` | **read this first if you are reviewing the draft** — decisions taken, open doubts, what is provisional |
| `build/` | LaTeX output; `build/main.pdf` is the document |

## Build

```bash
cd collection-01/ATBD
latexmk -pdf -outdir=build main.tex
```

Needs a TeX Live with `biblatex` + `biber`. The figures are committed, so neither R script has to
run to build the PDF:

```bash
cd figures
Rscript make_bpts_figures.R     # the step-03 schematic panels (tidyverse)
Rscript make_spatial_figure.R   # the region-growing panels (terra, tidyterra, patchwork, ggspatial)
```

`make_spatial_figure.R` reads `collection-00/docs/figures/raster_for_map.tif` in place.
