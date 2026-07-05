import pathlib
import sys

import geopandas as gpd

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

# AASHTO stopping sight distance design values (A Policy on Geometric
# Design of Highways and Streets, "Green Book"): perception-reaction time
# t_r = 2.5s, deceleration a = 3.4 m/s^2. Standard, citable civil
# engineering constants, not ad hoc. see p0-submission/methodology-plan.md
# physics addendum: this re-expresses Layer 2's OSR (km/h) into a
# physical unit for the findings summary, "this residual means ~14 extra
# metres of stopping distance", it does not change the regression itself.
REACTION_TIME_S = 2.5
DECELERATION_MS2 = 3.4


def stopping_distance_m(v_kmh):
    v_ms = v_kmh / 3.6
    return v_ms * REACTION_TIME_S + (v_ms**2) / (2 * DECELERATION_MS2)


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"KINEMATICS (stopping-distance reinterpretation of OSR) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_layer4.gpkg")

    gdf["ssd_actual_m"] = stopping_distance_m(gdf["F85thPercentileSpeed"])
    gdf["ssd_predicted_m"] = stopping_distance_m(gdf["F85th_predicted"])
    gdf["ssd_excess_m"] = gdf["ssd_actual_m"] - gdf["ssd_predicted_m"]

    print("ssd_excess_m describe (metres, +ve = needs more stopping distance than road context predicts):")
    print(gdf["ssd_excess_m"].describe().to_string())

    print("\ntop 5 by ssd_excess_m:")
    print(
        gdf.nlargest(5, "ssd_excess_m")[
            ["RoadClass", "LandUse", "F85thPercentileSpeed", "F85th_predicted", "ssd_excess_m", "SSS"]
        ].to_string(index=False)
    )

    out_path = CLEAN / f"{name}_final.gpkg"
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
