import pathlib
import sys

import geopandas as gpd
from scipy import stats

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"


def validate(name: str) -> None:
    print("=" * 60)
    print(f"VALIDATION (PRISMA-style: benchmark against expected trends) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_layer4.gpkg")

    # No crash ground truth exists (see p0-submission/literature-review.md,
    # item 1 — PRISMA's own answer to this is to benchmark against
    # expected risk trends rather than a held-out ground truth). Two
    # independent checks, using fields NOT used anywhere in building SSS:

    # 1. PercentOverLimit / NumberOverLimit are speeding-behavior fields we
    # never fed into any layer. If SSS is a real signal, segments we flag
    # as high-risk should independently show more speeding behavior.
    print("\n--- check 1: SSS vs speeding-behavior fields (unused in scoring) ---")
    for col in ["PercentOverLimit", "NumberOverLimit"]:
        valid = gdf[[col, "SSS"]].dropna()
        rho, p = stats.spearmanr(valid[col], valid["SSS"])
        print(f"  Spearman(SSS, {col}): rho={rho:.3f}, p={p:.2e}, n={len(valid):,}")

    # 2. Face validity: does the top decile concentrate in the
    # RoadClass x LandUse cells Safe System doctrine says should dominate
    # (pedestrian-conflict cells: secondary/primary x URBAN)?
    print("\n--- check 2: RoadClass x LandUse composition, top decile vs overall ---")
    top_decile = gdf.nlargest(int(len(gdf) * 0.1), "SSS")
    overall = gdf.groupby(["RoadClass", "LandUse"]).size() / len(gdf) * 100
    top = top_decile.groupby(["RoadClass", "LandUse"]).size() / len(top_decile) * 100
    comparison = (
        overall.rename("pct_overall").to_frame().join(top.rename("pct_top_decile"), how="outer").fillna(0).round(1)
    )
    comparison["concentration_ratio"] = (comparison["pct_top_decile"] / comparison["pct_overall"]).round(2)
    print(comparison.sort_values("concentration_ratio", ascending=False).to_string())

    # 3. Internal consistency: is_significant flag should concentrate at
    # the high end of SSS, not be scattered uniformly (would indicate the
    # two signals aren't actually related, since both were built from the
    # same peer-group / gap logic but via different aggregations).
    print("\n--- check 3: SSS by significance flag (internal consistency) ---")
    print(gdf.groupby("is_significant")["SSS"].describe().to_string())


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        validate(name)


if __name__ == "__main__":
    main()
