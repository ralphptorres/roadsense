# Data license and attribution

The code in this repository is MIT licensed (see `license`). Data is not, it
comes from several sources with different terms. This file documents each
one and what this repository actually includes.

## Original challenge dataset (Thailand, Maharashtra)

Not included in this repository. `data/raw/` and `data/clean/` are
gitignored. The source TomTom-derived probe/speed-limit GeoJSONs were
provided by ADB under the "AI for Safer Roads" Innovation Challenge's own
Free and Data Use Agreement (FDUA), governed by ADB's terms, not this
project's license. Anyone wanting to reproduce the pipeline needs to source
these datasets directly from the challenge organizers.

`web/data/{country}.geojson` (committed) is a derived export containing
per-segment scores (SSS, risk class, and the layer components that feed
them) computed from that source dataset. Since it's a derivative of
ADB-provided data, treat it as subject to the same FDUA terms as the
original, not as freely redistributable under a separate open license.

## OpenStreetMap (POI density, base map tiles)

© OpenStreetMap contributors, available under the
[Open Database License (ODbL)](https://www.openstreetmap.org/copyright).
Used for: POI density enrichment (`pipe/vue_osm.py`, `pipe/poi_markers.py`,
committed as `web/data/{country}_pois.geojson`) and the base map tiles
(CARTO, also OSM-derived, attributed in the map UI via MapLibre's
attribution control). ODbL requires attribution (provided) and that
substantial extracts of the database itself remain under ODbL if
redistributed, the POI geojson files here should be treated as ODbL.

## GADM administrative boundaries (jurisdiction overlay)

Source: [GADM](https://gadm.org) v4.1, used for `pipe/jurisdictions.py`,
committed as `web/data/{country}_jurisdictions.geojson`. GADM's license
permits academic and non-commercial use freely, but restricts redistribution
and commercial use without prior permission (see
[gadm.org/license.html](https://gadm.org/license.html)). This repository
includes a derived, aggregated (segment-count and score statistics per
jurisdiction, not the raw boundary attribute table) extract for a
non-commercial hackathon/research submission. If you plan to reuse this
specific file outside a non-commercial context, get your own copy directly
from GADM rather than relying on this one.

## WorldPop population density

Source: [WorldPop](https://www.worldpop.org), 2020 UN-adjusted 1km
population density rasters, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Used for VUE
tier 2 enrichment (`pipe/vue_worldpop.py`). Point-sampled values are folded
into `web/data/{country}.geojson`'s `pop_density` field, attribution: WorldPop.

## Mapillary map features

Source: [Mapillary](https://www.mapillary.com) `map_features` API (crosswalk
and regulatory speed-limit sign objects), collaboratively contributed data
under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Query
results are not committed to this repository (`data/raw/` is gitignored),
only aggregate findings are reported in
`docs/mapillary-tier3-findings.md` and `docs/findings-summary.typ`/PDF.
