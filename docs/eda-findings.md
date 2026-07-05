# EDA findings - Thailand vs Maharashtra

Independently re-verified in `review-log.md` (gate A), which also found
several additional issues not caught in this first pass (redundant
columns, a usable reliability flag in Maharashtra, and a correction to how
SampleSizeTotal should be used for filtering). Read that section before
writing the cleaning script.

## schema differs between the two datasets

Only 20 columns are shared. Thailand-only: `ForAnalysis`, `InvPercentile`,
`NO_OF_Result_Segments`, `OvertureID`, `ProvinceID`, `SampleSizeTotal`,
`english_ro`. Maharashtra-only: `DISSOLVE_ID`, `ExcludeFromSpeedSPI`,
`Pass`, `Sample_Size_Total` (note underscore placement differs from
Thailand's `SampleSizeTotal`), `UrbanPC`, `class`, `names_primary`,
`subtype`.

The old `ai-safer-roads` repo's `clean_data.py` was written for
Maharashtra only and assumed `ForAnalysis`/`NO_OF_Result_Segments` were
absent from the source file, true for Maharashtra, false for Thailand. A
shared cleaning function must not carry that assumption across countries;
it needs to resolve the sample-size column name and the exclude-flag
presence per dataset.

Also: `SpeedLimit` is `str` dtype in Maharashtra, `float64` in Thailand,
needs coercion either way.

## row counts and Valid filter

| | Thailand | Maharashtra |
|---|---|---|
| total rows | 55,884 | 14,082 |
| `AnalysisStatus == 'Valid'` | 11,544 (20.7%) | 4,010 (28.5%) |

Within `Valid` rows only (this is the correct filter, `LandUse`/
`RoadClass` null counts on the *unfiltered* frame are close to but not
exactly equal to the `Not Included` count, so don't infer validity from
those fields being non-null):

| | Thailand | Maharashtra |
|---|---|---|
| `SpeedLimit` null | 0 | 433 (10.8%) |
| `SpeedLimit == 0` (placeholder, not a real limit) | 410 | 0 |
| `LandUse` / `RoadClass` null | 0 | 0 |
| `SampleSizeTotal` zero/null | 0 | 1 |

**`SpeedLimit == 0` must be treated as missing, not as a real posted
limit of 0 km/h.** It shows up only in Thailand (410 rows) and would
otherwise get flagged as a nonsensical Safe System violation on every
road class.

## RoadClass x LandUse coverage (Valid rows), all 8 cells populated,
both countries

Thailand:

| | RURAL | URBAN |
|---|---|---|
| motorway | 27 | 115 |
| primary | 1489 | 1823 |
| secondary | 3144 | 2861 |
| trunk | 1123 | 962 |

Maharashtra:

| | RURAL | URBAN |
|---|---|---|
| motorway | 4 | 36 |
| primary | 758 | 339 |
| secondary | 1237 | 181 |
| trunk | 1098 | 357 |

All 8 RoadClass x LandUse combinations have enough rows in both datasets
to support the Layer 1 Safe System threshold lookup and Layer 3
peer-clustering. motorway x RURAL in Maharashtra is thinnest (4 rows),
worth flagging as low-confidence in the write-up.

## SampleSizeTotal is extremely heavy-tailed

Range spans 8 to ~90M (Thailand) / ~99.6M (Maharashtra), with median
around 2.2x10^5 (Thailand) and 2.3x10^4 (Maharashtra), a fixed absolute
cutoff (e.g. "drop <1000") will behave very differently in the two
countries. Use a percentile-based or log-scale threshold, not fixed
absolute counts, when filtering for reliability.

## the KS free-flow-normality check (He et al. 2023) does not directly
apply

That paper's technique needs raw per-vehicle speed samples to test for
normality. Our data is already pre-aggregated to segment-level
percentiles (`MedianSpeed`, `F85thPercentileSpeed`, `SampleSizeTotal`),
there's no raw distribution to run a KS test against. We fall back to
`SampleSizeTotal`-based reliability filtering as the free-flow/
confidence proxy instead, and this substitution should be stated
explicitly in the methodology writeup rather than silently dropped.

## F85th minus SpeedLimit gap (the core diagnostic signal) looks real,
not degenerate

Thailand: mean -2.3, IQR [-14, +10] km/h. Maharashtra: mean +3.6, IQR
[-10.7, +15.8] km/h. Both show meaningful spread in both directions
(segments running both faster and slower than posted limit), i.e.
there's a real signal here to build Layer 2/3/4 on, not just noise
around zero.

## anomaly counts (RoadClass vs SpeedLimit), confirmed after
zero-filtering

Raw motorway-with-SpeedLimit<60 counts (23 Thailand, 24 Maharashtra)
were inflated by the SpeedLimit==0 placeholder. After dropping those,
genuine anomalies are: **10** in Thailand (all URBAN, limits 20-50
km/h, plausible for an urban limited-access expressway tagged
"motorway") and **24** in Maharashtra (mostly URBAN 40-55 km/h, 2
RURAL). Worth a manual spot-check via `StreetImageLink` before scoring,
per the FAQ's own recommendation to cross-reference `SpeedLimit`
against street imagery.

## StreetImageLink format

Encodes segment endpoints as `lon1,lat1,lon2,lat2` (not a single
point), relevant if VUE tier 3 (Mapillary/VLM) is attempted later; need
to pick a point along the segment, not just one endpoint.

## UrbanPC (Maharashtra only): not independent of LandUse, but still
useful directly

Maharashtra has a continuous `UrbanPC` field (0-1) that agrees strongly
with the categorical `LandUse` label: RURAL rows average 0.025, URBAN
rows average 0.938. Follow-up check (2026-07-05): this isn't agreement
between two independent signals, `LandUse` was evidently computed by
thresholding `UrbanPC` at 0.5 (max RURAL value 0.498, min URBAN value
0.501, zero exceptions). So `UrbanPC` can't cross-validate the label,
but it's still worth using directly as a continuous VUE signal instead
of the binarized `LandUse` for Maharashtra, since 4.0% of segments fall
in the ambiguous 0.3-0.7 band, i.e. real uncertainty the binary cut
discards. Thailand has no equivalent field; giving Thailand a comparable
continuous signal (via OSM POI density / WorldPop, not by trying to
"validate" GRUMP) is the actual gap tier 2 needs to close.
