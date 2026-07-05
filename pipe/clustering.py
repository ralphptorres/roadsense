import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

MIN_GROUP_SIZE = 15  # below this, fall back to the coarser RoadClass x LandUse group for stats


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"LAYER 3 (peer clustering) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_vue2.gpkg")
    gdf["gap"] = gdf["F85thPercentileSpeed"] - gdf["SpeedLimit"]

    # finer peer group: RoadClass x LandUse split by median pop_density
    # within each cell (high vs low VUE-tier2 exposure), using the new
    # tier-2 signal rather than just the coarse RoadClass x LandUse cell.
    gdf["pop_density_median_in_cell"] = gdf.groupby(["RoadClass", "LandUse"])["pop_density"].transform("median")
    gdf["exposure_tier"] = np.where(gdf["pop_density"] >= gdf["pop_density_median_in_cell"], "high", "low")
    gdf["peer_group"] = gdf["RoadClass"] + "_" + gdf["LandUse"] + "_" + gdf["exposure_tier"]

    group_sizes = gdf.groupby("peer_group").size()
    print("peer group sizes:")
    print(group_sizes.to_string())

    # fall back to the coarser RoadClass x LandUse group wherever the finer
    # peer group is too thin to give stable statistics.
    small_groups = group_sizes[group_sizes < MIN_GROUP_SIZE].index
    gdf["stats_group"] = np.where(gdf["peer_group"].isin(small_groups), gdf["RoadClass"] + "_" + gdf["LandUse"], gdf["peer_group"])
    n_fallback = gdf["peer_group"].isin(small_groups).sum()
    if n_fallback:
        print(f"\n{n_fallback} rows fell back to the coarser RoadClass x LandUse group ({len(small_groups)} thin peer groups)")

    peer_mean = gdf.groupby("stats_group")["SpeedLimit"].transform("mean")
    peer_std = gdf.groupby("stats_group")["SpeedLimit"].transform("std").replace(0, np.nan)
    gdf["speedlimit_z"] = (gdf["SpeedLimit"] - peer_mean) / peer_std

    # this IS the SE source for Layer 4's significance flagging, per the
    # gate A correction: peer group's own empirical gap spread, not a
    # 1/sqrt(N) counting-statistics formula (see methodology-plan.md).
    gdf["peer_gap_std"] = gdf.groupby("stats_group")["gap"].transform("std")
    gdf["peer_gap_mean"] = gdf.groupby("stats_group")["gap"].transform("mean")

    print("\nspeedlimit_z describe:")
    print(gdf["speedlimit_z"].describe().to_string())

    outliers = gdf[gdf["speedlimit_z"] > 2]
    print(f"\nsegments posted >2 std above their peer group's mean SpeedLimit: {len(outliers):,} ({len(outliers)/len(gdf):.1%})")

    out_path = CLEAN / f"{name}_layer3.gpkg"
    gdf.to_file(out_path, driver="GPKG", layer=name)
    print(f"\nwritten -> {out_path}")
    return gdf


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        score(name)


if __name__ == "__main__":
    main()
