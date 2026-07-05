# roadsense

ADB "AI for Safer Roads" challenge submission - Speed Safety Score for
Thailand and Maharashtra road segments.

Live visualization: https://ralphptorres.github.io/roadsense/

## setup

```
uv sync
```

## pipeline

Scripts in `pipe/`, run in order, each `[thailand|maharashtra|both]`:

- `eda.py` - schema comparison, null/anomaly counts, distributional
  summaries for the raw datasets in `data/raw/`. Run before touching
  cleaning thresholds or the Safe System conf, since the two datasets
  differ in schema (see `docs/eda-findings.md`).
- `clean.py` - shared cleaning, handles the per-country schema
  differences noted in `docs/eda-findings.md` and `docs/review-log.md`.
- `safe_system.py` - Layer 1, Safe System Gap (power-law risk term).
- `operating_speed.py` - Layer 2, ML regression for expected operating
  speed.
- `vue_osm.py`, `vue_worldpop.py` - VUE tier 2 enrichment (OSM POI
  density, WorldPop population density).
- `clustering.py` - Layer 3, peer-group comparison.
- `composite.py` - Layer 4, composite Speed Safety Score.
- `kinematics.py` - stopping-distance reinterpretation of OSR (physical units).
- `network_centrality.py` - exploratory network-centrality check (negative
  result, see `docs/network-centrality-findings.md`, not used in scoring).
- `evt_tail.py` - Extreme Value Theory tail-risk check (see `docs/evt-findings.md`).
- `validate.py` - validation checks (see `docs/validation.md`).
- `jurisdictions.py` - spatially joins flagged segments to administrative
  boundaries (GADM, province level for Thailand, district level for
  Maharashtra) and aggregates per-jurisdiction stats, for the
  remediation-planning overlay.
- `poi_markers.py` - separate fetch from `vue_osm.py` (keeps OSM tags,
  which the VUE scoring fetch drops for a smaller payload), for the
  school/hospital/market marker overlay.
- `export_web.py` - exports the final per-segment data to `web/data/` for
  the frontend below. Rerun this after any pipeline change.

`nb/eda_explore.py` - marimo notebook (not Jupyter) for visual EDA. Run
with `uv run marimo edit nb/eda_explore.py`.

## data

`data/raw/` holds symlinks to the source GeoJSONs (not committed, see
`.gitignore`). `data/clean/` holds cleaned output written by the
pipeline (also not committed, regenerable by rerunning `pipe/`).

## geospatial visualization (`web/`)

The interactive map deliverable is a custom static frontend (plain
HTML/CSS/JS, MapLibre GL JS, no build step) rather than a quick
matplotlib/folium export, since this is meant to work for both a
technical judging panel and a non-technical policy audience. Features:

- light/dark theme toggle (light default)
- four segment-coloring modes: Speed Safety Score, stopping-distance
  excess (physics), traffic volume, and foot traffic (population
  density proxy)
- toggleable overlays: jurisdiction boundaries shaded by flagged-segment
  rate (click for per-jurisdiction stats, for remediation planning: which
  jurisdiction owns the fix for a cluster of segments), and
  school/hospital/market facility markers
- a policy/technical audience toggle: the side panel and popups switch
  between plain-language recommendations (mapped from the intervention
  table in `p0-submission/methodology-plan.md`) and percentile-based
  technical detail
- a ranked priority-segment panel spanning the full range of flagged
  segments, not just a cluster of near-identical worst cases

Regenerate the data and serve it:

```
uv run python pipe/jurisdictions.py both
uv run python pipe/poi_markers.py both
uv run python pipe/export_web.py both
uv run python pipe/serve_web.py       # serves web/ at http://localhost:8000
```

Opening `web/index.html` directly via `file://` won't work, the
`fetch()` calls that load `web/data/*.geojson` are blocked by the
browser's CORS rules for local files, it needs to be served over http.

## docs

See `docs/` for EDA findings, methodology notes, and the review log.
