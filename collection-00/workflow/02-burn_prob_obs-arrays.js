// Compute the burn probability at the observation level, 
// and export an annual array image with its time series.

// Load functions --------------------------------------------------------

// Used to get the quality-masked, harmonized, Landsat imagery, with
// fire indices computed. Summarizing functions too.
var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");

// Constants (roi, coeffs_obs, years)
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Constants and data ----------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_prob_obs/';
var roi = geometry;//cons.roi;
var startYear = cons.startYear;
var endYear = cons.endYear;

// vegetation type reclassified in forest, shrubland, grassland.
var vegCol = funk.mapBiomasReclassCol();

// burn indices summaries
var indSumm = ee.ImageCollection('projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_indices_summaries');

// To loop over years ----------------------------------------------------
    
for (var y = startYear; y <= endYear; y++) {
  // y is a client-side JS number/string here
  var yNum = ee.Number(y);

  // Build server-side dates from the client number
  var start = ee.Date.fromYMD(yNum, 1, 1);
  var end   = ee.Date.fromYMD(yNum.add(1), 1, 1);
    
  // Burn indices from focal year
  var indCol = funk.getLandsat(roi, start, end, funk.addFireFour)
                     .select(cons.ind_names);

  // Burn indices summaries from previous year
  var summ = indSumm.filterDate(start.advance(-1, 'year'), start).first();

  // Vegetation type from previous year
  var veg = vegCol.filterDate(start.advance(-1, 'year'), start).first();

  // Create multi-band coefficients image based on vegetation type
  var coeffImg = funk.makeCoeffImage(veg, cons.coeffs_obs);

  // Map over Landsat image collection
  var logitCol = indCol.map(function(indImg) {
    // Common mask across Landsat, summaries, and vegetation
    var commonMask = indImg.select(0).mask()
                           .and(summ.select(0).mask())
                           .and(veg.mask());

    // Create multi-band predictors image (masked)
    var predictors = funk.makePredictorsObs(indImg, summ, cons.coeffs_obs)
                         .updateMask(commonMask);

    // Compute logit burn probability (masked)
    var logit_p = predictors.multiply(coeffImg)
      .reduce(ee.Reducer.sum())
      .rename('logit_p')
      .updateMask(commonMask)
      .copyProperties(indImg, indImg.propertyNames());
        
    // Add fractional year with the SAME mask as logit_p
    var date = ee.Date(indImg.get('system:time_start'));
    var year = date.get('year');
    var doy = date.getRelative('day', 'year');
    var daysInYear = ee.Date.fromYMD(year.add(1), 1, 1)
      .difference(ee.Date.fromYMD(year, 1, 1), 'day');
    var fracYear = year.add(doy.divide(daysInYear));
  
    var fracYearBand = ee.Image.constant(fracYear)
      .rename('fracYear')
      .toFloat()
      .updateMask(commonMask); // Apply same mask!

    logit_p = ee.Image(logit_p).addBands(fracYearBand);
  
    return logit_p;
  });
    
  // Turn into array for export
  var arr = logitCol.toArray()
    .set('system:time_start', start.millis())
    .set('year', yNum);
    
  // Client-side strings for task description and assetId
  var desc = 'array_' + y;
  var assetId = dirbase + 'bp_array_' + y;
  
  Export.image.toAsset({
    image: arr,
    description: desc,
    assetId: assetId,
    region: roi,
    scale: 30,
    maxPixels: 1E13
  });
}