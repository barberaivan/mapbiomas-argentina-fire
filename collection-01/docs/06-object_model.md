# 06 — Polygons classification using an object-based model

From the vectorized snic objects with metadata, we classify which polygons
are actually fire. To do so we need to collect data at the polygon-level,
so later we can fit and deploy a classification model 
(fire vs. non-fire polygons).

In all this doc I refer to polygons but they may be actually multi-polygons,
these are the result of running terra::patches() in each yearly snic image.
Note these polygons should have a unique ID: if patches() repeats ids among years,
the year label has to be padded to the id as prefix.

## Data collection

### Asset ingestion

Polygons with the extensive metadata must be uploaded to GEE as assets, to 
display them in the map and choose which are fires and which not.
The local vectors have a lot of variables; we do not need to upload the asset
with all of them, but just a few. That will make the ingestion faster
(but perhaps this is not a problem, perhaps polygons are really light,
I'm not sure).

### Interactive data-collection GEE code

The data collection needs a GEE script that will be replicated across 
a few users (likely not so many, so it's easy to coordinate). 
It should show the candseed band (candidate, seed) in the snic asset and also
a few layers present in the explore_snic_IB-02 code. 

The data will be obtained by intersecting point-based feature collections 
that have a year property with the polygons in those years. The code should expose
a year range (y_lwr, y_upr) it shows all the polygons in those years.
The user may add geometry points intersecting those polys, and must set as property
the year range for those points. 

In fire-active regions, the user should explor small year ranges, or even one 
year at a time. In non fire-active regions, the user may visualize longer 
time-steps. The polygons from each year should be colored differently. 

We also need a helper panel in the map (left side) that shows rapidly a few
metadata variables of each cliked polygon. The inspector is too slow to show
this (lots of desplegable menus), so we must build it. It must show: year, fire_id, seed_mean, size (ha), and perhaps some more variables we choose later, like
agriculture proportion (this should be the sum of all agriculture classes). 
The variables shown there (numbers) should be chosen in the code, so one can
easily add variables to that panel if that is helpful. 

I still don't know how to deal with exports. I imagine each user will have many
point-feature collections, separated by year/year-range AND polygon class. 
That's to avoid putting metadata at point level, the idea is to put a lot of points
rapidly over polygons of the same class-year/year-range. Same as when we collected 
training_locations.

If users are just a few, Claude could edit all the scripts in the end, merge the
feature collections, set good tags at point level, merge all, and export (I should
run the export in GEE).

But let's think of this design.

## Model fitting and classification

I'm thinking of using all the variables to feed a XGB-additive-trees, to fit and classify locally, in python or R. We should tune hyperparams with CV. The year
variable should be included, though I think it mostly operates through n (in 1999,
for example, many fires had few seeds, but they are fires). It's not necessary to
validate this model, the CV is only to tune hyperparams. And perhaps we could put 
hard constraints on size, like remove polygons < 1 ha, and apply the model only 
to polygons with size >= 1 ha and size < 2000 ha (large ones are rarely non-fire),
but that may be risky. If so, we could remove them even in the data-collection 
step, so users do not spend time in data that won't be used. 

If we decide on the 1 ha limit, we could avoid uploading to asset a large amount
of features. Maybe we should check the file size of all polygons vs without the 
< 1 ha. Also check the number of features, which may be important for GEE? 

The local-drive polygons are then classified, and we collect the IDs of those 
that are fire, and filter then the GEE asset. 

## Rasterization

This is step 7, but it implies to rasterize the final fire polygons and make the 
images as mapbiomas requires (month of burn and so).
