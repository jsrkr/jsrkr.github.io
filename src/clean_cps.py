from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from .config import STATE_FIPS_TO_REGION


def _weighted_share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / denominator
    return result.replace([np.inf, -np.inf], np.nan)


def build_cps_wfh_state_year_panel(dta_path: str | Path, chunk_rows: int = 250000) -> pd.DataFrame:
    path = Path(dta_path)
    _, meta = pyreadstat.read_dta(path, metadataonly=True)
    total_rows = meta.number_rows

    usecols = [
        "year",
        "statefip",
        "wtfinl",
        "age",
        "sex",
        "marst",
        "sploc",
        "empstat",
        "labforce",
        "telwrkpay",
        "telwrkhr",
        "covidtelew",
        "wfh_share_2019",
        "wfh_share_post_2023_2024",
        "wfh_exposure_change",
        "has_public_wfh_coverage",
    ]

    accum: dict[tuple[str, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for offset in range(0, total_rows, chunk_rows):
        chunk, _ = pyreadstat.read_dta(
            path,
            usecols=usecols,
            row_offset=offset,
            row_limit=min(chunk_rows, total_rows - offset),
        )
        if chunk.empty:
            continue

        chunk["state_fips"] = pd.to_numeric(chunk["statefip"], errors="coerce").astype("Int64").astype(str).str.zfill(2)
        chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
        chunk["weight"] = pd.to_numeric(chunk["wtfinl"], errors="coerce").fillna(0.0)
        chunk["age"] = pd.to_numeric(chunk["age"], errors="coerce")
        chunk["employed"] = chunk["empstat"].isin([10, 12]).astype(float)
        chunk["labor_force_yes"] = chunk["labforce"].eq(2).astype(float)
        chunk["female"] = chunk["sex"].eq(2).astype(float)
        chunk["partnered"] = chunk["marst"].isin([1, 2]).astype(float)

        telwrkpay = pd.to_numeric(chunk["telwrkpay"], errors="coerce")
        covidtelew = pd.to_numeric(chunk["covidtelew"], errors="coerce")
        actual_wfh = np.where(telwrkpay.eq(1), 1.0, np.where(telwrkpay.eq(2), 0.0, np.nan))
        actual_wfh = np.where(np.isnan(actual_wfh) & covidtelew.eq(2), 1.0, actual_wfh)
        actual_wfh = np.where(np.isnan(actual_wfh) & covidtelew.eq(1), 0.0, actual_wfh)
        chunk["actual_wfh"] = actual_wfh
        chunk["actual_wfh_observed"] = np.where(np.isnan(chunk["actual_wfh"]), 0.0, 1.0)

        telework_hours = pd.to_numeric(chunk["telwrkhr"], errors="coerce")
        telework_hours = telework_hours.where(telework_hours.lt(997))
        chunk["telework_hours"] = telework_hours
        chunk["adult"] = chunk["age"].between(18, 54, inclusive="both").astype(float)
        chunk["female_adult"] = (chunk["female"].eq(1.0) & chunk["adult"].eq(1.0)).astype(float)

        for (state_fips, year), group in chunk.groupby(["state_fips", "year"], dropna=True):
            key = (state_fips, int(year))
            weight = group["weight"]
            employed_weight = (weight * group["employed"]).sum()
            adult_weight = (weight * group["adult"]).sum()
            female_adult_weight = (weight * group["female_adult"]).sum()
            wfh_obs_weight = (weight * group["employed"] * group["actual_wfh_observed"]).sum()
            telework_hours_weight = (weight * group["employed"] * group["actual_wfh"].fillna(0)).sum()
            telework_hours_denom = (
                weight * group["employed"] * group["actual_wfh"].fillna(0) * group["telework_hours"].notna().astype(float)
            ).sum()
            base_exposure_weight = (
                weight * group["employed"] * pd.to_numeric(group["wfh_share_2019"], errors="coerce").fillna(0)
            ).sum()
            post_exposure_weight = (
                weight * group["employed"] * pd.to_numeric(group["wfh_share_post_2023_2024"], errors="coerce").fillna(0)
            ).sum()
            base_exposure_denom = (
                weight * group["employed"] * pd.to_numeric(group["wfh_share_2019"], errors="coerce").notna().astype(float)
            ).sum()
            post_exposure_denom = (
                weight * group["employed"] * pd.to_numeric(group["wfh_share_post_2023_2024"], errors="coerce").notna().astype(float)
            ).sum()

            accum[key]["weight_sum"] += weight.sum()
            accum[key]["adult_weight_sum"] += adult_weight
            accum[key]["female_adult_weight_sum"] += female_adult_weight
            accum[key]["employed_weight_sum"] += employed_weight
            accum[key]["labor_force_weight_sum"] += (weight * group["labor_force_yes"] * group["adult"]).sum()
            accum[key]["female_employed_weight_sum"] += (weight * group["employed"] * group["female"]).sum()
            accum[key]["partnered_weight_sum"] += (weight * group["partnered"] * group["adult"]).sum()
            accum[key]["actual_wfh_weight_sum"] += (weight * group["employed"] * pd.Series(group["actual_wfh"]).fillna(0)).sum()
            accum[key]["actual_wfh_obs_weight_sum"] += wfh_obs_weight
            accum[key]["telework_hours_weighted_sum"] += (
                weight * group["employed"] * pd.Series(group["actual_wfh"]).fillna(0) * group["telework_hours"].fillna(0)
            ).sum()
            accum[key]["telework_hours_weight_denom"] += telework_hours_denom
            accum[key]["wfh_share_2019_weighted_sum"] += base_exposure_weight
            accum[key]["wfh_share_2019_weight_denom"] += base_exposure_denom
            accum[key]["wfh_share_post_weighted_sum"] += post_exposure_weight
            accum[key]["wfh_share_post_weight_denom"] += post_exposure_denom
            accum[key]["sample_size"] += float(len(group))
            accum[key]["public_wfh_cov_weight"] += (
                weight * group["employed"] * pd.to_numeric(group["has_public_wfh_coverage"], errors="coerce").fillna(0)
            ).sum()
            accum[key]["public_wfh_cov_denom"] += employed_weight

    rows = []
    for (state_fips, year), values in sorted(accum.items()):
        employed_weight = values["employed_weight_sum"]
        adult_weight = values["adult_weight_sum"]
        female_adult_weight = values["female_adult_weight_sum"]
        row = {
            "state_fips": state_fips,
            "year": year,
            "remote_work_share_state_year": (
                values["actual_wfh_weight_sum"] / values["actual_wfh_obs_weight_sum"]
                if values["actual_wfh_obs_weight_sum"] > 0
                else np.nan
            ),
            "observed_remote_work_share_cps": (
                values["actual_wfh_weight_sum"] / values["actual_wfh_obs_weight_sum"]
                if values["actual_wfh_obs_weight_sum"] > 0
                else np.nan
            ),
            "mean_commute_minutes_state_year": np.nan,
            "long_commute_share_state_year": np.nan,
            "labor_force_participation_rate": np.nan,
            "female_employment_rate": np.nan,
            "married_or_partnered_share_state_year": np.nan,
            "labor_force_participation_rate_partnered_sample": (
                values["labor_force_weight_sum"] / adult_weight if adult_weight > 0 else np.nan
            ),
            "female_employment_rate_partnered_sample": (
                values["female_employed_weight_sum"] / female_adult_weight if female_adult_weight > 0 else np.nan
            ),
            "married_or_partnered_share_partnered_sample": (
                values["partnered_weight_sum"] / adult_weight if adult_weight > 0 else np.nan
            ),
            "telework_hours_mean_among_remote": (
                values["telework_hours_weighted_sum"] / values["telework_hours_weight_denom"]
                if values["telework_hours_weight_denom"] > 0
                else np.nan
            ),
            "wfh_share_2019_occ_mix": (
                values["wfh_share_2019_weighted_sum"] / values["wfh_share_2019_weight_denom"]
                if values["wfh_share_2019_weight_denom"] > 0
                else np.nan
            ),
            "wfh_share_post_2023_2024_occ_mix": (
                values["wfh_share_post_weighted_sum"] / values["wfh_share_post_weight_denom"]
                if values["wfh_share_post_weight_denom"] > 0
                else np.nan
            ),
            "has_public_wfh_coverage_share": (
                values["public_wfh_cov_weight"] / values["public_wfh_cov_denom"]
                if values["public_wfh_cov_denom"] > 0
                else np.nan
            ),
            "sample_size": int(values["sample_size"]),
            "source_used": "Local CPS WFH extract",
            "source_warning": "Used as a fallback remote-work panel where ACS coverage is unavailable. The CPS WFH file is a married-sample analytic extract, not a population-representative all-adults panel.",
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    return out


def build_hansen_remote_postings_yearly(workbook_path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(workbook_path, sheet_name="country_by_month")
    df = df[df["Country"] == "USA"].copy()
    df["year"] = pd.to_numeric(df["Year"], errors="coerce").astype(int)
    df["remote_posting_share_monthly"] = pd.to_numeric(df["Percent"], errors="coerce") / 100.0
    df["remote_posting_share_3ma"] = pd.to_numeric(df["Percent_3MA"], errors="coerce") / 100.0
    yearly = (
        df.groupby("year", as_index=False)[["remote_posting_share_monthly", "remote_posting_share_3ma"]]
        .mean(numeric_only=True)
        .rename(columns={"remote_posting_share_3ma": "remote_posting_share_year"})
    )
    return yearly


def merge_hansen_with_cps_state_panel(cps_panel: pd.DataFrame, hansen_yearly: pd.DataFrame) -> pd.DataFrame:
    out = cps_panel.merge(hansen_yearly[["year", "remote_posting_share_year"]], on="year", how="left")
    national_exposure_mean = out.groupby("year")["wfh_share_2019_occ_mix"].transform("mean")
    out["remote_posting_proxy_state_year"] = (
        out["remote_posting_share_year"] * out["wfh_share_2019_occ_mix"] / national_exposure_mean
    )
    out["remote_posting_proxy_state_year"] = out["remote_posting_proxy_state_year"].where(
        national_exposure_mean.notna(), np.nan
    )
    out["remote_work_share_state_year"] = out["remote_work_share_state_year"].fillna(out["remote_posting_proxy_state_year"])
    out["proxy_mode"] = np.where(
        out["observed_remote_work_share_cps"].notna(),
        "observed_cps",
        np.where(out["remote_posting_proxy_state_year"].notna(), "hansen_scaled_proxy", "missing"),
    )
    return out
