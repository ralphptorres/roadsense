import pathlib
import sys
import geopandas as gpd
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

BASE = pathlib.Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"

DATASETS = {
    "thailand": RAW / "thailand.geojson",
    "maharashtra": RAW / "maharashtra.geojson",
}


def load(name: str) -> gpd.GeoDataFrame:
    print(f"\nloading {name} ...")
    gdf = gpd.read_file(DATASETS[name])
    print(f"  {len(gdf):,} rows, {len(gdf.columns)} columns, CRS={gdf.crs}")
    return gdf


def schema_report(gdfs: dict[str, gpd.GeoDataFrame]) -> None:
    print("\n" + "=" * 70)
    print("SCHEMA COMPARISON")
    print("=" * 70)
    all_cols = set()
    for gdf in gdfs.values():
        all_cols |= set(gdf.columns)
    rows = []
    for col in sorted(all_cols):
        row = {"column": col}
        for name, gdf in gdfs.items():
            row[name] = str(gdf[col].dtype) if col in gdf.columns else "ABSENT"
        rows.append(row)
    df = pd.DataFrame(rows)
    only_in = {name: [] for name in gdfs}
    shared = []
    for _, row in df.iterrows():
        present_in = [name for name in gdfs if row[name] != "ABSENT"]
        if len(present_in) == len(gdfs):
            shared.append(row["column"])
        elif len(present_in) == 1:
            only_in[present_in[0]].append(row["column"])
    print(f"\nshared columns ({len(shared)}): {shared}")
    for name, cols in only_in.items():
        print(f"\nonly in {name} ({len(cols)}): {cols}")
    print("\nfull dtype table:")
    print(df.to_string(index=False))


def field_report(gdf: gpd.GeoDataFrame, name: str) -> None:
    print("\n" + "=" * 70)
    print(f"FIELD REPORT — {name}")
    print("=" * 70)

    n = len(gdf)

    for col in ["AnalysisStatus", "RoadClass", "LandUse"]:
        if col in gdf.columns:
            print(f"\n--- {col} value_counts ---")
            print(gdf[col].value_counts(dropna=False).to_string())

    if "ExcludeFromSpeedSPI" in gdf.columns:
        print("\n--- ExcludeFromSpeedSPI value_counts ---")
        print(gdf["ExcludeFromSpeedSPI"].value_counts(dropna=False).to_string())

    if "Pass" in gdf.columns:
        print("\n--- Pass value_counts ---")
        print(gdf["Pass"].value_counts(dropna=False).to_string())

    # SampleSizeTotal — name differs across datasets
    sst_col = "SampleSizeTotal" if "SampleSizeTotal" in gdf.columns else (
        "Sample_Size_Total" if "Sample_Size_Total" in gdf.columns else None
    )
    if sst_col:
        sst = pd.to_numeric(gdf[sst_col], errors="coerce")
        print(f"\n--- {sst_col} describe ---")
        print(sst.describe())
        print(f"  zero or null: {(sst.fillna(0) == 0).sum():,} ({(sst.fillna(0) == 0).mean():.1%})")
        for q in [0.1, 0.25, 0.5, 0.75, 0.9]:
            print(f"  p{int(q*100)}: {sst.quantile(q):.1f}")

    # SpeedLimit — dtype differs (str in Maharashtra, float in Thailand)
    if "SpeedLimit" in gdf.columns:
        sl = pd.to_numeric(gdf["SpeedLimit"], errors="coerce")
        print("\n--- SpeedLimit describe (coerced numeric) ---")
        print(sl.describe())
        print(f"  null count: {sl.isna().sum():,} ({sl.isna().mean():.1%})")
        print(f"  value_counts top 20:\n{sl.value_counts(dropna=False).head(20).to_string()}")

    # F85thPercentileSpeed
    if "F85thPercentileSpeed" in gdf.columns:
        f85 = pd.to_numeric(gdf["F85thPercentileSpeed"], errors="coerce")
        print("\n--- F85thPercentileSpeed describe ---")
        print(f85.describe())
        print(f"  zero count: {(f85 == 0).sum():,}")

    # SpeedLimit vs RoadClass anomaly check: implausible combinations
    if "SpeedLimit" in gdf.columns and "RoadClass" in gdf.columns:
        print("\n--- SpeedLimit distribution by RoadClass (for anomaly spotting) ---")
        tmp = gdf.copy()
        tmp["SpeedLimit_num"] = pd.to_numeric(tmp["SpeedLimit"], errors="coerce")
        print(tmp.groupby("RoadClass")["SpeedLimit_num"].describe().to_string())

        print("\n--- flagged anomalies: motorway with SpeedLimit < 60 ---")
        anom1 = tmp[(tmp["RoadClass"].str.lower() == "motorway") & (tmp["SpeedLimit_num"] < 60)]
        print(f"  count: {len(anom1):,}")

        print("\n--- flagged anomalies: secondary with SpeedLimit > 100 ---")
        anom2 = tmp[(tmp["RoadClass"].str.lower() == "secondary") & (tmp["SpeedLimit_num"] > 100)]
        print(f"  count: {len(anom2):,}")

    # SpeedLimit vs F85th gap — the core diagnostic signal
    if "SpeedLimit" in gdf.columns and "F85thPercentileSpeed" in gdf.columns:
        tmp = gdf.copy()
        tmp["SpeedLimit_num"] = pd.to_numeric(tmp["SpeedLimit"], errors="coerce")
        tmp["gap"] = tmp["F85thPercentileSpeed"] - tmp["SpeedLimit_num"]
        print("\n--- F85th - SpeedLimit gap describe ---")
        print(tmp["gap"].describe())

    # geometry / length
    if "Shape_Length" in gdf.columns:
        print("\n--- Shape_Length (m) describe ---")
        print(gdf["Shape_Length"].describe())
    if "RoadLength" in gdf.columns:
        print("\n--- RoadLength (km, per data guide) describe ---")
        print(gdf["RoadLength"].describe())

    print(f"\nhead(3) (no geometry):")
    print(gdf.head(3).drop(columns="geometry").to_string())


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = list(DATASETS.keys()) if target == "both" else [target]

    gdfs = {name: load(name) for name in names}

    if len(gdfs) > 1:
        schema_report(gdfs)

    for name, gdf in gdfs.items():
        field_report(gdf, name)


if __name__ == "__main__":
    main()
