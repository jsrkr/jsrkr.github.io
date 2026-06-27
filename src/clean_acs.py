from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from .config import ACS_2020_WARNING, AGE_GROUPS, STATE_FIPS_TO_REGION
from .data_download import validate_columns


COMMUTE_BINS = {
    "lt_5": 2.5,
    "5_9": 7.0,
    "10_14": 12.0,
    "15_19": 17.0,
    "20_24": 22.0,
    "25_29": 27.0,
    "30_34": 32.0,
    "35_39": 37.0,
    "40_44": 42.0,
    "45_59": 52.0,
    "60_89": 74.5,
    "90_plus": 95.0,
}


def _normalize_state_year(df: pd.DataFrame, state_col: str = "state_fips", year_col: str = "year") -> pd.DataFrame:
    out = df.copy()
    out[state_col] = out[state_col].astype(str).str.zfill(2)
    out[year_col] = out[year_col].astype(int)
    out["region"] = out[state_col].map(STATE_FIPS_TO_REGION)
    out["acs_warning"] = np.where(out[year_col] == 2020, ACS_2020_WARNING, "")
    return out


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = ~(pd.isna(values) | pd.isna(weights))
    if not mask.any():
        return np.nan
    values = pd.to_numeric(values[mask], errors="coerce")
    weights = pd.to_numeric(weights[mask], errors="coerce")
    valid = ~(pd.isna(values) | pd.isna(weights))
    if not valid.any() or weights[valid].sum() == 0:
        return np.nan
    return float(np.average(values[valid], weights=weights[valid]))


def _weighted_share(condition: pd.Series, weights: pd.Series) -> float:
    condition_numeric = pd.Series(np.where(condition, 1.0, 0.0), index=condition.index)
    return _weighted_mean(condition_numeric, weights)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator is None or pd.isna(denominator) or float(denominator) == 0.0:
        return np.nan
    if numerator is None or pd.isna(numerator):
        return np.nan
    return float(numerator) / float(denominator)


def _weighted_distribution(group: pd.DataFrame, category_col: str, weight_col: str) -> dict[str, float]:
    if category_col not in group.columns:
        return {}
    subset = group[[category_col, weight_col]].dropna()
    if subset.empty:
        return {}
    total_weight = subset[weight_col].sum()
    if total_weight == 0:
        return {}
    shares = (
        subset.groupby(category_col, dropna=False)[weight_col]
        .sum()
        .div(total_weight)
        .to_dict()
    )
    return {str(key): float(value) for key, value in shares.items()}


def summarize_acs_year_coverage(df: pd.DataFrame) -> dict[str, int | bool]:
    validate_columns(df, ["YEAR"], "ACS/IPUMS microdata")
    years = pd.to_numeric(df["YEAR"], errors="coerce").dropna().astype(int)
    if years.empty:
        return {"min_year": -1, "max_year": -1, "n_years": 0, "has_modern_years": False}
    return {
        "min_year": int(years.min()),
        "max_year": int(years.max()),
        "n_years": int(years.nunique()),
        "has_modern_years": bool((years >= 2010).any()),
    }


def validate_modern_acs_years(df: pd.DataFrame, min_year: int = 2010) -> None:
    summary = summarize_acs_year_coverage(df)
    if summary["max_year"] < min_year:
        raise ValueError(
            f"ACS/IPUMS extract does not contain the modern dashboard period. "
            f"Found years {summary['min_year']} to {summary['max_year']}, expected at least {min_year}+."
        )


def restrict_to_dashboard_acs_window(
    df: pd.DataFrame,
    start_year: int = 2014,
    end_year: int = 2024,
    source_label: str = "IPUMS ACS microdata",
) -> pd.DataFrame:
    if df.empty or "year" not in df.columns:
        return df.copy()

    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out = out.loc[out["year"].between(start_year, end_year, inclusive="both")].copy()

    if "source_used" in out.columns:
        acs_rows = out["source_used"].astype(str).eq(source_label)
        if acs_rows.any():
            out = out.loc[acs_rows].copy()

    out["year"] = out["year"].astype(int)
    return out.sort_values(["state_fips", "year"]).reset_index(drop=True)


def clean_acs_api_wfh_commute(
    wfh_df: pd.DataFrame,
    commute_df: pd.DataFrame,
    digital_access_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    validate_columns(wfh_df, ["year", "state", "B08006_001E", "B08006_017E"], "ACS WFH table")
    validate_columns(
        commute_df,
        ["year", "state", "B08303_001E", "B08303_013E", "B08303_014E"],
        "ACS commute table",
    )

    wfh = wfh_df.rename(columns={"state": "state_fips"}).copy()
    for col in ["B08006_001E", "B08006_017E"]:
        wfh[col] = pd.to_numeric(wfh[col], errors="coerce")
    wfh["remote_work_share_state_year"] = wfh["B08006_017E"] / wfh["B08006_001E"]

    commute = commute_df.rename(columns={"state": "state_fips"}).copy()
    commute_numeric_cols = [col for col in commute.columns if col.startswith("B08303_") and col.endswith("E")]
    for col in commute_numeric_cols:
        commute[col] = pd.to_numeric(commute[col], errors="coerce")

    detailed_bin_map = {
        "B08303_002E": COMMUTE_BINS["lt_5"],
        "B08303_003E": COMMUTE_BINS["5_9"],
        "B08303_004E": COMMUTE_BINS["10_14"],
        "B08303_005E": COMMUTE_BINS["15_19"],
        "B08303_006E": COMMUTE_BINS["20_24"],
        "B08303_007E": COMMUTE_BINS["25_29"],
        "B08303_008E": COMMUTE_BINS["30_34"],
        "B08303_009E": COMMUTE_BINS["35_39"],
        "B08303_010E": COMMUTE_BINS["40_44"],
        "B08303_011E": COMMUTE_BINS["45_59"],
        "B08303_013E": COMMUTE_BINS["60_89"],
        "B08303_014E": COMMUTE_BINS["90_plus"],
    }

    weighted_sum = sum(commute[column] * midpoint for column, midpoint in detailed_bin_map.items() if column in commute.columns)
    commute["mean_commute_minutes_state_year"] = weighted_sum / commute["B08303_001E"]
    commute["long_commute_share_state_year"] = (
        commute[["B08303_013E", "B08303_014E"]].sum(axis=1) / commute["B08303_001E"]
    )

    merged = wfh[["year", "state_fips", "remote_work_share_state_year"]].merge(
        commute[["year", "state_fips", "mean_commute_minutes_state_year", "long_commute_share_state_year"]],
        on=["year", "state_fips"],
        how="outer",
    )

    if digital_access_df is not None:
        access = clean_acs_digital_access(digital_access_df)
        merged = merged.merge(access, on=["year", "state_fips"], how="left")

    return _normalize_state_year(merged)


def clean_acs_digital_access(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, ["year", "state_fips"], "ACS digital access")
    out = df.copy()
    rename_candidates = {
        "broadband_subscription_rate": "broadband_subscription_rate",
        "smartphone_or_computer_access_rate": "smartphone_or_computer_access_rate",
        "no_internet_rate": "no_internet_rate",
    }
    for column in rename_candidates:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if {"broadband_subscription_rate", "smartphone_or_computer_access_rate", "no_internet_rate"}.issubset(out.columns):
        out["digital_access_index"] = (
            out["broadband_subscription_rate"]
            + out["smartphone_or_computer_access_rate"]
            + (1.0 - out["no_internet_rate"])
        ) / 3.0
    return _normalize_state_year(out)


def age_group_from_age(age: int) -> str | None:
    if 15 <= age <= 24:
        return "15-24"
    if 25 <= age <= 34:
        return "25-34"
    if 35 <= age <= 44:
        return "35-44"
    if 45 <= age <= 54:
        return "45-54"
    return None


def clean_ipums_acs_microdata(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = ["YEAR", "STATEFIP", "PERWT", "AGE", "SEX", "EMPSTAT", "LABFORCE"]
    validate_columns(df, required, "IPUMS ACS microdata")

    micro = df.copy()
    micro["year"] = micro["YEAR"].astype(int)
    micro["state_fips"] = micro["STATEFIP"].astype(str).str.zfill(2)
    micro["person_weight"] = pd.to_numeric(micro["PERWT"], errors="coerce").fillna(0)
    micro["sex"] = micro["SEX"].map({1: "Male", 2: "Female"}).fillna(micro["SEX"].astype(str))
    micro["age_group"] = micro["AGE"].apply(age_group_from_age)
    micro = micro[micro["age_group"].isin(AGE_GROUPS)]

    micro["is_labor_force"] = micro["LABFORCE"].isin([2]).astype(int)
    micro["is_employed"] = micro["EMPSTAT"].isin([1]).astype(int)
    micro["is_female_employed"] = ((micro["sex"] == "Female") & (micro["is_employed"] == 1)).astype(int)

    if "TRANWORK" in micro.columns:
        micro["works_from_home"] = micro["TRANWORK"].isin([80]).astype(int)
    else:
        micro["works_from_home"] = np.nan

    if "TRANTIME" in micro.columns:
        micro["commute_minutes"] = pd.to_numeric(micro["TRANTIME"], errors="coerce")
        micro["is_long_commute"] = (micro["commute_minutes"] >= 60).astype(float)
    else:
        micro["commute_minutes"] = np.nan
        micro["is_long_commute"] = np.nan

    if "MARST" in micro.columns:
        micro["is_married_or_partnered"] = micro["MARST"].isin([1, 2]).astype(int)
    else:
        micro["is_married_or_partnered"] = np.nan

    if "FERTYR" in micro.columns:
        micro["fertility_past_year"] = micro["FERTYR"].eq(2).astype(float)
    else:
        micro["fertility_past_year"] = np.nan

    def _weighted_mean(group: pd.DataFrame, value_col: str) -> float:
        subset = group[[value_col, "person_weight"]].dropna()
        if subset.empty or subset["person_weight"].sum() == 0:
            return np.nan
        return np.average(subset[value_col], weights=subset["person_weight"])

    state_year = (
        micro.groupby(["state_fips", "year"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "remote_work_share_state_year": _weighted_mean(g, "works_from_home"),
                    "mean_commute_minutes_state_year": _weighted_mean(g, "commute_minutes"),
                    "long_commute_share_state_year": _weighted_mean(g, "is_long_commute"),
                    "married_or_partnered_share_state_year": _weighted_mean(g, "is_married_or_partnered"),
                    "fertility_past_year_share_state_year": _weighted_mean(g, "fertility_past_year"),
                    "sample_size": len(g),
                }
            )
        )
        .reset_index()
    )

    demographic_panel = (
        micro.groupby(["state_fips", "year", "sex", "age_group"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "labor_force_participation_rate": _weighted_mean(g, "is_labor_force"),
                    "employment_rate": _weighted_mean(g, "is_employed"),
                    "female_employment_rate": _weighted_mean(g, "is_female_employed"),
                    "sample_size": len(g),
                }
            )
        )
        .reset_index()
    )

    return _normalize_state_year(state_year), _normalize_state_year(demographic_panel)


def build_weighted_acs_state_year_panel(df: pd.DataFrame, min_year: int = 2010) -> pd.DataFrame:
    required = ["YEAR", "STATEFIP", "PERWT", "AGE", "SEX", "EMPSTAT", "LABFORCE"]
    validate_columns(df, required, "IPUMS ACS microdata")
    validate_modern_acs_years(df, min_year=min_year)

    micro = df.copy()
    micro["year"] = pd.to_numeric(micro["YEAR"], errors="coerce").astype(int)
    micro["state_fips"] = micro["STATEFIP"].astype(str).str.zfill(2)
    micro["person_weight"] = pd.to_numeric(micro["PERWT"], errors="coerce").fillna(0.0)
    micro["age"] = pd.to_numeric(micro["AGE"], errors="coerce")
    micro["sex"] = pd.to_numeric(micro["SEX"], errors="coerce")
    micro["is_female"] = micro["sex"].eq(2)
    micro["is_adult_18_64"] = micro["age"].between(18, 64, inclusive="both")
    micro["is_female_15_44"] = micro["is_female"] & micro["age"].between(15, 44, inclusive="both")
    micro["is_employed"] = pd.to_numeric(micro["EMPSTAT"], errors="coerce").isin([1])
    micro["is_labor_force"] = pd.to_numeric(micro["LABFORCE"], errors="coerce").isin([2])

    if "TRANWORK" in micro.columns:
        micro["works_from_home"] = pd.to_numeric(micro["TRANWORK"], errors="coerce").isin([80])
    else:
        micro["works_from_home"] = False
    micro["works_on_site"] = micro["is_employed"] & ~micro["works_from_home"]

    if "TRANTIME" in micro.columns:
        micro["commute_minutes"] = pd.to_numeric(micro["TRANTIME"], errors="coerce")
        micro["is_long_commute"] = micro["commute_minutes"] >= 45
    else:
        micro["commute_minutes"] = np.nan
        micro["is_long_commute"] = False

    if "HRSWORK1" in micro.columns:
        micro["usual_hours_worked"] = pd.to_numeric(micro["HRSWORK1"], errors="coerce")
        micro["usual_hours_worked"] = micro["usual_hours_worked"].where(micro["usual_hours_worked"].between(1, 99))
    else:
        micro["usual_hours_worked"] = np.nan
    micro["remote_work_hours_proxy_component"] = np.where(
        micro["works_from_home"],
        micro["usual_hours_worked"],
        0.0,
    )

    if "MARST" in micro.columns:
        micro["is_married_or_partnered"] = pd.to_numeric(micro["MARST"], errors="coerce").isin([1, 2])
    else:
        micro["is_married_or_partnered"] = False

    if "EDUC" in micro.columns:
        educ = pd.to_numeric(micro["EDUC"], errors="coerce")
        micro["education_group"] = np.select(
            [
                educ.le(5),
                educ.between(6, 8, inclusive="both"),
                educ.between(9, 10, inclusive="both"),
                educ.ge(11),
            ],
            [
                "less_than_high_school",
                "high_school",
                "some_college",
                "bachelors_plus",
            ],
            default="unknown",
        )
    else:
        micro["education_group"] = "unknown"

    micro["age_group"] = micro["age"].apply(age_group_from_age).fillna("other")

    rows: list[dict[str, object]] = []
    for (state_fips, year), group in micro.groupby(["state_fips", "year"], dropna=False):
        employed = group[group["is_employed"]].copy()
        commuters = employed[employed["works_on_site"]].copy()
        women_15_44 = group[group["is_female_15_44"]].copy()
        adult_18_64 = group[group["is_adult_18_64"]].copy()

        state_row: dict[str, object] = {
            "state_fips": state_fips,
            "year": int(year),
            "remote_work_share_state_year": _weighted_share(employed["works_from_home"], employed["person_weight"]) if not employed.empty else np.nan,
            "on_site_work_share_state_year": _weighted_share(employed["works_on_site"], employed["person_weight"]) if not employed.empty else np.nan,
            "usual_hours_all_workers": _weighted_mean(employed["usual_hours_worked"], employed["person_weight"]) if not employed.empty else np.nan,
            "usual_hours_wfh_workers": _weighted_mean(
                employed.loc[employed["works_from_home"], "usual_hours_worked"],
                employed.loc[employed["works_from_home"], "person_weight"],
            ) if not employed.empty else np.nan,
            "remote_work_hours_proxy": _weighted_mean(
                employed["remote_work_hours_proxy_component"],
                employed["person_weight"],
            ) if not employed.empty else np.nan,
            "mean_commute_minutes_state_year": _weighted_mean(commuters["commute_minutes"], commuters["person_weight"]) if not commuters.empty else np.nan,
            "long_commute_share_state_year": _weighted_share(commuters["is_long_commute"], commuters["person_weight"]) if not commuters.empty else np.nan,
            "female_employment_rate": _weighted_share(women_15_44["is_employed"], women_15_44["person_weight"]) if not women_15_44.empty else np.nan,
            "labor_force_participation_rate": _weighted_share(adult_18_64["is_labor_force"], adult_18_64["person_weight"]) if not adult_18_64.empty else np.nan,
            "married_or_partnered_share_state_year": _weighted_share(adult_18_64["is_married_or_partnered"], adult_18_64["person_weight"]) if not adult_18_64.empty else np.nan,
            "sample_size": int(len(group)),
            "source_used": "IPUMS ACS microdata",
            "remote_work_measure_note": "Remote work is identified from commute mode indicating work from home; usual hours proxy converts this into remote-work hours.",
            "commute_measure_note": "Commute estimates are weighted among on-site employed workers with valid travel-time responses.",
            "age_group_distribution": _weighted_distribution(adult_18_64, "age_group", "person_weight"),
            "education_distribution": _weighted_distribution(adult_18_64, "education_group", "person_weight"),
        }
        rows.append(state_row)

    return _normalize_state_year(pd.DataFrame(rows))


def build_weighted_acs_state_year_panel_from_dta(
    dta_path: str | Path,
    min_year: int = 2010,
    chunk_rows: int = 250000,
) -> pd.DataFrame:
    path = Path(dta_path)
    if not path.exists():
        raise FileNotFoundError(f"ACS file not found: {path}")

    _, meta = pyreadstat.read_dta(path, metadataonly=True)
    total_rows = meta.number_rows
    available_columns = {column.lower() for column in meta.column_names}
    requested_usecols = [
        "year",
        "statefip",
        "perwt",
        "age",
        "sex",
        "empstat",
        "labforce",
        "marst",
        "educ",
        "tranwork",
        "trantime",
        "hrswork1",
    ]
    usecols = [column for column in requested_usecols if column.lower() in available_columns]

    accum: dict[tuple[str, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    years_seen: set[int] = set()

    for offset in range(0, total_rows, chunk_rows):
        chunk, _ = pyreadstat.read_dta(
            path,
            usecols=usecols,
            row_offset=offset,
            row_limit=min(chunk_rows, total_rows - offset),
        )
        if chunk.empty:
            continue

        chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
        chunk = chunk[chunk["year"].ge(min_year)].copy()
        if chunk.empty:
            continue

        years_seen.update(chunk["year"].dropna().astype(int).unique().tolist())
        chunk["state_fips"] = pd.to_numeric(chunk["statefip"], errors="coerce").astype("Int64").astype(str).str.zfill(2)
        chunk["weight"] = pd.to_numeric(chunk["perwt"], errors="coerce").fillna(0.0)
        chunk["age"] = pd.to_numeric(chunk["age"], errors="coerce")
        chunk["is_female"] = pd.to_numeric(chunk["sex"], errors="coerce").eq(2)
        chunk["is_female_15_44"] = chunk["is_female"] & chunk["age"].between(15, 44, inclusive="both")
        chunk["is_adult_18_64"] = chunk["age"].between(18, 64, inclusive="both")
        chunk["is_employed"] = pd.to_numeric(chunk["empstat"], errors="coerce").isin([1])
        chunk["is_labor_force"] = pd.to_numeric(chunk["labforce"], errors="coerce").isin([2])
        chunk["works_from_home"] = pd.to_numeric(chunk["tranwork"], errors="coerce").eq(80)
        chunk["works_on_site"] = chunk["is_employed"] & ~chunk["works_from_home"]
        if "trantime" in chunk.columns:
            chunk["commute_minutes"] = pd.to_numeric(chunk["trantime"], errors="coerce")
            chunk["is_long_commute"] = chunk["commute_minutes"].ge(45)
        else:
            chunk["commute_minutes"] = np.nan
            chunk["is_long_commute"] = False
        chunk["usual_hours"] = pd.to_numeric(chunk["hrswork1"], errors="coerce").where(lambda s: s.between(1, 99))
        chunk["remote_work_hours_proxy_component"] = np.where(chunk["works_from_home"], chunk["usual_hours"], 0.0)
        if "marst" in chunk.columns:
            chunk["is_married_or_partnered"] = pd.to_numeric(chunk["marst"], errors="coerce").isin([1, 2])
        else:
            chunk["is_married_or_partnered"] = False

        for (state_fips, year), group in chunk.groupby(["state_fips", "year"], dropna=True):
            key = (state_fips, int(year))
            weight = group["weight"]
            employed = group["is_employed"]
            on_site = group["works_on_site"]
            women_15_44 = group["is_female_15_44"]
            adult = group["is_adult_18_64"]

            accum[key]["sample_size"] += float(len(group))
            accum[key]["weight_sum"] += weight.sum()

            employed_weight = (weight * employed).sum()
            accum[key]["employed_weight"] += employed_weight
            accum[key]["remote_work_weight"] += (weight * employed * group["works_from_home"]).sum()
            accum[key]["onsite_work_weight"] += (weight * employed * on_site).sum()

            hours_valid = group["usual_hours"].notna().astype(float)
            accum[key]["hours_weight_sum"] += (weight * employed * group["usual_hours"].fillna(0)).sum()
            accum[key]["hours_weight_denom"] += (weight * employed * hours_valid).sum()
            accum[key]["remote_hours_weight_sum"] += (weight * employed * group["remote_work_hours_proxy_component"]).sum()

            remote_subset = employed & group["works_from_home"] & group["usual_hours"].notna()
            accum[key]["wfh_hours_sum"] += (weight * remote_subset * group["usual_hours"].fillna(0)).sum()
            accum[key]["wfh_hours_denom"] += (weight * remote_subset).sum()

            commuter_subset = employed & on_site & group["commute_minutes"].notna()
            accum[key]["commute_sum"] += (weight * commuter_subset * group["commute_minutes"].fillna(0)).sum()
            accum[key]["commute_denom"] += (weight * commuter_subset).sum()
            accum[key]["long_commute_weight"] += (weight * employed * on_site * group["is_long_commute"]).sum()
            accum[key]["long_commute_denom"] += (weight * employed * on_site).sum()

            female_subset = women_15_44
            accum[key]["female_weight"] += (weight * female_subset).sum()
            accum[key]["female_employed_weight"] += (weight * female_subset * employed).sum()

            adult_subset = adult
            accum[key]["adult_weight"] += (weight * adult_subset).sum()
            accum[key]["adult_labor_force_weight"] += (weight * adult_subset * group["is_labor_force"]).sum()
            accum[key]["adult_partnered_weight"] += (weight * adult_subset * group["is_married_or_partnered"]).sum()

    if not years_seen:
        raise ValueError(
            f"ACS/IPUMS extract at {path} does not contain any records for years >= {min_year}."
        )

    rows = []
    for (state_fips, year), values in sorted(accum.items()):
        rows.append(
            {
                "state_fips": state_fips,
                "year": year,
                "remote_work_share_state_year": _safe_ratio(values["remote_work_weight"], values["employed_weight"]),
                "observed_remote_work_share_acs": _safe_ratio(values["remote_work_weight"], values["employed_weight"]),
                "on_site_work_share_state_year": _safe_ratio(values["onsite_work_weight"], values["employed_weight"]),
                "usual_hours_all_workers": _safe_ratio(values["hours_weight_sum"], values["hours_weight_denom"]),
                "usual_hours_wfh_workers": _safe_ratio(values["wfh_hours_sum"], values["wfh_hours_denom"]),
                "telework_hours_mean_among_remote": _safe_ratio(values["wfh_hours_sum"], values["wfh_hours_denom"]),
                "remote_work_hours_proxy": _safe_ratio(values["remote_hours_weight_sum"], values["employed_weight"]),
                "mean_commute_minutes_state_year": _safe_ratio(values["commute_sum"], values["commute_denom"]),
                "long_commute_share_state_year": _safe_ratio(values["long_commute_weight"], values["long_commute_denom"]),
                "female_employment_rate": _safe_ratio(values["female_employed_weight"], values["female_weight"]),
                "labor_force_participation_rate": _safe_ratio(values["adult_labor_force_weight"], values["adult_weight"]),
                "married_or_partnered_share_state_year": _safe_ratio(values["adult_partnered_weight"], values["adult_weight"]),
                "sample_size": int(values["sample_size"]),
                "source_used": "IPUMS ACS microdata",
                "source_warning": "State-year ACS estimates are directly weighted from the local IPUMS extract for years present in the file.",
                "measurement_note": "Remote work is identified from ACS commute mode indicating work from home; commute and work-hour measures are weighted among relevant employed respondents.",
                "proxy_mode": "observed_acs",
                "region": STATE_FIPS_TO_REGION.get(state_fips),
                "acs_warning": ACS_2020_WARNING if int(year) == 2020 else "",
            }
        )

    return pd.DataFrame(rows)
