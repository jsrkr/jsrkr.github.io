from __future__ import annotations

from pathlib import Path

from src.ml_models import (
    RECURSIVE_FORECAST_CEILING,
    RECURSIVE_FORECAST_FLOOR,
    predict_with_bundle,
    train_all_models,
    train_neural_network_model,
    time_based_split,
    default_feature_columns,
    _prepare_training_data,
)
from src.scenarios import build_future_covariate_scenarios
from tests.conftest import build_synthetic_ml_panel


def test_model_training_runs_on_small_synthetic_panel(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    bundles, predictions, metrics = train_all_models(
        ml_panel,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    assert {"statistical_ridge", "tree_gradient_boosting", "temporal_neural_net"}.issubset(bundles.keys())
    assert not predictions.empty
    assert not metrics.empty


def test_predictions_have_expected_columns(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    _, predictions, _ = train_all_models(
        ml_panel,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    required = {"state_fips", "year", "model_name", "split", "actual_fertility_rate", "predicted_fertility_rate"}
    assert required.issubset(predictions.columns)


def test_recursive_forecasts_produce_future_years(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    scenario_covariates = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2027,
        save_path=tmp_path / "scenario_covariates.parquet",
    )
    _, predictions, _ = train_all_models(
        ml_panel,
        scenario_covariates=scenario_covariates,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    forecast = predictions[predictions["split"] == "forecast"]
    assert not forecast.empty
    assert forecast["year"].min() > ml_panel["year"].max()


def test_recursive_forecast_stays_within_sane_bounds_over_long_horizon(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    # An exaggerated override stresses the recursive fertility_rate_lag1/lag2 feedback loop the
    # way an out-of-domain scenario would; the clamp in recursive_forecast must keep every
    # forecast year inside a plausible band regardless of how far the covariates have drifted.
    scenario_covariates = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="user_defined",
        annual_growth_overrides={"remote_work_exposure": 5.0, "digital_distraction": -5.0},
        end_year=2060,
        save_path=tmp_path / "scenario_covariates.parquet",
    )
    _, predictions, _ = train_all_models(
        ml_panel,
        scenario_covariates=scenario_covariates,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    forecast = predictions[predictions["split"] == "forecast"]
    ml_forecast = forecast[forecast["model_name"].isin(["statistical_ridge", "tree_gradient_boosting", "temporal_neural_net"])]
    assert not ml_forecast.empty
    assert ml_forecast["predicted_fertility_rate"].between(RECURSIVE_FORECAST_FLOOR, RECURSIVE_FORECAST_CEILING).all()


def test_neural_network_predictions_track_target_scale_and_avoid_ceiling():
    # The neural network standardizes its target and inverse-transforms predictions. Without that fix
    # the unscaled target against standardized inputs left the loss badly conditioned, the model
    # diverged, and predictions exploded to the recursive-forecast ceiling. In-sample predictions
    # should now sit near the observed fertility range, not pinned at the clamp.
    ml_panel = build_synthetic_ml_panel()
    training_frame = _prepare_training_data(ml_panel)
    splits = time_based_split(training_frame)
    _, numeric_columns, _ = default_feature_columns(training_frame)
    bundle = train_neural_network_model(splits["train"], splits["validation"], numeric_columns)

    if bundle.model_type == "torch_numeric":
        assert "target_mean" in bundle.model
        assert "target_std" in bundle.model
        assert bundle.model["target_std"] > 0

    predictions = predict_with_bundle(bundle, splits["train"])
    assert predictions.size
    at_ceiling = (predictions >= RECURSIVE_FORECAST_CEILING - 1e-3).mean()
    assert at_ceiling < 0.05
    observed = splits["train"]["fertility_rate"].to_numpy(dtype=float)
    # Predictions should land in the neighborhood of the observed target, not orders of magnitude off.
    assert predictions.mean() < observed.mean() * 3
