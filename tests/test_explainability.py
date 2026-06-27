from __future__ import annotations

from pathlib import Path

from src.explainability import build_explanations
from src.ml_models import train_all_models
from tests.conftest import build_synthetic_ml_panel


def test_global_explanation_output_exists(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    bundles, _, _ = train_all_models(
        ml_panel,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    global_df, _ = build_explanations(
        bundles,
        ml_panel,
        global_save_path=tmp_path / "ml_explanations_global.parquet",
        local_save_path=tmp_path / "ml_explanations_local.parquet",
    )
    assert not global_df.empty
    assert {"model_name", "feature", "importance_value"}.issubset(global_df.columns)


def test_local_explanation_for_one_state_year_exists(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    bundles, _, _ = train_all_models(
        ml_panel,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    _, local_df = build_explanations(
        bundles,
        ml_panel,
        global_save_path=tmp_path / "ml_explanations_global.parquet",
        local_save_path=tmp_path / "ml_explanations_local.parquet",
    )
    assert not local_df.empty
    assert {"state_fips", "year", "feature", "contribution"}.issubset(local_df.columns)


def test_fallback_explanation_works_without_shap(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    bundles, _, _ = train_all_models(
        ml_panel,
        predictions_path=tmp_path / "ml_predictions.parquet",
        metrics_path=tmp_path / "ml_model_metrics.parquet",
        artifact_dir=tmp_path / "artifacts",
    )
    global_df, _ = build_explanations(
        bundles,
        ml_panel,
        global_save_path=tmp_path / "ml_explanations_global.parquet",
        local_save_path=tmp_path / "ml_explanations_local.parquet",
    )
    assert "permutation_rmse_delta" in set(global_df["importance_type"])
