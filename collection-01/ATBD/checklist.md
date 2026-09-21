# ATBD Collection 1 — what is left

Three items. Everything else is resolved; git history is the archive.

## 1. The algorithm diagram

Figure 1 is still the Collection 0 diagram (`figures/algorithm_c00_placeholder.png`), and its
caption says so and lists what changed since — no annual probabilistic classifier, no hand-drawn
masks, a fitted object classifier instead of thresholds.

When the Collection 1 diagram exists: drop it in `figures/`, change the `\includegraphics` line in
`main.tex`, and delete the placeholder sentences from the caption.

## 2. The public addresses — waiting on Gonza and Luna

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

## 3. The Earth Engine snippet — waiting on Vera

The §7.4 listing has not been run, because the assets it reads cannot be reached:
`projects/mapbiomas-public/assets/argentina/fire` exists — it shows when listing
`…/assets/argentina` — but no read of it succeeds, while `…/paraguay/fire` and our own
`…/argentina/collection1` read fine with the same credentials. Earth Engine merges "absent" and
"not shared with you" into one message, so from outside the two are indistinguishable.

Three things to settle with her, then one action here:

- **the exact asset ids** she copied — the folder cannot be listed, so they cannot be discovered;
- **read access**, or confirmation that it opens at launch;
- **the version token.** The snippet carries `var V = '_v1'`, inferred from every published
  country (`mapbiomas_<country>_fire_collection1_<subproduct>_v1`, checked on Paraguay, Chile and
  Brazil) and consistent with `docs/07-vector_to_raster.md` "Why version rather than overwrite in
  place". Not verified for Argentina.

The band names are verified against Paraguay's published images: `burned_area_<year>`,
`burned_monthly_<year>`, and `fire_frequency_<from>_<to>` for every window, so
`fire_frequency_1999_2025` will exist. The polygon asset exists and is readable.

**Then**: paste the listing into a blank Code Editor tab, check it runs, **Get Link → Get Link**,
and replace `SNAPSHOT-ID` in the `\url{}` above the listing with the id it gives.

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
