# VUE tier 2 findings

OSM POI density and WorldPop population density enrichment, both countries.
Scripts: `vue_osm.py`, `vue_worldpop.py`. Output: `data/clean/{name}_vue2.gpkg`.

## OSM POI density (schools, hospitals, marketplaces, supermarkets,
convenience stores)

Sourced via bulk Overpass API queries, tiled into a 2.5-degree grid per
country (a single whole-country query hit a 504 timeout, Thailand's bbox
needed 24 tiles). Nearest-POI distance and count within 300m computed via
a haversine BallTree.

| | Thailand | Maharashtra |
|---|---|---|
| POIs found | 23,203 | 17,922 |
| `poi_count_300m` median | 0 | 0 |
| `poi_nearest_km` median | 1.45 | 4.20 |
| `poi_nearest_km` max | 24.1 | 21.3 |

Both distributions are heavily zero-inflated for `poi_count_300m` (median
0 in both countries) since most road segments are naturally not within
300m of a school/hospital/market. `poi_nearest_km` is the more informative
continuous signal for VUE weighting.

Note: an initial Thailand run had 4 of 24 tiles fail (429/504 from the
shared Overpass instance), which silently produced a much higher
`poi_nearest_km` max (117.9km) since some segments had no POI found within
range at all. Retried with backoff and all tiles succeeded on the second
pass (max dropped to 24.1km). If reusing this script, don't trust a
partial run's output without checking the tile-failure log.

## WorldPop population density (2020, 1km, UN-adjusted)

Per-country GeoTIFF, point-sampled at each segment centroid via rasterio.

| | Thailand | Maharashtra |
|---|---|---|
| median pop density (people/km^2) | 452 | 454 |
| max | 29,588 | 59,839 |
| no-coverage (NaN) | 14 | 0 |

Medians are similar across countries despite very different urban/rural
splits in the categorical `LandUse` field, consistent with both being
national/state-wide samples rather than urban-biased subsets.

**Download note**: `data.worldpop.org` throttled this sandbox's single-
connection download of the India raster (18MB) to roughly 1-2 KB/s, while
a baseline test against a different host (Cloudflare) got ~3.4 MB/s in the
same environment, and Thailand's smaller 2.9MB file from the same
WorldPop host downloaded fine. Parallel-connection racing got partway
there (~47 KB/s on the best of 4 concurrent connections) but still didn't
reliably finish; range-request splitting didn't work at all since the
server returns HTTP 200 (not 206) and ignores the `Range` header on this
redirect chain. Ended up downloading the file via a browser directly,
that's the fastest fix if this host is slow again.
