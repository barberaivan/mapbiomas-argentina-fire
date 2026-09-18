> **Extracted from** `collection-01/docs/07-vector_to_raster.md` §1.1 — "The two confinements",
> "What they remove" and "Choosing the thresholds" @ `f403d8c` (2026-09-18).
> Lab notebook — the record of building the step, not documentation of it.

# 07 — How the two exclusion rules were arrived at

The rules themselves, their thresholds and the three application points are live and stay in the
step doc. This is the evidence: the Delta problem that forced rule A's two confinements, the
measured drops, and how the thresholds were chosen.

##### The two confinements, and why they exist (2026-09-12)

**`veg_fire` 15 is not only Pampa pasture.** It is the remap of MapBiomas **11 Herbáceas
Inundables + 12 Herbáceas + 15 Pasturas** *in the PAMPA region* (`config/veg_fire_remap.csv`), so
the marshes of the **Delta del Paraná** carry class 15 exactly as a Pampa pasture does — and the
Delta burns inside 1 Jul → 15 Nov. Measured on FY2020, the unconfined rule deleted **432,966 ha of
the Delta, 65.7 % of that ecoregion's burned area and 58 % of the rule's whole national drop**,
including a single **121,058 ha** object with `frac_c15 = 1.000` whose median date is 11 Aug 2020 —
the Islas del Paraná fires, the most-reported fire event in the country that year. It is not a 2020
accident: the share of the Delta deleted was 80.1 % in FY2008, 77.6 % in FY2022, 65.9 % in FY2006,
65.5 % in FY2023. The rule bit hardest exactly in the big Delta fire years, so it distorted the
interannual series and not merely the level.

**The size cut.** Rule A's drop was bimodal: median dropped object 9.7 ha, but 39 % of its area sat
in **11 objects over 5,000 ha**. Harvest, tillage and stubble burning happen on fields; a 121 kha
scar is not a field. `RULE_A_MAX_HA = 150` costs almost nothing on the intended target.

**The AOI.** A hand-drawn 25-vertex polygon over the agricultural Pampa (Buenos Aires, southern
Santa Fe and Córdoba, eastern La Pampa), drawn by Iván in the Code Editor as the `aoiA` import of
`explore_rules_kept_vs_gone` and pulled into `config/rule_a_aoi.geojson` by
`scripts/rule_a_aoi_extract.py`. It excludes the Delta (1 of FY2020's 4,763 Delta objects falls
inside it) and Campos y Malezales entirely. **Re-run the extractor whenever the polygon is
redrawn** — the GeoJSON in the repo is the only copy the production scripts read.

**INTERSECTS, not centroid.** An object that merely touches the AOI is inside it: the rule is a
statement about a region and a scar straddling the edge is half in the agricultural Pampa. The
local side uses `terra::is.related(v, aoi, "intersects")` — the predicate, not `terra::intersect()`,
which would build 78 k clipped geometries a year to throw them away.

**The AOI must be PLANAR on the GEE side.** `C.rule_a_aoi_ee()` builds it with `geodesic=False`.
The ring has edges spanning several degrees, and a geodesic edge bows away from the straight
lon/lat line `terra` tests against: measured on FY2020, geodesic moves **6 objects / 65 ha**.
Planar, the two implementations agree **to the object** — 8,227 dropped / 136,993 ha from GEE and
from R alike.

`frac_c15` is one single `veg_fire` class — class 15, `grassland_pampa`, checked against
`config/veg_fire_remap.csv`. It deliberately does **not** use the `frac_gr_tp` predictor, which
lumps `grassland_ba + grassland_chaco + grassland_pampa`: the rule is about the Pampa alone.

**The date test is what makes this rule.** It is a composition threshold *and* a season: an object
that is almost entirely Pampa grassland is excluded if it burned inside the window and mapped if it
burned outside it. Without the season it would delete real Pampa fire; with it, it targets the
period when what the model sees on Pampa grassland is overwhelmingly agricultural.


---

#### What they remove

| | rule | measured, FY2020, whole country |
|---|---|---|
| **A** | Pampa grassland in the window, **confined** | 8,227 obj / 136,993 ha — **3.2 %** of the year's burned area |
| | *(A unconfined, for comparison)* | *15,092 obj / 746,603 ha — 17.5 %* |
| **B** | agriculture | 2,389 obj / 162,168 ha — **3.8 %** |
| | **A or B** | 10,616 obj / 299,162 ha — **7.0 %** |
| | the accepted set before them (`fire == 1 & area_ha >= 1`) | 62,605 obj / 4,268,189 ha |

Over all 28 fire-years: before the rules **69.12 Mha**; the unconfined ruleset published
**58.05 Mha (−16.0 %)**; the confined one publishes **63.33 Mha (−8.4 %)**. The **5.27 Mha**
difference is almost all real fire — the Delta's rule-A loss alone goes from **1.455 Mha to 23 ha**.

Rule A is therefore five times more aggressive than any national `frac_agri` threshold, which is why
it is a headline decision rather than a QC tweak. Its **window is the single biggest lever in the
ruleset**: moving the lower bound from 15 Aug to 1 Jul took rule A from 10,156 objects / 443,070 ha
(10.4 %) to 15,092 / 746,603 ha (17.5 %), while rule B did not move at all.

Over all 28 fire-years, rule B alone (`frac_agri >= 0.4`) drops 54,114 objects / 2.36 Mha — 4.3 % of
objects, 3.4 % of area, with **no trend across years**, so the national time series and its slope
are essentially unaffected by the choice of threshold. It is **not** a small-object filter in
disguise: the objects it drops have median 14.2 ha, p90 87 ha, max 10,704 ha.

**At these thresholds the two rules cannot both fire**, and that is arithmetic, not luck:
`frac_c15 > 0.70` leaves under 0.30 for every other class, so `frac_agri` cannot reach 0.40.
Measured on FY2020, the largest `frac_agri` among `frac_c15 > 0.7` objects is **0.299** and the
overlap is **empty** — confirmed independently in both implementations (below). They can overlap
only if the thresholds are moved far apart.

Where rule B bites, measured against the Burkart ecoregions: **Chaco carries 70 %** of the
burned-on-cropland area (2,056 kha, 7.0 % of its burned area) — and there, post-deforestation
burning of cleared plots is partly *real*, so dropping it is a scientific choice. **Yungas is the
worst in proportion** (15.0 % of its burned area on cropland, 14.2 % dropped at 0.4) and never
showed up in the national numbers because it is small. **Espinal and Monte are clean** (1.3 % and
0.6 %), so the rule costs almost nothing over most of the burned area of the country.

> **What an object rule cannot fix.** Pixel-weighted, burned area falling on annual cropland is
> 2.95 Mha (4.3 % of the total). Rule B at 0.4 leaves **1.37 Mha of cropland pixels still in the
> map**, inside mixed objects. So the rules fix *what the map looks like* — whole spurious
> crop-field "fires" disappear — but do not make a per-land-cover-class pixel statistic clean.
> That is a caption problem for the factsheet, not something a threshold can solve.


---

#### Choosing the thresholds

They were chosen by eye, with Camilo, from the Earth Engine explorers in the `fuego` repo
(`collection-01/visualization-misc/`): `explore_agri_filter_rules_single_year` draws both rules with
sliders and colours which rule fired (orange A, red B, violet both, yellow kept), and the click
readout spells out the comparison that excluded the object including the date and the window.
`explore_agri_filter_{single,multi}_year` carry the single-threshold view, both regionalisations
(13 Burkart ecoregions and the 5 MapBiomas regions) and the LULC/`veg_fire` basemaps with legends.
Clicking filters the source asset **by a point**, which rides the asset's spatial index — 0.6 s for
one fire-year, 4.0 s for all 28 — so it is zoom-independent.

Pasture is a separate question and is **not** in the ruleset: `frac_agri + frac_past >= 0.4` would
drop 5.78 Mha (8.4 %) instead of 2.36 Mha, and pasture fire is largely genuine management burning.
It is available as an option in the explorer; the prior is agriculture only.

