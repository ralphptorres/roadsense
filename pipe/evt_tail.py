import pathlib
import sys

import geopandas as gpd
import numpy as np
from scipy import stats

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

# Extreme Value Theory / peaks-over-threshold: fit a Generalized Pareto
# Distribution to exceedances of risk_index above a high threshold, to
# estimate tail (extreme-misalignment) risk beyond the observed range —
# same class of technique used for crash-probability tail estimation in
# our lit review (Songchitruksa & Tarko 2006, cited via PRISMA's related
# work, p0-submission/literature-review.md item 2). Standard peaks-over-
# threshold methodology (Coles 2001), not tied to a single paper.
THRESHOLD_PCTL = 0.90
EXTRAPOLATE_PCTL = 0.999


def fit_gpd(x: np.ndarray, u: float):
    exceedances = x[x > u] - u
    shape, loc, scale = stats.genpareto.fit(exceedances, floc=0)
    return shape, scale, exceedances


def return_level(u: float, shape: float, scale: float, n: int, n_exceed: int, target_pctl: float) -> float:
    # standard POT return-level formula: level exceeded with probability
    # (1 - target_pctl), given exceedance rate n_exceed/n at threshold u.
    zeta_u = n_exceed / n
    p_exceed = 1 - target_pctl
    if shape != 0:
        return u + (scale / shape) * ((p_exceed / zeta_u) ** (-shape) - 1)
    return u - scale * np.log(p_exceed / zeta_u)


def score(name: str, target_col: str) -> None:
    print("=" * 60)
    print(f"EVT TAIL-RISK (peaks-over-threshold on {target_col}) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    x = gdf[target_col].dropna().to_numpy()
    n = len(x)

    u = np.quantile(x, THRESHOLD_PCTL)
    shape, scale, exceedances = fit_gpd(x, u)
    n_exceed = len(exceedances)

    print(f"  threshold u (p{int(THRESHOLD_PCTL*100)}): {u:.3f}")
    print(f"  exceedances: {n_exceed:,} of {n:,} ({n_exceed/n:.1%})")
    print(f"  fitted GPD shape (xi): {shape:.3f}, scale (sigma): {scale:.3f}")
    if shape > 0:
        print("  shape > 0: heavy-tailed — extreme misalignment risk decays slowly, long tail of very")
        print("  badly-misaligned segments is more likely than a normal/exponential model would predict.")
    elif shape < 0:
        print("  shape < 0: bounded tail — there's a finite ceiling on how extreme risk_index gets.")
    else:
        print("  shape ~ 0: exponential-like tail decay.")

    extrapolated = return_level(u, shape, scale, n, n_exceed, EXTRAPOLATE_PCTL)
    empirical_extreme = np.quantile(x, EXTRAPOLATE_PCTL)
    print(f"\n  extrapolated p{EXTRAPOLATE_PCTL*100:.1f} risk_index (GPD): {extrapolated:.3f}")
    print(f"  empirical p{EXTRAPOLATE_PCTL*100:.1f} risk_index (direct, for comparison): {empirical_extreme:.3f}")

    # goodness-of-fit sanity check: KS test on the fitted GPD vs the
    # exceedances themselves.
    ks_stat, ks_p = stats.kstest(exceedances, "genpareto", args=(shape, 0, scale))
    print(f"\n  KS goodness-of-fit: stat={ks_stat:.3f}, p={ks_p:.3f} ({'fit not rejected' if ks_p > 0.05 else 'fit questionable'})")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        # SSG_risk_ratio was tried and rejected: it's built from discretized,
        # rounded SpeedLimit values (30/40/.../120 km/h), fundamentally not
        # continuous, catastrophic KS fit (stat=0.978 in Thailand). risk_index
        # is the continuous composite and the right target. see
        # docs/evt-findings.md.
        score(name, "risk_index")


if __name__ == "__main__":
    main()
