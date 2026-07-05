import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import geopandas as gpd
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import folium

    return folium, gpd, mo, np, pd, plt


@app.cell
def _(mo):
    mo.md("# roadsense EDA: visual exploration")
    return


@app.cell
def _(gpd, pd):
    import pathlib

    data_dir = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

    def load_valid(path: str) -> pd.DataFrame:
        gdf = gpd.read_file(path)
        v = gdf[gdf["AnalysisStatus"] == "Valid"].copy()
        v["SpeedLimit_num"] = pd.to_numeric(v["SpeedLimit"], errors="coerce")
        v["RoadClass"] = v["RoadClass"].str.lower().str.strip()
        v["LandUse"] = v["LandUse"].str.upper().str.strip()
        v.loc[v["SpeedLimit_num"] == 0, "SpeedLimit_num"] = pd.NA
        v["gap"] = v["F85thPercentileSpeed"] - v["SpeedLimit_num"]
        return v

    thailand = load_valid(data_dir / "thailand.geojson")
    maharashtra = load_valid(data_dir / "maharashtra.geojson")
    return maharashtra, thailand


@app.cell
def _(mo):
    mo.md("## SpeedLimit vs F85thPercentileSpeed, by RoadClass")
    return


@app.cell
def _(maharashtra, plt, thailand):
    def plot_scatter():
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
        for ax, (name, df) in zip(axes, [("thailand", thailand), ("maharashtra", maharashtra)]):
            for rc, sub in df.groupby("RoadClass"):
                ax.scatter(sub["SpeedLimit_num"], sub["F85thPercentileSpeed"], s=6, alpha=0.4, label=rc)
            ax.plot([0, 130], [0, 130], "k--", lw=1)
            ax.set_title(name)
            ax.set_xlabel("SpeedLimit (km/h)")
            ax.set_ylabel("F85thPercentileSpeed (km/h)")
            ax.legend(markerscale=3, fontsize=8)
        return fig

    plot_scatter()
    return


@app.cell
def _(mo):
    mo.md("## F85th minus SpeedLimit gap, distribution by RoadClass x LandUse")
    return


@app.cell
def _(maharashtra, plt, thailand):
    def plot_gap_boxplot():
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True)
        for ax, (name, df) in zip(axes, [("thailand", thailand), ("maharashtra", maharashtra)]):
            df.boxplot(column="gap", by=["RoadClass", "LandUse"], ax=ax, rot=90)
            ax.set_title(name)
            ax.axhline(0, color="red", lw=1)
        plt.suptitle("")
        return fig

    plot_gap_boxplot()
    return


@app.cell
def _(mo):
    mo.md("## SampleSizeTotal heavy tail, log-scale histogram")
    return


@app.cell
def _(maharashtra, np, pd, plt, thailand):
    def plot_sample_size_hist():
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        datasets = [
            ("thailand", thailand, "SampleSizeTotal" if "SampleSizeTotal" in thailand.columns else "Sample_Size_Total"),
            ("maharashtra", maharashtra, "SampleSizeTotal" if "SampleSizeTotal" in maharashtra.columns else "Sample_Size_Total"),
        ]
        for ax, (name, df, col) in zip(axes, datasets):
            vals = pd.to_numeric(df[col], errors="coerce").replace(0, 1)
            ax.hist(np.log10(vals.dropna()), bins=40)
            ax.set_title(f"{name}: log10({col})")
        return fig

    plot_sample_size_hist()
    return


@app.cell
def _(mo):
    mo.md("## flagged SpeedLimit anomalies on a map (motorway posted < 60 km/h)")
    return


@app.cell
def _(folium, mo, thailand):
    def anomaly_map(df, name):
        anom = df[(df["RoadClass"] == "motorway") & (df["SpeedLimit_num"] < 60)]
        if anom.empty:
            return mo.md(f"no anomalies in {name}")
        centroid = anom.geometry.centroid
        m = folium.Map(location=[centroid.y.mean(), centroid.x.mean()], zoom_start=6, tiles="cartodbpositron")
        for _, row in anom.iterrows():
            folium.GeoJson(row.geometry).add_to(m).add_child(
                folium.Popup(f"SpeedLimit={row['SpeedLimit_num']}, LandUse={row['LandUse']}")
            )
        return m

    anomaly_map(thailand, "thailand")
    return


@app.cell
def _(folium, maharashtra, mo):
    def anomaly_map_mh(df):
        anom = df[(df["RoadClass"] == "motorway") & (df["SpeedLimit_num"] < 60)]
        if anom.empty:
            return mo.md("no anomalies")
        centroid = anom.geometry.centroid
        m = folium.Map(location=[centroid.y.mean(), centroid.x.mean()], zoom_start=6, tiles="cartodbpositron")
        for _, row in anom.iterrows():
            folium.GeoJson(row.geometry).add_to(m).add_child(
                folium.Popup(f"SpeedLimit={row['SpeedLimit_num']}, LandUse={row['LandUse']}")
            )
        return m

    anomaly_map_mh(maharashtra)
    return


if __name__ == "__main__":
    app.run()
