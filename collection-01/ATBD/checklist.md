# ATBD Collection 1 — what is left

One item. Everything else is resolved; git history is the archive.

## The public addresses — waiting on Gonza and Luna

Two are already in §7.3 and were verified on 2026-09-21: the platform
(`https://plataforma.argentina.mapbiomas.org/`) and the download page
(`https://argentina.mapbiomas.org/descargas/`).

The boxed *"[To be completed before release]"* paragraph asks for the two that do not exist yet:

- **the address of the fire section.** There is none today — neither the site nor the downloads
  page mentions fuego. The siblings publish it as a page of its own
  (`paraguay.mapbiomas.org/mapbiomas-fuego/`, `peru.mapbiomas.org/descargas-mapbiomas-fuego/`,
  `plataforma.brasil.mapbiomas.org/fogo`), so ours will probably follow.
- **the form in which the fire-object vector database is shared.** It is not one of the network's
  six subproducts, so it is not copied into the public collection; we share it ourselves.

Delete the box once both are filled in. Worth knowing: the ATBD itself will hang on
`https://argentina.mapbiomas.org/atbd-entienda-cada-etapa/`, today land-cover only.

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
latexmk -pdf -outdir=build main.tex     # -> build/main.pdf
```

`figures/*.R` regenerate the two non-copied figures; neither is needed to build the PDF.
