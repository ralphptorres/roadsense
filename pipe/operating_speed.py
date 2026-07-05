import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.preprocessing import OneHotEncoder

BASE = pathlib.Path(__file__).resolve().parent.parent
CLEAN = BASE / "data" / "clean"

# deliberately excludes SpeedLimit and anything derived from it: the point
# of this layer is to predict the operating speed a road's own physical
# context would produce, independent of what's posted, so the residual
# against the *actual* posted limit means something. see
# p0-submission/methodology-plan.md.
CATEGORICAL_FEATURES = ["RoadClass", "LandUse"]
NUMERIC_FEATURES = ["length_km", "WeightedSample"]
TARGET = "F85thPercentileSpeed"

N_ESTIMATORS = 300
MAX_DEPTH = 8
MIN_SAMPLES_LEAF = 10
N_FOLDS = 5

# kept only as a reporting threshold for the write-up ("N rows have <30
# national training examples") — Layer 4 uses the continuous
# osr_uncertainty below, not this, to weight OSR's contribution.
THIN_ROADCLASS_ROWS = 30


def build_features(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    cat = encoder.fit_transform(gdf[CATEGORICAL_FEATURES])
    cat_df = pd.DataFrame(cat, columns=encoder.get_feature_names_out(CATEGORICAL_FEATURES), index=gdf.index)
    num_df = gdf[NUMERIC_FEATURES].copy()
    num_df["WeightedSample"] = num_df["WeightedSample"].clip(lower=0)
    return pd.concat([cat_df, num_df], axis=1)


def make_model() -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=N_ESTIMATORS, max_depth=MAX_DEPTH, min_samples_leaf=MIN_SAMPLES_LEAF, random_state=42
    )


def score(name: str) -> gpd.GeoDataFrame:
    print("=" * 60)
    print(f"LAYER 2 (operating speed regression) — {name}")
    print("=" * 60)

    gdf = gpd.read_file(CLEAN / f"{name}_layer1.gpkg")
    gdf = gdf[gdf[TARGET].notna() & (gdf[TARGET] > 0)].copy().reset_index(drop=True)

    X = build_features(gdf)
    y = gdf[TARGET]

    # held-out split, used only for the reported R^2/MAE below.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    holdout_model = make_model()
    holdout_model.fit(X_train, y_train)
    pred_test = holdout_model.predict(X_test)
    r2 = r2_score(y_test, pred_test)
    mae = mean_absolute_error(y_test, pred_test)
    print(f"  held-out R^2: {r2:.3f}")
    print(f"  held-out MAE: {mae:.2f} km/h")

    importances = pd.Series(holdout_model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\n  feature importances:")
    print(importances.to_string())

    # gate B fix (round 1): every row's OSR must be an out-of-fold
    # prediction, not a mix of in-sample (memorized) and out-of-sample
    # rows from a single split.
    #
    # gate B fix (round 2): also get a genuine per-row confidence measure
    # for that prediction — the spread across the fold model's individual
    # trees — rather than a coarse "RoadClass has <30 rows" cutoff. this
    # is the statistically correct version of what the earlier 1/sqrt(N)
    # counting-statistics idea (methodology-plan.md's physics addendum,
    # corrected in gate A) was reaching for: actual model uncertainty,
    # not a hypothesized formula that didn't hold empirically for the
    # gap variance. cross_val_predict doesn't expose per-fold models, so
    # this is a manual KFold loop.
    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    oof_pred = np.zeros(len(y))
    oof_std = np.zeros(len(y))
    for train_idx, test_idx in kf.split(X):
        fold_model = make_model()
        fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
        X_test_fold = X.iloc[test_idx].values
        tree_preds = np.stack([tree.predict(X_test_fold) for tree in fold_model.estimators_])
        oof_pred[test_idx] = tree_preds.mean(axis=0)
        oof_std[test_idx] = tree_preds.std(axis=0)

    gdf["F85th_predicted"] = oof_pred
    gdf["OSR"] = gdf[TARGET] - gdf["F85th_predicted"]
    gdf["osr_uncertainty"] = oof_std  # ensemble std across trees, km/h — higher = less trustworthy

    print("\n  OSR describe (5-fold out-of-fold predictions):")
    print(gdf["OSR"].describe().to_string())
    print("\n  osr_uncertainty describe (ensemble std, km/h):")
    print(gdf["osr_uncertainty"].describe().to_string())

    # reporting only, see THIN_ROADCLASS_ROWS note above.
    roadclass_counts = gdf["RoadClass"].value_counts()
    thin_classes = roadclass_counts[roadclass_counts < THIN_ROADCLASS_ROWS].index.tolist()
    if thin_classes:
        thin_uncertainty = gdf.loc[gdf["RoadClass"].isin(thin_classes), "osr_uncertainty"]
        other_uncertainty = gdf.loc[~gdf["RoadClass"].isin(thin_classes), "osr_uncertainty"]
        print(f"\n  RoadClasses with <{THIN_ROADCLASS_ROWS} national rows: {thin_classes}")
        print(f"  their mean osr_uncertainty: {thin_uncertainty.mean():.2f} vs {other_uncertainty.mean():.2f} elsewhere")

    out_path = CLEAN / f"{name}_layer2.gpkg"
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
