"""
collection-01/scripts/test-03-model_load.py

Preflight: verify the deployed coefficient set loads and the GEE prediction graph
builds against the models/P<NNN>/ layout — run once on each export account/clone
before launching step-03, so a missing/partial models/ folder fails loudly here
instead of mid-export.

Checks:
  1. The default load resolves to the DEPLOYED folder (C.COEF_DIR = models/P050)
     and returns the expected term count (52 for P050).
  2. The coefficient image builds exactly one band per loaded term — i.e. GEE
     computes the reduced graph, NOT a full-129 graph with zeroed coefficients
     (docs/03-bpts.md §9/§11).
  3. bpts_image() assembles without error for one tile-year.

    $PYTHON collection-01/scripts/test-03-model_load.py

Optionally compute prob over a small region (a real GEE reduceRegion) with --compute.
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F        # cross-step helpers (veg_fire_image, …)


def _load_step03():
    """Load workflow/03-bp_ts_metrics.py by PATH.

    Step 03's functions (load_all_coefficients, build_coeff_image, bpts_image, …) live
    in that file, but its name starts with a digit and has a hyphen — an invalid Python
    module identifier — so it cannot be `import`ed by name. importlib-by-path is the
    GEE require() analog: it runs the file's top-level defs but NOT its main() (guarded
    by `if __name__ == "__main__"`).
    """
    path = Path(__file__).resolve().parents[1] / "workflow" / "03-bp_ts_metrics.py"
    spec = importlib.util.spec_from_file_location("step03_bpts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _load_step03()                       # step-03 machinery

# Expected term count per deployed folder (intercept + kept terms). Update if redeployed.
EXPECTED_TERMS = {"P129": 130, "P080": 81, "P060": 62, "P050": 52, "P040": 42, "P030": 33}


def main(compute=False):
    ee.Initialize(project=C.GEE_PROJECT)

    print(f"DEPLOYED_MODEL : {C.DEPLOYED_MODEL}")
    print(f"COEF_DIR       : {C.COEF_DIR}")
    assert C.COEF_DIR.exists(), f"deployed coef folder missing: {C.COEF_DIR}"

    terms = S.load_all_coefficients()                      # default = C.COEF_DIR
    exp = EXPECTED_TERMS.get(C.DEPLOYED_MODEL)
    print(f"terms loaded   : {len(terms)}" + (f" (expected {exp})" if exp else ""))
    if exp is not None:
        assert len(terms) == exp, f"expected {exp} terms, got {len(terms)}"

    veg_fire = F.veg_fire_image(2015)
    n_bands = len(S.build_coeff_image(veg_fire, terms).bandNames().getInfo())
    print(f"coeff bands    : {n_bands}  (== terms? {n_bands == len(terms)})")
    assert n_bands == len(terms), "coeff image band count != term count — graph is not reduced!"

    img = S.bpts_image(2015, "SK-19-Y-A")                  # builds the graph (no compute)
    assert len(img.bandNames().getInfo()) == 16, "expected 16-band bpts output"
    print("bpts_image     : builds OK, 16 bands")

    if compute:
        bp_col, _ = S.burn_prob_collection(2015, "SK-19-Y-A", terms)
        focal = bp_col.filterDate("2015-01-01", "2015-12-31")
        prob = ee.Image(focal.sort("CLOUD_COVER").first()).select("prob")
        region = S._tile_geometry("SK-19-Y-A").centroid(maxError=100).buffer(1500).bounds()
        stats = prob.reduceRegion(ee.Reducer.minMax(), region, scale=30,
                                  maxPixels=int(1e8), bestEffort=True).getInfo()
        print(f"prob min/max   : {stats}")
        for v in stats.values():
            assert v is None or 0.0 <= v <= 1.0, f"prob out of [0,1]: {v}"

    print("\nOK — deployed model loads and the GEE graph is reduced to the deployed term set.")


if __name__ == "__main__":
    main(compute="--compute" in sys.argv)
