import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

SIGNIFICANCE_Z = 2  # flag threshold for "misalignment isn't just peer-group noise"
MIN_GROUP_SIZE_FOR_SIGNIFICANCE = 15  # must match clustering.py's MIN_GROUP_SIZE


def pctile_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"LAYER 4 (composite Speed Safety Score) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_layer3.gpkg")

    # --- risk components: z-scored, not percentile-ranked, on raw values.
    # percentile-ranking each component separately before combining would
    # mean the top segment in each component is already pinned near 100,
    # so averaging three of them and then applying a further multiplier
    # would clip a whole plateau of segments at the ceiling, destroying
    # exactly the discriminative power that matters most for
    # prioritization. do ONE percentile-rank pass, at the very end, on the
    # combined raw index instead. ---
    gdf["ssg_z"] = zscore(gdf["SSG_risk_ratio"])
    gdf["osr_z"] = zscore(gdf["OSR"])

    # gate B review (round 2): ssg_z and Layer 3's speedlimit_z-derived
    # outlier signal are NOT independent — both are monotonic transforms
    # of the same underlying SpeedLimit, correlating 0.83-0.92 within a
    # single RoadClass x LandUse cell. rather than average them into one
    # sub-signal (round-1 fix, still leaves them entangled), drop the
    # peer-outlier signal from the SCORE entirely: SSG_risk_ratio already
    # captures "how far posted limit is from a Safe-System benchmark",
    # and the peer-outlier lens ("how far from the typical peer") is a
    # weaker version of nearly the same thing. speedlimit_z / outlier_z
    # are still computed in Layer 3 and reported below as a named,
    # human-readable reason ("also posted N std above peer average"), just
    # not double-counted into the numeric score.
    gdf["outlier_z_reported"] = zscore(gdf["speedlimit_z"])

    # gate B fix: Layer 2's OSR is unreliable where the RandomForest's own
    # ensemble variance (osr_uncertainty) is high — this replaces the
    # earlier coarse "RoadClass has <30 national rows" binary cutoff with
    # a genuine, continuous per-row confidence measure. osr_weight ranges
    # 0 (highest uncertainty in this country) to 0.5 (lowest), so the
    # combination is at most a true 50/50 between posted-limit-derived and
    # operating-speed-derived risk, sliding toward posted-limit-only as
    # OSR's own confidence drops.
    if "osr_uncertainty" in gdf.columns:
        osr_confidence_pctile = 100 - pctile_rank(gdf["osr_uncertainty"])
        gdf["osr_weight"] = 0.5 * osr_confidence_pctile / 100
    else:
        gdf["osr_weight"] = 0.5

    gdf["risk_index"] = (1 - gdf["osr_weight"]) * gdf["ssg_z"] + gdf["osr_weight"] * gdf["osr_z"]

    # keep 0-100 percentile versions too, for the human-readable component
    # breakdown in the write-up ("this segment's SSG is in the 90th
    # percentile") — not all used in the SSS combination itself.
    gdf["ssg_pctile"] = pctile_rank(gdf["SSG_risk_ratio"])
    gdf["osr_pctile"] = pctile_rank(gdf["OSR"])
    gdf["outlier_pctile"] = pctile_rank(gdf["speedlimit_z"])  # reported reason only, see above

    # --- VUE: tier 1 (LandUse, WeightedSample) + tier 2 (OSM POI
    # proximity, WorldPop density), equal-weighted z-score blend, per
    # methodology-plan.md ("start equal, tune after EDA") ---
    gdf["vue_landuse_z"] = zscore(np.where(gdf["LandUse"] == "URBAN", 1.0, 0.0))
    gdf["vue_traffic_z"] = zscore(gdf["WeightedSample"].clip(lower=0))
    gdf["vue_poi_z"] = zscore(-gdf["poi_nearest_km"])  # closer = higher exposure
    gdf["vue_pop_z"] = zscore(gdf["pop_density"])

    vue_z_cols = ["vue_landuse_z", "vue_traffic_z", "vue_poi_z", "vue_pop_z"]
    gdf["vue_index"] = gdf[vue_z_cols].mean(axis=1)
    gdf["vue_score"] = pctile_rank(gdf["vue_index"])  # 0-100, for the write-up breakdown

    # VUE modulates the risk index (roughly 0.5x-1.5x, via a bounded
    # transform of the VUE z-score) rather than gating it to zero: a
    # segment can still be genuinely unsafe even where our VUE proxies are
    # weak, given how coarse LandUse/POI/pop proxies are (see
    # docs/eda-findings.md, docs/vue-tier2-findings.md).
    gdf["vue_multiplier"] = 1 + 0.5 * np.tanh(gdf["vue_index"])

    gdf["combined_raw"] = gdf["risk_index"] * gdf["vue_multiplier"]
    gdf["SSS"] = pctile_rank(gdf["combined_raw"])

    # --- significance flag, gate A-corrected: peer group's own empirical
    # spread as SE, not a 1/sqrt(N) counting-statistics formula. flag on
    # risk_index itself (the thing actually feeding SSS), not the raw
    # `gap` field — gap isn't one of the three risk components, and
    # flagging its outliers (which fire on BOTH directions: dangerously
    # fast AND overly-generous-limit segments) doesn't track "is this
    # segment's SSS-relevant misalignment real". ---
    peer_risk_mean = gdf.groupby("stats_group")["risk_index"].transform("mean")
    peer_risk_std = gdf.groupby("stats_group")["risk_index"].transform("std").replace(0, np.nan)
    gdf["risk_index_z"] = (gdf["risk_index"] - peer_risk_mean) / peer_risk_std

    # gate B review: clustering.py's MIN_GROUP_SIZE fallback guarantees the
    # peer group used here isn't the *thinnest* possible group, but the
    # fallback (coarse RoadClass x LandUse) can still itself be tiny (e.g.
    # Maharashtra motorway x RURAL: 4 rows total, nowhere finer to fall
    # back to). an empirical std from n=4 has ~50%+ relative uncertainty,
    # don't trust a significance flag built on that silently.
    stats_group_size = gdf.groupby("stats_group")["stats_group"].transform("size")
    gdf["significance_reliable"] = stats_group_size >= MIN_GROUP_SIZE_FOR_SIGNIFICANCE

    # only the high-risk direction counts as a "Speed-Unsafe Segment" flag
    # — a segment far *below* its peer group's risk index isn't unsafe,
    # it's just unusually well-aligned. and only where the peer group is
    # big enough to trust the std.
    gdf["is_significant"] = (gdf["risk_index_z"] > SIGNIFICANCE_Z) & gdf["significance_reliable"]
    n_unreliable = (~gdf["significance_reliable"]).sum()
    if n_unreliable:
        print(f"\n  {n_unreliable} rows in peer groups smaller than {MIN_GROUP_SIZE_FOR_SIGNIFICANCE} - significance flag forced False, not trusted")

    # discrete classification, not just the continuous SSS: combines
    # statistical significance (is the misalignment real, not peer-group
    # noise) with magnitude. SSS alone is a uniform percentile rank by
    # construction, so a pure percentile cut here would just recreate
    # arbitrary quartiles with no added meaning, the significance flag is
    # what actually carries information about whether a segment's SSS is
    # trustworthy, not just high.
    def classify(row):
        if row["is_significant"] and row["SSS"] >= 90:
            return "Critical"
        if row["is_significant"]:
            return "High"
        if row["SSS"] >= 50:
            return "Moderate"
        return "Low"

    gdf["risk_class"] = gdf.apply(classify, axis=1)

    print("SSS describe:")
    print(gdf["SSS"].describe().to_string())
    print(f"\nflagged as significant (risk_index_z > {SIGNIFICANCE_Z}, reliable peer group): {gdf['is_significant'].sum():,} ({gdf['is_significant'].mean():.1%})")
    print("\nrisk_class breakdown:")
    print(gdf["risk_class"].value_counts().to_string())

    print("\ntop 10 Speed-Unsafe Segments by SSS (significant only):")
    top = gdf[gdf["is_significant"]].nlargest(10, "SSS")
    print(
        top[["RoadClass", "LandUse", "SpeedLimit", "F85thPercentileSpeed", "SSG_risk_ratio", "OSR", "vue_score", "SSS"]].to_string(index=False)
    )

    out_path = CLEAN / f"{name}_layer4.gpkg"
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
