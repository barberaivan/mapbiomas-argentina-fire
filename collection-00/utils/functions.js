// Constants and functions to extract full Landsat time series ----------------

// Harmonization coefficients (Roy et al. 2016), to scale ETM+ to OLI
var coefficients = {
  itcps: ee.Image.constant([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172]),
  slopes: ee.Image.constant([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
};

// Rename and scale functions
function renameL5L7(img) {
  return img.select(
    ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL'],
    ['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'QA_PIXEL']
  );
}

function renameL8L9(img) {
  return img.select(
    ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL'],
    ['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'QA_PIXEL']
  );
}

var optBandNames = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'];

// Quality mask function
function maskq(img) {
  var qa = img.select('QA_PIXEL');
  var dilatedCloud = qa.bitwiseAnd(1 << 1); 
  var cloud = qa.bitwiseAnd(1 << 3);
  var shadow = qa.bitwiseAnd(1 << 4);
  var snow = qa.bitwiseAnd(1 << 5);
  var water = qa.bitwiseAnd(1 << 7);
  var clearMask = dilatedCloud.or(cloud).or(shadow).or(snow).or(water).not();
  
  // Add mapbiomas filters (water?)
  
  return img.updateMask(clearMask);
}

// Harmonize ETM+ to OLI
function harmonizeETM(img) {
  var orig = img;
  img = renameL5L7(img).select(optBandNames)
    .multiply(0.0000275).add(-0.2)
    .multiply(coefficients.slopes)
    .add(coefficients.itcps)
    .toFloat();
  return img.addBands(orig.select('QA_PIXEL')).copyProperties(orig, orig.propertyNames());
}

// Prepare OLI
function prepOLI(img) {
  var orig = img;
  img = renameL8L9(img)
    .multiply(0.0000275).add(-0.2)
    .toFloat();
  return img.copyProperties(orig, orig.propertyNames());
}

// Compute many spectral indices sensitive to fire
function addFireIndices(img) {
  // NBR - Normalized Burn Ratio (Key index for fire mapping)
  var nbr = img.normalizedDifference(['nir', 'swir2']).rename('nbr');
  
  // NBR2 - Normalized Burn Ratio 2 (SWIR-based)
  var nbr2 = img.normalizedDifference(['swir1', 'swir2']).rename('nbr2');
  
  // NDVI - Normalized Difference Vegetation Index
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  
  // MIRBI - Mid-Infrared Burn Index
  var mirbi = img.expression(
    '10 * swir2 - 9.8 * swir1 + 2', {
      'swir2': img.select('swir2'),
      'swir1': img.select('swir1')
    }).rename('mirbi');
  
  // BAI - Burn Area Index
  var bai = img.expression(
    '1 / ((0.1 - red) ** 2 + (0.06 - nir) ** 2)', {
      'red': img.select('red'),
      'nir': img.select('nir')
    }).rename('bai');
  
  // EVI - Enhanced Vegetation Index
  var evi = img.expression(
    '2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)', {
      'nir': img.select('nir'),
      'red': img.select('red'),
      'blue': img.select('blue')
    }).rename('evi');
  
  // SAVI - Soil Adjusted Vegetation Index
  var savi = img.expression(
    '1.5 * (nir - red) / (nir + red + 0.5)', {
      'nir': img.select('nir'),
      'red': img.select('red')
    }).rename('savi');
  
  // MSI - Moisture Stress Index
  var msi = img.expression(
    'swir1 / nir', {
      'swir1': img.select('swir1'),
      'nir': img.select('nir')
    }).rename('msi');
  
  // NDSI - Normalized Difference Snow Index
  var ndsi = img.normalizedDifference(['green', 'swir1']).rename('ndsi');
  
  // NDMI - Normalized Difference Moisture Index
  var ndmi = img.normalizedDifference(['nir', 'swir1']).rename('ndmi');
  
  // TCT - Tasseled Cap Transformations (Brightness, Greenness, Wetness)
  var brightness = img.expression(
    '0.3029 * blue + 0.2786 * green + 0.4733 * red + 0.5599 * nir + 0.5080 * swir1 + 0.1872 * swir2', {
      'blue': img.select('blue'),
      'green': img.select('green'),
      'red': img.select('red'),
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('brightness');
  
  var greenness = img.expression(
    '-0.2941 * blue - 0.2430 * green - 0.5424 * red + 0.7276 * nir + 0.0713 * swir1 - 0.1608 * swir2', {
      'blue': img.select('blue'),
      'green': img.select('green'),
      'red': img.select('red'),
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('greenness');
  
  var wetness = img.expression(
    '0.1511 * blue + 0.1973 * green + 0.3283 * red + 0.3407 * nir - 0.7117 * swir1 - 0.4559 * swir2', {
      'blue': img.select('blue'),
      'green': img.select('green'),
      'red': img.select('red'),
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('wetness');
  
  // Add all indices to the image
  return img.addBands([
    nbr, nbr2, ndvi, mirbi, bai, evi, savi, msi, ndsi, ndmi, 
    brightness, greenness, wetness
  ]);
}

// Compute NBR and NDVI
function addNBR_NDVI(img) {
  // NBR - Normalized Burn Ratio (Key index for fire mapping)
  var nbr = img.normalizedDifference(['nir', 'swir2']).rename('nbr');
  
  // NDVI - Normalized Difference Vegetation Index
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  
  return img.addBands([nbr, ndvi]);
}

// Compute NBR only
function addNBR(img) {
  // NBR - Normalized Burn Ratio (Key index for fire mapping)
  var nbr = img.normalizedDifference(['nir', 'swir2']).rename('nbr');
  
  return img.addBands([nbr]);
}


function addNDFI(img) {
  // Define endmembers for spectral unmixing
  var endmembers = ee.Array([
    [0.0500, 0.0900, 0.0400, 0.6100, 0.3000, 0.1000], // GV
    [0.1400, 0.1700, 0.2200, 0.3000, 0.5500, 0.3500], // NPV
    [0.1500, 0.2000, 0.2500, 0.3500, 0.5000, 0.3500], // Soil
    [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000]  // Shade
  ]);
  
  // Convert endmembers to image for matrix operations
  var endmemberImage = ee.Image(endmembers);
  
  // Select the required bands and convert to 2D array
  var reflectance = img.select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']);
  
  // Reshape reflectance to a 2D array [pixels x bands]
  var reflectanceArray = reflectance.toArray();
  
  // Perform linear unmixing: fractions = (M^T * M)^-1 * M^T * R
  var Mt = endmembers.transpose();
  var MtM = endmembers.matrixMultiply(Mt);
  var MtM_inv = MtM.matrixInverse();
  var inverseMt = MtM_inv.matrixMultiply(Mt);
  
  // Convert inverseMt to image for pixel-wise multiplication
  var inverseMtImage = ee.Image(inverseMt);
  
  // Calculate fractions: fractions = inverseMt * reflectance
  var fractionsArray = inverseMtImage.matrixMultiply(reflectanceArray.toArray(1));
  
  // Reshape fractions array to separate bands
  var fractions = fractionsArray.arrayFlatten([
    [['gv', 'npv', 'soil', 'shade']]
  ]);
  
  // Extract individual fractions
  var gv = fractions.select('gv').rename('gv_frac');
  var npv = fractions.select('npv').rename('npv_frac');
  var soil = fractions.select('soil').rename('soil_frac');
  var shade = fractions.select('shade').rename('shade_frac');
  
  // Calculate NDFI
  var ndfi = ee.Image().expression(
    '(gv - (soil + shade + npv)) / (gv + soil + shade + npv + 0.0001)', {
      'gv': gv,
      'soil': soil,
      'shade': shade,
      'npv': npv
    }).rename('ndfi');
  
  // Constrain values to valid ranges
  var constrainedGV = gv.max(0).min(1).rename('gv_frac');
  // var constrainedNPV = npv.max(0).min(1).rename('npv_frac');
  // var constrainedSoil = soil.max(0).min(1).rename('soil_frac');
  // var constrainedShade = shade.max(0).min(1).rename('shade_frac');
  var constrainedNDFI = ndfi.max(-1).min(1).rename('ndfi');
  
  // Add all to the image
  return img.addBands([
    constrainedGV, 
    // constrainedNPV, 
    // constrainedSoil, 
    // constrainedShade, 
    constrainedNDFI
  ]);
}

// Load and filter Landsat collections
// indicesFunction should be choose among addNBR or addFireIndices
function getLandsat(roi, startDate, endDate, indicesFunction) {
  // Define spatio-temporal filter
  var colFilter = ee.Filter.and(
    ee.Filter.bounds(roi),
    ee.Filter.date(startDate, endDate)
  );
  
  var ls5 = ee.ImageCollection('LANDSAT/LT05/C02/T1_L2').filter(colFilter).map(maskq).map(harmonizeETM);
  var ls7 = ee.ImageCollection('LANDSAT/LE07/C02/T1_L2').filter(colFilter).map(maskq).map(harmonizeETM);
  var ls8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filter(colFilter).map(maskq).map(prepOLI);
  var ls9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filter(colFilter).map(maskq).map(prepOLI);

  var landsat = ls5.merge(ls7).merge(ls8).merge(ls9)
    .select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']); // remove QA band
  var indices = landsat.map(indicesFunction);//.map(addNDFI);
  return indices;
}

// Probably not used (MODIS and GABAM)
// Function to get MODIS Burned Area product
function getMODISBurnedArea(startDate, endDate) {
  return ee.ImageCollection('MODIS/061/MCD64A1')
    .filterDate(startDate, endDate)
    .select('BurnDate')
    .mosaic()
    .clip(roi);
}

// Function to get GABAM dataset
function getGABAM() {
  return ee.ImageCollection('Tsinghua/FireEarth/GABAM')
    .mosaic()
    .clip(roi);
}


// Visualization functions ----------------------------------------------

// Mostly used to help in the selection of training points. These functions 
// create an NBR time series panel for the clicked point.

// pre_ and post_ identify dates for the pre and post fire, lwr and upr are 
// beginning and ending. 
// begin and end are the limits of the whole background period.

// // Global panel variables (internal to module)
// var panel = null;
// var chk_show_nbr_flag = null;
// var currentChart = null;

// Function to classify each image by period
function tagPeriod(img, pre_lwr, pre_upr, post_lwr, post_upr) {
  var date = ee.Date(img.get('system:time_start'));
  var period = ee.Algorithms.If(
    date.millis().gte(pre_lwr.millis()).and(date.millis().lte(pre_upr.millis())),
    'Pre-fire',
    ee.Algorithms.If(
      date.millis().gte(post_lwr.millis()).and(date.millis().lte(post_upr.millis())),
      'Post-fire',
      'Background'
    )
  );
  return img.set('period', period);
}

// Create a chart from the NBR time series with dynamic y-axis
function getNBRTimeSeriesChart(point, roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr) {
  var landsatCollection = getLandsat(roi, begin, end, addNBR)
    .select('nbr')
    .map(function(img) {
      return tagPeriod(img, pre_lwr, pre_upr, post_lwr, post_upr);
    });

  var features = landsatCollection.map(function(img) {
    var val = img.reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: point,
      scale: 30
    }).get('nbr');
    return ee.Feature(null, {
      'date': img.date().format('YYYY-MM-dd'),
      'nbr': val,
      'period': img.get('period')
    });
  }).sort('date');

  // Compute min and max dynamically
  var nbrValues = features.aggregate_array('nbr');
  var minVal = ee.Number(nbrValues.reduce(ee.Reducer.min()));
  var maxVal = ee.Number(nbrValues.reduce(ee.Reducer.max()));
  var range = maxVal.subtract(minVal);
  var yMin = minVal.subtract(range.multiply(0.2));
  var yMax = maxVal.add(range.multiply(0.2));

  return ui.Chart.feature.groups({
    features: features,
    xProperty: 'date',
    yProperty: 'nbr',
    seriesProperty: 'period'
  })
  .setChartType('ScatterChart')
  .setOptions({
    title: 'NBR Time Series',
    hAxis: {title: 'Date'},
    vAxis: {title: 'NBR Value', viewWindow: {min: yMin.getInfo(), max: yMax.getInfo()}},
    pointSize: 5,
    series: {
      0: {color: 'gray'},
      1: {color: 'blue'},
      2: {color: 'red'}
    }
  });
}

// Create a panel with chart
function getPanelChartTS(panel, roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr) {
  var chk_show_nbr_flag = ui.Checkbox({
    label: 'Show NBR time series',
    value: true
  });
  var currentChart = null;
  var currentPointLayer = null;

  Map.onClick(function(clickPoint) {
    if (!chk_show_nbr_flag.getValue()) return;

    var punto = ee.Geometry.Point([clickPoint.lon, clickPoint.lat]);

    // Remove old chart
    if (currentChart) panel.remove(currentChart);

    // Remove old point layer
    if (currentPointLayer) Map.layers().remove(currentPointLayer);

    // Add new chart
    currentChart = getNBRTimeSeriesChart(punto, roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr);
    panel.insert(1, currentChart);

    // Add new point layer
    currentPointLayer = ui.Map.Layer(punto, {color: 'red'}, 'Selected Point');
    Map.layers().add(currentPointLayer);

    // print('Selected point: ' + clickPoint.lon.toFixed(4) + ', ' + clickPoint.lat.toFixed(4));
  });

  return ui.Panel({
    widgets: [chk_show_nbr_flag],
    layout: ui.Panel.Layout.flow('vertical')
  });
}

// Initialize the NBR panel
function makeNBRtsPanel(roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr) {
  var panel = ui.Panel({
    widgets: [
      ui.Label('NBR time series', {fontWeight: 'bold', fontSize: '16px'}),
      ui.Label('Click checkbox to enable, then click on map'),
    ],
    style: {
      width: '500px',
      padding: '10px',
      backgroundColor: 'white',
      border: '1px solid black'
    }
  });

  // Build inner panel and insert it
  var innerPanel = getPanelChartTS(panel, roi, begin, end, pre_lwr, pre_upr, post_lwr, post_upr);
  panel.add(innerPanel);

  ui.root.insert(1, panel);
  return panel;
}

// MapBiomas Fire Reclassification ----------------------------------------

function mapBiomasReclass() {
  // Load MapBiomas image (multi-band: one per year)
  var mapbiomas = ee.Image("projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-2/GENERAL/CLASSIFICATION/FINAL_CLASSIFICATION/PAT/PAT-INTEGRACION-FINAL-v4");

  // Old and new values
  var from = [3, 66, 6, 12, 11, 75, 63, 21, 9, 29, 25, 24, 33, 34, 27];
  var to   = [1, 2,  1,  3,  3,  3,  3,  3, 1,  0,  0,  0,  0,  0,  0];

  /*
  new values:
  0: no quemable
  1: bosque
  2: arbustal
  3: pastizal
  */

  // Get all band names
  var bnames = mapbiomas.bandNames();
  
  // Reclassify each band
  var reclassifiedBands = bnames.map(function(year) {
    var band = mapbiomas.select([year])
      .remap(from, to)
      .rename([year]); // keep the band name
    return band;
  });

  // Merge all reclassified bands back into one multiband image
  var veg = ee.ImageCollection(reclassifiedBands).toBands().rename(bnames);
  return veg;
}

// Exports ----------------------------------------------------------

exports = {
  getLandsat: getLandsat,
  makeNBRtsPanel: makeNBRtsPanel,
  addNBR: addNBR,
  addNBR_NDVI: addNBR_NDVI,
  addFireIndices: addFireIndices,
  mapBiomasReclass: mapBiomasReclass
};