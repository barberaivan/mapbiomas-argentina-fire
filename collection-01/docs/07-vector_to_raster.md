# Notes on the final processing steps

In `06-object_model.md` we mentioned that we would upload the polygons
with metadata to GEE. Even if we could for timing, that's not reasonable.
They are lots, heavy, with lots of unnecessary variables.

Instead, we'll just collect data in GEE using the SNIC layer, not the polygons.
The docs/06**md should be edited so that is the preferred option, with no 
mention to the full polygons upload. 

Then the output of workflow/05 should consider how we will manage the
next steps. 

The object_model will classify polygons locally, and it will need only
the data table, not the geometries, so the polygons and the table can live
in separate files, with no redundancy. The only metadata that polygons should
have is the oid/pid (oid is preferred). 

Once classified, the fire polygons will be uploaded to GEE to filter the
snic images. The official mapbiomas layer is a raster with month of burn 
each calendar year. We will build that combining the uploaded fire polygons
and the snic_metrics images.

In addition, we will have an unofficial vectorial database (Feature Collection = FC)
in GEE of these polygons with metadata. So, we will have to upload only the 
fire-polygons (classified) with the metadata that we want for the FC. 

So far, the workflow/05 generates a gpkg file by year that contains both 
polygons and metadata: this should be reduced to save space. I.e., the geojson
should only store polygons and oid. 

---

More changes to workflow/05:

Keep all the shape/sparcity metrics as in docs/05, but only these 
raster-based (less than in docs/05):
- **veg abundance** — per-class fractions `frac_c1…c23` (absent = 0) [without
  first 5 ranked]
- **area** — `area_ha`, not in m2 = Σ per-cell `cellSize` (for a lon/lat grid 
  computed on a 1-column strip by latitude, O(nrow)) and `n_pixels`.
  (it probably outputs to m2, but turn into ha)
- **`abs_date` summaries** — `{median, min, max}`
- **`year_calendar`** and **`year_fire`**: compute the calendar-year and the 
    fire-year for each pixel's date. Then, take the mode across all pixels. 
    This is to assign the most common fire- or calendar-year to the polygon.
- **`n_mean`** the average number of observations of the polygon.
- **neighbourhood sparseness** `burned_around_{1,2,3}` — mean over the object's pixels of the
  burned fraction in the (2r+1)² window. Direct tiles carry it pre-computed in GEE (cell counts
  → ÷(2r+1)²); the legacy COG computes it here.


Pixels dilation for connecting components

The candseed = 3 (candidates from next-year spring) in patagonia bring problems in
the steppe. So, remove these pixels east of longitude -70.6. 
The correct would be to re-run SNIC, but that is expensive. This is clumsy but 
cheap solution.

In the union-find approach we have more conditions under which 
pixels must not to have enlarged context:

Ag/grass/pasture = veg_fire ∈
**{1, 2, 3, 12, 13, 15, 17, 18, 19}** 
(`agriculture_*`, `grassland_chaco`, `grassland-inund_chaco`,
    `grassland_ba`, `grassland_pampa` and `pasture_`),
OR
candseed = 3 pixels. 

None of this have enlarged context; they are connected only to their 8-neighbors.

--- 

Given all these changes, year 2000 should be re-run.
its gpkg and csv files could be removed later, as well as the test ones.