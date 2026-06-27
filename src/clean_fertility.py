from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FERTILITY_AGE_GROUPS, STATE_FIPS_TO_REGION, STATE_NAME_TO_FIPS
from .data_download import validate_columns


AGE_GROUP_TO_WIDTH = {
    "15-19": 5,
    "20-24": 5,
    "25-29": 5,
    "30-34": 5,
    "35-39": 5,
    "40-44": 5,
}


def clean_state_year_fertility_rates(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(
        df,
        ["state_name", "year", "general_fertility_rate", "total_fertility_rate_approx"],
        "state-year fertility rates",
    )
    out = df.copy()
    out["state_name"] = out["state_name"].astype(str)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype(int)
    out["general_fertility_rate"] = pd.to_numeric(out["general_fertility_rate"], errors="coerce")
    out["total_fertility_rate_approx"] = pd.to_numeric(out["total_fertility_rate_approx"], errors="coerce")
    out["state_fips"] = out["state_name"].map(STATE_NAME_TO_FIPS)
    out.loc[out["state_name"].eq("United States"), "state_fips"] = "00"
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION).fillna("National")
    out["source_used"] = "CDC NCHS Stats of the States manual state-year rates"
    out["measurement_note"] = (
        "General fertility rate is live births per 1,000 women ages 15-44. "
        "Total fertility rate values are copied from the user-supplied CDC state-year table."
    )
    return out


def normalize_cdc_wonder_export(df: pd.DataFrame) -> pd.DataFrame:
    if {"State", "Year", "Births"}.issubset(df.columns):
        out = df.rename(
            columns={
                "State Code": "state_fips",
                "State": "state_name",
                "Year": "year",
                "Births": "births",
                "Age of Mother": "mother_age_group",
                "Race/Ethnicity of Mother": "race_ethnicity",
            }
        ).copy()
    else:
        out = df.copy()
    validate_columns(out, ["state_fips", "year", "births"], "normalized CDC WONDER fertility")
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype(int)
    out["births"] = pd.to_numeric(out["births"], errors="coerce")
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    return out


def build_fertility_metrics(births_df: pd.DataFrame, female_population_df: pd.DataFrame) -> pd.DataFrame:
    births = normalize_cdc_wonder_export(births_df)
    validate_columns(
        female_population_df,
        ["state_fips", "year", "female_population_15_44"],
        "female population data",
    )
    pop = female_population_df.copy()
    pop["state_fips"] = pop["state_fips"].astype(str).str.zfill(2)
    pop["year"] = pop["year"].astype(int)
    pop["female_population_15_44"] = pd.to_numeric(pop["female_population_15_44"], errors="coerce")

    total_births = births.groupby(["state_fips", "year"], as_index=False)["births"].sum()
    merged = total_births.merge(pop, on=["state_fips", "year"], how="left")
    merged["general_fertility_rate"] = 1000.0 * merged["births"] / merged["female_population_15_44"]

    if "mother_age_group" not in births.columns or "female_population_age_group" not in pop.columns:
        merged["total_fertility_rate_approx"] = np.nan
        return merged

    age_births = births[births["mother_age_group"].isin(FERTILITY_AGE_GROUPS)].groupby(
        ["state_fips", "year", "mother_age_group"], as_index=False
    )["births"].sum()
    age_pop = pop.rename(columns={"female_population_age_group": "mother_age_group"})
    age_df = age_births.merge(age_pop, on=["state_fips", "year", "mother_age_group"], how="left")
    age_df["age_specific_fertility_rate"] = 1000.0 * age_df["births"] / age_df["female_population"]
    tfr = (
        age_df.assign(rate_per_woman=age_df["age_specific_fertility_rate"] / 1000.0)
        .assign(age_width=age_df["mother_age_group"].map(AGE_GROUP_TO_WIDTH))
        .groupby(["state_fips", "year"], as_index=False)
        .apply(lambda g: pd.Series({"total_fertility_rate_approx": (g["rate_per_woman"] * g["age_width"]).sum()}))
        .reset_index(drop=True)
    )
    return merged.merge(tfr, on=["state_fips", "year"], how="left")
