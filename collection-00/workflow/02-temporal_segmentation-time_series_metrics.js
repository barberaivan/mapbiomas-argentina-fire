/*
  Export annual metrics of the burn-probability time series.
  It takes each year, computes burn prov in years -1 to +1,
  makes an extended array, and summarized burn prob with ts metrics.
*/

// Load functions --------------------------------------------------------

// Used to get the quality-masked, harmonized, Landsat imagery, with
// fire indices computed. Summarizing functions too.
var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");

// Constants (roi, coeffs_obs, years, K, M)
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Constants and data ----------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/time_series_metrics_03/';
var roi = cons.roi;//geometry2;//
var startYear = cons.startYear;
var endYear = cons.endYear;
var M = cons.M;
var K = cons.K;
// Minimum number of observations in the annual lengthened arrays
// to compute the K-window median (two smoothed obs)
var minObs = K.add(1);

// vegetation type reclassified in forest, shrubland, grassland.
var vegCol = funk.mapBiomasReclassCol();

// burn indices summaries
var indSumm = ee.ImageCollection('projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_indices_summaries');

// Loop over years ------------------------------------------------------
    
for (var y = startYear; y <= endYear; y++) {
  var yNum = ee.Number(y);

  // Get array of logit-burn-prob and fractional year, borrowing
  // M obs from neighbouring years
  var arr_raw = funk.getExtendedArray(
    y, startYear, endYear, M, roi, indSumm, vegCol
  );
  
  // We need at least two 5-obs median smoothed values, so 
  // minimum length is 6.
  arr_raw = arr_raw.updateMask(arr_raw.arrayLength(0).gte(minObs));
  
  // Smooth burn probability with median
  var arr_smooth = funk.smoothBurnProb(arr_raw);
  
  // Get time series metrics
  var tsm = funk.summarizeTS(arr_smooth)
    .set('system:time_start', ee.Date.fromYMD(y, 1, 1).millis())
    .set('year', y);
  
  // Client-side strings for task description and assetId
  var desc = 'ts_metrics_' + y;
  var assetId = dirbase + 'ts_metrics_' + y;
  
  Export.image.toAsset({
    image: tsm,
    description: desc,
    assetId: assetId,
    region: roi,
    scale: 30,
    maxPixels: 1E13
  });
}