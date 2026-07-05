---
project: adb-safer-road
component: roadsense
type: findings
date: 2026-07-05
---

# VUE tier 3, Mapillary street-level check (findings)

## scope

A data-gap note in `p0-submission/methodology-plan.md` flagged that the challenge
brief describes pre-labeled Mapillary street-level features as a provided dataset,
but the actual GeoJSONs only carry a `StreetImageLink` field, and that field is not
an image link at all, it is the segment's own coordinate string. Getting real
street-level signal requires sourcing it directly from Mapillary's API.

Given the submission deadline, this check is scoped to the statistically
significant flagged segments only (228 Thailand, 137 Maharashtra), not the full
~14,700-segment dataset. Querying Mapillary's map features API for every segment
was not feasible in the time available (see below), so this is reported as a
targeted validation check on the segments the write-up actually discusses, not a
rescored input to the pipeline.

## method

For each flagged segment's centroid, query Mapillary's `map_features` endpoint
(`graph.mapillary.com`, free access token, no image download needed for this
part) within a ~100m radius, and check for:

- `regulatory--maximum-speed-limit-*` objects, Mapillary's taxonomy encodes the
  actual signed value in the object class name, so a real speed limit can be read
  off directly, no OCR or VLM required for this check
- crosswalk/pedestrian-crossing-related objects, as street-level corroboration of
  the vulnerable-user-exposure signal already used in Layer 4

`pipe/mapillary_tier3.py` implements this, output cached to
`data/raw/{country}_mapillary_tier3.json`.

## results

| metric | Thailand (228 flagged) | Maharashtra (137 flagged) |
|---|---|---|
| any Mapillary coverage nearby | 90 (39.5%) | 17 (12.4%) |
| readable speed-limit sign nearby | 0 (0%) | 1 (0.7%) |
| sign confirms posted `SpeedLimit` | n/a | 0 |
| sign contradicts posted `SpeedLimit` | n/a | 1 |
| pedestrian-crossing infrastructure nearby | 84 (36.8%) | 10 (7.3%) |

**Maharashtra's much lower coverage rate (12.4% vs. 39.5%) is consistent with,
not contradictory to, the project's existing finding that Maharashtra's
underlying data is sparser and lower-quality than Thailand's** (see
`docs/network-centrality-findings.md`, `docs/validation.md`). This is the same
data-sparsity pattern showing up in a completely independent data source, which
is itself a form of corroboration.

**Speed-limit sign coverage specifically is far sparser than general imagery
coverage, even within segments that do have nearby Mapillary imagery.** Zero
readable speed-limit signs were found near any of Thailand's 228 flagged
segments despite 90 of them having other nearby imagery. This is a genuine
negative result, not a bug, crowdsourced tagging of specific regulatory sign
types requires either community tagging or an object-detection pass having been
run on that imagery, which is a much sparser layer than raw image coverage
itself. Reported honestly rather than omitted.

**The one concrete match found is a striking one.** A Maharashtra flagged
segment posted at 60 km/h has an actual street sign reading 30 km/h nearby,
alongside 5 nearby pedestrian-crossing features. The most likely explanation is
a local zone restriction (school or market zone) that the TomTom-derived
`SpeedLimit` field did not capture, defaulting instead to a road-class-level
limit. This is a single data point, not a statistical result, but it is a real,
independently-sourced instance of exactly the kind of posted-limit
misalignment this project is built to detect, and it corroborates rather than
contradicts the segment's existing flag.

## path B demonstration: VLM scene description

Beyond the map-features check above (which reads pre-labeled objects directly,
no image understanding needed), a small demonstration of the path B approach
described in `p0-submission/methodology-plan.md` (running a vision-language
model on raw street images) was run on 13 sample images (9 Thailand, 4
Maharashtra, drawn from the top-ranked flagged segments) using Qwen2-VL-2B-Instruct
on a rented GPU instance. The model was prompted to describe sidewalk
presence, marked crossings, road width, median/barrier presence, visible
speed-limit signage, and general road type, exactly the kind of feature set
the SAGAI workflow (cited in the findings summary) extracts at scale.

Across the 13 images: only 1 showed a marked pedestrian crossing with visible
sidewalks (a Maharashtra segment), the rest showed no sidewalks or crossings,
and not one had readable speed-limit signage, consistent with the map-features
check's own finding that sign-specific visibility is sparse in this imagery.
The model's numeric estimates should not be trusted at face value: one
response estimated a road's width as "165 meters," an implausible value for
any road, a concrete illustration of why VLM outputs need independent
verification before being used as scored inputs, not just a caveat.

This is a proof of concept, not a scored input or a statistically meaningful
sample: 13 images is still a small slice of the 365 flagged segments, and the
model's outputs show the kind of inconsistency expected from a small
general-purpose VLM (repeated headings, implausible numeric estimates, a "cow
in the foreground" noted without independent confirmation). The value
demonstrated is that this kind of feature extraction is technically viable
directly from Mapillary imagery on modest hardware (a single rented A10 GPU),
not that these descriptions are individually authoritative. Scaling this to
the full flagged set, let alone all ~14,700 segments, is future work, the
per-image inference cost is a few seconds on this hardware, so the binding
constraint is the same
one as the map-features check: Mapillary's own image-lookup API latency, not
model inference time.

## why full-scale coverage was not attempted

Mapillary's `map_features` API responded at 4-12 seconds per request during
this run (observed directly, not a theoretical estimate), driven by API-side
latency, not local rate limiting or network issues on our end. At that pace,
querying all ~14,700 segments (rather than just the 365 flagged ones) would
take multiple hours, which was not available before the submission deadline.
This is flagged as a concrete scope boundary for future work, not a silently
dropped feature: with dedicated time, the same script generalizes directly to
the full dataset by removing the `is_significant` filter.
