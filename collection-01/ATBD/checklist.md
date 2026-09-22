# ATBD Collection 1 — what is left

Nothing. Everything is resolved; git history is the archive.

The two public links, in §7.4 (Where the products live), were verified on 2026-09-21: the platform
(`https://plataforma.argentina.mapbiomas.org/`) and the download page
(`https://argentina.mapbiomas.org/descargas/`).

The form in which the fire-object vector database is shared is resolved: a GEE asset with public
read access, `projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/FINAL_PRODUCTS/`
`burned_area_polygons_v2`, given directly in §7.2 and used as `POLYGONS` in the §7.5 snippet.

The address of the fire section itself is confirmed too, and the boxed
*"[To be completed before release]"* paragraph that used to ask for it in §7.2 is gone.

## How to look inside a public folder

There is no browser for it — you list it:

```bash
$PYTHON -c "
import ee; ee.Initialize(project='mapbiomas-fire-485203')
p = 'projects/mapbiomas-public/assets/paraguay/fire/collection1'
print([a['id'].split('/')[-1] for a in ee.data.listAssets({'parent': p})['assets']])
"
```

`earthengine ls <path>` from the shell, or `print(ee.data.listAssets({parent: '<path>'}))` in the
Code Editor, do the same.

## Build

```bash
cd collection-01/ATBD
latexmk -pdf -jobname=mapbiomas-argentina-fire-atbd-col01 -outdir=build main.tex
# -> build/mapbiomas-argentina-fire-atbd-col01.pdf
```

`figures/*.R` regenerate the two non-copied figures; neither is needed to build the PDF.
