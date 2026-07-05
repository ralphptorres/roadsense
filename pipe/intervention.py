"""Classify flagged (is_significant) segments into a recommended intervention.

Added post-submission (gate C review found the intervention breakdown quoted
in findings-summary.typ had no backing script anywhere in the repo, and its
Thailand sub-counts didn't even sum to the flagged total). This script is the
actual, auditable derivation.

Logic, per flagged segment, comparing posted limit and observed 85th
percentile speed against the same Safe System threshold used in Layer 1:

- both posted and actual exceed threshold -> road redesign (a new sign alone
  won't fix unsafe geometry that invites the observed speed)
- only actual exceeds threshold -> enforcement / traffic calming (the posted
  limit is fine, drivers are ignoring it)
- only posted exceeds threshold -> lower the posted limit (drivers are
  already at a safe speed, only the sign is misaligned)
- neither exceeds threshold -> flagged for peer-relative reasons rather than
  an absolute Safe System breach, reported separately rather than forced into
  one of the three buckets above
"""

import sys
import geopandas as gpd

COUNTRIES = ["thailand", "maharashtra"]


def classify(name: str) -> dict:
    df = gpd.read_file(f"data/clean/{name}_final.gpkg")
    flagged = df[df["is_significant"]].copy()
    n = len(flagged)

    posted_over = flagged["SpeedLimit"] > flagged["safe_limit_kmh"]
    actual_over = flagged["F85thPercentileSpeed"] > flagged["safe_limit_kmh"]

    redesign = int((posted_over & actual_over).sum())
    enforcement = int((~posted_over & actual_over).sum())
    lower_limit = int((posted_over & ~actual_over).sum())
    peer_only = int((~posted_over & ~actual_over).sum())
    high_vue = int((flagged["exposure_tier"] == "high").sum())

    assert redesign + enforcement + lower_limit + peer_only == n

    return {
        "n_flagged": n,
        "road_redesign": redesign,
        "enforcement_calming": enforcement,
        "lower_limit_only": lower_limit,
        "peer_relative_only": peer_only,
        "high_vue_exposure": high_vue,
    }


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = COUNTRIES if target == "both" else [target]
    for name in names:
        stats = classify(name)
        n = stats["n_flagged"]
        print(f"\n{name} (n={n} flagged)")
        for k, v in stats.items():
            if k == "n_flagged":
                continue
            print(f"  {k}: {v} ({v / n * 100:.1f}%)")


if __name__ == "__main__":
    main()
