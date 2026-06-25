from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.explainability import build_explanations
from src.config import DEFAULT_FORECAST_END_YEAR
from src.metrics import load_default_modeling_state_year_panel
from src.ml_dataset import prepare_ml_state_year_panel
from src.ml_models import train_all_models
from src.projections import project_population_scenarios
from src.scenarios import build_future_covariate_scenarios


def main() -> None:
    modeling_panel = load_default_modeling_state_year_panel()
    ml_panel = prepare_ml_state_year_panel(modeling_panel)

    scenario_frames = [
        build_future_covariate_scenarios(ml_panel, scenario_name=scenario_name, end_year=DEFAULT_FORECAST_END_YEAR)
        for scenario_name in [
            "baseline_continuation",
            "distraction_dominant",
            "remote_work_dominant",
            "digital_social_substitution",
            "in_person_revival",
            "gendered_care_penalty",
            "user_defined",
        ]
    ]
    scenario_covariates = pd.concat(scenario_frames, ignore_index=True, sort=False)
    scenario_covariates.to_parquet(PROJECT_ROOT / "data" / "processed" / "scenario_covariates.parquet", index=False)

    bundles, predictions, _ = train_all_models(ml_panel, scenario_covariates=scenario_covariates)
    forecast_inputs = predictions[predictions["split"].eq("forecast")].merge(
        scenario_covariates[["state_fips", "state_name", "region", "year", "scenario_name", "female_population_15_44", "total_population"]],
        on=["state_fips", "state_name", "region", "year", "scenario_name"],
        how="left",
    )

    population_history = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "population_metrics.parquet")
    if "female_population_15_44" not in population_history.columns and "female_population_15_44" in modeling_panel.columns:
        denominators = modeling_panel[["state_fips", "year", "female_population_15_44"]].dropna().drop_duplicates()
        population_history = population_history.merge(denominators, on=["state_fips", "year"], how="left")
    project_population_scenarios(forecast_inputs, population_history)
    build_explanations(bundles, ml_panel, forecast_rows=predictions[predictions["split"].eq("forecast")].copy())
    print("Built ML dashboard artifacts.")


if __name__ == "__main__":
    main()
