// Summarize metrics in merged polygons, and export polygons with metrics
  
// Load functions and constants ------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Define constants ------------------------------------------------------

var dirbase_load = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/polygons_03/';
var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/polygons_metrics_03/';
var roi = cons.roi;

// Load input image collections ------------------------------------------

var tsm  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/time_series_metrics_03"),
    bp   = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_prob_annual_03"),
    anc  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/ancillary_indices_summaries"),
    fi   = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_indices_summaries"),
    snic = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/snic_03");

// Annual processing -----------------------------------------------------

// Evaluate the year_list client-side so we can create client-side names
for (var y = cons.startYear; y <= cons.endYear; y++) {

  // y is a client-side JS number/string here
  // var y = 2015;
  var yNum = ee.Number(y);
  
  // Extract focal images
  var tsm_img  = tsm.filterMetadata('year', 'equals', y).first(),
      bp_img   = bp.filterMetadata('year', 'equals', y).first(),
      anc_img  = anc.filterMetadata('year', 'equals', y).first(),
      anc_prev = anc.filterMetadata('year', 'equals', yNum.add(-1)).first(),
      fi_img   = fi.filterMetadata('year', 'equals', y).first(),
      fi_prev  = fi.filterMetadata('year', 'equals', yNum.add(-1)).first(),
      snic_img = snic.filterMetadata('year', 'equals', y).first();
      
  // Brightness metrics
  var bright = anc_img.select('brightness_high');
  var bright_d = bright.subtract(anc_prev.select('brightness_high'));
      
  // Extract probabilities and ts metrics
  var prob_obs = tsm_img.select('pmax').rename('prob_obs'),
      prob_d   = tsm_img.select('pdiff_max').rename('prob_d'),
      prob_ann = bp_img.select('burn_prob').rename('prob_ann');
  
  // Seeds 
  var seed = prob_obs.gte(0.98)
    .and(prob_d.gte(0.90))
    .and(prob_ann.gte(0.98))
    // Not high brightness, avoid ash
    .and(
      bright.gt(0.5).or(bright_d.gt(0.15)).not()
    );

  // Compute new variables
  
  // Snic context, to merge nearby polygons
  var snic_context = snic_img.focalMax({
    radius: 1, kernelType: 'square', units: 'pixels'
  }).toInt().selfMask();
  
  // Avg burned layer around each pixel, using several radius values
  var burned_around_1 = snic_img.unmask(0).reduceNeighborhood({
    reducer: ee.Reducer.mean(),
    kernel: ee.Kernel.square({radius: 1, units: 'pixels'})
  }).rename('burned_around_1');
  
  var burned_around_2 = snic_img.unmask(0).reduceNeighborhood({
    reducer: ee.Reducer.mean(),
    kernel: ee.Kernel.square({radius: 2, units: 'pixels'})
  }).rename('burned_around_2');
  
  var burned_around_3 = snic_img.unmask(0).reduceNeighborhood({
    reducer: ee.Reducer.mean(),
    kernel: ee.Kernel.square({radius: 3, units: 'pixels'})
  }).rename('burned_around_3');
  
  // Summarize relevant variables in grouped polygons
  var variables = prob_obs
    .addBands([
      prob_d,
      prob_ann,
      seed.rename('seed'),
      burned_around_1,
      burned_around_2,
      burned_around_3
    ]);
  
  // Import focal polygons
  var dir = dirbase_load + 'polygons_' + y;
  var focal_polygons = ee.FeatureCollection(dir);
  
  // Reduce bands in polygons
  var merged_raster_metrics = variables.reduceRegions({
    collection: focal_polygons,
    reducer: ee.Reducer.mean(), 
    scale: 30,
    tileScale: 2
  });
  
  // Compute shape metrics
  var merged_all_metrics = ee.FeatureCollection(
    merged_raster_metrics.map(funk.addShapeMetrics)
  );
  
  // Client-side strings for task description and assetId
  var desc = 'polygons_metrics_' + y;
  var assetId = dirbase + desc;

  Export.table.toAsset({
    collection: merged_all_metrics, 
    description: desc,
    assetId: assetId,
    maxVertices: 1E13
  });
}