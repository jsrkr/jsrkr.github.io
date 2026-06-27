import pandas as pd

from src.projections import (
    add_uncertainty_bands,
    project_general_fertility_rate,
    project_population_accounting,
    scenario_adjustment_factor,
)


def test_scenario_adjustment_factor_direction():
    params = {
        "digital_distraction_growth": 0.02,
        "fertility_effect_distraction_per_hour": -0.04,
        "digital_social_growth": 0.01,
        "fertility_effect_social_per_hour": 0.02,
        "remote_work_growth": 0.01,
        "fertility_effect_remote_per_10pp": 0.03,
        "face_to_face_change": -0.01,
        "gendered_care_penalty": 0.02,
    }
    assert scenario_adjustment_factor(params, "A") < 0
    assert scenario_adjustment_factor(params, "C") > 0


def test_population_accounting_identity():
    population = pd.DataFrame(
        {
            "state_fips": ["01"],
            "year": [2024],
            "population_total": [1000.0],
            "death_rate": [0.01],
            "net_migration_rate": [0.02],
        }
    )
    projected_births = pd.DataFrame(
        {
            "state_fips": ["01", "01"],
            "year": [2025, 2026],
            "projected_births": [20.0, 22.0],
        }
    )
    out = project_population_accounting(population, projected_births)
    first = out.iloc[0]
    assert round(first["population_next_year"], 4) == 1030.0


def test_uncertainty_bands_scale_births():
    df = pd.DataFrame({"projected_births": [100.0]})
    out = add_uncertainty_bands(
        df,
        params={"uncertainty_multiplier_low": 0.8, "uncertainty_multiplier_mid": 1.0, "uncertainty_multiplier_high": 1.2},
    )
    assert out.loc[0, "births_low"] == 80.0
    assert out.loc[0, "births_high"] == 120.0


def test_project_general_fertility_rate_runs_with_gfr_only_inputs():
    fertility = pd.DataFrame(
        {
            "state_fips": ["01", "01", "01", "02", "02", "02"],
            "year": [2020, 2021, 2022, 2020, 2021, 2022],
            "general_fertility_rate": [58.0, 59.0, 57.0, 63.0, 62.0, 61.0],
            "total_fertility_rate_approx": [1.80, 1.82, 1.78, 1.95, 1.92, 1.89],
        }
    )
    out = project_general_fertility_rate(fertility, scenario_code="C", horizon=2025)
    assert not out.empty
    assert sorted(out["year"].unique().tolist()) == [2023, 2024, 2025]
    assert {"adjusted_general_fertility_rate", "projected_total_fertility_rate_approx"}.issubset(out.columns)
