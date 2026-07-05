import pathlib
import sys

import geopandas as gpd
import pandas as pd
import yaml

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
CONFIG = BASE / "conf" / "safe_system_thresholds.yaml"


def load_thresholds() -> pd.DataFrame:
    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)
    rows = list(cfg["thresholds"].values())
    return pd.DataFrame(rows)[["road_class", "land_use", "safe_limit_kmh", "n_conflict"]]


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"LAYER 1 (Safe System Gap) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}.gpkg")
    thresholds = load_thresholds()

    before = len(gdf)
    gdf = gdf.merge(
        thresholds,
        left_on=["RoadClass", "LandUse"],
        right_on=["road_class", "land_use"],
        how="left",
    )
    unmatched = gdf["safe_limit_kmh"].isna().sum()
    if unmatched:
        print(f"  WARNING: {unmatched} rows have no matching RoadClass x LandUse threshold")
    assert len(gdf) == before, "merge changed row count, threshold table must be one row per RoadClass x LandUse"

    # linear form, kept for interpretability in the write-up ("this segment is
    # posted N km/h above the Safe System recommendation")
    gdf["SSG_linear"] = gdf["SpeedLimit"] - gdf["safe_limit_kmh"]

    # power-law form (Elvik/Nilsson Power Model): risk scales with
    # (speed / safe_limit)^n, not linearly with the gap. see
    # p0-submission/methodology-plan.md, physics-informed addendum.
    gdf["SSG_risk_ratio"] = (gdf["SpeedLimit"] / gdf["safe_limit_kmh"]) ** gdf["n_conflict"]

    print(gdf[["SSG_linear", "SSG_risk_ratio"]].describe().to_string())
    print("\ntop 10 by SSG_risk_ratio:")
    print(
        gdf.nlargest(10, "SSG_risk_ratio")[
            ["RoadClass", "LandUse", "SpeedLimit", "safe_limit_kmh", "n_conflict", "SSG_risk_ratio"]
        ].to_string(index=False)
    )

    out_path = CLEAN / f"{name}_layer1.gpkg"
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
