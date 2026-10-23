# collection-01/scripts/assets_gee_change_access.py
#
# Make every asset under a set of GEE roots readable by anyone (`all_users_can_read`), recursively.
# Written to be run INTERACTIVELY (Positron: select a block, Ctrl+Enter), top to bottom.
#
# Two roots: our `FIRE/` folder, and the step-03 bpts collection for 1999–2009 that lives in the
# LEGACY `mapbiomas-chaco` project (`C.BP_TS_METRICS_COL_CHACO`, see the "Asset paths" note in
# utils/constants.py). Only that collection is opened there, not its parent `FIRE/` folder, which
# is owned by the Chaco workspace group, not by us.
#
# Why a walk and not one call on the folder: in a Cloud project a folder's ACL is NOT inherited by
# what is already inside it. As of 2026-10 `FIRE/` itself was public while ~630 of its 670 children
# were not, `TRAINING-DATA/CHACO/training_fires` among them.
#
# What it touches: each root itself, plus every FOLDER, TABLE, IMAGE and IMAGE_COLLECTION below it.
# It does not descend into an IMAGE_COLLECTION — its images take the collection's ACL.
# The existing owners / readers / writers are kept: `setAssetAcl` writes the WHOLE policy from the
# dict it is given, so each asset's current ACL is read and sent back with only the public flag
# flipped. Assets that are already public are skipped, so a rerun is cheap and safe.
#
# Run as an account with write access (the `mapbiomas-fuego` group is writer on both roots). A
# legacy asset lists as `projects/earthengine-legacy/assets/projects/mapbiomas-chaco/...`; that is
# the same asset under its canonical name.

import collections

import ee

# ─── Settings ────────────────────────────────────────────────────────────────
ROOTS = [
    "projects/mapbiomas-argentina/assets/FIRE",
    "projects/mapbiomas-chaco/FIRE/bp_ts_metrics",   # legacy project, bpts 1999–2009
]
COMPUTE_PROJECT = "mapbiomas-fire-485203"
APPLY = False   # set True only when you mean to run section 2; guards a whole-file run

ee.Initialize(project=COMPUTE_PROJECT)


# ─── Functions ───────────────────────────────────────────────────────────────
def list_children(parent):
    """All direct children of `parent`, following pagination."""
    out, token = [], None
    while True:
        params = {"parent": parent}
        if token:
            params["pageToken"] = token
        resp = ee.data.listAssets(params)
        out.extend(resp.get("assets", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def walk(root):
    """List of (asset_id, type) for root and everything below it, not entering image collections."""
    kind = ee.data.getAsset(root)["type"]
    out = [(root, kind)]
    stack = [root] if kind == "FOLDER" else []
    while stack:
        for a in list_children(stack.pop()):
            out.append((a["name"], a["type"]))
            if a["type"] == "FOLDER":
                stack.append(a["name"])
    return out


def is_public(asset_id):
    return ee.data.getAssetAcl(asset_id).get("all_users_can_read", False)


def make_public(asset_id):
    acl = ee.data.getAssetAcl(asset_id)
    acl["all_users_can_read"] = True
    ee.data.setAssetAcl(asset_id, acl)


# ─── 1. List everything and find what is still private (changes nothing) ─────
assets = [a for r in ROOTS for a in walk(r)]
private = [(asset_id, kind) for asset_id, kind in assets if not is_public(asset_id)]

print(f"{len(assets)} assets, {len(private)} private")
print(collections.Counter(kind for _, kind in private))
for asset_id, kind in private:
    print(f"  {kind:<16} {asset_id}")


# ─── 2. Make them public (THIS CHANGES THE ACLs) ─────────────────────────────
assert APPLY, "set APPLY = True in Settings to change the ACLs"
errors = []
for asset_id, kind in private:
    try:
        make_public(asset_id)
        print(f"  opened  {kind:<16} {asset_id}")
    except ee.EEException as e:
        print(f"  ERROR   {kind:<16} {asset_id}: {e}")
        errors.append((asset_id, e))

print(f"\nopened {len(private) - len(errors)}, errors {len(errors)}")


# ─── 3. Check: should print 0 ────────────────────────────────────────────────
still_private = [asset_id for asset_id, _ in assets if not is_public(asset_id)]
print(len(still_private), "still private")
