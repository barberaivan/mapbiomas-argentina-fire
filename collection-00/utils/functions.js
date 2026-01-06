// Other constants -----------------------------------------------------------

var cons = require('users/mapbiomas-arg/fuego:collection-00/utils/constants.js');

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
  return img.addBands(orig.select('QA_PIXEL'))
            //.addBands(orig.select('ST_B6').rename('thermal'))
            .copyProperties(orig, orig.propertyNames());
}

// Prepare OLI
function prepOLI(img) {
  var orig = img;
  img = renameL8L9(img)
    .multiply(0.0000275).add(-0.2)
    .toFloat();
  return img
            //.addBands(orig.select('ST_B10').rename('thermal'))
            .copyProperties(orig, orig.propertyNames());
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


// Compute brightness indices
function addBright(img) {
  // TCT - Tasseled Cap Transformations (Brightness)
  var brightness = img.expression(
    '0.3029 * blue + 0.2786 * green + 0.4733 * red + 0.5599 * nir + 0.5080 * swir1 + 0.1872 * swir2', {
      'blue': img.select('blue'),
      'green': img.select('green'),
      'red': img.select('red'),
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('brightness');
  
  // Visible bands sum
  var visSum = img.select('blue')
    .add(img.select('green'))
    .add(img.select('red'))
    .rename('visSum');
 
  // Add all indices to the image
  return img.addBands([
    brightness, visSum
  ]);
}

// Compute brightness indices
function addAncillaryIndices(img) {
  // TCT - Tasseled Cap Transformations (Brightness)
  var brightness = img.expression(
    '0.3029 * blue + 0.2786 * green + 0.4733 * red + 0.5599 * nir + 0.5080 * swir1 + 0.1872 * swir2', {
      'blue': img.select('blue'),
      'green': img.select('green'),
      'red': img.select('red'),
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('brightness');
  
  // NDSI - Normalized Difference Snow Index
  var ndsi = img.normalizedDifference(['green', 'swir1']).rename('ndsi');
  
  // Add all indices to the image
  return img.addBands([
    brightness, ndsi
  ]);
}

// Burn indices, using -MIRBI, so all indices decrease with fire.
function addFireFour(img) {
  // NBR - Normalized Burn Ratio (Key index for fire mapping)
  var nbr = img.normalizedDifference(['nir', 'swir2']).rename('nbr');
  
  // NBR2 - Normalized Burn Ratio 2 (SWIR-based)
  var nbr2 = img.normalizedDifference(['swir1', 'swir2']).rename('nbr2');
  
  // NDVI - Normalized Difference Vegetation Index
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  
  // MIRBI - Mid-Infrared Burn Index * (-1)
  var mirbi = img.expression(
    '10 * swir2 - 9.8 * swir1 + 2', {
      'swir2': img.select('swir2'),
      'swir1': img.select('swir1')
    }).rename('mirbi').multiply(-1); 
  
  // Add all indices to the image
  return img.addBands([
    nbr, nbr2, ndvi, mirbi
  ]);
}

// Burn indices, using -MIRBI, so all indices decrease with fire.
function addFireSix(img) {
  // NBR - Normalized Burn Ratio (Key index for fire mapping)
  var nbr = img.normalizedDifference(['nir', 'swir2']).rename('nbr');
  
  // NBR2 - Normalized Burn Ratio 2 (SWIR-based)
  var nbr2 = img.normalizedDifference(['swir1', 'swir2']).rename('nbr2');
  
  // NDVI - Normalized Difference Vegetation Index
  var ndvi = img.normalizedDifference(['nir', 'red']).rename('ndvi');
  
  // MIRBI - Mid-Infrared Burn Index * (-1)
  var mirbi = img.expression(
    '10 * swir2 - 9.8 * swir1 + 2', {
      'swir2': img.select('swir2'),
      'swir1': img.select('swir1')
    }).rename('mirbi').multiply(-1); 
  
  // ATBI, an improvement over NBRs
  var atbi = nbr.multiply(img.select('nir')).divide(img.select('swir2'))
                .rename('atbi');
  
  var atbi2 = nbr2.multiply(img.select('swir1')).divide(img.select('swir2'))
                  .rename('atbi2');
  
  // Add all indices to the image
  return img.addBands([
    nbr, nbr2, ndvi, mirbi, atbi, atbi2
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

// Compute spectral indices useful for detecting drought (moisture-sensitive)
function addMoistureIndices(img) {

  // NDMI - Normalized Difference Moisture Index
  var ndmi = img.normalizedDifference(['nir', 'swir1']).rename('ndmi');

  // NDWI (Gao 1996) - Moisture content in vegetation
  var ndwi_gao = img.normalizedDifference(['nir', 'swir1']).rename('ndwi_gao');

  // NMDI - Normalized Multiband Drought Index (Wang & Qu 2007)
  var nmdi = img.expression(
    '(nir - (swir1 - swir2)) / (nir + (swir1 - swir2))', {
      'nir': img.select('nir'),
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('nmdi');

  // MSI - Moisture Stress Index (Dryness)
  var msi = img.expression(
    'swir1 / nir', {
      'swir1': img.select('swir1'),
      'nir': img.select('nir')
    }).rename('msi');

  // GVMI - Global Vegetation Moisture Index
  var gvmi = img.expression(
    '(nir + 0.1 - (swir2 + 0.02)) / (nir + 0.1 + swir2 + 0.02)', {
      'nir': img.select('nir'),
      'swir2': img.select('swir2')
    }).rename('gvmi');

  // SWI - Shortwave Infrared Water Stress Index
  var swi = img.expression(
    '(swir1 - swir2) / (swir1 + swir2)', {
      'swir1': img.select('swir1'),
      'swir2': img.select('swir2')
    }).rename('swi');

  // SMRI - Soil Moisture Ratio Index (soil-focused)
  var smri = img.expression(
    '(nir - swir2) / (nir + swir2)', {
      'nir': img.select('nir'),
      'swir2': img.select('swir2')
    }).rename('smri');

  // NBRsoil - Soil-adjusted NBR (good to separate soil vs fire)
  var nbr_soil = img.normalizedDifference(['red', 'swir2']).rename('nbr_soil');

  // NDGI - Normalized Difference Grain Index (dry soil discrimination)
  var ndgi = img.normalizedDifference(['green', 'red']).rename('ndgi');

  // Add all moisture-related indices
  return img.addBands([
    ndmi, ndwi_gao, nmdi, msi, gvmi, swi, smri, nbr_soil, ndgi
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
    .select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']); // remove QA band //, 'thermal'
  var indices = landsat.map(indicesFunction);
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


// MapBiomas LandCover Reclassification for fire, 
// returning multi-band image
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

// MapBiomas LandCover Reclassification for fire, 
// returning ImageCollection
function mapBiomasReclassCol() {
  // Load MapBiomas image (multi-band: one per year)
  var mapbiomas = ee.Image("projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-2/GENERAL/CLASSIFICATION/FINAL_CLASSIFICATION/PAT/PAT-INTEGRACION-FINAL-v4");

  // Old and new values
  var from = [3, 66, 6, 12, 11, 75, 63, 21, 9, 29, 25, 24, 33, 34, 27];
  var to   = [1,  2, 1,  3,  3,  3,  3,  3, 1,  0,  0,  0,  0,  0,  0];

  /*
  new values:
  0: no quemable
  1: bosque
  2: arbustal
  3: pastizal
  */

  // Get all band names
  var bnames = mapbiomas.bandNames();

  // Convert each band to an image with a 'year' property
  var reclassCol = ee.ImageCollection(
    bnames.map(function(bname) {
      bname = ee.String(bname);
      var year = bname.split('_').get(1); // extract the year part
      var img = mapbiomas
        .select([bname])
        .remap(from, to)
        .rename('classification')
        .set('year', ee.Number.parse(year))
        .set('system:time_start', ee.Date.parse('YYYY', year).millis());
      return img;
    })
  );

  return reclassCol;
}

// Compute coefficients-image, from a 3-class vegetation image and 
// a dictionary of coefficients (a simple remap).
function makeCoeffImage(veg, coeffs) {
  // Mask out non-burnable areas (veg == 0)
  veg = veg.updateMask(veg.neq(0));

  // Helper: make one coefficient band
  var coeffBands = Object.keys(coeffs).map(function(varName) {
    // Get the 3 coefficients for veg classes 1, 2, 3
    var values = coeffs[varName];

    // Remap vegetation values (1, 2, 3) to the corresponding coefficients
    var band = veg.remap(
      [1, 2, 3],
      [values[0], values[1], values[2]]
    ).rename(varName);

    return band;
  });

  // Combine all bands into one image
  var coeffImg = ee.Image.cat(coeffBands);

  return coeffImg;
}

// Function to add Day of Year (DOY) band to image
function addDOY(image) {
  // Get time_start property (milliseconds since 1970-01-01)
  var millis = ee.Date(image.get('system:time_start'));
  
  // Compute day of year
  var doy = millis.getRelative('day', 'year').add(1); // add(1) to make it 1–365
  
  var doyimg = ee.Image.constant(doy).rename('DOY').toInt16();
  // copy mask from image
  doyimg = doyimg.updateMask(image.mask());
  
  // Option 1: set as a property
  image = image.set('DOY', doy);
  
  // Option 2 (optional): add as a constant band
  image = image.addBands(doyimg);
  
  return image;
}

// Compute low and high values for a single-band collection.
// Returns a 2-band image: <band>_low and <band>_high.
function computeExtremesSingle(collection) {
  // Get the single band name
  var bandName = ee.String(collection.first().bandNames().get(0));

  // Count valid observations
  var N = collection.count().select([0]).rename('N');

  // Convert to array (remove singleton band dimension)
  var arr = collection.toArray().arrayProject([0]); // shape: [time]

  // Sort ascending (low) and descending (high)
  var sortedAsc  = arr.arraySort();
  var sortedDesc = arr.multiply(-1).arraySort().multiply(-1);
  
  // metrics:
  // m1: first (minimum or maximum)
  // m2: mean(first, second)
  // m3: mean(second, third)

  // --- LOWS ---
  var low1 = sortedAsc.arrayGet([0]);  // min
  var low2 = sortedAsc.arraySlice(0, 0, 2)
                      .arrayReduce(ee.Reducer.mean(), [0])
                      .arrayGet([0]);
  var low3 = sortedAsc.arraySlice(0, 1, 3)
                      .arrayReduce(ee.Reducer.mean(), [0])
                      .arrayGet([0]);

  // --- HIGHS ---
  var high1 = sortedDesc.arrayGet([0]);  // max
  var high2 = sortedDesc.arraySlice(0, 0, 2)
                        .arrayReduce(ee.Reducer.mean(), [0])
                        .arrayGet([0]);
  var high3 = sortedDesc.arraySlice(0, 1, 3)
                        .arrayReduce(ee.Reducer.mean(), [0])
                        .arrayGet([0]);

  // --- Select depending on number of valid obs ---
  // Choose metric according to N
  // N > 20 -> m3
  // 20 >= N >=9 -< m2
  // 9 > N -> m1
  // 2 > N -> masked
  var low = low3
    .where(N.lte(20), low2)
    .where(N.lt(9), low1)
    .updateMask(N.gt(1));

  var high = high3
    .where(N.lte(20), high2)
    .where(N.lt(9), high1)
    .updateMask(N.gt(1));

  // Rename bands
  low  = low.rename(bandName.cat('_low'));
  high = high.rename(bandName.cat('_high'));

  // Return 2-band image
  return low.addBands(high);
}

// Compute a predictor image matching the coeffs_obs dictionary
// keys defined in utils/constants.js.
// indImg: landsat image with the four fire indices.
// summ: image with the summaries of those indices in previous year (low and high).
// coeffs: coefficients dictionary, to get keys.
function makePredictorsObs(indImg, summ, coeffs) {
  // Step 1. Compute "_d" variables for each fire index
  var fireIndices = ['nbr', 'nbr2', 'mirbi', 'ndvi'];
  var diffs = {};
  fireIndices.forEach(function(idx) {
    diffs[idx + '_d'] = summ.select(idx + '_low').subtract(indImg.select(idx)).rename(idx + '_d');
  });

  // Step 2. Build a dictionary of available base variables
  var base = {};
  fireIndices.forEach(function(idx) {
    base[idx] = indImg.select(idx);
    base[idx + '_low'] = summ.select(idx + '_low');
    base[idx + '_high'] = summ.select(idx + '_high');
    base[idx + '_d'] = diffs[idx + '_d'];
  });

  // Step 3. Iterate over all keys in coeffs and build corresponding predictor bands
  var predictorsList = Object.keys(coeffs).map(function(term) {
    if (term === 'intercept') {
      return ee.Image.constant(1).rename('intercept');
    }

    // Interaction term (contains "X")
    if (term.indexOf('X') > -1) {
      var parts = term.split('X');
      var img = ee.Image.constant(1);
      parts.forEach(function(p) {
        img = img.multiply(base[p]);
      });
      return img.rename(term);
    }

    // Regular single variable
    return base[term].rename(term);
  });

  // Step 4. Concatenate into a single multi-band image
  var predictors = ee.Image.cat(predictorsList);

  return predictors;
}

// Add fractional year from system:time_start
function addFracYear(img) {
  // Ensure img is cast as ee.Image
  img = ee.Image(img);
  
  var date = ee.Date(img.get('system:time_start'));
  var year = date.get('year');
  var doy = date.getRelative('day', 'year'); // day-of-year (0–365)
  var daysInYear = ee.Date.fromYMD(year.add(1), 1, 1)
    .difference(ee.Date.fromYMD(year, 1, 1), 'day');
  var fracYear = year.add(doy.divide(daysInYear)); // e.g. 2019.25
  
  return img.addBands(
    ee.Image.constant(fracYear).rename('fracYear').toFloat()
  );
}



// getLogitArray: compute [logit_p, fracYear] array from a given year.
// summ and veg must be computed outside, because to get the array of 
// prev and next years, we use the summ and veg corresponding to focal year
// See usage in getExtendedArray().
function getLogitArray(roi, start, end, summ, veg) {
  // Burn indices from focal year
  var indCol = getLandsat(roi, start, end, addFireFour)
                    .select(cons.ind_names);

  // Create multi-band coefficients image based on vegetation type
  var coeffImg = makeCoeffImage(veg, cons.coeffs_obs);

  // Map over Landsat image collection
  var logitCol = indCol.map(function(indImg) {
    // Common mask across Landsat, summaries, and vegetation
    var commonMask = indImg.select(0).mask()
                           .and(summ.select(0).mask())
                           .and(veg.mask());

    // Create multi-band predictors image (masked)
    var predictors = makePredictorsObs(indImg, summ, cons.coeffs_obs)
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
    
  // Turn into array
  var arr = logitCol
    .sort('system:time_start')
    .toArray();
    
  return arr;
}


// Get the extended array for focal year, borrowing M obs from neighbouring years.
// The vegetation and summarized indices are obtained only from the focal year,
// as fire turs vegetation unburnable, and that brings masking problems.
function getExtendedArray(y, startYear, endYear, M, roi, indSumm, vegCol) {
  var yNum = ee.Number(y);
  var start = ee.Date.fromYMD(yNum, 1, 1);
  var end   = ee.Date.fromYMD(yNum.add(1), 1, 1);
  
  // Burn indices summaries from previous year
  var summ = indSumm.filterDate(start.advance(-1, 'year'), start).first();

  // Vegetation type from previous year
  var veg = vegCol.filterDate(start.advance(-1, 'year'), start).first();

  // Always get focal array
  var arr_focal = getLogitArray(roi, start, end, summ, veg);
  
  // Flags for existence
  var hasPrev = yNum.gt(startYear);
  var hasNext = yNum.lt(endYear);
  
  // Get previous year array once
  var arr_prev_full = ee.Image(
    ee.Algorithms.If(
      hasPrev,
      getLogitArray(roi, start.advance(-1, 'year'), end.advance(-1, 'year'), summ, veg),
      arr_focal.arraySlice(0, 0, 0)  // empty array
    )
  );
  
  // Get next year array once
  var arr_next_full = ee.Image(
    ee.Algorithms.If(
      hasNext,
      getLogitArray(roi, start.advance(1, 'year'), end.advance(1, 'year'), summ, veg),
      arr_focal.arraySlice(0, 0, 0)  // empty array
    )
  );
  
  // Extract and mask previous year's last M observations
  var arr_prev_tail = arr_prev_full
    .updateMask(arr_prev_full.arrayLength(0).gte(M))
    .arraySlice(0, M.multiply(-1), null);
  
  // Extract and mask next year's first M observations
  var arr_next_head = arr_next_full
    .updateMask(arr_next_full.arrayLength(0).gte(M))
    .arraySlice(0, 0, M);
  
  // Concatenate arrays
  var extendedArray = ee.Algorithms.If(
    hasPrev,
    ee.Algorithms.If(
      hasNext,
      arr_prev_tail.arrayCat(arr_focal, 0).arrayCat(arr_next_head, 0),
      arr_prev_tail.arrayCat(arr_focal, 0)
    ),
    ee.Algorithms.If(
      hasNext,
      arr_focal.arrayCat(arr_next_head, 0),
      arr_focal
    )
  );
  
  return ee.Image(extendedArray);
}


/**
 * Centered 5-observation median smoother for logit_p
 *
 * @param {ee.Image} arrayImg - Array [time, 2] with columns [logit_p, fracYear].
 * @returns {ee.Image} Smoothed array [time-(K-1), 2].
 */
function smoothBurnProb(arrayImg) {
  var K = ee.Number(5); // make variable in future versions
  
  // Split columns
  var logit_p = arrayImg.arraySlice(1, 0, 1);
  var fracYear = arrayImg.arraySlice(1, 1, 2);

  // Create the 5 shifted slices (each has length T-(K-1))
  var a0 = logit_p.arraySlice(0, 0, -4); // indices 0 .. T-5
  var a1 = logit_p.arraySlice(0, 1, -3); // indices 1 .. T-4
  var a2 = logit_p.arraySlice(0, 2, -2); // center slice
  var a3 = logit_p.arraySlice(0, 3, -1); // ...
  var a4 = logit_p.arraySlice(0, 4);     // indices 4 .. T-1
  
  // Stack them into a 2D array [time_centered, window_index] of shape [T-4, 5]
  // We concatenate along axis 1 so each row is the 5 values for that center time.
  var stacked = a0.arrayCat(a1, 1)
                  .arrayCat(a2, 1)
                  .arrayCat(a3, 1)
                  .arrayCat(a4, 1); // shape: [T-4, 5]
  
  // Compute the median across the window-axis (axis 1)
  var med5 = stacked.arrayReduce(ee.Reducer.median(), [1]); // shape: [T-4]

  // Midpoint timestamps
  var fracYear_subset = fracYear.arraySlice(0, 2, -2);

  // Combine [logit_p_median, fracYear_subset]
  var smoothed = med5.arrayCat(fracYear_subset, 1);
  return smoothed;
}

// Simple softplus and invLogit (operate elementwise on array-valued images)
function softplus(x) {
  return x.exp().add(1).log();
}

function invLogit(x) {
  return x.multiply(-1).exp().add(1).pow(-1);
}

// Summarize the time series of burn probability. 
// ts_array has structure [dates, vars] 
// with vars = [logit_p (smoothed), fracYear]
function summarizeTS(ts_array) {
  
  // Keep the second (vars) dimension: each slice is shape [dates=T, 1]
  var logit_p = ts_array.arraySlice(1, 0, 1);   // shape: [T, 1]
  var fracYear = ts_array.arraySlice(1, 1, 2);  // shape: [T, 1]
  
  // --- Step 1: burn probability (keeps shape [T,1]) ---
  var p = invLogit(logit_p);   // [T,1]
  
  // --- Step 2: cumulative probability ---
  // s_t = softplus(logit_p)  => [T,1]
  var s = softplus(logit_p);
  
  // arrayAccum along axis 0 computes cumulative sum over dates and keeps shape [T,1]
  var S = s.arrayAccum(0);  // [T,1]
  var P = ee.Image(1).subtract(S.multiply(-1).exp()); // [T,1]
  
  // --- Step 3: differences (length L = T-1), shapes [L,1] ---
  var pdiff = p.arraySlice(0, 1, null).subtract(p.arraySlice(0, 0, -1));   // [L,1]
  var Pdiff = P.arraySlice(0, 1, null).subtract(P.arraySlice(0, 0, -1));   // [L,1]
  
  // --- Step 4: scalar metrics (reduce across time axis 0) ---
  // arrayReduce with axis [0] will return an array of shape [1,1]; arrayGet([0,0]) reads scalar
  var pmax = p.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0,0]);
  var pdiff_max = pdiff.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0,0]);
  var Pmax = P.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0,0]);
  var Pdiff_max = Pdiff.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0,0]);
  var Pdiff_mean = Pdiff.arrayReduce(ee.Reducer.mean(), [0]).arrayGet([0,0]);
  
  // --- Step 5: find dates around the max pdiff ---
  // dates_behind and dates_ahead are already [L,1] because fracYear was [T,1]
  var dates_behind = fracYear.arraySlice(0, 0, -1);   // [L,1]
  var dates_ahead  = fracYear.arraySlice(0, 1, null); // [L,1]
  
  // Stack columns: [date_pre, date_post] -> shape [L,2]
  var dates = dates_behind.arrayCat(dates_ahead, 1);  
    
  // print('Shape pdates:', pdates.arrayDimensions());

  // Sort rows by column 0 (pdiff) ascending, take last row = max pdiff
  var dates_sorted = dates.arraySort(pdiff);                    // [L,3] sorted
  var dates_burn = dates_sorted.arraySlice(0, -1, null)  // [1,3]
                     .arrayProject([1]);                  // -> [3] (vector: [pdiff, date_pre, date_post])
  
  // var pdiff_at_max = pdates_maxRow.arrayGet([0]);
  var date_pre  = dates_burn.arrayGet([0]);
  var date_post = dates_burn.arrayGet([1]);
  var date_mid  = date_pre.add(date_post).divide(2);
  
  // number of observations after the pdiff max: idx_max = index of pdiff argmax
  var idx_max = pdiff.arrayProject([0]).arrayArgmax(); // scalar index (0-based)
  var n_after_max = pdiff.arrayLength(0)
    .subtract(idx_max).subtract(1)
    .arrayGet([0]);
    
  // n_obs in the burn prob series (smoothed)
  var n_obs = p.arrayLength(0);
  
  // --- Step 6: compose an output image with bands named as you like ---
  // Build scalar images for each metric. For scalars we wrap with ee.Image()
  var out = ee.Image.cat([
    ee.Image(pmax).rename('pmax'),
    ee.Image(pdiff_max).rename('pdiff_max'),
    ee.Image(Pmax).rename('Pmax'),
    ee.Image(Pdiff_max).rename('Pdiff_max'),
    ee.Image(Pdiff_mean).rename('Pdiff_mean'),
    ee.Image(date_pre).rename('date_pre'),
    ee.Image(date_post).rename('date_post'),
    ee.Image(date_mid).rename('date_mid'),
    ee.Image(n_obs).rename('n_obs'),
    ee.Image(n_after_max).rename('n_after_max')
  ]);
  
  return out;
}

// Create predictor image for the annual model
// tsm: image with time-series metrics (pmax, pdiff_max, etc.)
// summ: image with burn index summaries (_low, _high)
// coeffs: coefficients dictionary (e.g., coeffs_annual)
function makePredictorsAnnual(tsm, summ, coeffs) {
  // Step 1. Merge tsm and summ images
  var base = tsm.addBands(summ);

  // Step 2. Build a dictionary of base variable bands
  var baseDict = {};
  base.bandNames().evaluate(function(names) {
    names.forEach(function(n) { baseDict[n] = base.select(n); });
  });

  // Step 3. Build predictors based on coeffs keys
  var predictorsList = Object.keys(coeffs).map(function(term) {
    if (term === 'intercept') {
      return ee.Image.constant(1).rename('intercept');
    }

    // Interaction term (contains "X")
    if (term.indexOf('X') > -1) {
      var parts = term.split('X');
      var img = ee.Image.constant(1);
      parts.forEach(function(p) {
        img = img.multiply(base.select(p));
      });
      return img.rename(term);
    }

    // Regular variable
    return base.select(term).rename(term);
  });

  // Step 4. Concatenate all predictors into one multi-band image
  var predictors = ee.Image.cat(predictorsList);

  return predictors;
}

// Shape metrics for fire polygons
function addShapeMetrics(feat) {

  var geom = feat.geometry();
  var area = geom.area({'maxError': 30});  // in m²
  var perimeter = geom.perimeter({'maxError': 30}); // in meters

  // --------- Convex hull metrics -------------
  var hull = geom.convexHull({'maxError': 30});
  var hullArea = hull.area({'maxError': 30});

  // Area / Convex Hull Area  (compactness / sparsity)
  var convexity = area.divide(hullArea);

    // --------- Minimum Bounding Rectangle ----------
  var mbr = geom.bounds();
  var mbrArea = mbr.area({'maxError': 30});

  // Extract rectangle corners
  var coords = ee.List(mbr.coordinates().get(0));
  var p1 = ee.Geometry.Point(coords.get(0));
  var p2 = ee.Geometry.Point(coords.get(1));
  var p3 = ee.Geometry.Point(coords.get(2));

  // Distance between p1–p2 and p2–p3 -> sides in meters
  var side1 = p1.distance(p2);   // meters
  var side2 = p2.distance(p3);   // meters

  var maxSide = side1.max(side2);
  var minSide = side1.min(side2);

  var elongation = maxSide.divide(minSide);
  var mbrFill = area.divide(mbrArea);

  // --------- Classic metrics: circularity & shape index -------
  var circularity = ee.Number(4).multiply(Math.PI).multiply(area)
                       .divide(perimeter.pow(2));

  var shapeIndex = perimeter.divide(
      ee.Number(2).multiply(ee.Number(Math.PI).multiply(area).sqrt())
  );

  // --------- Add all properties to Feature ----------
  return feat.set({
    area_m2: area,
    perimeter_m: perimeter,
    convexity: convexity,            // Area / Convex Hull Area
    mbr_fill: mbrFill,               // Area / MBR area
    mbr_elongation: elongation,      // MBR long/short side ratio
    circularity: circularity,        // 4πA / P²
    shape_index: shapeIndex          // P / (2√πA)
  });
};


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

// Exports ----------------------------------------------------------

exports = {
  getLandsat: getLandsat,
  makeNBRtsPanel: makeNBRtsPanel,
  addNBR: addNBR,
  addNBR_NDVI: addNBR_NDVI,
  addFireIndices: addFireIndices,
  addFireFour: addFireFour,
  addFireSix: addFireSix,
  addBright: addBright,
  addAncillaryIndices: addAncillaryIndices,
  addMoistureIndices: addMoistureIndices,
  mapBiomasReclass: mapBiomasReclass,
  mapBiomasReclassCol: mapBiomasReclassCol,
  addDOY: addDOY,
  computeExtremesSingle: computeExtremesSingle,
  makeCoeffImage: makeCoeffImage,
  makePredictorsObs: makePredictorsObs,
  addFracYear: addFracYear,
  getLogitArray: getLogitArray,
  getExtendedArray: getExtendedArray,
  smoothBurnProb: smoothBurnProb,
  softplus: softplus,
  invLogit: invLogit,
  summarizeTS: summarizeTS,
  makePredictorsAnnual: makePredictorsAnnual,
  addShapeMetrics: addShapeMetrics
};