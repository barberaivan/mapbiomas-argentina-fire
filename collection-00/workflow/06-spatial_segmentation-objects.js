// Merge nearby burns by vectorization 
// This _03 version uses the raster - vector - raster - vector method
// for joining nearby polygons.

// Load functions and constants ------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:collection-00/utils/functions.js");
var cons = require("users/mapbiomas-arg/fuego:collection-00/utils/constants.js");

// Define constants ------------------------------------------------------

var dirbase = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/polygons_03/';
var roi = cons.roi;

// Load input image collections ------------------------------------------

var snic = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/snic_04");
var maskFC = ee.FeatureCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/masks");

// Loop over years -------------------------------------------------------

// ========================================
// SAFE SNIC → CONTEXT → RASTER-ID → VECTORS PIPELINE
// ========================================

for (var y = cons.startYear; y <= cons.endYear; y++) {
  // var y = 2015;
  var year = ee.Number(y);
  
  // Define roi based on availability of hand-made masks
  var yearMask = maskFC.filter(ee.Filter.eq('year', year));
  var hasMask = yearMask.size().gt(0);
  
  var roiUse = ee.Algorithms.If({
    condition: hasMask,
    trueCase: roi.difference(yearMask.union().geometry(), 500),
    falseCase: roi
  });
  
  // Get SNIC image for that year
  var snic_img = snic.filterMetadata('year', 'equals', y).first();

  // ----------------------------------------
  // 1) Binary mask of SNIC clusters
  // ----------------------------------------
  var snic_bin = snic_img
      .select('clusters')
      .mask()
      .gt(0)
      .rename('burned');

  // ----------------------------------------
  // 2) Context neighborhood to merge nearby clusters
  //    (same logic: focalMax radius=1px)
  // ----------------------------------------
  var snic_context = snic_bin
      .focalMax({
        radius: 1,
        kernelType: 'square',
        units: 'pixels'
      })
      .toInt()
      .rename('context');

  // ----------------------------------------
  // 3) Vectorize CONTEXT, not SNIC
  // ----------------------------------------
  var vectors_context = snic_context
      .updateMask(snic_context.gt(0))
      .reduceToVectors({
        geometry: roiUse,
        crs: snic_img.select('clusters').projection(),
        scale: 30,
        geometryType: 'polygon',
        eightConnected: false,
        labelProperty: 'context_id',
        reducer: null,
        maxPixels: 1e13
      });

  // ----------------------------------------
  // 4) For each context polygon, find max SNIC-cluster ID
  // ----------------------------------------
  var vectors_with_id = snic_img
      .select('clusters')
      .reduceRegions({
        collection: vectors_context,
        reducer: ee.Reducer.max(),
        scale: 120
      });

  // ----------------------------------------
  // 5) Rasterize the assigned IDs
  // ----------------------------------------
  var id_raster = vectors_with_id
      .reduceToImage({
        properties: ['max'],
        reducer: ee.Reducer.first()
      })
      .updateMask(snic_bin.gt(0))
      .rename('snic_id');

  // ----------------------------------------
  // 6) Vectorize final merged IDs
  // ----------------------------------------
  var vectors_final = id_raster
      .updateMask(id_raster.gt(0))
      .reduceToVectors({
        geometry: roiUse,
        crs: id_raster.projection(),
        scale: 30,
        geometryType: 'polygon',
        eightConnected: false,
        labelProperty: 'fire_id_raw',
        reducer: null,
        maxPixels: 1e13
      });

  // ----------------------------------------
  // 7) Distinct raw IDs and dissolve each group
  // ----------------------------------------
  var unique_ids = vectors_final.distinct('fire_id_raw');

  var merged = unique_ids.map(function (f) {

    var raw_id = f.get('fire_id_raw');
    var group = vectors_final
        .filterMetadata('fire_id_raw', 'equals', raw_id);

    // dissolve geometries safely
    var dissolved = group.geometry().dissolve({maxError: 60});
    var area_ha = dissolved.area({maxError: 60}).multiply(1e-4);
    var fire_id = year.toInt().format().cat('_').cat(ee.String(raw_id));

    return ee.Feature(dissolved, {
      'fire_id': fire_id,
      'year': year.toInt().format(),
      'area_ha': area_ha
    });
  });

  // ----------------------------------------
  // EXPORT 
  // ----------------------------------------
  var desc = 'polygons_' + y;
  var assetId = dirbase + desc;

  Export.table.toAsset({
    collection: merged,
    description: desc,
    assetId: assetId,
    maxVertices: 1e13
  });
}