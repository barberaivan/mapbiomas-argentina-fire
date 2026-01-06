// Compute annual images with extreme values of ancillary indices:
// brightness and NDSI, to remove volcanic ash, clouds, and snow.
// Edited from <01-burn_prob_obs-burn_indices_summaries>.
 
// Load functions --------------------------------------------------------

// Used to get the quality-masked, harmonized, Landsat imagery, with
// fire indices computed. Summarizing functions too.
var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");

// Constants (years, roi)
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Constants -------------------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/ancillary_indices_summaries/';

var roi = cons.roi;

// Export annual summaries -----------------------------------------------

// Evaluate the year_list client-side so we can create client-side names
for (var y = cons.startYearSumm; y <= cons.endYearSumm; y++) {
  // y is a client-side JS number/string here
  var yNum = ee.Number(y);

  // Build server-side dates from the client number
  var start = ee.Date.fromYMD(yNum, 1, 1);
  var end   = ee.Date.fromYMD(yNum.add(1), 1, 1);

  var landsat = funk.getLandsat(roi, start, end, funk.addAncillaryIndices)
                    .select(cons.anc_names);

  // Apply computeExtremesSingle band-by-band
  var summ = ee.ImageCollection(
    cons.anc_names.map(function(band) {
      band = ee.String(band);
      var col = landsat.select([band]);
      var extremes = funk.computeExtremesSingle(col);

      // Rename all bands so they start with the band name itself
      var renamed = extremes.rename([
        band.cat('_low'),
        band.cat('_high')
      ]);
      return renamed;
    })
  ).toBands()  
  .rename(cons.anc_names.map(function(b) {
    return [ee.String(b).cat('_low'), ee.String(b).cat('_high')];
  }).flatten())
  .set('year', yNum)
  .set('system:time_start', start.millis());

  // Client-side strings for task description and assetId
  var desc = 'summ_' + y;
  var assetId = dirbase + 'ancillary_summ_' + y;

  // Queue export task (the Export call itself accepts server-side objects)
  Export.image.toAsset({
    image: summ,
    description: desc,
    assetId: assetId,
    region: roi,
    scale: 30,
    maxPixels: 1E13
  });
}