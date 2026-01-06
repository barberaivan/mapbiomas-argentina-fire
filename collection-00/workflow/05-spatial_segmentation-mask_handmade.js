// Draw polygons by hand to mask burned-like areas in certain years:
// Ash in 2011 and drought in 2015. 
// Export a feature collection with year property. 

// Geometries drawn by hand

var poly_2011 = /* color: #d63000 */ee.Geometry.Polygon(
        [[[-68.45127435826234, -41.0792300926439],
          [-68.85776849888734, -40.83862763906613],
          [-69.15439935826234, -40.480259275706025],
          [-69.26426263951234, -39.96857766536168],
          [-69.15439935826234, -39.58016649835172],
          [-69.94541498326234, -39.41909667333774],
          [-70.45078607701234, -39.68170241636381],
          [-70.80234857701234, -39.90961304888121],
          [-71.24180170201234, -40.01907831910584],
          [-71.59336420201234, -40.421738102247296],
          [-72.02197420268269, -40.48008689760692],
          [-72.03342075953827, -40.75557197664384],
          [-71.63181635044984, -41.02123394508556],
          [-71.41758295201234, -41.30245044952584],
          [-70.56064935826234, -42.17142731118538],
          [-69.51694818638734, -42.996494859929],
          [-68.45127435826234, -43.4049308130641]]]),
    poly_2015 = /* color: #98ff00 */ee.Geometry.Polygon(
        [[[-70.91965211265621, -40.361787976139105],
          [-70.61203492515621, -40.34085658604645],
          [-70.52414430015621, -40.240295499466576],
          [-70.44174683921871, -40.213034458841314],
          [-70.41153443687496, -40.12068492912667],
          [-70.30991090171871, -40.04082743351061],
          [-70.13687623374996, -39.98192514677973],
          [-69.97757447593746, -39.863968126032375],
          [-69.99405396812496, -39.63802121117663],
          [-70.25497926109371, -39.557600127324605],
          [-70.41977418296871, -39.34764376559637],
          [-70.72189820640621, -38.95360597566004],
          [-71.01852906578121, -38.92156032406346],
          [-71.33713258140621, -38.981367158406925],
          [-71.40579713218746, -39.29877542195987],
          [-71.58707154624996, -39.421943110092684],
          [-71.63925660484371, -39.519473344586565],
          [-71.56235230796871, -39.70989774906035],
          [-71.43051637046871, -39.97771589564732],
          [-71.31515992515621, -40.23819888586794],
          [-71.18057740562496, -40.37015871304898],
          [-71.02951539390621, -40.41617918231457]]]);

// Load snic img collection
var bp  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/burn_prob_annual_03"),
    sn  = ee.ImageCollection("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/snic_03");
    
var y = 2011;

var bprob = bp.filterMetadata('year', 'equals', y).first(),
    snic  = sn.filterMetadata('year', 'equals', y).first();
      // .select('clusters').selfMask().mask().gt(0);

var snicVis = {
  min:0, max:1, palette: ['black', 'blue']
};

var bprobVis = {
  min:0, max:1, palette: ['black', 'yellow', 'red']
};

Map.addLayer(bprob, bprobVis, 'burn prob');
Map.addLayer(snic, snicVis, 'snic');

var masks = ee.FeatureCollection([
    ee.Feature(poly_2011, {'year': 2011}),
    ee.Feature(poly_2015, {'year': 2015})
  ]);
// Map.addLayer(masks, {}, 'fff')

Export.table.toAsset({
  collection: masks,
  description: 'polygon_masks',
  assetId: 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/WORKFLOW-EXPORTS/masks'
});