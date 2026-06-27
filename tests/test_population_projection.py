from __future__ import annotations

import pandas as pd

from src.projections import calculate_births_from_fertility, project_population_accounting


def test_births_are_calculated_correctly_from_fertility_rates():
    df = pd.DataFrame({"predicted_fertility_rate": [60.0], "female_population_15_44": [2000.0]})
    births = calculate_births_from_fertility(df)
    assert births.iloc[0] == 120.0


def test_population_accounting_equation():
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
            "state_fips": ["01"],
            "year": [2025],
            "projected_births": [30.0],
        }
    )
    out = project_population_accounting(population, projected_births)
    row = out.iloc[0]
    assert row["population_next_year"] == row["population_current"] + row["projected_births"] - row["projected_deaths"] + row["projected_net_migration"]
