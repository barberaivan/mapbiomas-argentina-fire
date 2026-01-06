// Summarize metrics in merged polygons, and export polygons with metrics

// Load functions and constants ------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Define constants ------------------------------------------------------

var dirbase_load = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/polygons_metrics_03/';
var dirbase_imgcol = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/PRODUCTS/burned_area_annual';
var img_asset_id = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/PRODUCTS/fire_freq';

var roi = cons.roi;

// Filter for fire polygons

var a1 = 1,
    a2 = 50,
    a3 = 300;

var f = ee.Filter.or(
  // Case 1: a1 <= area_ha < a2
  ee.Filter.and(
    ee.Filter.gte('area_ha', a1),
    ee.Filter.lt('area_ha', a2),
    ee.Filter.gt('convexity', 0.5),
    ee.Filter.gt('burned_around_3', 0.7),
    ee.Filter.gt('circularity', 0.01),
    ee.Filter.lt('shape_index', 7)
  ),

  // Case 2: a2 <= area_ha < a3
  ee.Filter.and(
    ee.Filter.gte('area_ha', a2),
    ee.Filter.lt('area_ha', a3),
    ee.Filter.gt('convexity', 0.4),
    ee.Filter.gt('burned_around_3', 0.6),
    ee.Filter.lt('shape_index', 7)
  ),

  // Case 3: area_ha >= a3 → automatically accepted
  ee.Filter.gte('area_ha', a3)
);

// Load input image collections ------------------------------------------

var tsm  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/time_series_metrics_03"),
    snic = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/snic_03");

// Burned area annual (image collection) ---------------------------------

// Evaluate the year_list client-side so we can create client-side names
for (var y = cons.startYear; y <= cons.endYear; y++) {

  // y is a client-side JS number/string here
  // var y = 2021;

  var yNum = ee.Number(y);
  
  // Extract focal tsm image
  var date_img = tsm.filterMetadata('year', 'equals', y).first().select('date_mid'),
      snic_img = snic.filterMetadata('year', 'equals', y).first();
  
  // Get polygons
  var dir = dirbase_load + 'polygons_metrics_' + y;
  var poly = ee.FeatureCollection(dir).filter(f);
 
  // -------------------------------------------------------------------
  // Make image mask including only pixels inside the polygon
  // -------------------------------------------------------------------

  // Rasterize polygons to an image mask
  var polyMask = ee.Image(0).byte()
    .paint(poly, 1)
    .selfMask();

  // Apply polygon mask to date image
  var dateMasked = date_img.updateMask(polyMask);
  
  // -------------------------------------------------------------------
  // Mask out pixels where year(date_img) != y
  // -------------------------------------------------------------------

  // Extract year from fractional year image
  var yearImg = dateMasked.floor();

  // Keep only pixels burned in year y
  var dateMasked2 = dateMasked.updateMask(yearImg.eq(yNum));
  
  // -------------------------------------------------------------------
  // Transform the masked date_img from fractional year to month (integer)
  // -------------------------------------------------------------------

  // Fractional part of the year
  var frac = dateMasked2.subtract(yNum);

  // Convert to month: [0,1) -> [1,12]
  var month = frac.multiply(12)
    .floor()
    .add(1)
    .clamp(1, 12)
    .rename('month');

  // -------------------------------------------------------------------
  // Compute connected components on the masked image
  // -------------------------------------------------------------------

  // Binary burned mask
  var burnedMask = month.mask().selfMask().rename('burned').toInt();

  // Label connected burned patches (8-connected)
  var labels = burnedMask.connectedComponents({
    connectedness: ee.Kernel.square(1), // 8-connected
    maxSize: 1024
  }).select('labels');

  // -------------------------------------------------------------------
  // Compute scar size (ha) per connected component
  // -------------------------------------------------------------------

  var pixelAreaHa = ee.Image.pixelArea().divide(1e4);

  var scarSize = pixelAreaHa
    .addBands(labels)
    .reduceConnectedComponents({
      reducer: ee.Reducer.sum(),
      labelBand: 'labels'
    })
    .rename('scar_size');

  // Mask scar size outside burned pixels
  scarSize = scarSize.updateMask(burnedMask);

  // -------------------------------------------------------------------
  // Create output image
  // -------------------------------------------------------------------

  var out = month
    .addBands(scarSize)
    .set('year', y)
    .set(
      'system:time_start',
      ee.Date.fromYMD(y, 1, 1).millis()
    )
    .clip(roi);
  
  // Client-side strings for task description and assetId
  var desc = 'burned_area_' + y;
  var assetId = dirbase_imgcol + '/' + desc;

  Export.image.toAsset({
    image: out, 
    description: desc,
    assetId: assetId,
    maxPixels: 1E13,
    scale: 30
  });
}

// Scar size masks clusters larger than 1024 pixels.

// fire_freq (image) ------------------------------------------
// This must be run after the previous export is complete

// Load burned area annual collection
var ba = ee.ImageCollection(dirbase_imgcol)
  .select('month');

// Binary burned mask per year (month exists → burned)
var burned = ba.map(function(img) {
  return img.gt(0)
    .rename('burned')
    .copyProperties(img, ['year', 'system:time_start']);
});

// Frequency: number of years burned
var freq = burned
  .sum().toInt()
  .rename('freq');

// Last burned year
var last = burned.map(function(img) {
  var y = ee.Number(img.get('year'));
  return img.multiply(y).rename('last').toInt();
}).max().toInt();

// Combine bands
var fireFreq = freq
  .addBands(last)
  .clip(roi);

// Export single image
Export.image.toAsset({
  image: fireFreq,
  description: 'fire_freq',
  assetId: img_asset_id,
  scale: 30,
  region: roi,
  maxPixels: 1e13
});