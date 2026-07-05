import pathlib
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from sklearn.neighbors import BallTree

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
RAW = BASE / "data" / "raw"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "roadsense-adb-challenge/0.1 (research, hackathon submission, non-commercial)"}

# schools/hospitals/markets are the exposure proxies the ADB FAQ names
# explicitly ("proximity to schools and markets"). skel qt keeps the
# payload small since we only need coordinates, not full tag sets.
POI_QUERY = """
[out:json][timeout:300];
(
  node["amenity"="school"]({bbox});
  node["amenity"="hospital"]({bbox});
  node["amenity"="marketplace"]({bbox});
  node["shop"="supermarket"]({bbox});
  node["shop"="convenience"]({bbox});
);
out skel qt;
"""

BUFFER_KM = 0.3  # 300m, matches the methodology plan's tier-2 buffer
EARTH_RADIUS_KM = 6371.0


GRID_DEG = 2.5  # tile size in degrees; keeps each Overpass request small enough to avoid 504s


def _query_tile(minx: float, miny: float, maxx: float, maxy: float, retries: int = 4) -> list[dict]:
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


def fetch_pois(bbox: tuple[float, float, float, float], name: str) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox

    cache_path = RAW / f"{name}_pois.json"
    if cache_path.exists():
        print(f"  using cached POI response: {cache_path}")
        import json

        elements = json.loads(cache_path.read_text())
    else:
        nx = max(1, int(np.ceil((maxx - minx) / GRID_DEG)))
        ny = max(1, int(np.ceil((maxy - miny) / GRID_DEG)))
        xs = np.linspace(minx, maxx, nx + 1)
        ys = np.linspace(miny, maxy, ny + 1)
        print(f"  querying Overpass for {name} in {nx}x{ny} tiles ...")
        elements = []
        t0 = time.time()
        for i in range(nx):
            for j in range(ny):
                tminx, tmaxx = xs[i], xs[i + 1]
                tminy, tmaxy = ys[j], ys[j + 1]
                try:
                    els = _query_tile(tminx, tminy, tmaxx, tmaxy)
                except requests.exceptions.HTTPError as e:
                    print(f"    tile ({i},{j}) failed: {e}, skipping")
                    els = []
                elements.extend(els)
                time.sleep(2)  # be considerate to the shared public instance
        print(f"  got {len(elements):,} POIs in {time.time()-t0:.0f}s")
        import json

        cache_path.write_text(json.dumps(elements))

    rows = [{"lon": el["lon"], "lat": el["lat"]} for el in elements if "lon" in el]
    df = pd.DataFrame(rows)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")


def enrich(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"VUE tier 2 (OSM POI density) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_layer2.gpkg")
    bbox = gdf.total_bounds
    pois = fetch_pois(tuple(bbox), name)

    if pois.empty:
        print("  no POIs returned, skipping enrichment")
        gdf["poi_count_300m"] = 0
        gdf["poi_nearest_km"] = np.nan
        return gdf

    # BallTree with haversine metric, not a simple lon/lat Euclidean
    # distance: at these latitudes a degree of longitude is a meaningfully
    # different real-world distance than a degree of latitude, haversine
    # accounts for that, a flat Euclidean check would systematically
    # distort the 300m buffer depending on how far from the equator a
    # segment sits.
    centroids = gdf.geometry.centroid
    seg_rad = np.radians(np.column_stack([centroids.y, centroids.x]))
    poi_rad = np.radians(np.column_stack([pois.geometry.y, pois.geometry.x]))

    tree = BallTree(poi_rad, metric="haversine")
    radius = BUFFER_KM / EARTH_RADIUS_KM
    counts = tree.query_radius(seg_rad, r=radius, count_only=True)
    dist, _ = tree.query(seg_rad, k=1)
    nearest_km = dist[:, 0] * EARTH_RADIUS_KM

    gdf["poi_count_300m"] = counts
    gdf["poi_nearest_km"] = nearest_km

    print(f"  poi_count_300m describe:\n{gdf['poi_count_300m'].describe().to_string()}")
    print(f"\n  poi_nearest_km describe:\n{gdf['poi_nearest_km'].describe().to_string()}")

    out_path = CLEAN / f"{name}_vue2osm.gpkg"
    gdf.to_file(out_path, driver="GPKG", layer=name)
    print(f"\nwritten -> {out_path}")
    return gdf


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        enrich(name)


if __name__ == "__main__":
    main()
