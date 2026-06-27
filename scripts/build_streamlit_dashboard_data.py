from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_acs import clean_acs_api_wfh_commute
from src.clean_atus import clean_atus_microdata, pool_small_state_estimates
from src.clean_digital_media import (
    build_measurement_quality_panel,
    clean_acs_internet_tables,
    clean_commercial_media_data,
    clean_google_trends_proxy,
    clean_ntia_state_data,
)
from src.clean_fertility import build_fertility_metrics, normalize_cdc_wonder_export
from src.clean_population import clean_population_estimates
from src.config import PROCESSED_DATA_DIR
from src.data_download import cache_dataframe


def maybe_read_csv(path: str | None) -> pd.DataFrame | None:
    if not path:
        return None
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    return pd.read_csv(csv_path)


def write_if_not_none(df: pd.DataFrame | None, name: str) -> None:
    if df is None or df.empty:
        return
    cache_dataframe(df, PROCESSED_DATA_DIR / f"{name}.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build processed inputs for the Streamlit home-shift dashboard.")
    parser.add_argument("--acs-wfh")
    parser.add_argument("--acs-commute")
    parser.add_argument("--acs-access")
    parser.add_argument("--atus")
    parser.add_argument("--fertility")
    parser.add_argument("--female-population")
    parser.add_argument("--population")
    parser.add_argument("--ntia")
    parser.add_argument("--commercial-digital")
    parser.add_argument("--google-trends")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    acs_state_year = None
    digital_access = None
    if args.acs_wfh and args.acs_commute:
        wfh = pd.read_csv(args.acs_wfh)
        commute = pd.read_csv(args.acs_commute)
        access = pd.read_csv(args.acs_access) if args.acs_access else None
        acs_state_year = clean_acs_api_wfh_commute(wfh, commute, access)
        write_if_not_none(acs_state_year, "acs_state_year")
        if access is not None:
            digital_access = acs_state_year[
                [column for column in acs_state_year.columns if column in {"state_fips", "year", "broadband_subscription_rate", "smartphone_or_computer_access_rate", "no_internet_rate", "digital_access_index", "region", "acs_warning"}]
            ].copy()
            write_if_not_none(digital_access, "digital_access")

    atus_metrics = None
    if args.atus:
        atus_raw = pd.read_csv(args.atus)
        atus_metrics = pool_small_state_estimates(clean_atus_microdata(atus_raw))
        write_if_not_none(atus_metrics, "atus_metrics")

    fertility_metrics = None
    age_specific_fertility = None
    if args.fertility and args.female_population:
        fertility_raw = normalize_cdc_wonder_export(pd.read_csv(args.fertility))
        female_population = pd.read_csv(args.female_population)
        fertility_metrics = build_fertility_metrics(fertility_raw, female_population)
        write_if_not_none(fertility_metrics, "fertility_metrics")
        if {"state_fips", "year", "mother_age_group", "births"}.issubset(fertility_raw.columns):
            age_specific_fertility = fertility_raw.groupby(["state_fips", "year", "mother_age_group"], as_index=False)["births"].sum()
            if "female_population" in female_population.columns:
                age_specific_fertility = age_specific_fertility.merge(
                    female_population[["state_fips", "year", "mother_age_group", "female_population"]],
                    on=["state_fips", "year", "mother_age_group"],
                    how="left",
                )
                age_specific_fertility["age_specific_fertility_rate"] = (
                    1000.0 * age_specific_fertility["births"] / age_specific_fertility["female_population"]
                )
            write_if_not_none(age_specific_fertility, "age_specific_fertility")
            write_if_not_none(female_population, "female_population_age")

    population_metrics = None
    if args.population:
        population_metrics = clean_population_estimates(pd.read_csv(args.population))
        write_if_not_none(population_metrics, "population_metrics")

    digital_prevalence = None
    if args.ntia:
        digital_prevalence = clean_ntia_state_data(pd.read_csv(args.ntia))
        write_if_not_none(digital_prevalence, "digital_prevalence")

    digital_attention = None
    if args.google_trends:
        google_df = pd.read_csv(args.google_trends)
        digital_attention = clean_google_trends_proxy(
            google_df,
            {
                "chatgpt": "search_interest_genai_state_year",
                "tinder": "search_interest_online_dating_state_year",
                "instagram": "search_interest_social_media_state_year",
                "remote jobs": "search_interest_remote_work_state_year",
            },
        )
        write_if_not_none(digital_attention, "digital_attention")

    if args.commercial_digital:
        commercial = clean_commercial_media_data(pd.read_csv(args.commercial_digital))
        write_if_not_none(commercial, "commercial_digital_media")

    quality_panel = build_measurement_quality_panel(
        acs_state_year,
        atus_metrics,
        fertility_metrics,
        population_metrics,
        digital_access,
        digital_prevalence,
        digital_attention,
    )
    write_if_not_none(quality_panel, "measurement_quality")
    print(f"Processed tables written to {PROCESSED_DATA_DIR}")


if __name__ == "__main__":
    main()
