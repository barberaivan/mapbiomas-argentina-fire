/*
  Export raw NBR time series and land cover for training locations.
  Process summaries locally in R/Python.
  
  For each fire, export:
  1) Fire indices observations (all years, all points)
     [NBR, NBR2, MIRBI, NDVI]. MIRBI is negated, so it decreases with fire.
  2) MapBiomas land cover (years that will be used as predictors, all points)
  
  FI stands for Fire Indices.
*/ 

var funk = require("users/mapbiomas-arg/fuego:functions.js");

// Max year reached by MapBiomas landcover
var mblimit = ee.Number(2024);

// Sample NBR time series at all points for a fire
function sampleFIts(fireFC) {
  var fireDate = ee.Date(fireFC.get('date'));
  var fireYear = ee.Number(fireDate.get('year'));

  var startYear = fireYear.subtract(2);
  var endYear = fireYear.add(2);

  var start = ee.Date.fromYMD(startYear, 1, 1)
                .advance(-6, 'month');
  var end   = ee.Date.fromYMD(endYear.add(1), 7, 1);
                
  // Get FI collection
  var fi_ts = funk.getLandsat(fireFC, start, end, funk.addFireFour)
                   .select("nbr", "nbr2", "mirbi", "ndvi");

  // Sample at points
  var samples = fi_ts.map(function(img) {
    var date = img.get('system:time_start');
    var dateObj = ee.Date(date);
    return img.sampleRegions({
      collection: fireFC,
      scale: 30,
      geometries: false
    }).map(function(f) {
      return f.set({
        'date': dateObj.format('YYYY-MM-dd'),
        'year': dateObj.get('year'),
        'month': dateObj.get('month'),
        'day': dateObj.get('day')
      });
    });
  }).flatten();

  return samples;
}

// Sample land cover for all years needed (first N-1 years)
function sampleLandCover(fireFC, mapbiomas) {
  var fireDate = ee.Date(fireFC.get('date'));
  var fireYear = ee.Number(fireDate.get('year'));
  
  var startYear = fireYear.subtract(2);
  var endYear = fireYear.add(2);
  
  // MapBiomas reaches only year mblimit
  endYear = ee.Number(ee.Algorithms.If(endYear.gt(mblimit), mblimit, endYear));

  var yearList = ee.List.sequence(startYear, endYear);
  
  var samples = yearList.map(function(y) {
    y = ee.Number(y);
    var vegname = ee.String('classification_').cat(y.toInt().format());
    var veg = mapbiomas.select(vegname);
    
    return veg.sampleRegions({
      collection: fireFC,
      scale: 30,
      geometries: false
    }).map(function(f) {
      return f.set('year', y)
               .select(['.*'], null, false)  // Remove original property name
               .set('veg', f.get(vegname));
    });
  }).flatten();
  
  return ee.FeatureCollection(samples).flatten();
}

// Set ID for points
var setID = function(z) {
  z = ee.List(z);
  var pointId = ee.Number(z.get(0));
  var f = ee.Feature(z.get(1));
  return f.set('point_id', pointId);
};

// Constants
var mapbiomas = ee.Image("projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-2/GENERAL/CLASSIFICATION/FINAL_CLASSIFICATION/PAT/PAT-INTEGRACION-FINAL-v4");

// Training fires
var tf = ee.FeatureCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_fires");

var basePath = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/';

// Loop over all 30 fires
for (var i = 1; i <= 30; i++) {
  // var i = 14;
  var id = (i < 10) ? '0' + i : i.toString();
  var assetPath = basePath + 'training_locations-fire_' + id;
  
  var idname = 'fire_' + id;
  var metadata = tf.filterMetadata('fire_id', 'equals', idname).first();
  
  // Get the date - check if property name is correct
  var fireDate = metadata.get('pre_upr');
  
  // Import points and add IDs
  var fireFC = ee.FeatureCollection(assetPath);
  var list = fireFC.toList(fireFC.size());
  var ids = ee.List.sequence(0, fireFC.size().subtract(1));
  var fireFC2 = ee.FeatureCollection(ids.zip(list).map(setID)).set('date', metadata.get('pre_upr'));
  
  // Export 1: NBR time series
  var fiSamples = sampleFIts(fireFC2);

  Export.table.toDrive({
    collection: fiSamples,
    description: 'fire_indices_ts_fire_' + id,
    fileFormat: 'CSV',
    folder: 'GEE_exports'
  });
  
  // Export 2: Land cover
  var vegSamples = sampleLandCover(fireFC2, mapbiomas);

  Export.table.toDrive({
    collection: vegSamples,
    description: 'landcover_fire_' + id,
    fileFormat: 'CSV',
    folder: 'GEE_exports',
    selectors: ['class', 'point_id', 'veg', 'year']
  });
}

/*
  To run all tasks at once, you may install the 
  Open Earth Engine extension for Chrome,
  which provides the "RUN ALL!" button.
  
  https://chromewebstore.google.com/detail/dhkobehdekjgdahfldleahkekjffibhg?utm_source=item-share-cb
*/