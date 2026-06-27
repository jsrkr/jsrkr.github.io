from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import MODEL_ARTIFACTS_DIR, PROCESSED_DATA_DIR
from src.metrics import load_default_modeling_state_year_panel
from src.ml_dataset import prepare_ml_state_year_panel
from src.ml_models import (
    ML_PREDICTIONS_PATH,
    ModelBundle,
    TemporalFertilityMLP,
    _prepare_training_data,
    baseline_recursive_forecast,
    recursive_forecast,
)

try:
    import torch
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PyTorch is required to rebuild saved neural-network forecasts.") from exc


class StoredStatisticsImputer:
    def __init__(self, statistics: list[float]) -> None:
        self.statistics_ = np.asarray(statistics, dtype=float)

    def transform(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float).copy()
        mask = np.isnan(arr)
        if mask.any():
            arr[mask] = np.take(self.statistics_, np.where(mask)[1])
        return arr


class StoredStatisticsScaler:
    def __init__(self, mean: list[float], scale: list[float]) -> None:
        self.mean_ = np.asarray(mean, dtype=float)
        self.scale_ = np.asarray(scale, dtype=float)
        self.scale_[self.scale_ == 0] = 1.0

    def transform(self, values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        return (arr - self.mean_) / self.scale_


def _metadata(model_name: str) -> dict:
    path = MODEL_ARTIFACTS_DIR / f"{model_name}_metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_saved_bundles() -> list[ModelBundle]:
    bundles: list[ModelBundle] = []

    ridge_meta = _metadata("statistical_ridge")
    ridge_features = ridge_meta["feature_columns"]
    bundles.append(
        ModelBundle(
            model_name="statistical_ridge",
            model_type="sklearn_pipeline",
            model=joblib.load(MODEL_ARTIFACTS_DIR / "statistical_ridge.joblib"),
            feature_columns=ridge_features,
            categorical_columns=[column for column in ["state_fips", "region"] if column in ridge_features],
            numeric_columns=[column for column in ridge_features if column not in {"state_fips", "region"}],
            metadata=ridge_meta,
        )
    )

    tree_meta = _metadata("tree_gradient_boosting")
    tree_features = tree_meta["feature_columns"]
    bundles.append(
        ModelBundle(
            model_name="tree_gradient_boosting",
            model_type="sklearn_numeric",
            model=joblib.load(MODEL_ARTIFACTS_DIR / "tree_gradient_boosting.joblib"),
            feature_columns=tree_features,
            categorical_columns=[],
            numeric_columns=tree_features,
            metadata=tree_meta,
        )
    )

    neural_meta = _metadata("temporal_neural_net")
    neural_artifact = torch.load(MODEL_ARTIFACTS_DIR / "temporal_neural_net.pt", map_location="cpu")
    neural_features = neural_artifact["feature_columns"]
    neural_model = TemporalFertilityMLP(
        input_dim=len(neural_features),
        hidden_dim=min(64, max(16, len(neural_features) * 2)),
    )
    neural_model.load_state_dict(neural_artifact["state_dict"])
    neural_model.eval()
    bundles.append(
        ModelBundle(
            model_name="temporal_neural_net",
            model_type="torch_numeric",
            model={
                "torch_model": neural_model,
                "imputer": StoredStatisticsImputer(neural_artifact["imputer_statistics"]),
                "scaler": StoredStatisticsScaler(
                    neural_artifact["scaler_mean"],
                    neural_artifact["scaler_scale"],
                ),
                "target_mean": neural_artifact.get("target_mean", 0.0),
                "target_std": neural_artifact.get("target_std", 1.0),
            },
            feature_columns=neural_features,
            categorical_columns=[],
            numeric_columns=neural_features,
            metadata=neural_meta,
        )
    )

    return bundles


def main() -> None:
    modeling_panel = load_default_modeling_state_year_panel()
    ml_panel = prepare_ml_state_year_panel(
        modeling_panel,
        save_path=PROCESSED_DATA_DIR / "ml_state_year_panel.parquet",
        dictionary_path=PROJECT_ROOT / "outputs" / "ml_data_dictionary.csv",
    )
    training_frame = _prepare_training_data(ml_panel)
    scenario_covariates = pd.read_parquet(PROCESSED_DATA_DIR / "scenario_covariates.parquet")
    existing_predictions = pd.read_parquet(ML_PREDICTIONS_PATH)
    non_forecast = existing_predictions[existing_predictions["split"] != "forecast"].copy()

    bundles = _load_saved_bundles()
    future_predictions: list[pd.DataFrame] = []
    scenario_names = scenario_covariates["scenario_name"].dropna().unique().tolist()
    for scenario_name in scenario_names:
        scenario_frame = scenario_covariates[scenario_covariates["scenario_name"] == scenario_name].copy()
        for baseline_model_name in ["baseline_last_observed", "baseline_recent_trend"]:
            baseline_forecast = baseline_recursive_forecast(
                training_frame,
                scenario_frame,
                model_name=baseline_model_name,
                scenario_name=scenario_name,
            )
            if baseline_forecast.empty:
                continue
            baseline_out = baseline_forecast.copy()
            baseline_out["split"] = "forecast"
            baseline_out["actual_fertility_rate"] = np.nan
            future_predictions.append(baseline_out)

        for bundle in bundles:
            forecast_df = recursive_forecast(bundle, training_frame, scenario_frame, scenario_name=scenario_name)
            if forecast_df.empty:
                continue
            future_out = forecast_df.copy()
            future_out["split"] = "forecast"
            future_out["actual_fertility_rate"] = np.nan
            future_predictions.append(future_out)

    updated = pd.concat([non_forecast] + future_predictions, ignore_index=True, sort=False)
    updated = updated.sort_values(["model_name", "split", "scenario_name", "state_fips", "year"]).reset_index(drop=True)
    updated.to_parquet(ML_PREDICTIONS_PATH, index=False)
    print(f"Saved updated forecast rows to {ML_PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
