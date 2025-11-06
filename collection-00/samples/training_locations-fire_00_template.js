// See the instructions for sampling burned and unburned points in 
// https://docs.google.com/presentation/d/1fdXjeh7q-fqbQgsHaloRDQVIeQFRD5nAdWLhZVj-S3I/edit?usp=sharing

// See the 'README' code for an overview of the mapping algorithm and 
// summarized instructions.

// Inputs (edit here) -------------------------------------------------------

// Define fire ID to target sampling. They are listed in 
// [...]
var fire_id = "..."; // Write thNe ID you chose 
var author = "...";  // Your full name

// Dates --------------------------------------------------------------------

// You probably don't need to edit this

// Get focal fire
var training_fires = ee.FeatureCollection('projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_fires');
var feat = training_fires.filterMetadata("fire_id", "equals", fire_id).first(); 

// Date ranges of pre- and post-fire periods.
// Edit if they are wrong.

// End of pre-fire period
var pre_upr = ee.Date(feat.get("pre_upr")).advance(1, "day"); // Pre-fire end
var pre_lwr = pre_upr.advance(-1, "year");

// Begining and end of post-fire period
var post_lwr = ee.Date(feat.get("post_lwr"));
var post_upr_long = ee.Date(feat.get("post_upr_long")).advance(1, "day");
var post_upr_short = ee.Date(feat.get("post_upr_short")).advance(1, "day");

// Beggining of pre-fire period, defined as months before its end 
// (months before pre_upr)
var train_window_pre = ee.Number(12); 

// Expand the NBR time series for as many years before and after 
// the focal year (July-June) as defined here. This is only 
// used to visualize the NBR time series in the inspector.
var y_forward = ee.Number(1); 
var y_backward = ee.Number(-1);

// Focal year
var year = pre_upr.get('year');
var month = pre_upr.get('month');
// If month >= July (7), fire-year is next calendar year
var fireYear = ee.Number(year).add(month.gte(7));

// Time series limits
var begin = ee.Date.fromYMD(fireYear.add(-1).add(y_backward), 07, 01);
var end = ee.Date.fromYMD(fireYear.add(y_forward), 07, 01);

// Load functions --------------------------------------------------------

// Used to get the quality-masked, harmonized, Landsat imagery, with
// NBR computed
var funk = require("users/mapbiomas-arg/fuego:functions.js");

// Data extraction --------------------------------------------------------

// Get roi
var roi = feat.geometry();

// Decide which upper limit for post-fire period to use depending on fire ID:
// 1:10 are forest (long), 11:20 are grassland (short).
var fire_num_str = fire_id.slice(5);  // "01" -> 1
var fire_num = ee.Number.parse(fire_num_str);
var isForest = fire_num.lte(10).or(fire_num.gte(26));
var post_upr_use = ee.Date(ee.Algorithms.If(
    isForest, post_upr_long, post_upr_short
  ));

// Landsat imagery
var landsat = funk.getLandsat(roi, begin, end, funk.addNBR);

// NBR time series to visualize in inspector
var NBRts = landsat.select("nbr");

// Filter Landsat image collections for pre- and post-fire periods
var preFireCol = landsat.filterDate(pre_lwr, pre_upr);
var postFireCol = landsat.filterDate(post_lwr, post_upr_use);

// Compute median composites for pre- and post-fire periods
var preFireMedian = preFireCol.median().clip(roi);
var postFireMedian = postFireCol.median().clip(roi);

// Compute dNBR
var dNBR = preFireMedian.select('nbr')
  .subtract(postFireMedian.select('nbr'))
  .rename('dnbr');

// MapBiomas classification
var vegtype_all = funk.mapBiomasReclass();
var year_mb = ee.Date(pre_upr).get('year').subtract(1);
var bandName = ee.String('classification_').cat(year_mb.format());
var vegtype = vegtype_all.select(bandName).clip(roi);

// Non burnable layer
var temp = vegtype.eq(0);
var nonBurnable = temp.updateMask(temp).clip(roi);

// Visualization --------------------------------------------------------

Map.centerObject(roi, 12);
Map.setOptions("satellite");

// Polygon mapped by Barberá et al. (2025), only available for fire_ids 01 to 11.
var poly = fires_barbera.filterMetadata("fire_id", "equals", feat.get("polygon_id"));
Map.addLayer(poly, {color: "red"}, "Polygon", false);

// NBR time series (for inspector)
Map.addLayer(NBRts, {}, "NBR time series", false);

// dNBR layer
var min_dnbr = ee.Algorithms.If(isForest, -0.5, -0.2).getInfo();
var max_dnbr = ee.Algorithms.If(isForest, 0.5, 0.2).getInfo();
var dNBRVis = {
  min: min_dnbr, 
  max: max_dnbr,
  palette: ['blue', 'white', 'red']
};
var dNBRon = isForest.getInfo() ? false : true;
Map.addLayer(dNBR, dNBRVis, 'dNBR (pre - post)', dNBRon);

// False-color composite for burned area detection (SWIR2, NIR, Red)
var vis = {
  bands: ['swir2', 'nir', 'red'],
  min: [0.05, 0.05, 0.05],
  max: [0.35, 0.5, 0.35],  
  gamma: 1.2
};
Map.addLayer(preFireMedian, vis, 'False color pre-fire');
Map.addLayer(postFireMedian, vis, 'False color post-fire');

// Non-burnable 
Map.addLayer(nonBurnable, {palette: ['000000']}, "Non burnable");

/*
  NBR ts panel:
  Nice tool to see which observations will be exported for every point,
  but very expensive. Uncomment line below to use
*/
// funk.makeNBRtsPanel(roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr_use);

// Export ------------------------------------------------------------

// Merge burned and unburned
var points = burned.merge(unburned);  

var asset_id = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_locations-' +
  fire_id;

// Add metadata (common to all features)
var out = points.set({
  fire_id: fire_id,
  polygon_id: feat.get("polygon_id"),
  description: feat.get("description"),
  author: author,
  // Dates, in case they were updated
  pre_lwr: pre_lwr,
  pre_upr: pre_upr,
  post_lwr: post_lwr,
  post_upr_long: post_upr_long,
  post_upr_short: post_upr_short
});

// Export.table.toAsset({
//   collection: out,
//   description: 'points-' + fire_id,
//   assetId: asset_id
// });