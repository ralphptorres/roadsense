import json
import pathlib
import sys

import geopandas as gpd
import pandas as pd

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"
WEB_DATA = BASE / "web" / "data"

SIMPLIFY_TOLERANCE_DEG = 0.0003  # ~30m, lighter than the folium version since this also carries JSON key overhead per feature

FIELDS = [
    "RoadClass",
    "LandUse",
    "SpeedLimit",
    "F85thPercentileSpeed",
    "SSG_risk_ratio",
    "OSR",
    "ssd_excess_m",
    "SSS",
    "vue_score",
    "ssg_pctile",
    "osr_pctile",
    "outlier_pctile",
    "is_significant",
    "risk_class",
]


def export(name: str) -> None:
    print(f"exporting {name} ...")
    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=False)
    gdf = gdf[FIELDS + ["geometry"]].copy()

    for col in ["SpeedLimit", "F85thPercentileSpeed", "SSG_risk_ratio", "OSR", "ssd_excess_m", "SSS", "vue_score", "ssg_pctile", "osr_pctile", "outlier_pctile"]:
        gdf[col] = gdf[col].round(1)

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    out_path = WEB_DATA / f"{name}.geojson"
    gdf.to_file(out_path, driver="GeoJSON")

    # also emit a ranked list for the side panel, precomputed so the
    # frontend doesn't need to sort/filter thousands of features.
    #
    # a pure top-50-by-SSS was all near-identical worst-case scores
    # (mostly one RoadClass/LandUse combo, same dominant component, so
    # the same canned recommendation sentence repeated over and over) and
    # never showed how SSS looks lower in the flagged set. instead: keep
    # the 15 worst (they're genuinely the highest priority, worth
    # surfacing first), then systematically sample the rest of the
    # flagged set so the list spans the full range down to the lowest
    # flagged score, not just the top sliver.
    flagged_sorted = gdf[gdf["is_significant"]].sort_values("SSS", ascending=False)
    top_worst = flagged_sorted.head(15)
    remaining = flagged_sorted.iloc[15:]
    if len(remaining):
        step = max(1, len(remaining) // 35)
        sampled = remaining.iloc[::step].head(35)
    else:
        sampled = remaining
    flagged = pd.concat([top_worst, sampled]).sort_values("SSS", ascending=False)

    ranked = []
    for _, row in flagged.iterrows():
        centroid = row.geometry.centroid
        ranked.append(
            {
                "roadClass": row["RoadClass"],
                "landUse": row["LandUse"],
                "speedLimit": row["SpeedLimit"],
                "f85": row["F85thPercentileSpeed"],
                "sss": row["SSS"],
                "riskClass": row["risk_class"],
                "osr": row["OSR"],
                "ssgRatio": row["SSG_risk_ratio"],
                "ssdExcess": row["ssd_excess_m"],
                "ssgPctile": row["ssg_pctile"],
                "osrPctile": row["osr_pctile"],
                "outlierPctile": row["outlier_pctile"],
                "vueScore": row["vue_score"],
                "lon": round(centroid.x, 5),
                "lat": round(centroid.y, 5),
            }
        )
    ranked_path = WEB_DATA / f"{name}_ranked.json"
    ranked_path.write_text(json.dumps(ranked, indent=None))

    print(f"  -> {out_path} ({out_path.stat().st_size/1e6:.1f} MB), {ranked_path.name} ({len(ranked)} ranked)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        export(name)


if __name__ == "__main__":
    main()
