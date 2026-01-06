// Imports 
// (most are geometries around fires, hand-drawn)

var fires_barbera = ee.FeatureCollection("projects/ivanbarbera-001/assets/patagonian_fires_2025"),
    steffen_martin = 
    /* color: #00ff00 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.82095619439193, -41.429829908057116],
          [-71.82095619439193, -41.591283309130205],
          [-71.36777015923568, -41.591283309130205],
          [-71.36777015923568, -41.429829908057116]]], null, false),
    large_area = 
    /* color: #d63000 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.36898129551116, -38.73520374954311],
          [-72.02816098301116, -40.12678319669135],
          [-72.35775082676116, -42.95478775482978],
          [-71.91829770176116, -44.46355689945934],
          [-68.73226254551116, -44.44787299372979],
          [-68.64437192051116, -38.700916155023414]]]),
    la_negra_01 = 
    /* color: #98ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.39006652147928, -39.51389882590646],
          [-70.39006652147928, -39.654134499423876],
          [-70.12021483690897, -39.654134499423876],
          [-70.12021483690897, -39.51389882590646]]], null, false),
    coquelen_03 = 
    /* color: #0b4a8b */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.43824436394, -40.509692151733276],
          [-70.43824436394, -40.7514874846447],
          [-70.12238743034625, -40.7514874846447],
          [-70.12238743034625, -40.509692151733276]]], null, false),
    montenegro_24 = 
    /* color: #bf04c2 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.38318424233255, -42.7847949598975],
          [-70.38318424233255, -42.89354945424617],
          [-70.23967533119973, -42.89354945424617],
          [-70.23967533119973, -42.7847949598975]]], null, false),
    lonco_vaca_16 = 
    /* color: #00ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-69.46068782063651, -40.10120891109088],
          [-69.46068782063651, -40.23553247029478],
          [-69.09127253743338, -40.23553247029478],
          [-69.09127253743338, -40.10120891109088]]], null, false),
    naupa_huen_02 = 
    /* color: #0000ff */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-69.45912420934086, -39.90830574531127],
          [-69.45912420934086, -40.15173664754887],
          [-69.12747442906742, -40.15173664754887],
          [-69.12747442906742, -39.90830574531127]]], null, false),
    achico_16 = 
    /* color: #999900 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-70.47578738093979, -40.46407683980347],
          [-70.30687258601792, -40.55074071712312],
          [-70.08439944148667, -40.40972435080039],
          [-70.01848147273667, -40.30193493432672],
          [-70.14757082820542, -40.202364799937776],
          [-70.27528689265854, -40.21495016318005],
          [-70.48540041804917, -40.38880784875619]]]),
    trevelin_19 = 
    /* color: #d63000 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.24932399310713, -43.026675471486726],
          [-71.24932399310713, -43.17908242582206],
          [-70.84557643451338, -43.17908242582206],
          [-70.84557643451338, -43.026675471486726]]], null, false),
    turbio_15 = 
    /* color: #d63000 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-72.04864564589596, -42.217588786493614],
          [-72.04864564589596, -42.36083097883633],
          [-71.63116517714596, -42.36083097883633],
          [-71.63116517714596, -42.217588786493614]]], null, false),
    norquinco_14 = 
    /* color: #98ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.40889344541627, -39.08979730002483],
          [-71.40889344541627, -39.20056290403224],
          [-71.18161378233033, -39.20056290403224],
          [-71.18161378233033, -39.08979730002483]]], null, false),
    tromen_22 = 
    /* color: #0b4a8b */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.1982475156094, -39.42103542899218],
          [-71.1982475156094, -39.55034112305871],
          [-71.07121809666408, -39.55034112305871],
          [-71.07121809666408, -39.42103542899218]]], null, false),
    alerces_15 = 
    /* color: #d63000 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.70659651914919, -42.80752702964225],
          [-71.70659651914919, -42.94891908126898],
          [-71.55759444395387, -42.94891908126898],
          [-71.55759444395387, -42.80752702964225]]], null, false),
    lolog_08 = 
    /* color: #0b4a8b */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.63047882704723, -39.9423259278639],
          [-71.63047882704723, -40.066454118304335],
          [-71.37710663466441, -40.066454118304335],
          [-71.37710663466441, -39.9423259278639]]], null, false),
    patriada_12 = 
    /* color: #ffc82d */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.6709590512008, -42.04681886629233],
          [-71.6709590512008, -42.20469162710333],
          [-71.37638812834923, -42.20469162710333],
          [-71.37638812834923, -42.04681886629233]]], null, false),
    sanico_16 = 
    /* color: #00ffff */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-70.37888935988911, -40.113638440343664],
          [-70.36240986770161, -40.06215676560237],
          [-70.28962544387349, -40.036927047261926],
          [-70.32121113723286, -39.94012663523209],
          [-70.53681782668599, -39.94644388653453],
          [-70.73319844192036, -40.01799863049357],
          [-70.79224995559224, -40.072666391953405],
          [-70.77165059035786, -40.1724269554842],
          [-70.66178730910786, -40.19865540186407],
          [-70.53681782668599, -40.18816524026588],
          [-70.47776631301411, -40.15248655422495]]]),
    piedra_pintada_16 = 
    /* color: #bf04c2 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-70.47635617725686, -40.15508087804784],
          [-70.4702248897421, -40.24110468307964],
          [-70.34799031203755, -40.22015515999445],
          [-70.1474898237563, -40.20127768871717],
          [-70.1474898237563, -40.16035846489432],
          [-70.15229634231099, -40.02483449796964],
          [-70.27863911574849, -40.035349879806425],
          [-70.35897664016255, -40.072140949145606],
          [-70.3782027143813, -40.11521379574534]]]),
    comarca_estepa_21 = 
    /* color: #ff0000 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.3282681791046, -41.989928125656085],
          [-71.32689488808897, -42.018501747163256],
          [-71.30217564980772, -42.0756104894844],
          [-71.05498326699522, -42.0756104894844],
          [-71.05635655801085, -41.8795953980023],
          [-71.2898160306671, -41.883685198755614],
          [-71.3008023587921, -41.91945978882262],
          [-71.32552159707335, -41.939893412368995],
          [-71.3062955228546, -41.96236283807145],
          [-71.30904210488585, -41.97665743948045]]]),
    comarca_21 = 
    /* color: #00ff00 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.3282681791046, -42.012379908562565],
          [-71.32689488808897, -41.9940108572362],
          [-71.31041539590147, -41.981761876880675],
          [-71.31590855996397, -41.96236283807145],
          [-71.32964147012022, -41.94295789135434],
          [-71.3172818509796, -41.92559056314575],
          [-71.29668248574522, -41.88981940906777],
          [-71.30217564980772, -41.86016526976931],
          [-71.35710729043272, -41.83254387603116],
          [-71.5150357572296, -41.822310704027366],
          [-71.5534879056671, -41.84686756878965],
          [-71.56722081582335, -41.96134167237118],
          [-71.53563512246397, -41.99299019889199],
          [-71.32689488808897, -42.04604272838625]]]),
    cholila = 
    /* color: #0000ff */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-72.08298096292782, -42.59654049901388],
          [-71.39770874613095, -42.59148563581402],
          [-71.3949621640997, -42.311821415667325],
          [-71.62704834574032, -42.30572789258794],
          [-71.62704834574032, -42.36257783394942],
          [-72.0925940000372, -42.35953360414874]]]),
    alerces_24 = 
    /* color: #d63000 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.55843426207016, -42.88024259902754],
          [-71.52993847349595, -42.88577709362243],
          [-71.5220420501561, -42.90212610895381],
          [-71.5220420501561, -42.964966542421905],
          [-71.40050579527329, -42.96672515170094],
          [-71.39947582701157, -42.859609654311974],
          [-71.42659832457016, -42.807241493093834],
          [-71.51792217710923, -42.74045816531085],
          [-71.67344738462876, -42.73314542955064],
          [-71.75172497251938, -42.7916231681571],
          [-71.70159985044907, -42.849038889614675],
          [-71.66932751158188, -42.888041061946794],
          [-71.59070660093735, -42.87571400688891],
          [-71.57251049498032, -42.87571400688891]]]),
    gualjaina_17 = 
    /* color: #d63000 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.813549046776, -42.81629607261548],
          [-70.813549046776, -42.90286827538451],
          [-70.62403488661975, -42.90286827538451],
          [-70.62403488661975, -42.81629607261548]]], null, false),
    costa_del_lepa_04 = 
    /* color: #98ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.8716380893083, -42.47085396812556],
          [-70.8716380893083, -42.54425107236024],
          [-70.73087576020674, -42.54425107236024],
          [-70.73087576020674, -42.47085396812556]]], null, false),
    quetrequile_16 = 
    /* color: #98ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-69.12931870929077, -41.48079349929439],
          [-69.12931870929077, -41.59592102073671],
          [-68.98512315265015, -41.59592102073671],
          [-68.98512315265015, -41.48079349929439]]], null, false),
    jacobacci_18 = 
    /* color: #0b4a8b */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.01561936460487, -41.258018460760496],
          [-70.01561936460487, -41.341071216821476],
          [-69.85631760679237, -41.341071216821476],
          [-69.85631760679237, -41.258018460760496]]], null, false),
    necolman_05 = 
    /* color: #ffc82d */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-70.56791030361947, -41.07976521541384],
          [-70.56791030361947, -41.148827194531655],
          [-70.46113692715463, -41.148827194531655],
          [-70.46113692715463, -41.07976521541384]]], null, false),
    foyel_02 = 
    /* color: #00ffff */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.30448502016228, -41.81696512613165],
          [-71.26122635317009, -41.84305866073468],
          [-71.24886673402946, -41.877322236309034],
          [-71.15136307192009, -41.87681097462394],
          [-71.14792984438103, -41.85737999995121],
          [-71.15479629945915, -41.81031213189478],
          [-71.1630360455529, -41.77140387569909],
          [-71.24200027895134, -41.73042230527979],
          [-71.36353653383415, -41.71812273252295],
          [-71.36353653383415, -41.783693244750474]]]),
    foyel_00 = 
    /* color: #bf04c2 */
    /* shown: false */
    ee.Geometry.Polygon(
        [[[-71.23719376039665, -41.720178294623246],
          [-71.17127579164665, -41.723253310178876],
          [-71.12801712465446, -41.69916175009395],
          [-71.1245838971154, -41.63555770846066],
          [-71.19393509340446, -41.620673504040845],
          [-71.27427261781853, -41.621186809672395],
          [-71.29075211000603, -41.655568978935996],
          [-71.29624527406853, -41.68736897301298],
          [-71.26877945375603, -41.713515256112835]]]),
    guacho_21 = 
    /* color: #00ff00 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.43674868246303, -43.767155429563566],
          [-71.43674868246303, -43.85659223622211],
          [-71.27950686117397, -43.85659223622211],
          [-71.27950686117397, -43.767155429563566]]], null, false),
    nahuel_huapi_15 = 
    /* color: #0000ff */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.3436246413943, -41.01062941922761],
          [-71.3436246413943, -41.06967025699438],
          [-71.16921668240992, -41.06967025699438],
          [-71.16921668240992, -41.01062941922761]]], null, false),
    corcovado_18 = 
    /* color: #999900 */
    /* shown: false */
    /* displayProperties: [
      {
        "type": "rectangle"
      }
    ] */
    ee.Geometry.Polygon(
        [[[-71.46988531828768, -43.63567273464246],
          [-71.46988531828768, -43.70297233144996],
          [-71.39847418547518, -43.70297233144996],
          [-71.39847418547518, -43.63567273464246]]], null, false);
          
// -------------------------------------------------------------

/*
  Create a feature collection with a rectangular roi by fire, and the
  dates defining the pre- and post-fire periods.
*/

// Edit this to choose the date range for each fire.
var roi = corcovado_18;
var id = 'fire_30'; // to get dNBR based on dates
var year = ee.Number(2018).toInt();
var startDate = ee.Date.fromYMD(year.add(-2), 07, 01);
var endDate = ee.Date.fromYMD(year.add(1), 07, 01);

Map.centerObject(roi, 12);
// Map.setCenter(large_area);

// Import Landsat imagery ---------------------------------------------------

var funk = require("users/mapbiomas-arg/fuego/utils:functions.js");

var landsat = funk.getLandsat(roi, startDate, endDate, funk.addNBR);

// Impost MODIS burned area -------------------------------------------------

// Inputs for MODIS
var roi = large_area;
var startYear = 2001;   // MCD64A1 starts in 2000/2001 depending on region
var endYear   = 2025;

// Use the latest collection (v6.1). If unavailable in your GEE, switch to 'MODIS/006/MCD64A1'.
var mcd64 = ee.ImageCollection('MODIS/061/MCD64A1')
  .filterBounds(roi)
  .filterDate(ee.Date.fromYMD(startYear,1,1), ee.Date.fromYMD(endYear+1,1,1))
  .select('BurnDate');  // BurnDate > 0 means burned within that month

// Helper: make a 0/1 mask per month where burned
var monthlyBurnMask = mcd64.map(function(img){
  // Any positive BurnDate means burned
  return img.gt(0).selfMask()
    .copyProperties(img, ['system:time_start']);
});

// Aggregate by year: for each year, mark pixels that burned at any month in that year.
var years = ee.List.sequence(startYear, endYear);
var perYearImages = ee.ImageCollection.fromImages(
  years.map(function(y){
    y = ee.Number(y);
    var start = ee.Date.fromYMD(y,1,1);
    var stop  = start.advance(1, 'year');

    // If a pixel burned any month in this year -> set it to that year value
    var burnedThisYear = monthlyBurnMask
      .filterDate(start, stop)
      .max();                     // 1 where burned at least once in the year
    var yearImg = burnedThisYear
      .updateMask(burnedThisYear) // keep only burned pixels
      .multiply(y)                // put the calendar year as the pixel value
      .toInt16()
      .rename('burn_year')
      .set('year', y);
    return yearImg;
  })
);

// First detected burn year (earliest year)
var firstBurnYear = perYearImages.reduce(ee.Reducer.max())  // min year across stack
  .rename('burn_year')
  .clip(roi);

// Optional: Most recent burn year (if pixels reburned)
// var lastBurnYear = perYearImages.reduce(ee.Reducer.max()).rename('burn_year').clip(roi);

// Styling
var vis = {
  min: startYear,
  max: endYear,
  palette: [
    // pick a simple ramp; tweak as you like
    '440154','3b528b','21918c','5ec962','fde725'
  ]
};

// Add to map. Unburned pixels are masked; clicking shows the year.
// Map.centerObject(roi, 8);
Map.addLayer(firstBurnYear, vis, 'MODIS First Burn Year', true);

// MapBiomas classification -------------------------------------------
var vegtype_all = funk.mapBiomasReclass();
var bandName = ee.String('classification_').cat(year.add(-1).format());
var vegtype = vegtype_all.select(bandName);

// Mapbiomas
var vegvis = {
  min: 0,
  max: 3,
  palette: ["black", "green", "lightgreen", "orange"]
};
Map.addLayer(vegtype, vegvis, "Vegetation type " + year.add(-1).getInfo(), false);

// Landsat NBR ts------------------------------------------------------

Map.addLayer(landsat.select("nbr"), {}, "NBR ts", false);

// Feature collection -------------------------------------------------

// Create a feature collection with manually defined fire events
var training_events = ee.FeatureCollection([
  
  // Boscosos ------------------------------------------
  
  ee.Feature(
    cholila,
    {
      'fire_id': 'fire_01',
      'polygon_id': '2015_50',
      'description': 'cholila',

      'pre_upr': '2015-02-14', 
      'post_lwr': '2015-03-10', 
      'post_upr_long': '2015-12-01',
      'post_upr_short': '2015-12-01' 
    } 
  ),
  
  ee.Feature(
    steffen_martin,
    {
      'fire_id': 'fire_02',
      'polygon_id': '2022_2125136700_r',
      'description': 'steffen_martin',

      'pre_upr': '2021-11-30',
      'post_lwr': '2022-02-01',
      'post_upr_long': '2022-12-01',
      'post_upr_short': '2022-12-01'
    }
  ),
  
  ee.Feature(
    turbio_15,
    {
      'fire_id': 'fire_03',
      'polygon_id': '2015_47',
      'description': 'turbio_15',

      'pre_upr': '2015-02-06',
      'post_lwr': '2015-03-02',
      'post_upr_long': '2015-11-30',
      'post_upr_short': '2015-11-30'
    }
  ),

  ee.Feature(
    norquinco_14,
    {
      'fire_id': 'fire_04',
      'polygon_id': '2014_1',
      'description': 'norquinco_14',

      'pre_upr': '2014-01-10',
      'post_lwr': '2014-01-18',
      'post_upr_long': '2014-11-30',
      'post_upr_short': '2014-10-30'
    }
  ),  
  
  ee.Feature(
    tromen_22,
    {
      'fire_id': 'fire_05',
      'polygon_id': '2022_TromenEste',
      'description': 'tromen_22',

      'pre_upr': '2021-12-15',
      'post_lwr': '2021-12-31',
      'post_upr_long': '2022-10-15',
      'post_upr_short': '2022-10-15'
    }
  ),  
  
  ee.Feature(
    comarca_21,
    {
      'fire_id': 'fire_06',
      'polygon_id': '2021_2146405150_W',
      'description': 'comarca_21',

      'pre_upr': '2021-01-25',
      'post_lwr': '2021-02-07',
      'post_upr_long': '2021-11-30',
      'post_upr_short': '2021-10-30'
    }
  ),  
  
  ee.Feature(
    alerces_15,
    {
      'fire_id': 'fire_07',
      'polygon_id': '2015_53',
      'description': 'alerces_15',

      'pre_upr': '2015-03-18',
      'post_lwr': '2015-03-26',
      'post_upr_long': '2015-12-31',
      'post_upr_short': '2015-12-31'
    }
  ),  
  
  ee.Feature(
    alerces_24,
    {
      'fire_id': 'fire_08',
      'polygon_id': '2024_2143416051',
      'description': 'alerces_24',

      'pre_upr': '2024-01-22',
      'post_lwr': '2024-02-07',
      'post_upr_long': '2024-12-31',
      'post_upr_short': '2024-10-31'
    }
  ),
  
  ee.Feature(
    lolog_08,
    {
      'fire_id': 'fire_09',
      'polygon_id': '2008_5',
      'description': 'lolog_08',

      'pre_upr': '2008-02-27',
      'post_lwr': '2008-04-05',
      'post_upr_long': '2008-12-31',
      'post_upr_short': '2008-10-31'
    }
  ),
  
  ee.Feature(
    patriada_12,
    {
      'fire_id': 'fire_10',
      'polygon_id': '2012_57-2012_58',
      'description': 'patriada_12',

      'pre_upr': '2011-12-31',
      'post_lwr': '2012-01-07',
      'post_upr_long': '2012-12-31',
      'post_upr_short': '2012-10-31'
    }
  ),

  // Esteparios -----------------------------------
  
  ee.Feature(
    comarca_estepa_21,
    {
      'fire_id': 'fire_11',
      'polygon_id': '2021_2146405150_E',
      'description': 'comarca_estepa_21',

      'pre_upr': '2021-01-31',
      'post_lwr': '2021-03-15',
      'post_upr_long': '2021-12-01',
      'post_upr_short': '2021-12-01'
    }
  ),
  
  ee.Feature(
    la_negra_01,
    {
      'fire_id': 'fire_12',
      'polygon_id': null,
      'description': 'la_negra_01',
      
      'pre_upr': '2001-02-16',
      'post_lwr': '2001-02-23',
      'post_upr_long': '2001-05-31',
      'post_upr_short': '2001-03-31'
    }
  ),
  
  ee.Feature(
    coquelen_03,
    {
      'fire_id': 'fire_13',
      'polygon_id': null,
      'description': 'coquelen_03',

      'pre_upr': '2003-02-13',
      'post_lwr': '2003-02-22',
      'post_upr_long': '2003-05-31',
      'post_upr_short': '2003-05-31'
    }
  ),
  
  ee.Feature(
    montenegro_24,
    {
      'fire_id': 'fire_14',
      'polygon_id': null,
      'description': 'montenegro_24',

      'pre_upr': '2024-02-16',
      'post_lwr': '2024-03-03',
      'post_upr_long': '2024-04-30',
      'post_upr_short': '2024-04-30'
    }
  ),

  ee.Feature(
    lonco_vaca_16,
    {
      'fire_id': 'fire_15',
      'polygon_id': null,
      'description': 'lonco_vaca_16',

      'pre_upr': '2015-12-17',
      'post_lwr': '2016-01-02',
      'post_upr_long': '2016-03-21',
      'post_upr_short': '2016-02-28'
    }
  ),
  
  ee.Feature(
    naupa_huen_02,
    {
      'fire_id': 'fire_16',
      'polygon_id': null,
      'description': 'naupa_huen_02',

      'pre_upr': '2001-12-25',
      'post_lwr': '2002-01-18',
      'post_upr_long': '2002-03-31',
      'post_upr_short': '2002-03-31'
    }
  ),
  
  ee.Feature(
    achico_16,
    {
      'fire_id': 'fire_17',
      'polygon_id': null,
      'description': 'achico_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-09',
      'post_upr_long': '2016-04-30',
      'post_upr_short': '2016-04-14'
    }
  ),
  
  ee.Feature(
    sanico_16,
    {
      'fire_id': 'fire_18',
      'polygon_id': null,
      'description': 'sanico_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-09',
      'post_upr_long': '2016-04-21',
      'post_upr_short': '2016-04-21'
    }
  ),
  
  ee.Feature(
    piedra_pintada_16,
    {
      'fire_id': 'fire_19',
      'polygon_id': null,
      'description': 'piedra_pintada_16',

      'pre_upr': '2015-12-31',
      'post_lwr': '2016-01-17',
      'post_upr_long': '2016-05-31',
      'post_upr_short': '2016-04-21'
    }
  ),
  
  ee.Feature(
    trevelin_19,
    {
      'fire_id': 'fire_20',
      'polygon_id': null,
      'description': 'trevelin_19',

      'pre_upr': '2019-02-17',
      'post_lwr': '2019-02-18',
      'post_upr_long': '2019-05-24',
      'post_upr_short': '2019-05-24'
    }
  ),
  
  // First export did not include the following:
  // Esteparios [21-25] --------------------------------
  
  ee.Feature(
    gualjaina_17,
    {
      'fire_id': 'fire_21',
      'polygon_id': null,
      'description': 'gualjaina_17',

      'pre_upr': '2017-01-27',
      'post_lwr': '2017-02-20',
      'post_upr_long': '2017-03-30',
      'post_upr_short': '2017-03-30'
    }
  ),
  
  ee.Feature(
    costa_del_lepa_04,
    {
      'fire_id': 'fire_22',
      'polygon_id': null,
      'description': 'costa_del_lepa_04',

      'pre_upr': '2004-02-01',
      'post_lwr': '2004-02-17',
      'post_upr_long': '2004-03-30',
      'post_upr_short': '2004-03-30'
    }
  ),
  
  ee.Feature(
    quetrequile_16,
    {
      'fire_id': 'fire_23',
      'polygon_id': null,
      'description': 'quetrequile_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-10',
      'post_upr_long': '2016-06-30',
      'post_upr_short': '2016-03-30'
    }
  ),
  
  ee.Feature(
    jacobacci_18,
    {
      'fire_id': 'fire_24',
      'polygon_id': null,
      'description': 'jacobacci_18',

      'pre_upr': '2018-01-30',
      'post_lwr': '2018-02-07',
      'post_upr_long': '2018-06-30',
      'post_upr_short': '2018-03-30'
    }
  ),
  
  
  ee.Feature(
    necolman_05,
    {
      'fire_id': 'fire_25',
      'polygon_id': null,
      'description': 'necolman_05',

      'pre_upr': '2005-01-17',
      'post_lwr': '2005-01-18',
      'post_upr_long': '2005-06-30',
      'post_upr_short': '2005-03-30'
    }
  ),
  
  // Boscosos [26-30] --------------------------------------
  
  ee.Feature(
    foyel_02,
    {
      'fire_id': 'fire_26',
      'polygon_id': '2002_19',
      'description': 'foyel_02',

      'pre_upr': '2002-02-12',
      'post_lwr': '2002-02-17',
      'post_upr_long': '2002-12-30',
      'post_upr_short': '2002-03-30'
    }
  ),
  
  ee.Feature(
    foyel_00,
    {
      'fire_id': 'fire_27',
      'polygon_id': '2000_31j',
      'description': 'foyel_00',

      'pre_upr': '1999-10-18',
      'post_lwr': '1999-10-22',
      'post_upr_long': '2000-10-30',
      'post_upr_short': '2000-03-30'
    }
  ),
  
  ee.Feature(
    guacho_21,
    {
      'fire_id': 'fire_28',
      'polygon_id': '2021_1229',
      'description': 'guacho_21',

      'pre_upr': '2021-02-25',
      'post_lwr': '2021-03-05',
      'post_upr_long': '2021-12-30',
      'post_upr_short': '2021-04-30'
    }
  ),
  
  ee.Feature(
    nahuel_huapi_15,
    {
      'fire_id': 'fire_29',
      'polygon_id': '2015_16',
      'description': 'nahuel_huapi_15',

      'pre_upr': '2015-01-04',
      'post_lwr': '2015-01-08',
      'post_upr_long': '2015-12-30',
      'post_upr_short': '2015-06-30'
    }
  ),
  
  ee.Feature(
    corcovado_18,
    {
      'fire_id': 'fire_30',
      'polygon_id': '2018_44',
      'description': 'corcovado_18',

      'pre_upr': '2017-11-29',
      'post_lwr': '2017-12-02',
      'post_upr_long': '2018-12-30',
      'post_upr_short': '2018-04-30'
    }
  )
]);

Map.addLayer(training_events, {}, "events", false);

// Visualize landsat dNBR using focal dates ---------------------------

var feat = training_events.filterMetadata("fire_id", "equals", id).first();
var pre = landsat.filterDate(
    ee.Date(feat.get("pre_upr")).advance(-3, "month"),
    ee.Date(feat.get("pre_upr")).advance(1, "day")
  ).median();
  
var post_long = landsat.filterDate(
    feat.get("post_lwr"),
    feat.get("post_upr_long")
  ).median();
  
var post_short = landsat.filterDate(
    feat.get("post_lwr"),
    feat.get("post_upr_short")
  ).median();

var dnbr_long = pre.select("nbr").subtract(post_long.select("nbr"));
var dnbr_short = pre.select("nbr").subtract(post_short.select("nbr"));
var dnbr_vis = {
  min: -0.3,
  max: 0.3,
  palette: ["blue", "white", "red"]
};
Map.addLayer(dnbr_long, dnbr_vis, "dNBR long");
Map.addLayer(dnbr_short, dnbr_vis, "dNBR short");

// Fires Barbera 25 ---------------------------------------------------

Map.addLayer(fires_barbera, {color: "red"}, "fires barbera", false);
// Map.addLayer(fires_barbera.filterMetadata("year", "equals", 2012), {color: "red"}, "fires barbera", false);

// Exports ----------------------------------------------------------------

// // Asset
// Export.table.toAsset({
//   collection: training_events,
//   description: 'events_export',
//   assetId: 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_fires'
// });
// // Table for Drive
// Export.table.toDrive({
//   collection: training_events,
//   description: 'training_fires',
//   folder: 'earth_engine_exports',
//   fileFormat: 'CSV'
// });