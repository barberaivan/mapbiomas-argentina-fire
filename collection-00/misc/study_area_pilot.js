// Define study area for pilot


// Imports

var patagonia = ee.FeatureCollection("projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/PAT/Patagonia_ContornoSimplificado"),
    trains = ee.FeatureCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_fires"),
    geometry = 
    /* color: #3897d6 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-72.48821797958328, -38.650054152546964],
          [-72.48821797958328, -44.55811949986534],
          [-68.31341329208328, -44.55811949986534],
          [-68.31341329208328, -38.650054152546964]]], null, false),
    patagonia_zones = ee.FeatureCollection("projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/PAT/ZonificacionesPatagonia_Buffer5km");

// Settings

// Map.addLayer(patagonia, {color: "yellow"}, "p1");
Map.addLayer(patagonia_zones, {color: "yellow"}, "Patagonia");

var rect = 
    /* color: #3897d6 */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-72.5, -38.6],
          [-72.5, -44.5],
          [-68.5, -44.5],
          [-68.5, -38.6]]], null, false);

// Map.addLayer(rect, {color: "green"}, "rect");

var study_area = patagonia
  .filterBounds(rect)
  .geometry()
  .intersection(rect, ee.ErrorMargin(1));

Map.addLayer(study_area, {color: "red"}, "Study area");
Map.addLayer(trains, {color: "black"}, "Training areas");

var assetName = "projects/mapbiomas-argentina/assets/FIRE/AUXILIARY_DATA/VECTOR/pilot_study_area";

// Export.table.toAsset({
//   description: "Study area pilot",
//   collection: ee.FeatureCollection(study_area),
//   assetId: assetName
// });