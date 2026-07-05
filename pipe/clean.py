import pathlib
import sys

import geopandas as gpd
import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
RAW = DATA_DIR / "raw"
CLEAN = DATA_DIR / "clean"

# NOTE: this used to be a "drop bottom 2% of SampleSizeTotal per
# RoadClass" percentile gate, written before gate A's own review found
# no correlation between SampleSizeTotal and gap/F85th noise on this
# data (see docs/review-log.md). Checking what it actually discarded
# showed it was dropping rows with tens of thousands of samples in
# Thailand (p2 threshold per RoadClass: 7,615-52,109) — nowhere near a
# genuine data-validity problem, just an unjustified heuristic quietly
# removing real, substantial data. Replaced with a floor on true
# zero-observation rows only (matching the reasoning already validated
# in the old ai-safer-roads repo's clean_data.py), which is nearly a
# no-op here (0 rows in Thailand, 1 in Maharashtra within Valid rows)
# because genuinely degenerate rows are already rare post-AnalysisStatus
# filtering.
MIN_SAMPLE_SIZE = 1

REDUNDANT_COLS = ["ForAnalysis", "SpeedLimitFloor", "Percent_"]


def _drop(gdf: gpd.GeoDataFrame, step: str, before: int) -> None:
    after = len(gdf)
    print(f"  [{step}] {before:,} -> {after:,}  (dropped {before - after:,})")


def clean(name: str) -> gpd.GeoDataFrame:
    path = RAW / f"{name}.geojson"
    print("=" * 60)
    print(f"CLEANING {name}")
    print("=" * 60)
    gdf = gpd.read_file(path)
    print(f"loaded {len(gdf):,} rows, {len(gdf.columns)} columns")

    before = len(gdf)
    gdf = gdf[gdf["AnalysisStatus"] == "Valid"].copy()
    _drop(gdf, "AnalysisStatus == 'Valid'", before)

    if "ExcludeFromSpeedSPI" in gdf.columns:
        before = len(gdf)
        gdf = gdf[gdf["ExcludeFromSpeedSPI"] != 1.0].copy()
        _drop(gdf, "ExcludeFromSpeedSPI != 1", before)

    gdf["SpeedLimit"] = pd.to_numeric(gdf["SpeedLimit"], errors="coerce")
    zero_count = (gdf["SpeedLimit"] == 0).sum()
    gdf.loc[gdf["SpeedLimit"] == 0, "SpeedLimit"] = pd.NA
    print(f"  SpeedLimit == 0 treated as missing: {zero_count:,} rows")

    before = len(gdf)
    gdf = gdf[gdf["SpeedLimit"].notna()].copy()
    _drop(gdf, "SpeedLimit not null (after zero->NaN)", before)

    gdf["RoadClass"] = gdf["RoadClass"].str.lower().str.strip()
    gdf["LandUse"] = gdf["LandUse"].str.upper().str.strip()

    sample_col = "SampleSizeTotal" if "SampleSizeTotal" in gdf.columns else "Sample_Size_Total"
    gdf["sample_size"] = pd.to_numeric(gdf[sample_col], errors="coerce")

    before = len(gdf)
    gdf = gdf[gdf["sample_size"] >= MIN_SAMPLE_SIZE].copy()
    _drop(gdf, f"sample_size >= {MIN_SAMPLE_SIZE} (zero-observation floor)", before)

    gdf["length_km"] = gdf["Shape_Length"] / 1000

    present_redundant = [c for c in REDUNDANT_COLS if c in gdf.columns]
    gdf = gdf.drop(columns=present_redundant)
    print(f"  dropped redundant columns: {present_redundant}")

    print(f"\nfinal: {len(gdf):,} rows")
    print(gdf.groupby(["RoadClass", "LandUse"]).size().to_string())

    CLEAN.mkdir(parents=True, exist_ok=True)
    out_path = CLEAN / f"{name}.gpkg"
    gdf.to_file(out_path, driver="GPKG", layer=name)
    print(f"written -> {out_path}")

    return gdf


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        clean(name)


if __name__ == "__main__":
    main()
