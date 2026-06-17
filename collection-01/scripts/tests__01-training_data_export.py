# Test subfunctions of 01-training_data_export.py

# Open the target file besides this to run definitions of functions from there.
# Do not test the main(), as it exports truely.

# To inspect gee objets by printing
import eerepr
eerepr.initialize()   # ← this is the step that hooks into EE objects


# Add collection-01/ to sys.path so `utils` package is importable
# But instead of running this:
#   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# run this
sys.path.insert(0, "collection-01")

ee.Initialize(project=C.GEE_PROJECT)

region = "PAT"
version = 1

fires_path = f"{C.TRAINING_DATA_COL1}/{region}/training_fires"
fires = ee.FeatureCollection(fires_path)
fires_info = fires.getInfo()["features"]

props     = fires_info[0]["properties"]   # fix to first fire
locations = _load_locations(props["fire_id"], region)

# now call the inner function directly
fc = process_fire(props, region, locations)
fc  # inspect with eerepr
