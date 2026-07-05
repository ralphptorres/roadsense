import pathlib
import sys

import geopandas as gpd
import networkx as nx
import numpy as np
from scipy import stats

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

# node-snap tolerance in degrees (~11m at the equator) to merge segment
# endpoints that represent the same intersection without needing a
# separate topology dataset. built from our own cleaned segment geometry
# rather than pulling another OSMnx/Overpass graph for the same area, see
# p0-submission/methodology-plan.md's graph-theory addendum: literature
# check found no canonical method here and flagged centrality as likely
# redundant with traffic volume (WeightedSample) — this is an exploratory
# check, not a scoring input, unless it demonstrably diverges.
SNAP_DECIMALS = 4
BETWEENNESS_SAMPLE_K = 500  # exact betweenness is O(V*E), sample for feasibility


def snap(coord):
    return (round(coord[0], SNAP_DECIMALS), round(coord[1], SNAP_DECIMALS))


def build_graph(gdf: gpd.GeoDataFrame) -> nx.Graph:
    G = nx.Graph()
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        coords = list(geom.coords)
        u, v = snap(coords[0]), snap(coords[-1])
        G.add_edge(u, v, segment_idx=idx, length_km=row["length_km"])
    return G


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"NETWORK CENTRALITY (exploratory) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_final.gpkg")
    G = build_graph(gdf)
    print(f"  graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges (from {len(gdf):,} segments)")

    k = min(BETWEENNESS_SAMPLE_K, G.number_of_nodes())
    centrality = nx.edge_betweenness_centrality(G, k=k, weight="length_km", seed=42)

    seg_centrality = {}
    for (u, v), c in centrality.items():
        idx = G.edges[u, v]["segment_idx"]
        seg_centrality[idx] = c

    gdf["betweenness"] = gdf.index.map(seg_centrality).fillna(0.0)

    print("\n  betweenness describe:")
    print(gdf["betweenness"].describe().to_string())

    # the actual test: does centrality carry information beyond
    # WeightedSample (traffic volume), or is it redundant, per the
    # literature check's caution?
    valid = gdf[["betweenness", "WeightedSample"]].dropna()
    rho, p = stats.spearmanr(valid["betweenness"], valid["WeightedSample"])
    print(f"\n  Spearman(betweenness, WeightedSample): rho={rho:.3f}, p={p:.2e}, n={len(valid):,}")

    # a near-zero correlation here is NOT "found independent information" —
    # check whether it's actually because the graph is too fragmented for
    # betweenness to mean anything before drawing that conclusion.
    n_components = nx.number_connected_components(G)
    largest_cc = len(max(nx.connected_components(G), key=len))
    zero_frac = (gdf["betweenness"] == 0).mean()
    print(f"  connected components: {n_components:,} (largest: {largest_cc} of {G.number_of_nodes():,} nodes)")
    print(f"  betweenness == 0: {zero_frac:.1%}")
    if zero_frac > 0.5 or largest_cc < 0.1 * G.number_of_nodes():
        print("  -> graph is too fragmented for betweenness to be meaningful (this dataset is a")
        print("     simplified/sampled set of monitored links, not a complete street network).")
        print("     NOT a validated signal — do not report or score. see docs/network-centrality-findings.md.")
    elif abs(rho) > 0.5:
        print("  -> as the literature suggested: substantially redundant with traffic volume.")
        print("     reporting as a diagnostic only, NOT feeding it into risk_index/SSS.")
    else:
        print("  -> weaker correlation than the literature suggested on a well-connected graph:")
        print("     carries some information WeightedSample doesn't. exploratory/diagnostic only.")

    out_path = CLEAN / f"{name}_final.gpkg"
    gdf.to_file(out_path, driver="GPKG", layer=name)
    print(f"\nwritten -> {out_path}")
    return gdf


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "both"
    names = ["thailand", "maharashtra"] if target == "both" else [target]
    for name in names:
        score(name)


if __name__ == "__main__":
    main()
