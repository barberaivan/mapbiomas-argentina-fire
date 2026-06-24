# Burn probability at the observation level

An observation is a pixel-date with valid Landsat data (post-filters).

Step 3 of the workflow does this by year and mapbiomas carta tile:
- compute the burn probability for every landsat image,
- summarize by pixel in the burn-probability time-series metrics (bp_ts_metrics)
- set properties:
    - date (system:time_start) at YYYY-07-01 for visualization in the inspector
    - year
    - mapbiomas carta id
- export to target image collection: projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics

Mapbiomas carta: 
described in constants.py

years: 1999:2025 (check in constants.)

Apply this over all tiles intersecting the
argentina buffer FC:
projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais_buffer

The time series metrics are explained in /docs/03-bp_ts_metrics.md

Here I explain how to compute the burn probability time series in a given year.

# Procedure by year [y] and tile

1. Get mapbiomas mosaic from year y-1.
2. Get mapbiomas land cover (with buffer) from year y-1.
2. Get mapbiomas regions raster (with buffer).
3. Compute the veg_fire class, from region_class (mapbiomas land cover + region * 100).

4. Compute the parameters-image: a multi-band image where each band is a parameter. remap from veg_fire class to parameter values. There are ~128 parameters (including intercept). 

5. Compute the terms for the logistic regression that depend only on this previous-year data:

var prev_terms = intercept + mosaic_prev main terms + mosaic_prev * mosaic_prev interaction terms (check whether we still have these interaction terms). The efficient way to do this: for products, create a factor1 * factor2 * betas multiplication, where factor1 and factor2 are multi-band images, and so is betas (only the corresponding parameters), so we dont loop over terms. This is then cat to intercept and to mosaic_prev main terms * betas (prev_betas), then .reduce(sum).

This image will be summed to the linear predictor of all images in the year (reused).

6. Create the time-series landsat image collection for the focal tile, using all the landsat image collection in the year +- padded M = 4 months:
Filter all landsat images intersecting the tile from september y-1 to april y+1 (both months fully included). Apply quality filters and harmonization, as in getLandsat function. 

7. Mosaic per unique date: this avoids having 2 obs in the same day. Compute the set of unique dates in the obtained image collection and create a mosaic by day (reducer mean?). Can we skip mosaicking when the date has a single image? Should these date-based mosaics be clipped to the tile or is it inefficient? Perhaps the export region (tile) in the end makes the clip efficient.

## loop over each image in this landsat-img col:

8. Within each image in the time series, compute spectral indices needed for logistic regression.

9. Build the logistic regression terms. Main focal terms are easy, but to compute the interactions (products), we should make a code that creates a small compute graph. So, create a factor1 image that will be multiplied by a factor2 image, times the corresponding beta parameters.

10. Add prev_terms to the linear predictor and compute probability.

11. Compute fractional year from date, and include as band. The output is a 2-band image with [prob, date] bands, date as fractional year.

[end loop oever images]

11. Split the imgCol in 3: previous year (latest M months), focal year (full), and next year (fist M months).

12. Turn them into array-image. Each pixel is a 2D array, with [prob, date] variables along the second dimension, and dates in the first dimension.

13. Create focal-padded array: grab latest 3 obs from the prev array, concat to focal array, and concat to first 2 obs from next array. (The final array must end sorted by date). The asymmetric padding (3 left, 2 right) ensures maxback3 is fully defined at the first focal obs — see docs/03-bp_ts_metrics.md for the rationale.

14. Compute the bp ts metrics from the array. This procedure is described in its own md. Output: a multi-band image, where each band is a metric or quality band.

15. Export with large maxpixels, region: focal tile. 

# To resolve

- What happens with missing data? The prob computation should not give zero value to missing pixels in an image; it should be masked. In the final product, masked pixels should have n = 0 (no clean observations were found in landsat series). 

- In the case of veg_fire in {24, 25}, this should be indicated, perhaps at the n band, taking value = -1 for non-burnable (24) and -2 for non-observed (25). Right? Is there a way to pre-apply this mask from the beginning, so that even to compute prev_terms those pixels are ignored?

- Store the prev-year veg_fire? Could be useful, but it takes memory, and is cheap to compute. Prefer not to.

# Code considerations

Iván (author, main developer) is worried about the following aspects, so they should be revised carefully: 

1. Computing the coefficients the right way so that predictors are used in their raw scale (no centering before products). Check the exported csv coefficients are ready to deploy.

2. The remapping of veg_fire to coefficients: tidy well.

3. The ordering of coefficients so that they mimic exactly the order of bands. Perhaps this is not so important if we subset coefficients-bands and terms-bands by name. BUT CAREFUL here.

4. Careful with array operations; they are tricky.

# Code style for testing and readability

Code must be very commented so it is easy to read by humans and understand it. Do not worry by being succint; it's better to be expressive. But DO care a lot about coputing efficiency. 

I would like to be able to run a single tile-year in positron, like
bpts(1999, tile_id) - I don't know how tiles in the carta are named. Or
bpts(., .), with "." meaning export all.

It would also be good to have most important functions able to run interactive tests. For example, a testing interactive code in scripts/ to call these functions and do:
- print a single landsat image (nir-swir1-swir2 false-color) in the map
- add the burn probability layer
- add the veg_fire class

Then select a year and a tile and compute the full output:
- put the bpts image in the map, 
- put the whole prob imagecolletion to visualize the NBR, NBR2 and prob time series in the inspector.

This testing code is another development, but these requirements may lead what to expose in the workflow/03- code. 

The way I usually worked was writing and testing step by step in the code editor. The whole code was a loop over years (single region for pilot), so I fixed the year and tested pieces. Perhaps the best here is to have a separate testing code calling the functions, with an example of how to use it.

# Collection-00 reference

Read the col 0 code to see how I computed things before. Most will not be useful, but maybe you can find some good practices there, specially with arrays. 

# functions.py and constants.py

I don't know when to write a function in functions or in the workflow code. I liked the style of col0 where each workflow code was a loop over years (now over tiles too) with a succint call to functions that expressed clearly each step. That's what I like, but is it fine? That's readable... Do you think there are better ways? That also makes neater to re-use the code for testing and visualiztion in other scripts. 

Note here I gave data that may be in the constants.py code. For example, months to pad (M = 4), obs to pad, what ts metrics (see its md)