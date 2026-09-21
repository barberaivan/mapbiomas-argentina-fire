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
| `figures/` | the seven images, plus the scripts that regenerate the non-copied ones |
| `checklist.md` | **read this first** — the three things still missing, and what each one is waiting on |
| `build/` | LaTeX output; `build/main.pdf` is the document |

## Build

```bash
cd collection-01/ATBD
latexmk -pdf -outdir=build main.tex
```

Needs a TeX Live with `biblatex` + `biber`. The figures are committed, so none of these has to
run to build the PDF:

```bash
cd figures
Rscript make_bpts_figures.R              # the step-03 schematic panels (tidyverse)
$PYTHON export_spatial_figure_raster.py  # the region-growing raster, from the Collection 1 assets
Rscript make_spatial_figure.R            # the region-growing panels (terra, tidyterra, patchwork, ggspatial)
```

`make_spatial_figure.R` reads `raster_for_map_c01.tif`, which
`export_spatial_figure_raster.py` writes beside it. That export pulls all four panels --- RGB,
`delta2_peak`, `candseed`, the SNIC mask --- from Collection 1 for **fire-year 2014**, the
fire-year holding the February 2015 Rio Turbio and Cholila fires. It calls
`workflow/04-snic.py`'s own `build_candseed_pre()` rather than reimplementing it, and reads panel
(D) from the exported `snic_2014` asset, because SNIC growth depends on candidates outside the
window and so cannot be recomputed on a clip. The raster is committed, so the build needs
neither script.
