# network centrality: attempted, found not usable

Per the graph-theory addendum in `p0-submission/methodology-plan.md`, built a
road-network graph from our own cleaned segment geometry (snapping endpoint
coordinates within ~11m, `pipe/network_centrality.py`) rather than pulling a
separate OSMnx extract, and computed edge betweenness centrality to test whether
it carries information beyond `WeightedSample` (traffic volume).

## the graph is not actually a network

| | Thailand | Maharashtra |
|---|---|---|
| segments (edges) | 11,134 | 3,577 |
| nodes | 15,892 | 5,653 |
| connected components | 5,023 | 2,178 |
| largest component size | 58 nodes | 46 nodes |
| dead-end (degree-1) node fraction | 67.6% | 80.9% |
| segments with betweenness = 0 | 83.0% | 71.7% |

This dataset provides a **simplified, sampled set of monitored road links**
("Overture data was simplified to create road sections... some links may be very
long... others quite short", per `ref/adb-data-user-guide.md`), not the complete
street topology. The segments we have don't connect up into a real mesh, most
form tiny isolated fragments (largest connected component is under 60 nodes out
of tens of thousands). Betweenness centrality on a graph this fragmented is not
measuring real network importance, it's mostly an artifact of which segments
happen to be endpoints of the tiny fragment they're in.

## conclusion

**Don't use `betweenness` as a signal, reported or scored.** The initial
Spearman correlation with `WeightedSample` came back near-zero (rho=0.008
Thailand, 0.068 Maharashtra), which might look like "found independent
information" at a glance, but that's the wrong read: the near-zero correlation
is because 72-83% of segments have betweenness exactly zero by construction
(isolated/dead-end fragments), not because centrality captures something real
that traffic volume doesn't. This is a negative result, correctly downgrading
the graph-theory addendum further: not just "exploratory only, check for
redundancy with WeightedSample first" (the original plan), but "not usable at
all without a complete street network topology" (e.g. a full OSMnx or
Overture-unsimplified extract), which isn't worth pursuing given the literature
check already found weak justification for this signal even under ideal
conditions. The `betweenness` column stays in `data/clean/*_final.gpkg` for
transparency but should not appear in the findings summary as a validated
result.

