// Export annual burn probability

// Load functions --------------------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");

// Constants (roi, coeffs_obs, years, K, M)
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Constants and data ----------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_prob_annual_03/';
var roi = cons.roi;
var startYear = cons.startYear;
var endYear = cons.endYear;

// vegetation type reclassified in forest, shrubland, grassland.
var vegCol = funk.mapBiomasReclassCol();

// burn indices summaries
var indSumm = ee.ImageCollection('projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_indices_summaries');

// time series metrics
var tsmCol = ee.ImageCollection('projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/time_series_metrics_03');

// Loop over years ---------------------------------------------------------
    
for (var y = startYear; y <= endYear; y++) {
  var yNum = ee.Number(y);
  var start = ee.Date.fromYMD(y, 1, 1);
  
  // Time series metrics from focal year
  var tsm = tsmCol.filterDate(start, start.advance(1, 'year')).first();
  
  // Burn indices summaries from previous year
  var summ = indSumm.filterDate(start.advance(-1, 'year'), start).first();

  // Vegetation type from previous year
  var veg = vegCol.filterDate(start.advance(-1, 'year'), start).first();

  // Create multi-band coefficients image based on vegetation type
  var coeffImg = funk.makeCoeffImage(veg, cons.coeffs_annual);

  // Common mask across Landsat, summaries, and vegetation
  var commonMask = tsm.select(0).mask()
                      .and(summ.select(0).mask())
                      .and(veg.mask());

  // Create multi-band predictors image (masked)
  var predictors = funk.makePredictorsAnnual(tsm, summ, cons.coeffs_annual)
                       .updateMask(commonMask);
                     
  // Compute logit burn probability (masked)
  var lp = predictors
     .multiply(coeffImg).reduce(ee.Reducer.sum())
     .updateMask(commonMask);
     
  var bp = funk.invLogit(ee.Image(lp))
    .rename('burn_prob')
    .set('system:time_start', ee.Date.fromYMD(y, 1, 1).millis())
    .set('year', y);
  
  // Client-side strings for task description and assetId
  var desc = 'bp_annual_' + y;
  var assetId = dirbase + 'burn_prob_annual_' + y;
  
  Export.image.toAsset({
    image: bp,
    description: desc,
    assetId: assetId,
    region: roi,
    scale: 30,
    maxPixels: 1E13
  });
}