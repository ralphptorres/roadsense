# RoadSense

### Not just where a speed limit is unsafe. Why, and what to actually do about it.

A submission to ADB's [AI for Safer Roads Innovation Challenge](https://challenges.adb.org/en/challenges/ai4saferroads).

Most "is this speed limit safe" tools stop at detection: here are N unsafe
segments. That answer doesn't tell a transport ministry what to actually do
about any of them, and spending money on the wrong fix (a new sign where the
real problem is enforcement, or vice versa) wastes a limited road-safety
budget.

RoadSense separates *that* a segment is unsafe from *why*, and gets a
different, often counterintuitive, answer: across 14,711 monitored segments
in Thailand and Maharashtra, the majority fix for flagged segments is
**enforcement or traffic calming, not new signage** (62% Thailand, 48%
Maharashtra). Only a small fraction actually need the posted limit lowered.
That distinction, not just the flagging, is the deliverable, because it's
the difference between a dashboard and a decision.

Three things back that diagnosis up rather than asking a judge to take a
single model's output on faith: a peer-relative statistical significance
test (not an arbitrary percentile cutoff) gates which segments count as
genuinely misaligned, an Extreme Value Theory tail-risk model and a
stopping-distance reinterpretation independently corroborate the score in
physical/statistical terms, and a live Mapillary street-level check found a
real segment where the actual posted sign (30 km/h) contradicts the dataset's
recorded limit (60 km/h), an independent, real-world confirmation of exactly
the kind of misalignment this pipeline is built to catch. Negative results
(an exploratory network-centrality check, EVT's own goodness-of-fit test)
are reported honestly rather than hidden.

The same unmodified pipeline also degrades gracefully rather than breaking
when data gets sparser: Maharashtra's flagged set is smaller but higher
confidence, not noisier, demonstrating the methodology actually scales
rather than only working on one clean dataset.

**Live visualization**: https://ralphptorres.github.io/roadsense/
**Findings summary (PDF)**: [`findings-summary.pdf`](findings-summary.pdf)

## this repo covers all four challenge deliverables

| Deliverable | Where |
|---|---|
| **Analytical model**: documented code + evaluation methodology | this repo, see [Methodology](#methodology) and [Evaluation methodology](#evaluation-methodology) below, code in [`pipe/`](pipe) |
| **Speed Safety Score**: classification per segment | [`pipe/composite.py`](pipe/composite.py), see [Classification system](#classification-system) below |
| **Geospatial visualization**: Speed-Unsafe Segments map | live at https://ralphptorres.github.io/roadsense/, source in [`web/`](web) |
| **Findings summary**: findings + recommended interventions | [`findings-summary.pdf`](findings-summary.pdf) (max 5 pages) |

## methodology

Four layers combine into a single 0-100 Speed Safety Score (SSS), each
targeting a distinct, named failure mode rather than one opaque model:

1. **Safe System Gap** ([`pipe/safe_system.py`](pipe/safe_system.py)): each
   segment's posted limit is scored against a WHO/OECD survivable-speed
   threshold for its road class and land use, as a power-law ratio
   `(posted / threshold)^n` (the Power Model of speed and crash severity,
   Elvik et al. 2004), not a linear gap. Thresholds in
   [`conf/safe_system_thresholds.yaml`](conf/safe_system_thresholds.yaml).
2. **Expected operating speed** ([`pipe/operating_speed.py`](pipe/operating_speed.py))
  : a RandomForest regression predicts each segment's 85th-percentile
   operating speed from road context alone (deliberately excluding the posted
   limit), with genuine out-of-fold cross-validation and per-prediction
   confidence from the model's own ensemble variance.
3. **Peer comparison** ([`pipe/clustering.py`](pipe/clustering.py)): segments
   grouped by road class, land use, and local population density, to flag
   posted limits that are outliers relative to similar roads.
4. **Composite score and classification** ([`pipe/composite.py`](pipe/composite.py))
  : combines the Safe System Gap and operating-speed residual (z-scored, not
   independently percentile-ranked, see the code comments for why), modulated
   by a vulnerable-user-exposure multiplier built from land use, traffic
   volume, OpenStreetMap POI density, and WorldPop population density.

Beyond the core four layers: a stopping-distance reinterpretation of the
operating-speed residual in physical units
([`pipe/kinematics.py`](pipe/kinematics.py)), an Extreme Value Theory tail-risk
check ([`pipe/evt_tail.py`](pipe/evt_tail.py)), an exploratory network-centrality
check (negative result, documented not used,
[`docs/network-centrality-findings.md`](docs/network-centrality-findings.md)),
and a Mapillary street-level validation check on the flagged segments
([`pipe/mapillary_tier3.py`](pipe/mapillary_tier3.py),
[`docs/mapillary-tier3-findings.md`](docs/mapillary-tier3-findings.md)).

## classification system

Each segment gets a continuous **Speed Safety Score (0-100)** and a discrete
four-tier classification, so the result is usable without needing to
interpret a raw number:

| Class | Criteria |
|---|---|
| **Critical** | statistically significant misalignment AND score in the top decile (SSS ≥ 90) |
| **High** | statistically significant misalignment, score below the top decile |
| **Moderate** | not statistically significant, but SSS ≥ 50 |
| **Low** | not statistically significant, SSS < 50 |

"Statistically significant" means the segment's risk index exceeds its own
peer cohort's mean by more than two standard deviations, with a minimum
cohort-size floor so a small, noisy peer group can't trigger a false flag
(see `is_significant` and `classify()` in
[`pipe/composite.py`](pipe/composite.py)).

## evaluation methodology

No crash records exist for either country, so validation benchmarks the score
against expected trends rather than a held-out ground truth, following the
same logic used in the surrogate-safety-measure literature:

1. **Internal consistency**: flagged segments score far higher than
   unflagged ones (mean SSS 78-94 vs. 49-50).
2. **Concentration in the expected road categories**: the highest-risk
   segments concentrate in urban secondary / pedestrian-conflict roads,
   exactly where Safe System doctrine predicts.
3. **Deliberately weak correlation with speeding-behavior fields never used
   in scoring**: a strong correlation would mean the score was just
   re-measuring compliance rather than limit-appropriateness.

Full detail in [`docs/validation.md`](docs/validation.md). Two independent
review passes (gate A: EDA/cleaning, gate B: Layers 1-4 + validation) are
documented in [`docs/review-log.md`](docs/review-log.md), including issues
found and how they were fixed.

## repository structure

```
pipe/     pipeline scripts, run in order (see below)
conf/     Safe System threshold table (RoadClass x LandUse -> safe limit)
docs/     findings, methodology notes, review log
web/      geospatial visualization frontend (MapLibre GL JS, no build step)
nb/       marimo notebook for exploratory EDA
```

## running the pipeline

```
uv sync
uv run python pipe/eda.py both
uv run python pipe/clean.py both
uv run python pipe/safe_system.py both
uv run python pipe/operating_speed.py both
uv run python pipe/vue_osm.py both
uv run python pipe/vue_worldpop.py both
uv run python pipe/clustering.py both
uv run python pipe/composite.py both
uv run python pipe/kinematics.py both
uv run python pipe/evt_tail.py both
uv run python pipe/validate.py both
uv run python pipe/jurisdictions.py both
uv run python pipe/poi_markers.py both
uv run python pipe/export_web.py both
uv run python pipe/serve_web.py       # serves web/ at http://localhost:8000
```

Requires the source datasets in `data/raw/` (not committed, see
`.gitignore`, sourced from the challenge organizers). `pipe/network_centrality.py`
and `pipe/mapillary_tier3.py` are exploratory checks, not required for the
core score, run independently if wanted.

Opening `web/index.html` directly via `file://` won't work, the browser
blocks the `fetch()` calls that load `web/data/*.geojson` for local files, it
needs to be served over http (`pipe/serve_web.py` above).

## geospatial visualization features

- light/dark theme toggle, and a policy/technical audience toggle (the side
  panel and popups switch between plain-language recommendations and
  percentile-based technical detail)
- four segment-coloring modes: Speed Safety Score, stopping-distance excess,
  traffic volume, and foot traffic (population density proxy)
- toggleable overlays: jurisdiction boundaries shaded by flagged-segment rate
  (click for per-jurisdiction stats, for remediation planning: which
  jurisdiction owns the fix for a cluster of segments), and
  school/hospital/market facility markers
- a ranked priority-segment panel spanning the full range of flagged
  segments, not just a cluster of near-identical worst cases

## docs

- [`docs/eda-findings.md`](docs/eda-findings.md): exploratory analysis
- [`docs/review-log.md`](docs/review-log.md): two independent review passes, issues found and fixed
- [`docs/validation.md`](docs/validation.md): validation approach and results
- [`docs/vue-tier2-findings.md`](docs/vue-tier2-findings.md): OSM/WorldPop enrichment
- [`docs/network-centrality-findings.md`](docs/network-centrality-findings.md): exploratory check, negative result
- [`docs/evt-findings.md`](docs/evt-findings.md): Extreme Value Theory tail-risk check
- [`docs/mapillary-tier3-findings.md`](docs/mapillary-tier3-findings.md): street-level validation check
