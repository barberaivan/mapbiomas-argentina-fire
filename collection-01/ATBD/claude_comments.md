# ATBD Collection 1 — decisions, doubts and things for Iván to check

Written by Claude while drafting `main.tex` (2026-09-18/19). Everything below is either a
decision I took that you may want to reverse, a doubt I could not settle from the allowed
sources, or a thing that is *knowingly* provisional. Ordered by how much I think it matters.

---

## 1. Things you must change before this goes out

- **The algorithm diagram is the Collection 0 one, as agreed** (`figures/algorithm_c00_placeholder.png`,
  Fig. 1). Its caption says so explicitly and lists what has changed since — no annual
  probabilistic classifier, no hand-drawn masks, a fitted object classifier instead of thresholds.
  When your diagram arrives, drop it in `figures/`, change the `\includegraphics` line and delete
  the placeholder sentences from the caption.
- **The team list on the front page is copied verbatim from the Collection 0 ATBD.** Collection 1
  had a larger group (the label collection alone involved several collaborators who are not in
  that table). Please rewrite it. Same for "Version 1.0" — set whatever version you want.
- **The GEE snapshot link and the public-location paragraph in §7 are placeholders** — see §8
  below, which says exactly what has to go in each.
- **The `stochtree` citation is a placeholder** (`references.bib`, key `stochtree`). I did not
  want to invent author names, so it is cited as a software package with a generic author and the
  version we actually use (0.4.5). Replace with the canonical citation (and add the XBART /
  warm-start paper if you want the method cited rather than the package).

## 2. Figures — what I used and why

Seven images live in `figures/`; four are copies, two are regenerated in English, one is a
placeholder.

| file | origin | note |
|---|---|---|
| `logo_mapbiomas_fuego.png` | copied from c-00 | unchanged |
| `algorithm_c00_placeholder.png` | c-00 `algorithm.png` (the **English** one) | placeholder, see above |
| `regions_argentina.png` | c-00 `area_piloto.png` | **see the caveat below** |
| `ts_panel_pat_fire01.png` | `collection-01/models-store/prediction_plots/PAT/PAT fire_01.png` | a **collection-1** figure, already in English |
| `bpts_metrics_k3.png` | regenerated, English | from `notebooks/bpts_metrics_explained.qmd` |
| `bpts_metrics_k2.png` | regenerated, English | **generated but NOT used** — see §3 |
| `spatial_analysis.png` | regenerated, English | from `collection-00/docs/figures/map_spatial_analysis.R` |

Two scripts are kept next to the figures so anyone can rebuild them:
`make_bpts_figures.R` and `make_spatial_figure.R` (the latter reads the c-00 raster in place, it
does not copy the 38 MB GeoTIFF).

**The study-area map is a compromise you may dislike.** `regions_argentina.png` *is* the pilot's
figure — Argentina with the five MapBiomas regions outlined in black and the Collection 0 pilot
area as a blue rectangle. Since we are not making new figures, I kept it and wrote an honest
caption: "the five regions defined by MapBiomas Argentina; the blue rectangle is the Collection 0
pilot area, shown here only for reference". If that reads badly, the alternatives are (a) redraw
it without the rectangle, or (b) drop the figure and keep the region list in prose.

**The region-growing figure is also a c-00 figure, and its panel (B) is a Collection 0 quantity.**
The pilot had an *annual burn probability* raster; Collection 1 has no such layer — the equivalent
per-pixel evidence is `delta_peak`. I regenerated the panels with English labels but did **not**
relabel panel (B), because the underlying raster really is the pilot's annual probability. The
caption says this in italics: the logic of the step is unchanged, the quantity the cuts are taken
on is not. If you would rather have a Collection 1 version, it is a small job — the `candseed`
asset and a `delta2_peak` mosaic over the same ROI would reproduce the four panels exactly.

## 3. The K = 2 schematic exists but is not in the document

I generated both `bpts_metrics_k3.png` and `bpts_metrics_k2.png`, then **used only K = 3** and
folded the K = 2 explanation into its caption. Reason: the two figures are visually near-identical
(same series, same `t*`, narrower windows), the second one costs a whole page in a document you
want at ~20 pages, and a reader gains one sentence. The file is there if you disagree — re-adding
it is four lines of LaTeX.

## 4. Numbers I computed from the data rather than from the docs

The docs give "~5.7 M obs over 5 regions" and no fire/point counts, so I computed the training-set
figures directly from `collection-01/data/training_observations_*_v1.csv` and
`training_fires_*.csv`:

- **198 fires** — BA 13, CUYO 30, PAMPA 37, PAT 47, CHACO 71
- **147,222 points** (unique `region × fire_id × point_id`)
- **6,177,098 observations** extracted
- **5,923,062 pass the `fit` gate**, of which **541,789 (9.1 %)** are labelled burned

Two things to check. First, the docs say "~5.7 M"; I get 6.18 M raw / 5.92 M fitted. The doc
figure is probably older or rounded differently — **please confirm which number you want to
publish**. Second, 147,222 points over 198 fires is ~743 points per fire, which is nearly double
the pilot's 400/fire; if that is because some fires were sampled much more densely, the
"roughly forty observations per point" efficiency sentence still holds (41.96) but you may want to
say something about the spread.

I also verified directly that **all 23 deployed coefficient CSVs carry an identical 52-row term
set** (51 terms + intercept), which is what the "every class shares one predictor set" claim in
§3.5 rests on.

## 5. Scope decisions

- **§7 Products was expanded on your second pass** (2026-09-19), and for it I did read
  `docs/07-published_products.md`, the 07b/07c sections of `docs/07-vector_to_raster.md` and the
  "What Argentina delivers" section of `docs/08-postprocessing.md`. It now has four subsections:
  the six network subproducts (with the twelve-asset table and the pixel encodings), the fire-object
  vector database, where the products live, and a worked GEE example. It states plainly that these
  are the network's products and does **not** justify them, as you asked.
- **Validation and statistics are absent**, as instructed — including from the limitations section,
  where I was careful not to imply accuracy figures we have not published. The only accuracy
  numbers in the whole document are the object classifier's cross-validated ones, which are a
  model diagnostic, not a product validation. §9 says the algorithm has commission problems in
  croplands without quantifying them.
- **I did not tell the "story" of how the predictor sets were reached**, per the brief. §3.6 says
  the design "began as several hundred terms... and was reduced in two steps", and §6.5 says the
  five vegetation groups "replaced the 23 raw class fractions"; neither narrates the search.
- **No `n_break`, no threshold values, no window months, no SNIC neighbourhood size, no longitude
  cuts.** Every numeric setting of the segmentation stage is described qualitatively and delegated
  to `docs/04`. That is the "conceptual, not a specification" promise in §1.1 being kept. The one
  exception is the object-model threshold table (§6.6), because the *shape* of that result — the
  cut rises with size — is an argument, not a setting.

## 6. Things I asserted that rest on a single sentence in the docs

Worth a second pair of eyes, because if any of these is stale the ATBD repeats it:

- *"a probability-mode random forest is not exportable to an asset"* (§3.5) — from
  `docs/02-model_fitting.md` Foundations. Still true in GEE?
- *"May is the country-wide activity trough in MODIS/VIIRS and in our own mid-dates"* (§5.2) —
  from `docs/04-snic.md`. I state it as fact.
- *"the residual trend that survives the fix is unattributed, not proven clean"* (§9.2) — I
  deliberately did **not** give the Spearman 0.407, because quoting it invites someone to read it
  as a result. Say if you want the number in.
- *"one hectare is about eleven pixels"* (§6.8) — from `docs/08`, which I did not read; I got it
  from the CLAUDE.md index line and it is consistent with the 831–517 m²/px range. Check.

## 7. Style notes

- English throughout, including the two regenerated figures. The Spanish originals are untouched.
- Preamble, page geometry, fonts (`lmodern` + `\sfdefault`), `biblatex` authoryear, the frontpage
  layout and the section shape all follow `collection-00/docs/documentation_pilot_latex/main.tex`
  exactly. The only preamble change is `babel` english and an English month macro.
- Register: I kept the pilot ATBD's habit of stating a design decision in bold and then arguing it
  in one paragraph, and its willingness to say plainly what did not work. The Foundations sections
  of the step docs carried most of that argument already, which is why the ATBD reads like them.
- **31 pages**, ~9,900 words of prose. The Products expansion cost 3 pages, not the 2 you budgeted
  — I trimmed it twice and the third page would not come back without dropping content you asked
  for (the encoding table, the three user caveats, or half the code listing). Say which and I will
  cut it. Otherwise the cheapest page is in §9 and §10 (limitations and improvements, ~4 pages
  between them), which are the most compressible and the least load-bearing.
- One deliberate omission from the pilot ATBD: **no effort/time budget section.** The pilot's
  closing estimate of hours and contracts was a planning document for Collection 1; it has no
  equivalent role here, and §11 "Considerations for Collection 2" takes that slot instead.

## 8. The two placeholders in §7 Products (your second pass)

Both are marked in the PDF, not silently left blank.

- **Where the products live for the public.** §7.3 says the structure — the production folder is
  ours and restricted; the six subproducts are copied by an explicit subproduct list into the
  network's public collection and rendered on the MapBiomas Argentina platform; the vector database
  is ours and shared directly by link. The only public URL I used is
  `https://argentina.mapbiomas.org/`, which is already cited in the bibliography and which I know is
  real. **I invented no other URL.** The section closes with a boxed
  *"[To be completed before release]"* paragraph naming exactly the four things your teammates have
  to supply: the platform URL of the fire section, the public asset path of the network copy, the
  download page for the statistics, and the form in which the vector database is shared. Delete the
  box once they are filled in.
- **The GEE snapshot link is `https://code.earthengine.google.com/SNAPSHOT-ID`.** I cannot create a
  snapshot — it needs an interactive Code Editor session. The listing printed underneath it *is* the
  script: paste it into a blank tab, check it runs, then **Get Link → Get Link** and replace
  `SNAPSHOT-ID` with the id you get. I wrote the listing against the asset paths and band names in
  `constants.py` and `docs/07-published_products.md`, but **it has not been executed**, so run it
  once before you publish the link.

## 9. Build

```bash
cd collection-01/ATBD
latexmk -pdf -outdir=build main.tex     # -> build/main.pdf
```

`figures/*.R` regenerate the two non-copied figures; neither is needed to build the PDF.

## 10. Two small housekeeping items I could not do

I was only allowed to create files inside `ATBD/`, so these are left for you:

- **Nothing in the repo points at this document yet.** `collection-01/README.md` and the doc table
  in `CLAUDE.md` should gain a line for `collection-01/ATBD/` — it is the conceptual entry point
  above `docs/`, and a reader arriving at the repo has no way to find it.
- **`.gitignore`**: I added one inside `ATBD/` that keeps `build/main.pdf` and drops the LaTeX
  aux files. Check it does not fight the repo-root `.gitignore`.
