from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from src.ml_dataset import prepare_ml_state_year_panel


def build_synthetic_modeling_panel() -> pd.DataFrame:
    rows = []
    for state_fips, state_name, region, base in [
        ("01", "Alabama", "South", 60.0),
        ("02", "Alaska", "West", 63.0),
        ("04", "Arizona", "West", 58.0),
    ]:
        for offset, year in enumerate(range(2016, 2025)):
            remote = 0.2 + 0.01 * offset + (0.02 if state_fips == "02" else 0.0)
            distraction = 0.1 + 0.005 * offset + (0.01 if state_fips == "04" else 0.0)
            digital_social = 0.05 + 0.002 * offset
            in_person_social = 0.3 - 0.006 * offset
            commute_minutes = 24.0 - 0.3 * offset + (2.0 if state_fips == "04" else 0.0)
            digital_media_minutes_narrow = 42.0 + 1.8 * offset + (2.0 if state_fips == "04" else 0.0)
            screen_leisure_minutes_broad = 130.0 + 3.2 * offset + (5.0 if state_fips == "04" else 0.0)
            in_person_social_minutes = 58.0 - 1.4 * offset + (2.0 if state_fips == "02" else 0.0)
            household_work_minutes = 92.0 + 0.8 * offset
            unpaid_care_minutes = 71.0 + 1.1 * offset
            search_interest_online_dating = 40.0 + 0.5 * offset + (3.0 if state_fips == "02" else 0.0)
            remote_work_time_saved = remote * commute_minutes * 2.0
            fertility = base + 1.5 * remote - 2.0 * distraction + 0.6 * digital_social + 0.4 * in_person_social
            rows.append(
                {
                    "state_fips": state_fips,
                    "state_name": state_name,
                    "region": region,
                    "year": year,
                    "fertility_rate": fertility,
                    "births": 500 + offset * 5,
                    "total_population": 1_000_000 + offset * 10_000,
                    "female_population_15_44": 210_000 + offset * 1_000,
                    "population_growth_rate": 0.01 + offset * 0.0001,
                    "remote_work_share_state_year": remote,
                    "mean_commute_minutes_state_year": commute_minutes,
                    "remote_work_time_saved_roundtrip_minutes_state_year": remote_work_time_saved,
                    "digital_media_minutes_narrow_state_year": digital_media_minutes_narrow,
                    "screen_leisure_minutes_broad_state_year": screen_leisure_minutes_broad,
                    "in_person_social_minutes_state_year": in_person_social_minutes,
                    "household_work_minutes_state_year": household_work_minutes,
                    "unpaid_care_minutes_state_year": unpaid_care_minutes,
                    "care_burden_minutes_state_year": household_work_minutes + unpaid_care_minutes,
                    "search_interest_online_dating_state_year": search_interest_online_dating,
                    "remote_work_exposure_index": remote,
                    "in_person_work_exposure_index": 0.4 - 0.01 * offset,
                    "digital_distraction_index": distraction,
                    "digital_social_index": digital_social,
                    "in_person_social_index": in_person_social,
                    "digital_access_index": 0.6 + 0.01 * offset,
                    "digital_use_prevalence_index": 0.55 + 0.01 * offset,
                    "commute_burden_index": 0.45 - 0.01 * offset,
                    "work_family_compatibility_proxy": 0.2 + 0.015 * offset,
                    "gendered_care_risk_proxy": 0.15 + 0.003 * offset,
                    "labor_force_participation_rate": 0.6 + 0.002 * offset,
                    "female_employment_rate": 0.55 + 0.002 * offset,
                    "married_or_partnered_share_state_year": 0.5 - 0.001 * offset + (0.05 if state_fips == "04" else 0.0),
                    "source_quality_flags": "{}",
                }
            )
    return pd.DataFrame(rows)


def build_synthetic_ml_panel() -> pd.DataFrame:
    temp_dir = Path(tempfile.mkdtemp(prefix="synthetic-ml-panel-"))
    return prepare_ml_state_year_panel(
        build_synthetic_modeling_panel(),
        save_path=temp_dir / "ml_state_year_panel.parquet",
        dictionary_path=temp_dir / "ml_data_dictionary.csv",
    )
