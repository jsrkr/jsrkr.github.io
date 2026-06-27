from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import DEFAULT_FORECAST_END_YEAR, PROCESSED_DATA_DIR, SCENARIO_DEFAULTS, SCENARIO_SPECS
from .data_download import cache_dataframe


SCENARIO_LABELS = {
    "A": "Distraction-dominant digital growth",
    "B": "Social-preserving digital growth",
    "C": "Remote-work dominant growth",
    "D": "Gendered-care penalty",
    "E": "Balanced remote-work scenario",
    **{name: spec["label"] for name, spec in SCENARIO_SPECS.items()},
}

POPULATION_SCENARIO_PATH = PROCESSED_DATA_DIR / "population_projection_scenarios.parquet"


def estimate_baseline_trend(df: pd.DataFrame, value_col: str, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    subset = df.dropna(subset=["year", value_col]).copy()
    for keys, group in subset.groupby(group_cols, dropna=False):
        if group["year"].nunique() < 3:
            continue
        X = sm.add_constant(group["year"].astype(float))
        model = sm.OLS(group[value_col].astype(float), X).fit()
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["intercept"] = model.params["const"]
        row["slope"] = model.params["year"]
        row["r_squared"] = model.rsquared
        rows.append(row)
    return pd.DataFrame(rows)


def estimate_baseline_fertility_trend(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return estimate_baseline_trend(df, "age_specific_fertility_rate", group_cols)


def scenario_adjustment_factor(params: dict, scenario_code: str) -> float:
    distraction = params["digital_distraction_growth"] * params["fertility_effect_distraction_per_hour"]
    social = params["digital_social_growth"] * params["fertility_effect_social_per_hour"]
    remote = params["remote_work_growth"] * 10 * params["fertility_effect_remote_per_10pp"]
    face_to_face = params["face_to_face_change"] * params["fertility_effect_social_per_hour"]
    penalty = params["gendered_care_penalty"]

    if scenario_code == "A":
        return distraction + 0.5 * face_to_face
    if scenario_code == "B":
        return 0.25 * distraction + social
    if scenario_code == "C":
        return remote + 0.25 * social
    if scenario_code == "D":
        return remote - penalty + distraction
    if scenario_code == "E":
        return 0.65 * remote + 0.35 * social - 0.25 * penalty
    raise ValueError(f"Unknown scenario code: {scenario_code}")


def project_age_specific_fertility(
    baseline_rates: pd.DataFrame,
    female_population: pd.DataFrame,
    params: dict | None = None,
    scenario_code: str = "C",
    horizon: int | None = None,
) -> pd.DataFrame:
    params = {**SCENARIO_DEFAULTS, **(params or {})}
    horizon = horizon or int(params["projection_horizon"])
    adjustment = scenario_adjustment_factor(params, scenario_code)

    trend_df = estimate_baseline_fertility_trend(baseline_rates, ["state_fips", "mother_age_group"])
    latest_year = int(baseline_rates["year"].max())
    years = list(range(latest_year + 1, horizon + 1))
    rows = []
    for _, trend in trend_df.iterrows():
        population_subset = female_population[
            (female_population["state_fips"] == trend["state_fips"])
            & (female_population["mother_age_group"] == trend["mother_age_group"])
        ].sort_values("year")
        if population_subset.empty:
            continue
        last_population = float(population_subset.iloc[-1]["female_population"])
        growth_rate = population_subset["female_population"].pct_change().dropna().tail(3).mean()
        growth_rate = float(growth_rate) if pd.notna(growth_rate) else 0.0

        for year in years:
            baseline_rate = trend["intercept"] + trend["slope"] * year
            adjusted_rate = max(0.0, baseline_rate * (1.0 + adjustment))
            years_forward = year - latest_year
            projected_population = last_population * ((1.0 + growth_rate) ** years_forward)
            births = adjusted_rate / 1000.0 * projected_population
            rows.append(
                {
                    "state_fips": trend["state_fips"],
                    "mother_age_group": trend["mother_age_group"],
                    "year": year,
                    "baseline_age_specific_fertility_rate": baseline_rate,
                    "adjusted_age_specific_fertility_rate": adjusted_rate,
                    "female_population": projected_population,
                    "projected_births": births,
                    "scenario_code": scenario_code,
                }
            )
    return pd.DataFrame(rows)


def project_general_fertility_rate(
    fertility_df: pd.DataFrame,
    params: dict | None = None,
    scenario_code: str = "C",
    horizon: int | None = None,
) -> pd.DataFrame:
    params = {**SCENARIO_DEFAULTS, **(params or {})}
    horizon = horizon or int(params["projection_horizon"])
    adjustment = scenario_adjustment_factor(params, scenario_code)

    trend_df = estimate_baseline_trend(fertility_df, "general_fertility_rate", ["state_fips"])
    if trend_df.empty:
        return pd.DataFrame()
    latest_year = int(fertility_df["year"].max())
    years = list(range(latest_year + 1, horizon + 1))
    latest_tfr = (
        fertility_df.dropna(subset=["total_fertility_rate_approx"])
        .sort_values(["state_fips", "year"])
        .groupby("state_fips", as_index=False)
        .tail(1)[["state_fips", "general_fertility_rate", "total_fertility_rate_approx"]]
        .rename(
            columns={
                "general_fertility_rate": "latest_general_fertility_rate",
                "total_fertility_rate_approx": "latest_total_fertility_rate_approx",
            }
        )
    )
    trend_df = trend_df.merge(latest_tfr, on="state_fips", how="left")

    rows = []
    for _, trend in trend_df.iterrows():
        tfr_ratio = np.nan
        if pd.notna(trend.get("latest_total_fertility_rate_approx")) and pd.notna(trend.get("latest_general_fertility_rate")):
            if float(trend["latest_general_fertility_rate"]) != 0:
                tfr_ratio = float(trend["latest_total_fertility_rate_approx"]) / float(trend["latest_general_fertility_rate"])
        for year in years:
            baseline_rate = trend["intercept"] + trend["slope"] * year
            adjusted_rate = max(0.0, baseline_rate * (1.0 + adjustment))
            projected_tfr = adjusted_rate * tfr_ratio if pd.notna(tfr_ratio) else np.nan
            rows.append(
                {
                    "state_fips": trend["state_fips"],
                    "year": year,
                    "baseline_general_fertility_rate": baseline_rate,
                    "adjusted_general_fertility_rate": adjusted_rate,
                    "projected_total_fertility_rate_approx": projected_tfr,
                    "scenario_code": scenario_code,
                }
            )
    return pd.DataFrame(rows)


def calculate_births_from_fertility(
    df: pd.DataFrame,
    fertility_col: str = "predicted_fertility_rate",
    female_population_col: str = "female_population_15_44",
) -> pd.Series:
    if {fertility_col, female_population_col}.issubset(df.columns):
        return pd.to_numeric(df[fertility_col], errors="coerce") / 1000.0 * pd.to_numeric(df[female_population_col], errors="coerce")

    asfr_cols = [column for column in df.columns if column.startswith("predicted_age_specific_fertility_rate_")]
    female_age_cols = [column for column in df.columns if column.startswith("female_population_age_")]
    if asfr_cols and female_age_cols:
        births = pd.Series(0.0, index=df.index, dtype=float)
        for asfr_col in asfr_cols:
            suffix = asfr_col.replace("predicted_age_specific_fertility_rate_", "")
            population_col = f"female_population_age_{suffix}"
            if population_col in df.columns:
                births = births + (pd.to_numeric(df[asfr_col], errors="coerce") / 1000.0) * pd.to_numeric(df[population_col], errors="coerce")
        return births
    return pd.Series(np.nan, index=df.index, dtype=float)


def extrapolate_population_components(population_df: pd.DataFrame) -> pd.DataFrame:
    population = population_df.sort_values(["state_fips", "year"]).copy()
    if "death_rate" not in population.columns:
        if {"deaths", "population_total"}.issubset(population.columns):
            population["death_rate"] = population["deaths"] / population["population_total"]
        else:
            population["death_rate"] = np.nan
    if "net_migration_rate" not in population.columns:
        if {"net_migration", "population_total"}.issubset(population.columns):
            population["net_migration_rate"] = population["net_migration"] / population["population_total"]
        else:
            population["net_migration_rate"] = np.nan

    rows = []
    for state_fips, group in population.groupby("state_fips", sort=False):
        recent = group.tail(5)
        death_rate = recent["death_rate"].dropna().mean()
        migration_rate = recent["net_migration_rate"].dropna().mean()
        rows.append(
            {
                "state_fips": state_fips,
                "baseline_death_rate": float(death_rate) if pd.notna(death_rate) else 0.008,
                "baseline_net_migration_rate": float(migration_rate) if pd.notna(migration_rate) else 0.0,
                "death_assumption": "observed_recent_average" if recent["death_rate"].notna().any() else "extrapolated_default",
                "migration_assumption": "observed_recent_average" if recent["net_migration_rate"].notna().any() else "extrapolated_default",
            }
        )
    return pd.DataFrame(rows)


def project_population_accounting(
    population_df: pd.DataFrame,
    projected_births_df: pd.DataFrame,
    baseline_death_rate_col: str = "death_rate",
    baseline_net_migration_rate_col: str = "net_migration_rate",
) -> pd.DataFrame:
    latest_population = population_df.sort_values(["state_fips", "year"]).groupby("state_fips", as_index=False).tail(1).copy()
    component_defaults = extrapolate_population_components(population_df)
    latest_population = latest_population.merge(component_defaults, on="state_fips", how="left")

    births_frame = projected_births_df.copy()
    if "projected_births" not in births_frame.columns:
        births_frame["projected_births"] = calculate_births_from_fertility(
            births_frame,
            fertility_col="predicted_fertility_rate" if "predicted_fertility_rate" in births_frame.columns else "fertility_rate",
            female_population_col="female_population_15_44",
        )

    group_keys = ["state_fips", "year"]
    if "scenario_name" in births_frame.columns:
        group_keys = ["scenario_name", *group_keys]
    birth_totals = births_frame.groupby(group_keys, as_index=False)["projected_births"].sum()

    rows = []
    scenario_iter_cols = ["state_fips"]
    if "scenario_name" in birth_totals.columns:
        scenario_iter_cols = ["scenario_name", "state_fips"]
    for keys, subset in birth_totals.groupby(scenario_iter_cols, sort=False):
        if isinstance(keys, tuple) and len(keys) == 2:
            scenario_name, state_fips = keys
        elif isinstance(keys, tuple) and len(keys) == 1:
            scenario_name, state_fips = "baseline_continuation", keys[0]
        else:
            scenario_name, state_fips = "baseline_continuation", keys

        state_current = latest_population[latest_population["state_fips"] == state_fips]
        if state_current.empty:
            continue
        current_population = float(state_current.iloc[0]["population_total"])
        death_rate = float(state_current.iloc[0].get(baseline_death_rate_col, np.nan))
        if not np.isfinite(death_rate):
            death_rate = float(state_current.iloc[0]["baseline_death_rate"])
        migration_rate = float(state_current.iloc[0].get(baseline_net_migration_rate_col, np.nan))
        if not np.isfinite(migration_rate):
            migration_rate = float(state_current.iloc[0]["baseline_net_migration_rate"])
        female_population = state_current.iloc[0].get("female_population_15_44", np.nan)

        for _, row in subset.sort_values("year").iterrows():
            births = float(row["projected_births"]) if pd.notna(row["projected_births"]) else 0.0
            deaths = current_population * death_rate
            net_migration = current_population * migration_rate
            next_population = current_population + births - deaths + net_migration
            rows.append(
                {
                    "scenario_name": scenario_name,
                    "state_fips": state_fips,
                    "year": int(row["year"]),
                    "population_current": current_population,
                    "projected_births": births,
                    "projected_deaths": deaths,
                    "projected_net_migration": net_migration,
                    "population_next_year": next_population,
                    "female_population_15_44": female_population,
                    "death_assumption": state_current.iloc[0]["death_assumption"],
                    "migration_assumption": state_current.iloc[0]["migration_assumption"],
                }
            )
            current_population = next_population
    return pd.DataFrame(rows)


def add_uncertainty_bands(projected_df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    params = {**SCENARIO_DEFAULTS, **(params or {})}
    out = projected_df.copy()
    out["births_low"] = out["projected_births"] * params["uncertainty_multiplier_low"]
    out["births_mid"] = out["projected_births"] * params["uncertainty_multiplier_mid"]
    out["births_high"] = out["projected_births"] * params["uncertainty_multiplier_high"]
    return out


def project_population_scenarios(
    fertility_forecasts: pd.DataFrame,
    historical_population: pd.DataFrame,
    save_path: str | Path = POPULATION_SCENARIO_PATH,
    end_year: int = DEFAULT_FORECAST_END_YEAR,
) -> pd.DataFrame:
    forecasts = fertility_forecasts.copy()
    if "predicted_fertility_rate" not in forecasts.columns and "fertility_rate" in forecasts.columns:
        forecasts["predicted_fertility_rate"] = forecasts["fertility_rate"]
    forecasts = forecasts[forecasts["year"] <= end_year].copy()
    forecasts["projected_births"] = calculate_births_from_fertility(forecasts, fertility_col="predicted_fertility_rate")
    population = project_population_accounting(historical_population, forecasts)
    cache_dataframe(population, Path(save_path))
    return population
