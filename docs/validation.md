# validation

No crash ground truth exists for either country (see
`p0-submission/literature-review.md`, item 1). Following PRISMA's own answer to
this exact problem (arXiv:2303.07891): benchmark the score against expected
trends, since a held-out ground-truth comparison isn't possible. Three checks,
run via `validate.py`.

## check 1: SSS vs speeding-behavior fields never used in scoring

`PercentOverLimit` / `NumberOverLimit` aren't inputs to any layer. Spearman
correlation with SSS:

| | Thailand | Maharashtra |
|---|---|---|
| `PercentOverLimit` | rho=0.026, p=6e-03 | rho=0.164, p=4e-23 |
| `NumberOverLimit` | rho=-0.039, p=4e-05 | rho=0.024, p=0.155 (n.s.) |

(numbers as of the final pipeline, post gate-B fixes; they shifted slightly
across fix iterations, Thailand's `NumberOverLimit` correlation even flipped
sign once. That instability is itself informative, not a concern: it confirms
the relationship is genuinely close to zero rather than a real weak effect,
consistent with the reasoning below.)

Thailand's correlations are statistically significant in places (large n) but
consistently tiny in effect size, close enough to zero that the sign isn't
stable across pipeline revisions. **This is not a failure of the score**: the
challenge brief explicitly frames the problem as "whether speed limits
themselves are appropriate, not whether drivers exceed them." A segment can have
an appropriate-but-high limit with low `PercentOverLimit` (nobody's speeding
relative to it) while still scoring high on SSS if the limit itself exceeds the
Safe System threshold. Strong correlation with raw speeding behavior would
actually suggest SSS is just re-measuring compliance instead of
limit-appropriateness, the opposite of what's wanted. Report this honestly as a
weak-but-expected result, not oversold as strong validation.

## check 2: RoadClass x LandUse concentration, top decile vs overall

| Thailand | pct overall | pct top decile | concentration |
|---|---|---|---|
| secondary URBAN | 25.1% | 96.3% | 3.84x |

| Maharashtra | pct overall | pct top decile | concentration |
|---|---|---|---|
| secondary URBAN | 5.0% | 39.4% | 7.88x |

The top decile is heavily concentrated in secondary/urban roads in both
countries, matching Safe System doctrine (pedestrian-conflict cells should
dominate). **Caveat, be honest about this in the write-up, and correctly
attributed**: gate B review tested the original explanation here (that
`n_conflict=4`, the fatal-scale Power Model exponent, drives the concentration)
by rerunning the whole pipeline with a uniform `n_conflict=2` for every cell.
The concentration barely moved (Thailand 3.83x -> 3.76x, Maharashtra 7.88x ->
8.19x, actually slightly higher). **The exponent is not the mechanical driver.**
Isolating components instead shows `ssg_z` is the driver, and the real cause is
the threshold table itself: `secondary_URBAN`'s `safe_limit_kmh = 30` is far
lower than every other cell's threshold (50-100 km/h), so `SpeedLimit / 30` is
already a large ratio regardless of what exponent is applied. This is a stronger
and harder-to-avoid caveat than the original one: **any** Safe-System-anchored
score with a 30 km/h pedestrian-conflict floor will concentrate here, not just
this particular power-law design choice. This check demonstrates internal
consistency with our own doctrine encoding (the 30 km/h floor is itself a
deliberate, cited Safe System threshold, not an arbitrary number), not fully
independent external validation, don't present it as if it were.

## check 3: SSS by significance flag (internal consistency)

**Found and fixed a real bug during this check.** `is_significant` was
originally built from `gap_z` (peer-group z-score of `F85th - SpeedLimit` raw
gap), but `gap` isn't one of the three components that make up `risk_index`
inside SSS. `gap_z` fires on BOTH directions, dangerously fast operating speed
AND overly-generous limits relative to peers, so it was diluting/inverting the
check: significant segments had a *lower* mean SSS (14.5) than non-flagged ones
(51.8) for Thailand, backwards.

Fixed: `is_significant` now flags `risk_index` (the actual thing feeding SSS)
more than 2 peer-group standard deviations above the peer mean, matching the
gate A correction (empirical peer-group spread, not 1/sqrt(N)), and only in the
high-risk direction (a segment far *below* its peer group isn't unsafe, it's
just well-aligned).

Post-fix (final pipeline, after gate B's round-2 fixes: dropping `outlier_z`
from scoring, continuous ensemble-uncertainty OSR weighting, and a
minimum-group-size floor on the significance flag itself):

| | Thailand mean SSS | Maharashtra mean SSS |
|---|---|---|
| `is_significant = False` | 49.4 | 48.3 |
| `is_significant = True` | 78.1 | 93.5 |

Still strongly in the expected direction. Thailand's gap narrowed somewhat (94.8
-> 78.1) compared to the round-1 fix, because dropping the redundant `outlier_z`
and adding the significance-reliability floor made the flag stricter and more
conservative (228 flagged rows in the final Thailand run vs 514 before, so the
remaining flagged set is more tightly bound to genuine `risk_index` outliers), a
smaller but more trustworthy gap, not a regression.

