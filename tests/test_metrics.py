import pandas as pd

from src.clean_atus import clean_atus_microdata
from src.metrics import build_modeling_state_year_panel, construct_remote_work_metrics, zscore_by_year


def test_construct_remote_work_metrics_computes_growth_and_time_saved():
    df = pd.DataFrame(
        {
            "state_fips": ["01", "01", "01", "02", "02", "02"],
            "year": [2018, 2019, 2021, 2018, 2019, 2021],
            "remote_work_share_state_year": [0.04, 0.06, 0.12, 0.05, 0.05, 0.08],
            "mean_commute_minutes_state_year": [24, 25, 20, 18, 19, 16],
        }
    )
    out = construct_remote_work_metrics(df, baseline_years=(2018, 2019))
    state_01_2021 = out[(out["state_fips"] == "01") & (out["year"] == 2021)].iloc[0]
    assert round(state_01_2021["remote_work_growth"], 4) == 0.07
    assert round(state_01_2021["commute_savings_proxy"], 4) == 4.5
    assert round(state_01_2021["remote_work_time_saved_roundtrip_minutes_state_year"], 4) == 4.8


def test_atus_digital_media_measures_use_documented_codes() -> None:
    atus = pd.DataFrame(
        {
            "year": [2023, 2023, 2023, 2023],
            "wt06": [1.0, 1.0, 1.0, 1.0],
            "activity_code": ["120308", "120303", "120307", "120101"],
            "tier1_code": ["12", "12", "12", "12"],
            "duration_minutes": [30, 45, 20, 15],
            "state_fips": ["01", "01", "01", "01"],
            "region": ["South", "South", "South", "South"],
        }
    )
    out = clean_atus_microdata(atus)
    row = out.iloc[0]
    assert row["digital_media_minutes_narrow"] == 7.5
    assert row["screen_leisure_minutes_broad"] == 23.75
    assert row["digital_media_minutes_narrow_se"] >= 0
    assert row["respondent_count_unweighted"] == 4


def test_zscore_by_year_handles_constant_series():
    df = pd.DataFrame({"year": [2020, 2020, 2021, 2021], "value": [1.0, 1.0, 2.0, 2.0]})
    result = zscore_by_year(df, "value")
    assert result.tolist() == [0.0, 0.0, 0.0, 0.0]


def test_build_modeling_panel_contains_required_index_columns():
    acs = pd.DataFrame(
        {
            "state_fips": ["01", "01", "02", "02"],
            "year": [2022, 2023, 2022, 2023],
            "remote_work_share_state_year": [0.20, 0.24, 0.22, 0.25],
            "mean_commute_minutes_state_year": [25, 24, 21, 20],
            "long_commute_share_state_year": [0.12, 0.11, 0.10, 0.09],
            "telework_hours_mean_among_remote": [12, 13, 11, 12],
            "remote_posting_proxy_state_year": [0.15, 0.16, 0.14, 0.15],
            "labor_force_participation_rate": [0.60, 0.61, 0.62, 0.63],
            "female_employment_rate": [0.55, 0.56, 0.57, 0.58],
            "married_or_partnered_share_state_year": [0.50, 0.49, 0.52, 0.51],
            "region": ["South", "South", "West", "West"],
        }
    )
    fertility = pd.DataFrame(
        {
            "state_fips": ["01", "01", "02", "02"],
            "state_name": ["Alabama", "Alabama", "Alaska", "Alaska"],
            "year": [2022, 2023, 2022, 2023],
            "general_fertility_rate": [58.0, 57.5, 61.0, 60.5],
        }
    )
    population = pd.DataFrame(
        {
            "state_fips": ["01", "01", "02", "02"],
            "year": [2022, 2023, 2022, 2023],
            "population_total": [1000, 1010, 900, 905],
            "female_population_15_44": [220, 221, 205, 206],
        }
    )
    atus = pd.DataFrame(
        {
            "state_fips": ["01", "02"],
            "year": [2023, 2023],
            "geography_type": ["state", "state"],
            "region": ["South", "West"],
            "digital_media_minutes_narrow": [62, 59],
            "screen_leisure_minutes_broad": [205, 198],
            "digital_distraction_minutes": [210, 200],
            "face_to_face_social_minutes": [40, 42],
            "in_person_social_minutes": [40, 42],
            "work_at_home_minutes": [30, 28],
            "work_away_minutes": [160, 150],
            "away_from_home_minutes": [410, 400],
            "household_work_minutes": [125, 118],
            "unpaid_care_minutes": [82, 79],
            "care_burden_minutes": [207, 197],
            "time_alone_minutes": [290, 280],
            "time_with_spouse_only_minutes": [100, 95],
            "time_with_friends_minutes": [45, 43],
            "time_with_family_minutes": [280, 275],
            "time_with_children_minutes": [120, 110],
            "time_with_spouse_minutes": [155, 150],
            "is_pooled_estimate": [False, False],
            "sample_size": [220, 210],
            "respondent_count_unweighted": [220, 210],
        }
    )
    panel = build_modeling_state_year_panel(acs, fertility, population, atus_df=atus)
    required = {
        "remote_work_time_saved_roundtrip_minutes_state_year",
        "digital_media_minutes_narrow_state_year",
        "screen_leisure_minutes_broad_state_year",
        "in_person_social_minutes_state_year",
        "care_burden_minutes_state_year",
        "remote_work_exposure_index",
        "in_person_work_exposure_index",
        "digital_distraction_index",
        "digital_social_index",
        "in_person_social_index",
        "commute_burden_index",
        "work_family_compatibility_proxy",
        "gendered_care_risk_proxy",
        "source_quality_flags",
    }
    assert required.issubset(panel.columns)
    assert panel["remote_work_time_saved_roundtrip_minutes_state_year"].notna().all()
    assert (panel["mean_commute_minutes_state_year"] > 0).all()
    assert panel.loc[panel["year"] == 2023, "mean_commute_minutes_state_year"].nunique() > 1


def test_build_modeling_panel_uses_region_fallback_for_missing_commute_values() -> None:
    acs = pd.DataFrame(
        {
            "state_fips": ["01", "02", "04", "05"],
            "year": [2023, 2023, 2023, 2023],
            "remote_work_share_state_year": [0.20, 0.24, 0.18, 0.16],
            "mean_commute_minutes_state_year": [pd.NA, pd.NA, pd.NA, pd.NA],
            "long_commute_share_state_year": [pd.NA, pd.NA, pd.NA, pd.NA],
            "telework_hours_mean_among_remote": [12, 13, 11, 10],
            "labor_force_participation_rate": [0.60, 0.61, 0.62, 0.59],
            "female_employment_rate": [0.55, 0.56, 0.57, 0.54],
            "married_or_partnered_share_state_year": [0.50, 0.49, 0.52, 0.48],
            "region": ["South", "West", "West", "South"],
        }
    )
    fertility = pd.DataFrame(
        {
            "state_fips": ["01", "02", "04", "05"],
            "state_name": ["Alabama", "Alaska", "Arizona", "Arkansas"],
            "year": [2023, 2023, 2023, 2023],
            "general_fertility_rate": [58.0, 61.0, 57.0, 56.5],
        }
    )
    population = pd.DataFrame(
        {
            "state_fips": ["01", "02", "04", "05"],
            "year": [2023, 2023, 2023, 2023],
            "population_total": [1000, 900, 1200, 800],
            "female_population_15_44": [220, 205, 260, 180],
        }
    )
    atus = pd.DataFrame(
        {
            "year": [2023, 2023, 2023],
            "geography_type": ["national", "region", "region"],
            "region": [None, "South", "West"],
            "state_fips": [None, None, None],
            "commuting_minutes": [14.0, 15.4, 12.6],
        }
    )
    panel = build_modeling_state_year_panel(acs, fertility, population, atus_df=atus)
    assert set(panel["commute_minutes_quality_state_year"]) == {"region_fallback"}
    assert (panel["mean_commute_minutes_state_year"] > 0).all()
    assert panel["mean_commute_minutes_state_year"].nunique() == 2
