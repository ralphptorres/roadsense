import pathlib
import sys

import geopandas as gpd
import pandas as pd

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
BOUNDARIES_RAW = BASE / "data" / "raw" / "boundaries"

# free, no-API-key administrative boundaries (GADM v4.1), used for the
# remediation-planning overlay: which jurisdiction should own the fix for
# a cluster of nearby flagged segments. Thailand at province level
# (GADM level 1), Maharashtra at district level (GADM level 2, since
# level 1 for India is state, i.e. all of Maharashtra as one polygon,
# too coarse to be useful for clustering fixes).
CONFIG = {
    "thailand": {
        "boundary_file": "gadm41_THA_1.json",
        "name_col": "NAME_1",
        "filter": None,
    },
    "maharashtra": {
        "boundary_file": "gadm41_IND_2.json",
        "name_col": "NAME_2",
        "filter": ("NAME_1", "Maharashtra"),
    },
}

SIMPLIFY_TOLERANCE_DEG = 0.005


def process(name: str) -> None:
    print("=" * 60)
    print(f"JURISDICTIONS — {name}")
    print("=" * 60)

    cfg = CONFIG[name]
    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    bounds = gpd.read_file(BOUNDARIES_RAW / cfg["boundary_file"])
    if cfg["filter"]:
        col, val = cfg["filter"]
        bounds = bounds[bounds[col] == val].copy()
    bounds = bounds.rename(columns={cfg["name_col"]: "jurisdiction"})[["jurisdiction", "geometry"]]

    # spatial join on segment centroids, a segment's own line geometry can
    # span a boundary in rare edge cases, the centroid gives a single
    # unambiguous jurisdiction per segment for aggregation purposes.
    centroids = gpd.GeoDataFrame(gdf[["is_significant", "SSS", "risk_class"]], geometry=gdf.geometry.centroid, crs=gdf.crs)
    joined = gpd.sjoin(centroids, bounds, how="left", predicate="within")

    n_unmatched = joined["jurisdiction"].isna().sum()
    print(f"  segments matched to a jurisdiction: {len(joined) - n_unmatched:,} of {len(joined):,}")

    agg = joined.groupby("jurisdiction", dropna=True).agg(
        total_segments=("is_significant", "size"),
        flagged_segments=("is_significant", "sum"),
        mean_sss=("SSS", "mean"),
    )
    agg["flagged_pct"] = (agg["flagged_segments"] / agg["total_segments"] * 100).round(1)
    agg["mean_sss"] = agg["mean_sss"].round(1)
    agg = agg.reset_index()

    print("\n  top 5 jurisdictions by flagged segment count:")
    print(agg.nlargest(5, "flagged_segments").to_string(index=False))

    bounds_out = bounds.merge(agg, on="jurisdiction", how="left")
    bounds_out[["total_segments", "flagged_segments", "flagged_pct", "mean_sss"]] = bounds_out[
        ["total_segments", "flagged_segments", "flagged_pct", "mean_sss"]
    ].fillna(0)
    bounds_out["geometry"] = bounds_out.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)

    out_path = CLEAN / f"{name}_jurisdictions.gpkg"
    bounds_out.to_file(out_path, driver="GPKG", layer=name)
    print(f"\nwritten -> {out_path}")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        process(name)


if __name__ == "__main__":
    main()
