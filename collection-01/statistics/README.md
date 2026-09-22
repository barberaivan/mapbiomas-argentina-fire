# `statistics/`

Every number and figure the factsheet reports, computed from the **published** maps. **None of
this is part of the product** — it exists to communicate results.

**Episodic, and per launch.** Statistics are produced only for the products a given launch
actually shows, so they live here beside their code rather than in [`../docs/`](../docs/), which
holds the map-making chain and nothing else.

Three sources, and every figure must say which one it used: the **numerator** is the network's
toolkit run on our ecoregión layer, the **denominator** is ours and constant, and the **fire
counts** are local, off the polygons.

→ **[`docs/statistics.md`](docs/statistics.md)** — where every number comes from, which of the four
`factsheet_*` notebooks is the deliverable, and the verification gates.
→ [`docs/factsheet-sep2026-spec.md`](docs/factsheet-sep2026-spec.md) — what each slide *says* and
why (Spanish, tied to the September 2026 launch).

The GEE exports are the `*_export.py` files; `factsheet_tables.R` turns the downloads into
plot-ready tables and `fire_counts.R` is the vector pass. The notebooks that render it all are in
[`../notebooks/`](../notebooks/).

`excel_workbook.R` turns those same tables into **`mapbiomas-arg-fire-stats.xlsx`**
(`../data/statistics/`), the Spanish, six-sheet workbook published on the web page alongside the
maps — see [`docs/statistics.md`](docs/statistics.md) "Excel table for the web page".
