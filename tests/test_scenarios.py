from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import SCENARIO_SPECS
from src.scenarios import TRANSPARENT_SCENARIO_GROWTH_OVERRIDES, build_future_covariate_scenarios
from tests.conftest import build_synthetic_ml_panel


def test_scenario_covariates_extend_to_2050(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    future = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2050,
        save_path=tmp_path / "scenario_covariates.parquet",
    )
    assert future["year"].max() == 2050


def test_user_defined_growth_rates_apply_correctly(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    state_panel = ml_panel[ml_panel["state_fips"] == "01"].copy()
    future = build_future_covariate_scenarios(
        state_panel,
        scenario_name="user_defined",
        annual_growth_overrides={"remote_work_exposure": 0.02},
        end_year=2025,
        save_path=tmp_path / "scenario_covariates.parquet",
    )
    anchor = future[(future["state_fips"] == "01") & (future["year"] == 2024)].iloc[0]
    next_year = future[(future["state_fips"] == "01") & (future["year"] == 2025)].iloc[0]
    expected_increment = next_year["remote_work_exposure_index"] - anchor["remote_work_exposure_index"]
    assert round(expected_increment, 6) >= 0.02


def test_scenario_growth_override_saturates_instead_of_compounding_forever(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    remote = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="remote_work_dominant",
        end_year=2060,
        save_path=tmp_path / "remote_long_horizon.parquet",
    )
    baseline = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2060,
        save_path=tmp_path / "baseline_long_horizon.parquet",
    )

    merged = remote.merge(
        baseline[["state_fips", "year", "remote_work_exposure_index"]],
        on=["state_fips", "year"],
        how="left",
        suffixes=("_remote", "_baseline"),
    )
    merged["override_shift"] = merged["remote_work_exposure_index_remote"] - merged["remote_work_exposure_index_baseline"]

    state_fips = merged["state_fips"].iloc[0]
    state_rows = merged[merged["state_fips"] == state_fips].sort_values("year")
    early_anchor_year = int(state_rows["year"].min())
    early_shift = state_rows.loc[state_rows["year"] == early_anchor_year + 1, "override_shift"].iloc[0]
    mid_shift = state_rows.loc[state_rows["year"] == early_anchor_year + 15, "override_shift"].iloc[0]
    late_shift = state_rows.loc[state_rows["year"] == 2059, "override_shift"].iloc[0]
    final_shift = state_rows.loc[state_rows["year"] == 2060, "override_shift"].iloc[0]

    # The per-year increment must shrink (geometric decay), not stay constant, so the
    # cumulative shift approaches a finite ceiling instead of growing forever.
    assert (mid_shift - early_shift) > (final_shift - late_shift)
    assert (final_shift - late_shift) < 0.01


def test_remote_work_dominant_scenario_is_state_specific(tmp_path: Path):
    ml_panel = build_synthetic_ml_panel()
    baseline = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2027,
        save_path=tmp_path / "baseline.parquet",
    )
    remote = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="remote_work_dominant",
        end_year=2027,
        save_path=tmp_path / "remote.parquet",
    )

    merged = remote.merge(
        baseline[["state_fips", "year", "remote_work_share_state_year", "remote_work_time_saved_roundtrip_minutes_state_year"]],
        on=["state_fips", "year"],
        how="left",
        suffixes=("_remote", "_baseline"),
    )
    year_2027 = merged[merged["year"] == 2027].copy()
    year_2027["delta_remote_share"] = (
        year_2027["remote_work_share_state_year_remote"] - year_2027["remote_work_share_state_year_baseline"]
    )
    year_2027["delta_remote_time_saved"] = (
        year_2027["remote_work_time_saved_roundtrip_minutes_state_year_remote"]
        - year_2027["remote_work_time_saved_roundtrip_minutes_state_year_baseline"]
    )

    assert "scenario_scale_remote_work_share_state_year" in remote.columns
    assert year_2027["delta_remote_share"].round(6).nunique() > 1
    assert (year_2027["delta_remote_time_saved"] > 0).all()


def test_remote_work_dominant_growth_overrides_follow_time_saving_direction() -> None:
    overrides = SCENARIO_SPECS["remote_work_dominant"]["growth_overrides"]
    transparent = TRANSPARENT_SCENARIO_GROWTH_OVERRIDES["remote_work_dominant"]

    assert overrides["remote_work_exposure_index"] > 0
    assert overrides["work_family_compatibility_proxy"] > 0
    assert transparent["remote_work_share_state_year"] > 0
    assert transparent["digital_media_minutes_narrow_state_year"] >= 0


def test_remote_work_dominant_projects_transparent_remote_work_measures(tmp_path: Path) -> None:
    ml_panel = build_synthetic_ml_panel()
    future = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="remote_work_dominant",
        end_year=2027,
        save_path=tmp_path / "remote_transparent.parquet",
    )
    row = future[(future["state_fips"] == "01") & (future["year"] == 2027)].iloc[0]
    assert row["remote_work_share_state_year"] > 0
    assert row["remote_work_time_saved_roundtrip_minutes_state_year"] > 0
    assert row["commute_time_saved_by_remote_work"] == row["remote_work_time_saved_roundtrip_minutes_state_year"]


def test_remote_work_share_stays_bounded_across_all_states_years_and_scenarios(tmp_path: Path) -> None:
    ml_panel = build_synthetic_ml_panel()
    frames = []
    for scenario_name in SCENARIO_SPECS:
        frames.append(
            build_future_covariate_scenarios(
                ml_panel,
                scenario_name=scenario_name,
                end_year=2060,
                save_path=tmp_path / f"{scenario_name}.parquet",
            )
        )
    stacked = pd.concat(frames, ignore_index=True, sort=False)
    assert stacked["remote_work_share_state_year"].between(0.0, 1.0, inclusive="both").all()


def test_digital_social_substitution_moves_online_dating_search_interest_and_is_state_specific(tmp_path: Path) -> None:
    ml_panel = build_synthetic_ml_panel()
    baseline = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2027,
        save_path=tmp_path / "baseline.parquet",
    )
    online = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="digital_social_substitution",
        end_year=2027,
        save_path=tmp_path / "online.parquet",
    )

    merged = online.merge(
        baseline[["state_fips", "year", "search_interest_online_dating_state_year"]],
        on=["state_fips", "year"],
        how="left",
        suffixes=("_scenario", "_baseline"),
    )
    year_2027 = merged[merged["year"] == 2027].copy()
    year_2027["delta_dating_interest"] = (
        year_2027["search_interest_online_dating_state_year_scenario"]
        - year_2027["search_interest_online_dating_state_year_baseline"]
    )

    assert "scenario_scale_search_interest_online_dating_state_year" in online.columns
    assert (year_2027["delta_dating_interest"] > 0).all()
    assert year_2027["delta_dating_interest"].round(6).nunique() > 1


def test_gendered_care_penalty_care_burden_delta_is_state_specific(tmp_path: Path) -> None:
    ml_panel = build_synthetic_ml_panel()
    baseline = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2027,
        save_path=tmp_path / "baseline.parquet",
    )
    care = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="gendered_care_penalty",
        end_year=2027,
        save_path=tmp_path / "care.parquet",
    )

    merged = care.merge(
        baseline[["state_fips", "year", "care_burden_minutes_state_year"]],
        on=["state_fips", "year"],
        how="left",
        suffixes=("_scenario", "_baseline"),
    )
    year_2027 = merged[merged["year"] == 2027].copy()
    year_2027["delta_care_burden"] = (
        year_2027["care_burden_minutes_state_year_scenario"] - year_2027["care_burden_minutes_state_year_baseline"]
    )

    assert "scenario_scale_care_burden_minutes_state_year" in care.columns
    assert (year_2027["delta_care_burden"] > 0).all()
    assert year_2027["delta_care_burden"].round(6).nunique() > 1


def test_remote_work_saves_time_delta_is_nonnegative_relative_to_reference(tmp_path: Path) -> None:
    ml_panel = build_synthetic_ml_panel()
    baseline = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="baseline_continuation",
        end_year=2030,
        save_path=tmp_path / "baseline.parquet",
    )
    remote = build_future_covariate_scenarios(
        ml_panel,
        scenario_name="remote_work_dominant",
        end_year=2030,
        save_path=tmp_path / "remote.parquet",
    )
    merged = remote.merge(
        baseline[
            [
                "state_fips",
                "year",
                "remote_work_share_state_year",
                "mean_commute_minutes_state_year",
            ]
        ],
        on=["state_fips", "year"],
        how="left",
        suffixes=("_scenario", "_reference"),
    )
    merged["delta_remote_work_share"] = (
        merged["remote_work_share_state_year_scenario"] - merged["remote_work_share_state_year_reference"]
    )
    merged["delta_remote_work_time_saved"] = (
        merged["delta_remote_work_share"] * merged["mean_commute_minutes_state_year_reference"] * 2.0
    )
    assert (merged["remote_work_share_state_year_scenario"] >= merged["remote_work_share_state_year_reference"]).all()
    assert (merged["delta_remote_work_time_saved"] >= 0).all()
