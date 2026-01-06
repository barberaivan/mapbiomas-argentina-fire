// Compute annual spatial segmentation (SNIC). 
// Seeds clusters with less than N cells are removed.

/*
  Rerun this step: remove brightness restrictions from candidates
  and run the SNIC with large neighbourhoodSize.
*/
 
// Load functions and constants ------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Define constants ------------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/snic_04/';
var roi = cons.roi;

var N = 5;
var Nlim = N-1;

// Load input image collections ------------------------------------------

var tsm = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/time_series_metrics_03"),
    bp  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_prob_annual_03"),
    anc = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/ancillary_indices_summaries"),
    fi  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_indices_summaries");

// Loop over years -------------------------------------------------------

// Evaluate the year_list client-side so we can create client-side names
for (var y = cons.startYear; y <= cons.endYear; y++) {
  // y is a client-side JS number/string here
  // var y = 2015;
  var yNum = ee.Number(y);
  
  // Extract focal images
  var tsm_img = tsm.filterMetadata('year', 'equals', y).first(),
      bp_img = bp.filterMetadata('year', 'equals', y).first(),
      anc_img = anc.filterMetadata('year', 'equals', y).first(),
      anc_prev = anc.filterMetadata('year', 'equals', yNum.add(-1)).first(),
      fi_img = fi.filterMetadata('year', 'equals', y).first(),
      fi_prev = fi.filterMetadata('year', 'equals', yNum.add(-1)).first();
      
  // Brightness metrics
  var bright = anc_img.select('brightness_high');
  var bright_d = bright.subtract(anc_prev.select('brightness_high'));
  
  // NBR and NBR2 delta
  // var nbr_d = fi_prev.select('nbr_low').subtract(fi_img.select('nbr_low')),
  //     nbr2_d = fi_prev.select('nbr2_low').subtract(fi_img.select('nbr2_low'));
      
  // Extract probabilities and ts metrics
  var prob_obs = tsm_img.select('pmax'),
      prob_d   = tsm_img.select('pdiff_max'),
      prob_ann = bp_img.select('burn_prob');
  
  // Seeds 
  var seed_raw = prob_obs.gte(0.98)
    .and(prob_d.gte(0.90))
    .and(prob_ann.gte(0.98))
    // Not high brightness, avoid ash
    .and(
      bright.gt(0.5).or(bright_d.gt(0.15)).not()
    );
  
  // Count pixels in each connected component
  var cluster_size = seed_raw.selfMask().connectedPixelCount({
    maxSize: 10,  // or whatever reasonable limit
    eightConnected: true
  });
  
  // Remove small clusters from seeds
  var seed = cluster_size.gte(N).selfMask();

  // Candidates
  var candidate = prob_obs.gte(0.25)
    .and(prob_d.gte(0.2))
    .and(prob_ann.gte(0.30));
    // No brightness constraints, and softer thresholds on probabilities
  
  var snic = ee.Algorithms.Image.Segmentation.SNIC({
      image: candidate.selfMask(),
      seeds: seed,
      compactness: 0,
      connectivity: 8,
      neighborhoodSize: 1000 // Avoid tile limits
    })
    // .select('clusters')//.rename('burned').mask().selfMask()
    .set('year', yNum)
    .set('system:time_start', ee.Date.fromYMD(y, 1, 1).millis());

  // Client-side strings for task description and assetId
  var desc = 'snic_' + y;
  var assetId = dirbase + 'snic_' + y;

  Export.image.toAsset({
    image: snic,
    description: desc,
    assetId: assetId,
    region: roi,
    scale: 30,
    maxPixels: 1E13
  });
}