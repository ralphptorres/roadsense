import json
import os
import pathlib
import re
import sys
import time

import geopandas as gpd
import requests

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
RAW = BASE / "data" / "raw"

# load MAPILLARY_TOKEN from .env without adding a dependency on
# python-dotenv, this is a small one-off script, not core scoring.
def _load_env():
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
TOKEN = os.environ.get("MAPILLARY_TOKEN")
GRAPH_URL = "https://graph.mapillary.com/map_features"

# a scoped VUE tier 3 check, not a full rescore: query real street-level
# map features (Mapillary) around only the statistically significant
# flagged segments (the ones that matter for the write-up), not all
# ~14,700 segments, since that volume of individual API calls isn't
# feasible in the time available. this validates two things the
# challenge FAQ explicitly calls out as a data-quality gap: SpeedLimit
# is a TomTom estimate, and StreetImageLink coordinates were suggested
# for visual cross-referencing (in practice the field is just raw
# coordinates, not an actual image link, see methodology-plan.md).
RADIUS_DEG = 0.0009  # ~100m
SPEED_LIMIT_RE = re.compile(r"regulatory--maximum-speed-limit-(\d+)(?:-mph)?--")
CROSSING_VALUES = {"marking--discrete--crosswalk-zebra", "object--traffic-light--pedestrians", "object--support--utility-pole"}


def query_features(lon, lat, retries=2):
    bbox = f"{lon - RADIUS_DEG},{lat - RADIUS_DEG},{lon + RADIUS_DEG},{lat + RADIUS_DEG}"
    for attempt in range(retries):
        resp = requests.get(GRAPH_URL, params={"access_token": TOKEN, "fields": "id,object_value", "bbox": bbox, "limit": 50}, timeout=15)
        if resp.status_code == 429 and attempt < retries - 1:
            time.sleep(3)
            continue
        if resp.status_code == 429:
            return []  # give up on this segment rather than blocking the whole run
        resp.raise_for_status()
        return resp.json().get("data", [])
    return []


def process(name: str) -> None:
    print("=" * 60)
    print(f"MAPILLARY TIER 3 — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    flagged = gdf[gdf["is_significant"]].copy()
    print(f"  querying map features for {len(flagged)} flagged segments ...")

    results = []
    for i, (_, row) in enumerate(flagged.iterrows()):
        c = row.geometry.centroid
        try:
            features = query_features(c.x, c.y)
        except requests.exceptions.RequestException as e:
            print(f"    row {i} failed: {e}, skipping")
            features = []

        signs = [f["object_value"] for f in features if f["object_value"].startswith("regulatory--maximum-speed-limit")]
        crossing_count = sum(1 for f in features if f["object_value"] in CROSSING_VALUES or "crosswalk" in f["object_value"])
        parsed_limit = None
        for s in signs:
            m = SPEED_LIMIT_RE.match(s)
            if m:
                parsed_limit = int(m.group(1))
                break

        results.append(
            {
                "posted_limit": row["SpeedLimit"],
                "mapillary_signed_limit": parsed_limit,
                "n_features_nearby": len(features),
                "n_speed_signs_nearby": len(signs),
                "n_crossing_features_nearby": crossing_count,
            }
        )
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(flagged)} done", flush=True)
        time.sleep(1.0)

    out_path = RAW / f"{name}_mapillary_tier3.json"
    out_path.write_text(json.dumps(results))

    n_with_coverage = sum(1 for r in results if r["n_features_nearby"] > 0)
    n_with_sign = sum(1 for r in results if r["mapillary_signed_limit"] is not None)
    n_match = sum(1 for r in results if r["mapillary_signed_limit"] is not None and r["mapillary_signed_limit"] == r["posted_limit"])
    n_mismatch = n_with_sign - n_match
    n_crossings = sum(1 for r in results if r["n_crossing_features_nearby"] > 0)

    print(f"\n  flagged segments: {len(results)}")
    print(f"  with any Mapillary coverage nearby: {n_with_coverage} ({n_with_coverage/len(results)*100:.1f}%)")
    print(f"  with a readable speed-limit sign nearby: {n_with_sign} ({n_with_sign/len(results)*100:.1f}%)")
    print(f"  sign confirms posted SpeedLimit: {n_match}")
    print(f"  sign contradicts posted SpeedLimit: {n_mismatch}")
    print(f"  with pedestrian-crossing infrastructure nearby: {n_crossings} ({n_crossings/len(results)*100:.1f}%)")


def main():
    if not TOKEN:
        print("MAPILLARY_TOKEN not set in .env, aborting")
        sys.exit(1)
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        process(name)


if __name__ == "__main__":
    main()
