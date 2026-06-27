from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import EXPOSURE_INDEX_COLUMNS, PROCESSED_DATA_DIR
from .data_download import cache_dataframe
from .ml_models import ModelBundle, predict_with_bundle, time_based_split

try:
    import shap  # pragma: no cover - optional dependency
except Exception:  # pragma: no cover - optional dependency
    shap = None


GLOBAL_EXPLANATIONS_PATH = PROCESSED_DATA_DIR / "ml_explanations_global.parquet"
LOCAL_EXPLANATIONS_PATH = PROCESSED_DATA_DIR / "ml_explanations_local.parquet"


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def permutation_importance_bundle(bundle: ModelBundle, frame: pd.DataFrame, target_col: str = "fertility_rate") -> pd.DataFrame:
    scored = frame.dropna(subset=[target_col]).copy()
    if scored.empty:
        return pd.DataFrame()
    baseline_pred = predict_with_bundle(bundle, scored)
    baseline_rmse = _rmse(scored[target_col].to_numpy(dtype=float), baseline_pred)
    rows = []
    for feature in bundle.feature_columns:
        permuted = scored.copy()
        permuted[feature] = np.random.default_rng(42).permutation(permuted[feature].to_numpy())
        permuted_pred = predict_with_bundle(bundle, permuted)
        permuted_rmse = _rmse(scored[target_col].to_numpy(dtype=float), permuted_pred)
        rows.append(
            {
                "model_name": bundle.model_name,
                "feature": feature,
                "importance_value": permuted_rmse - baseline_rmse,
                "importance_type": "permutation_rmse_delta",
            }
        )
    return pd.DataFrame(rows).sort_values("importance_value", ascending=False)


def global_explanations(
    model_bundles: dict[str, ModelBundle],
    ml_panel: pd.DataFrame,
    save_path: str | Path = GLOBAL_EXPLANATIONS_PATH,
) -> pd.DataFrame:
    scored = ml_panel.dropna(subset=["fertility_rate"]).copy()
    split = time_based_split(scored)
    test_frame = split["test"]
    rows = []
    for bundle in model_bundles.values():
        perm = permutation_importance_bundle(bundle, test_frame)
        if not perm.empty:
            rows.append(perm)
        if shap is not None and bundle.model_type in {"sklearn_pipeline", "sklearn_numeric"}:
            sample = test_frame.head(min(50, len(test_frame))).copy()
            try:  # pragma: no cover - optional dependency
                explainer = shap.Explainer(lambda x: predict_with_bundle(bundle, pd.DataFrame(x, columns=bundle.feature_columns)), sample[bundle.feature_columns])
                shap_values = explainer(sample[bundle.feature_columns])
                shap_importance = np.abs(shap_values.values).mean(axis=0)
                rows.append(
                    pd.DataFrame(
                        {
                            "model_name": bundle.model_name,
                            "feature": bundle.feature_columns,
                            "importance_value": shap_importance,
                            "importance_type": "shap_mean_abs",
                        }
                    )
                )
            except Exception:
                pass
    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["model_name", "feature", "importance_value", "importance_type"])
    cache_dataframe(result, Path(save_path))
    return result


def _feature_family(feature: str) -> str:
    if feature.startswith("remote_work_exposure_index"):
        return "remote_work"
    if feature.startswith("digital_distraction_index"):
        return "digital_distraction"
    if feature.startswith("digital_social_index"):
        return "digital_social"
    if feature.startswith("in_person_social_index"):
        return "in_person_social"
    if feature.startswith("in_person_work_exposure_index"):
        return "in_person_work"
    if feature.startswith("fertility_rate_lag"):
        return "fertility_lags"
    if feature.startswith("state_history_") or feature.startswith("year_index"):
        return "state_trend_history"
    return "other"


def local_explanation_for_row(
    bundle: ModelBundle,
    row: pd.Series,
    reference_frame: pd.DataFrame,
) -> pd.DataFrame:
    row_df = pd.DataFrame([row])
    predicted = float(predict_with_bundle(bundle, row_df)[0])
    rows = []
    reference = {}
    for feature in bundle.feature_columns:
        if feature in reference_frame.columns and pd.api.types.is_numeric_dtype(reference_frame[feature]):
            reference[feature] = float(pd.to_numeric(reference_frame[feature], errors="coerce").median())
        elif feature in reference_frame.columns:
            reference[feature] = reference_frame[feature].mode(dropna=True).iloc[0] if not reference_frame[feature].mode(dropna=True).empty else row.get(feature)
        else:
            reference[feature] = row.get(feature)

    for feature in bundle.feature_columns:
        perturbed = row_df.copy()
        if feature in perturbed.columns and pd.api.types.is_numeric_dtype(perturbed[feature]):
            perturbed[feature] = pd.to_numeric(pd.Series([reference[feature]]), errors="coerce")
        else:
            perturbed[feature] = reference[feature]
        perturbed_prediction = float(predict_with_bundle(bundle, perturbed)[0])
        contribution = predicted - perturbed_prediction
        rows.append(
            {
                "state_fips": row.get("state_fips"),
                "state_name": row.get("state_name"),
                "region": row.get("region"),
                "year": row.get("year"),
                "model_name": bundle.model_name,
                "predicted_fertility_rate": predicted,
                "feature": feature,
                "feature_family": _feature_family(feature),
                "contribution": contribution,
                "direction": "positive" if contribution >= 0 else "negative",
                "importance_rank": 0,
            }
        )

    contributions = pd.DataFrame(rows)
    contributions["importance_rank"] = contributions["contribution"].abs().rank(method="first", ascending=False).astype(int)
    contributions["temporal_bucket"] = contributions["feature"].str.extract(r"_lag(\d)$", expand=False).fillna("current")
    contributions["plain_english"] = contributions.apply(
        lambda r: (
            f"{r['state_name']} {int(r['year'])}: {r['feature_family']} "
            f"{'raises' if r['contribution'] >= 0 else 'lowers'} the projected fertility rate by about {abs(r['contribution']):.2f}."
        ),
        axis=1,
    )
    return contributions.sort_values("importance_rank")


def local_explanations(
    model_bundles: dict[str, ModelBundle],
    candidate_rows: pd.DataFrame,
    reference_frame: pd.DataFrame,
    save_path: str | Path = LOCAL_EXPLANATIONS_PATH,
) -> pd.DataFrame:
    outputs = []
    for bundle in model_bundles.values():
        bundle_rows = candidate_rows.copy()
        if "model_name" in bundle_rows.columns:
            bundle_rows = bundle_rows[bundle_rows["model_name"].isna() | bundle_rows["model_name"].eq(bundle.model_name)].copy()
        if bundle_rows.empty:
            continue
        if any(feature not in bundle_rows.columns for feature in bundle.feature_columns):
            continue
        for _, row in bundle_rows.iterrows():
            outputs.append(local_explanation_for_row(bundle, row, reference_frame))
    result = pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
    cache_dataframe(result, Path(save_path))
    return result


def build_explanations(
    model_bundles: dict[str, ModelBundle],
    ml_panel: pd.DataFrame,
    forecast_rows: pd.DataFrame | None = None,
    global_save_path: str | Path = GLOBAL_EXPLANATIONS_PATH,
    local_save_path: str | Path = LOCAL_EXPLANATIONS_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    global_df = global_explanations(model_bundles, ml_panel, save_path=global_save_path)
    split = time_based_split(ml_panel.dropna(subset=["fertility_rate"]))
    candidate_rows = split["test"].sort_values(["state_fips", "year"]).groupby("state_fips", as_index=False).tail(1)
    if forecast_rows is not None and not forecast_rows.empty:
        feature_complete = [feature for bundle in model_bundles.values() for feature in bundle.feature_columns]
        usable_forecasts = forecast_rows.dropna(subset=["year"]).copy()
        usable_forecasts = usable_forecasts[[column for column in usable_forecasts.columns if column in set(usable_forecasts.columns)]]
        if all(feature in usable_forecasts.columns for feature in feature_complete[: min(len(feature_complete), 5)]):
            forecast_candidate = usable_forecasts.sort_values(["state_fips", "year"]).groupby(["model_name", "state_fips"], as_index=False).tail(1)
            candidate_rows = pd.concat([candidate_rows, forecast_candidate], ignore_index=True, sort=False)
    local_df = local_explanations(model_bundles, candidate_rows, ml_panel, save_path=local_save_path)
    return global_df, local_df
