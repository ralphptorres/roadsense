import pathlib
import subprocess
import sys

import geopandas as gpd
import numpy as np
import rasterio

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
RAW = BASE / "data" / "raw"

WORLDPOP_URLS = {
    "thailand": "https://data.worldpop.org/GIS/Population_Density/Global_2000_2020_1km_UNadj/2020/THA/tha_pd_2020_1km_UNadj.tif",
    "maharashtra": "https://data.worldpop.org/GIS/Population_Density/Global_2000_2020_1km_UNadj/2020/IND/ind_pd_2020_1km_UNadj.tif",
}


def download_raster(name: str) -> pathlib.Path:
    # curl, not requests: WorldPop's server throttled python-requests
    # downloads heavily in testing (~1-2 KB/s) while curl reached full
    # bandwidth on the same connection, -C - resumes a partial download,
    # though WorldPop's redirect returns 200 not 206 so resume support is
    # best-effort, not guaranteed.
    url = WORLDPOP_URLS[name]
    dest = RAW / f"{name}_worldpop.tif"
    if dest.exists():
        print(f"  using cached raster: {dest}")
        return dest
    print(f"  downloading {url} ...", flush=True)
    subprocess.run(
        ["curl", "-sL", "-C", "-", "-m", "1800", "--retry", "5", "--retry-delay", "10", "-o", str(dest), url],
        check=True,
    )
    print(f"  saved {dest.stat().st_size/1e6:.1f} MB -> {dest}", flush=True)
    return dest


def enrich(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"VUE tier 2 (WorldPop population density) — {name}")
    print("=" * 60)

    in_path = CLEAN / f"{name}_vue2osm.gpkg"
    gdf = gpd.read_file(in_path)

    raster_path = download_raster(name)
    centroids = gdf.geometry.centroid  # a single point sample per segment, a 1km-resolution raster can't resolve within-segment variation anyway

    with rasterio.open(raster_path) as src:
        coords = list(zip(centroids.x, centroids.y))
        samples = np.array([v[0] for v in src.sample(coords)], dtype=float)
        nodata = src.nodata
        if nodata is not None:
            samples[samples == nodata] = np.nan
        samples[samples < 0] = np.nan  # WorldPop uses negative sentinel for no-data in some products

    gdf["pop_density"] = samples
    print(f"  pop_density describe:\n{gdf['pop_density'].describe().to_string()}")
    print(f"  nan (no raster coverage): {gdf['pop_density'].isna().sum()}")

    out_path = CLEAN / f"{name}_vue2.gpkg"
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
