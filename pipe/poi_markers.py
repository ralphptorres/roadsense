import json
import pathlib
import sys
import time

import geopandas as gpd
import requests

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
RAW = BASE / "data" / "raw"
WEB_DATA = BASE / "web" / "data"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "roadsense-adb-challenge/0.1 (research, hackathon submission, non-commercial)"}

# separate fetch from vue_osm.py's scoring pipeline (which deliberately
# drops tags for a smaller payload), this one keeps tags so the map can
# render differentiated icons per category, purely a visualization
# overlay, not a scored input.
POI_QUERY = """
[out:json][timeout:300];
(
  node["amenity"="school"]({bbox});
  node["amenity"="hospital"]({bbox});
  node["amenity"="marketplace"]({bbox});
  node["shop"="supermarket"]({bbox});
);
out body qt;
"""

GRID_DEG = 5.0


def _query_tile(minx, miny, maxx, maxy, retries=4):
    overpass_bbox = f"{miny},{minx},{maxy},{maxx}"
    query = POI_QUERY.format(bbox=overpass_bbox)
    for attempt in range(retries):
        resp = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=320)
        if resp.status_code in (429, 504) and attempt < retries - 1:
            wait = 15 * (attempt + 1)
            print(f"    {resp.status_code}, retrying in {wait}s (attempt {attempt+1}/{retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    return resp.json()["elements"]


def category(tags: dict) -> str:
    if tags.get("amenity") == "school":
        return "school"
    if tags.get("amenity") == "hospital":
        return "hospital"
    if tags.get("amenity") == "marketplace" or tags.get("shop") == "supermarket":
        return "market"
    return "other"


def fetch(name: str, bbox) -> list:
    cache_path = RAW / f"{name}_poi_markers.json"
    if cache_path.exists():
        print(f"  using cached: {cache_path}")
        return json.loads(cache_path.read_text())

    import numpy as np

    minx, miny, maxx, maxy = bbox
    nx = max(1, int(np.ceil((maxx - minx) / GRID_DEG)))
    ny = max(1, int(np.ceil((maxy - miny) / GRID_DEG)))
    xs = np.linspace(minx, maxx, nx + 1)
    ys = np.linspace(miny, maxy, ny + 1)
    print(f"  querying Overpass for {name} in {nx}x{ny} tiles ...")
    elements = []
    for i in range(nx):
        for j in range(ny):
            try:
                els = _query_tile(xs[i], ys[j], xs[i + 1], ys[j + 1])
            except requests.exceptions.HTTPError as e:
                print(f"    tile ({i},{j}) failed: {e}, skipping")
                els = []
            elements.extend(els)
            time.sleep(2)
    print(f"  got {len(elements):,} POIs")
    cache_path.write_text(json.dumps(elements))
    return elements


def export(name: str) -> None:
    print("=" * 60)
    print(f"POI MARKERS — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    bbox = tuple(gdf.total_bounds)
    elements = fetch(name, bbox)

    features = []
    for el in elements:
        if "lon" not in el:
            continue
        tags = el.get("tags", {})
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                "properties": {"category": category(tags), "name": tags.get("name", "")},
            }
        )

    fc = {"type": "FeatureCollection", "features": features}
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    out_path = WEB_DATA / f"{name}_pois.geojson"
    out_path.write_text(json.dumps(fc))

    counts = {}
    for f in features:
        c = f["properties"]["category"]
        counts[c] = counts.get(c, 0) + 1
    print(f"  categories: {counts}")
    print(f"  written -> {out_path} ({out_path.stat().st_size/1e6:.2f} MB)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        export(name)


if __name__ == "__main__":
    main()
