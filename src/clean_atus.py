from __future__ import annotations

from pathlib import Path

import math
import numpy as np
import pandas as pd

from .config import ATUS_SMALL_STATE_WARNING, MIN_ATUS_STATE_SAMPLE, STATE_FIPS_TO_REGION
from .data_download import validate_columns


SOCIAL_ACTIVITY_PREFIXES = ("1201", "1202")
DIGITAL_MEDIA_NARROW_CODES = {"120308"}
SCREEN_LEISURE_BROAD_CODES = {"120303", "120307", "120308"}
WORK_PREFIX = "05"
COMMUTING_PREFIXES = ("1805",)
HOUSEHOLD_WORK_TIER1_CODES = {"02"}
UNPAID_CARE_TIER1_CODES = {"03", "04"}
WORK_AT_HOME_WHERE_CODES = {1}
OUT_OF_HOME_WHERE_CODES = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 30, 31, 32, 89, 99}


def _starts_with_any(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value.startswith(prefix) for prefix in prefixes)


def classify_atus_activity(activity_code: str, tier1_code: str | None = None) -> dict[str, int]:
    code = str(activity_code)
    tier1 = str(tier1_code).zfill(2) if tier1_code is not None and not pd.isna(tier1_code) else code[:2]
    return {
        "is_socializing": int(_starts_with_any(code, SOCIAL_ACTIVITY_PREFIXES)),
        "is_digital_media_narrow": int(code in DIGITAL_MEDIA_NARROW_CODES),
        "is_screen_leisure_broad": int(code in SCREEN_LEISURE_BROAD_CODES),
        "is_work": int(code.startswith(WORK_PREFIX)),
        "is_commuting": int(_starts_with_any(code, COMMUTING_PREFIXES)),
        "is_household_work": int(tier1 in HOUSEHOLD_WORK_TIER1_CODES),
        "is_unpaid_care": int(tier1 in UNPAID_CARE_TIER1_CODES),
    }


def _weighted_mean_and_ci(values: pd.Series, weights: pd.Series) -> tuple[float, float, float, float]:
    mask = ~(values.isna() | weights.isna())
    values = values[mask]
    weights = weights[mask]
    if values.empty or weights.sum() == 0:
        return (math.nan, math.nan, math.nan, math.nan)

    mean_value = np.average(values, weights=weights)
    normalized = weights / weights.sum()
    effective_n = 1.0 / np.square(normalized).sum()
    variance = np.average((values - mean_value) ** 2, weights=weights)
    standard_error = math.sqrt(variance / max(effective_n, 1.0))
    margin = 1.96 * standard_error
    return mean_value, standard_error, mean_value - margin, mean_value + margin


def _age_group(age: float) -> str | None:
    if pd.isna(age):
        return None
    age = int(age)
    if 15 <= age <= 24:
        return "15-24"
    if 25 <= age <= 34:
        return "25-34"
    if 35 <= age <= 44:
        return "35-44"
    if 45 <= age <= 54:
        return "45-54"
    return None


def _education_group(peeduca: float) -> str | None:
    if pd.isna(peeduca):
        return None
    code = int(peeduca)
    if code <= 38:
        return "Less than high school"
    if code in {39, 40}:
        return "High school"
    if 41 <= code <= 42:
        return "Some college"
    if code >= 43:
        return "Bachelor's or higher"
    return None


def _marital_group(code: float) -> str | None:
    if pd.isna(code):
        return None
    code = int(code)
    if code in {1, 2}:
        return "Married"
    if code == 6:
        return "Never married"
    if code in {3, 4, 5}:
        return "Previously married"
    return None


def clean_atus_microdata(df: pd.DataFrame, min_state_sample: int = MIN_ATUS_STATE_SAMPLE) -> pd.DataFrame:
    required = ["year", "wt06", "activity_code", "duration_minutes"]
    validate_columns(df, required, "ATUS activity data")
    out = df.copy()
    out["year"] = out["year"].astype(int)
    out["weight"] = pd.to_numeric(out["wt06"], errors="coerce").fillna(0)
    out["duration_minutes"] = pd.to_numeric(out["duration_minutes"], errors="coerce").fillna(0)
    out["state_fips"] = out.get("state_fips", pd.Series(["00"] * len(out))).astype(str).str.zfill(2)
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION).fillna(out.get("region", "National"))

    tier1 = out.get("tier1_code")
    classifications = [
        classify_atus_activity(activity_code, tier1_code)
        for activity_code, tier1_code in zip(out["activity_code"], tier1 if tier1 is not None else [None] * len(out))
    ]
    classifications = pd.DataFrame(classifications, index=out.index)
    out = pd.concat([out, classifications], axis=1)
    out["digital_media_minutes_narrow"] = out["duration_minutes"] * out["is_digital_media_narrow"]
    out["screen_leisure_minutes_broad"] = out["duration_minutes"] * out["is_screen_leisure_broad"]
    out["digital_distraction_minutes"] = out["screen_leisure_minutes_broad"]
    out["in_person_social_minutes"] = out["duration_minutes"] * out["is_socializing"]
    out["face_to_face_social_minutes"] = out["in_person_social_minutes"]
    out["commuting_minutes"] = out["duration_minutes"] * out["is_commuting"]
    out["household_work_minutes"] = out["duration_minutes"] * out["is_household_work"]
    out["unpaid_care_minutes"] = out["duration_minutes"] * out["is_unpaid_care"]
    out["care_burden_minutes"] = out["household_work_minutes"] + out["unpaid_care_minutes"]

    if "where_code" in out.columns:
        where = pd.to_numeric(out["where_code"], errors="coerce")
        out["work_at_home_minutes"] = out["duration_minutes"] * (out["is_work"] & where.isin(WORK_AT_HOME_WHERE_CODES))
        out["work_away_minutes"] = out["duration_minutes"] * (out["is_work"] & where.isin(OUT_OF_HOME_WHERE_CODES))
        out["away_from_home_minutes"] = out["duration_minutes"] * where.isin(OUT_OF_HOME_WHERE_CODES)
    else:
        out["work_at_home_minutes"] = np.nan
        out["work_away_minutes"] = np.nan
        out["away_from_home_minutes"] = np.nan

    group_cols = ["year", "region"]
    rows: list[dict] = []
    for keys, group in out.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["sample_size"] = int(group.shape[0])
        row["respondent_count_unweighted"] = int(group.shape[0])
        for metric in [
            "digital_media_minutes_narrow",
            "screen_leisure_minutes_broad",
            "digital_distraction_minutes",
            "in_person_social_minutes",
            "face_to_face_social_minutes",
            "commuting_minutes",
            "work_at_home_minutes",
            "work_away_minutes",
            "away_from_home_minutes",
            "household_work_minutes",
            "unpaid_care_minutes",
            "care_burden_minutes",
        ]:
            mean_value, standard_error, ci_low, ci_high = _weighted_mean_and_ci(group[metric], group["weight"])
            row[metric] = mean_value
            row[f"{metric}_se"] = standard_error
            row[f"{metric}_ci_low"] = ci_low
            row[f"{metric}_ci_high"] = ci_high
        rows.append(row)
    return pd.DataFrame(rows)


def pool_small_state_estimates(df: pd.DataFrame, window: int = 3, min_state_sample: int = MIN_ATUS_STATE_SAMPLE) -> pd.DataFrame:
    if df.empty or "state_fips" not in df.columns:
        return df
    pooled = df.sort_values(["state_fips", "year"]).copy()
    metrics = [
        "digital_media_minutes_narrow",
        "screen_leisure_minutes_broad",
        "digital_distraction_minutes",
        "face_to_face_social_minutes",
        "commuting_minutes",
        "time_alone_minutes",
        "time_with_spouse_only_minutes",
        "time_with_friends_minutes",
        "time_with_nonhousehold_minutes",
        "work_at_home_minutes",
        "work_away_minutes",
        "away_from_home_minutes",
        "household_work_minutes",
        "unpaid_care_minutes",
        "care_burden_minutes",
        "in_person_social_minutes",
    ]
    for metric in metrics:
        if metric not in pooled.columns:
            continue
        pooled[f"{metric}_pooled"] = (
            pooled.groupby("state_fips")[metric]
            .transform(lambda series: series.rolling(window=window, min_periods=1, center=True).mean())
        )
    pooled["is_pooled_estimate"] = pooled["sample_size"] < min_state_sample
    return pooled


def _find_atus_component(year_root: Path, component: str, year: int) -> Path | None:
    candidates = [
        year_root / f"{component}_{year}" / f"{component}_{year}" / f"{component}_{year}.dat",
        year_root / f"{component}-{year}" / f"{component}-{year}" / f"{component}-{year}.dat",
        year_root / f"{component}_{year}" / f"{component}_{year}.dat",
        year_root / f"{component}-{year}" / f"{component}-{year}.dat",
        year_root / f"{component}-{year}" / f"{component}_{year}.dat",
        year_root / f"{component}_{year}" / f"{component}-{year}.dat",
    ]
    for path in candidates:
        if path.exists():
            return path

    glob_patterns = [
        f"{component}_{year}.dat",
        f"{component}-{year}.dat",
        f"{component}*{year}.dat",
    ]
    for pattern in glob_patterns:
        matches = sorted(year_root.rglob(pattern))
        if matches:
            return matches[0]
    return None


def read_atus_raw_component(base_dir: str | Path, year: int, component: str, usecols: list[str] | None = None) -> pd.DataFrame | None:
    year_root = Path(base_dir) / str(year)
    data_path = _find_atus_component(year_root, component, year)
    if data_path is None:
        return None
    available_usecols = usecols
    if usecols is not None:
        with data_path.open("r", encoding="utf-8", errors="ignore") as handle:
            header = handle.readline().strip().split(",")
        available_usecols = [column for column in usecols if column in header]
    df = pd.read_csv(data_path, usecols=available_usecols, low_memory=False)
    df.columns = [column.lower() for column in df.columns]
    return df


def build_atus_respondent_day(base_dir: str | Path, year: int) -> pd.DataFrame:
    activity = read_atus_raw_component(
        base_dir,
        year,
        "atusact",
        usecols=["TUCASEID", "TEWHERE", "TRCODE", "TUACTDUR24", "TUTIER1CODE"],
    )
    respondent = read_atus_raw_component(
        base_dir,
        year,
        "atusresp",
        usecols=[
            "TUCASEID",
            "TULINENO",
            "TUYEAR",
            "TUMONTH",
            "TUFINLWGT",
            "TU20FWGT",
            "TRTALONE",
            "TRTSPONLY",
            "TRTFRIEND",
            "TRTFAMILY",
            "TRTCHILD",
            "TRHHCHILD",
            "TRTSPOUSE",
        ],
    )
    if activity is None or respondent is None:
        raise FileNotFoundError(f"ATUS activity/respondent files were not both found for {year}.")

    cps = read_atus_raw_component(
        base_dir,
        year,
        "atuscps",
        usecols=["TUCASEID", "TULINENO", "GESTFIPS", "PESEX", "PRTAGE", "PEEDUCA", "PRMARSTA", "PTDTRACE"],
    )

    activity["trcode"] = activity["trcode"].astype(str).str.zfill(6)
    activity["tutier1code"] = activity["tutier1code"].astype(str).str.zfill(2)
    activity["tewhere"] = pd.to_numeric(activity["tewhere"], errors="coerce")
    activity["tuactdur24"] = pd.to_numeric(activity["tuactdur24"], errors="coerce").fillna(0.0)

    class_df = [
        classify_atus_activity(activity_code, tier1_code)
        for activity_code, tier1_code in zip(activity["trcode"], activity["tutier1code"])
    ]
    class_df = pd.DataFrame(class_df, index=activity.index)
    activity = pd.concat([activity, class_df], axis=1)
    activity["digital_media_minutes_narrow"] = activity["tuactdur24"] * activity["is_digital_media_narrow"]
    activity["screen_leisure_minutes_broad"] = activity["tuactdur24"] * activity["is_screen_leisure_broad"]
    activity["digital_distraction_minutes"] = activity["screen_leisure_minutes_broad"]
    activity["in_person_social_minutes"] = activity["tuactdur24"] * activity["is_socializing"]
    activity["face_to_face_social_minutes"] = activity["in_person_social_minutes"]
    activity["commuting_minutes"] = activity["tuactdur24"] * activity["is_commuting"]
    activity["household_work_minutes"] = activity["tuactdur24"] * activity["is_household_work"]
    activity["unpaid_care_minutes"] = activity["tuactdur24"] * activity["is_unpaid_care"]
    activity["care_burden_minutes"] = activity["household_work_minutes"] + activity["unpaid_care_minutes"]
    activity["work_at_home_minutes"] = activity["tuactdur24"] * (
        activity["tutier1code"].eq(WORK_PREFIX) & activity["tewhere"].isin(WORK_AT_HOME_WHERE_CODES)
    )
    activity["work_away_minutes"] = activity["tuactdur24"] * (
        activity["tutier1code"].eq(WORK_PREFIX) & activity["tewhere"].isin(OUT_OF_HOME_WHERE_CODES)
    )
    activity["away_from_home_minutes"] = activity["tuactdur24"] * activity["tewhere"].isin(OUT_OF_HOME_WHERE_CODES)

    activity_person = (
        activity.groupby("tucaseid", as_index=False)[
            [
                "digital_media_minutes_narrow",
                "screen_leisure_minutes_broad",
                "digital_distraction_minutes",
                "face_to_face_social_minutes",
                "in_person_social_minutes",
                "commuting_minutes",
                "work_at_home_minutes",
                "work_away_minutes",
                "away_from_home_minutes",
                "household_work_minutes",
                "unpaid_care_minutes",
                "care_burden_minutes",
            ]
        ]
        .sum()
    )

    respondent = respondent.rename(columns={"tufinlwgt": "weight", "tu20fwgt": "weight"}).copy()
    respondent["year"] = pd.to_numeric(respondent["tuyear"], errors="coerce").astype("Int64")
    respondent["month"] = pd.to_numeric(respondent["tumonth"], errors="coerce").astype("Int64")
    respondent["weight"] = pd.to_numeric(respondent["weight"], errors="coerce")
    for col in ["trtalone", "trtsponly", "trtfriend", "trtfamily", "trtchild", "trthhchild", "trtspouse"]:
        if col in respondent.columns:
            respondent[col] = pd.to_numeric(respondent[col], errors="coerce")

    merged = respondent.merge(activity_person, on="tucaseid", how="left")
    if cps is not None:
        cps["gestfips"] = pd.to_numeric(cps["gestfips"], errors="coerce").astype("Int64")
        cps["state_fips"] = cps["gestfips"].astype(str).str.zfill(2)
        cps["age"] = pd.to_numeric(cps["prtage"], errors="coerce")
        cps["sex"] = pd.to_numeric(cps["pesex"], errors="coerce").map({1: "Male", 2: "Female"})
        cps["age_group"] = cps["age"].apply(_age_group)
        cps["education_group"] = pd.to_numeric(cps["peeduca"], errors="coerce").apply(_education_group)
        cps["marital_status"] = pd.to_numeric(cps["prmarsta"], errors="coerce").apply(_marital_group)
        cps["region"] = cps["state_fips"].map(STATE_FIPS_TO_REGION)
        merged = merged.merge(
            cps[["tucaseid", "tulineno", "state_fips", "region", "age", "age_group", "sex", "education_group", "marital_status"]],
            on=["tucaseid", "tulineno"],
            how="left",
        )
        merged["geography_mode"] = "state_and_region_available"
    else:
        merged["state_fips"] = pd.NA
        merged["region"] = "National only"
        merged["age"] = pd.NA
        merged["age_group"] = pd.NA
        merged["sex"] = pd.NA
        merged["education_group"] = pd.NA
        merged["marital_status"] = pd.NA
        merged["geography_mode"] = "national_only_no_atuscps"

    merged = merged.rename(
        columns={
            "trtalone": "time_alone_minutes",
            "trtsponly": "time_with_spouse_only_minutes",
            "trtfriend": "time_with_friends_minutes",
            "trtfamily": "time_with_family_minutes",
            "trtchild": "time_with_children_minutes",
            "trhhchild": "presence_household_children",
            "trtspouse": "time_with_spouse_minutes",
        }
    )
    merged["digital_social_proxy_minutes"] = np.nan
    merged["digital_social_proxy_mode"] = "not_directly_observed"
    merged["time_with_nonhousehold_minutes"] = merged["time_with_friends_minutes"]
    merged["source_year"] = year
    return merged


def _aggregate_atus_groups(df: pd.DataFrame, group_cols: list[str], geography_type: str, min_state_sample: int) -> pd.DataFrame:
    rows: list[dict] = []
    metrics = [
        "digital_media_minutes_narrow",
        "screen_leisure_minutes_broad",
        "digital_distraction_minutes",
        "face_to_face_social_minutes",
        "in_person_social_minutes",
        "commuting_minutes",
        "work_at_home_minutes",
        "work_away_minutes",
        "away_from_home_minutes",
        "household_work_minutes",
        "unpaid_care_minutes",
        "care_burden_minutes",
        "time_alone_minutes",
        "time_with_spouse_only_minutes",
        "time_with_friends_minutes",
        "time_with_nonhousehold_minutes",
        "time_with_family_minutes",
        "time_with_children_minutes",
        "time_with_spouse_minutes",
        "in_person_social_minutes",
    ]
    for keys, group in df.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row["sample_size"] = int(len(group))
        row["respondent_count_unweighted"] = int(len(group))
        row["geography_type"] = geography_type
        row["quality_warning"] = ""
        if geography_type == "state" and row["sample_size"] < min_state_sample:
            row["quality_warning"] = ATUS_SMALL_STATE_WARNING
        for metric in metrics:
            if metric not in group.columns:
                continue
            mean_value, standard_error, ci_low, ci_high = _weighted_mean_and_ci(group[metric], group["weight"])
            if geography_type == "state" and row["sample_size"] < min_state_sample:
                row[metric] = np.nan
                row[f"{metric}_se"] = np.nan
                row[f"{metric}_ci_low"] = np.nan
                row[f"{metric}_ci_high"] = np.nan
            else:
                row[metric] = mean_value
                row[f"{metric}_se"] = standard_error
                row[f"{metric}_ci_low"] = ci_low
                row[f"{metric}_ci_high"] = ci_high
        row["digital_social_proxy_mode"] = "not_directly_observed"
        row["estimate_status"] = (
            "observed"
            if geography_type in {"national", "region"}
            else ("pooled_or_modeled_required" if row["sample_size"] < min_state_sample else "observed")
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_atus_aggregates_from_raw(base_dir: str | Path, years: list[int], min_state_sample: int = MIN_ATUS_STATE_SAMPLE) -> pd.DataFrame:
    respondent_days: list[pd.DataFrame] = []
    for year in years:
        respondent_days.append(build_atus_respondent_day(base_dir, year))
    micro = pd.concat(respondent_days, ignore_index=True)

    national = _aggregate_atus_groups(micro, ["year"], "national", min_state_sample)
    regional = _aggregate_atus_groups(micro[micro["region"].notna()], ["year", "region"], "region", min_state_sample)
    state_source = micro[micro["state_fips"].notna()].copy()
    state = _aggregate_atus_groups(state_source, ["year", "state_fips", "region"], "state", min_state_sample)
    state = pool_small_state_estimates(state, window=3, min_state_sample=min_state_sample)

    out = pd.concat([national, regional, state], ignore_index=True, sort=False)
    out["source_used"] = "Local ATUS raw files"
    out["estimate_mode"] = np.where(
        out["geography_type"].eq("national"),
        "direct national estimate",
        np.where(out["geography_type"].eq("region"), "direct regional estimate", "direct state estimate if sample is large enough; otherwise pooled or hidden"),
    )
    return out
