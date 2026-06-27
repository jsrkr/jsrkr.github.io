from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from .clean_acs import restrict_to_dashboard_acs_window
from .config import (
    DIGITAL_SOCIAL_WARNING,
    EXPOSURE_INDEX_COLUMNS,
    MIN_ATUS_STATE_SAMPLE,
    MODEL_REQUIRED_COLUMNS,
    PROCESSED_DATA_DIR,
    STATE_FIPS_TO_NAME,
)
from .data_download import cache_dataframe


ATUS_METRICS = [
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
]

INDEX_COMPONENTS = {
    "remote_work_exposure_index": [
        ("remote_work_share_state_year", 1.0),
        ("remote_work_time_saved_roundtrip_minutes_state_year", 1.0),
        ("work_at_home_minutes_state_year", 0.5),
        ("telework_hours_mean_among_remote", 0.5),
    ],
    "in_person_work_exposure_index": [
        ("on_site_work_share", 1.0),
        ("work_away_minutes_state_year", 0.75),
        ("commuting_minutes_state_year", 0.75),
        ("mean_commute_minutes_state_year", 0.5),
        ("long_commute_share_state_year", 0.75),
    ],
    "digital_distraction_index": [
        ("screen_leisure_minutes_broad_state_year", 1.0),
        ("digital_media_minutes_narrow_state_year", 0.75),
    ],
    "digital_social_index": [
        ("digital_social_proxy_value", 0.75),
        ("search_interest_online_dating_state_year", 1.0),
        ("internet_use_rate_state_year", 0.5),
    ],
    "in_person_social_index": [
        ("in_person_social_minutes_state_year", 1.0),
        ("face_to_face_social_minutes_state_year", 0.5),
        ("time_with_friends_minutes_state_year", 0.5),
    ],
    "digital_access_index": [
        ("digital_access_index_raw", 1.0),
        ("broadband_subscription_rate", 0.75),
        ("smartphone_or_computer_access_rate", 0.75),
        ("no_internet_rate_inverse", 0.5),
    ],
    "digital_use_prevalence_index": [
        ("internet_use_rate_state_year", 1.0),
        ("mobile_device_use_rate_state_year", 0.75),
        ("online_activity_index_state_year", 0.75),
        ("digital_access_gap_state_year_inverse", 0.5),
    ],
    "commute_burden_index": [
        ("mean_commute_minutes_state_year", 1.0),
        ("long_commute_share_state_year", 1.0),
        ("commuting_minutes_state_year", 0.75),
        ("work_away_minutes_state_year", 0.5),
    ],
    "work_family_compatibility_proxy": [
        ("remote_work_time_saved_roundtrip_minutes_state_year", 1.0),
        ("remote_work_share_state_year", 0.75),
        ("work_at_home_minutes_state_year", 0.5),
        ("care_burden_minutes_state_year_inverse", 0.5),
    ],
    "gendered_care_risk_proxy": [
        ("remote_work_share_state_year", 0.75),
        ("female_employment_rate", 0.75),
        ("care_burden_minutes_state_year", 1.0),
        ("unpaid_care_minutes_state_year", 0.75),
        ("household_work_minutes_state_year", 0.5),
    ],
}

COMMUTE_FALLBACK_NATIONAL_ANCHOR_MINUTES = 25.0
COMMUTE_QUALITY_COLUMN = "commute_minutes_quality_state_year"
COMMUTE_SOURCE_COLUMN = "commute_minutes_source_state_year"


def zscore_by_year(df: pd.DataFrame, value_col: str, year_col: str = "year") -> pd.Series:
    return df.groupby(year_col)[value_col].transform(
        lambda series: (series - series.mean()) / series.std(ddof=0) if series.std(ddof=0) else 0.0
    )


def construct_remote_work_metrics(df: pd.DataFrame, baseline_years: tuple[int, int] = (2010, 2019)) -> pd.DataFrame:
    out = df.copy()
    baseline_mask = out["year"].between(baseline_years[0], baseline_years[1])
    baseline = (
        out.loc[baseline_mask]
        .groupby("state_fips", as_index=False)["remote_work_share_state_year"]
        .mean()
        .rename(columns={"remote_work_share_state_year": "remote_work_share_baseline"})
    )
    out = out.merge(baseline, on="state_fips", how="left")
    out["remote_work_growth"] = out["remote_work_share_state_year"] - out["remote_work_share_baseline"]
    if "mean_commute_minutes_state_year" in out.columns:
        baseline_commute = (
            out.loc[baseline_mask]
            .groupby("state_fips", as_index=False)["mean_commute_minutes_state_year"]
            .mean()
            .rename(columns={"mean_commute_minutes_state_year": "mean_commute_baseline"})
        )
        out = out.merge(baseline_commute, on="state_fips", how="left")
        out["commute_savings_proxy"] = out["mean_commute_baseline"] - out["mean_commute_minutes_state_year"]
        out["remote_work_time_saved_one_way_minutes_state_year"] = (
            pd.to_numeric(out["remote_work_share_state_year"], errors="coerce")
            * pd.to_numeric(out["mean_commute_minutes_state_year"], errors="coerce")
        )
        out["remote_work_time_saved_roundtrip_minutes_state_year"] = (
            out["remote_work_time_saved_one_way_minutes_state_year"] * 2.0
        )
        out["commute_time_saved_by_remote_work"] = out["remote_work_time_saved_roundtrip_minutes_state_year"]
        out["remote_work_time_saved_proxy"] = out["remote_work_time_saved_roundtrip_minutes_state_year"]
    out["on_site_work_share"] = 1.0 - out["remote_work_share_state_year"]
    return out


def construct_digital_distraction_index(atus_df: pd.DataFrame) -> pd.DataFrame:
    out = atus_df.copy()
    source_col = "screen_leisure_minutes_broad" if "screen_leisure_minutes_broad" in out.columns else "digital_distraction_minutes"
    out["digital_distraction_index"] = zscore_by_year(out, source_col)
    return out


def construct_face_to_face_index(atus_df: pd.DataFrame) -> pd.DataFrame:
    out = atus_df.copy()
    out["face_to_face_social_index"] = zscore_by_year(out, "face_to_face_social_minutes")
    return out


def construct_digital_social_proxy(
    atus_df: pd.DataFrame | None = None,
    manual_assumption: float | None = None,
) -> pd.DataFrame:
    if atus_df is None or atus_df.empty:
        return pd.DataFrame(
            {
                "digital_social_proxy_value": [manual_assumption if manual_assumption is not None else np.nan],
                "digital_social_proxy_mode": ["manual_assumption"],
                "warning_flag": [DIGITAL_SOCIAL_WARNING],
            }
        )
    out = atus_df.copy()
    if "computer_leisure_with_others_minutes" in out.columns:
        out["digital_social_proxy_value"] = out["computer_leisure_with_others_minutes"]
        out["digital_social_proxy_mode"] = "measured_proxy"
    else:
        out["digital_social_proxy_value"] = manual_assumption if manual_assumption is not None else np.nan
        out["digital_social_proxy_mode"] = "manual_assumption"
    out["warning_flag"] = DIGITAL_SOCIAL_WARNING
    return out


def merge_state_year_metrics(
    acs_df: pd.DataFrame,
    fertility_df: pd.DataFrame,
    population_df: pd.DataFrame,
    digital_access_df: pd.DataFrame | None = None,
    digital_prevalence_df: pd.DataFrame | None = None,
    attention_proxy_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frames = [acs_df, fertility_df, population_df, digital_access_df, digital_prevalence_df, attention_proxy_df]
    base_frame = next((frame.copy() for frame in frames if frame is not None and not frame.empty), pd.DataFrame())
    if base_frame.empty:
        return base_frame

    panel = base_frame
    for frame in frames:
        if frame is None or frame.empty:
            continue
        if frame is base_frame:
            continue
        merge_cols = [col for col in ["state_fips", "year"] if col in frame.columns]
        if not merge_cols or any(col not in panel.columns for col in merge_cols):
            continue
        panel = panel.merge(frame, on=merge_cols, how="left", suffixes=("", "_dup"))
        panel = panel.loc[:, ~panel.columns.str.endswith("_dup")]
    return panel


def _safe_mean(series_list: Iterable[pd.Series]) -> pd.Series:
    combined = pd.concat(series_list, axis=1)
    return combined.mean(axis=1, skipna=True)


def _infer_component_status(series: pd.Series, fallback: str = "modeled") -> pd.Series:
    return np.where(series.notna(), fallback, "missing")


def _safe_zscore_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)
    numeric = pd.to_numeric(df[column], errors="coerce")
    if numeric.notna().sum() == 0:
        return pd.Series(0.0, index=df.index, dtype=float)
    return zscore_by_year(df.assign(**{column: numeric}), column)


def _prepare_prevalence_inputs(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if "digital_access_index" in out.columns:
        out = out.rename(columns={"digital_access_index": "digital_access_index_raw"})
    if "no_internet_rate" in out.columns:
        out["no_internet_rate_inverse"] = 1.0 - out["no_internet_rate"]
    if "digital_access_gap_state_year" in out.columns:
        out["digital_access_gap_state_year_inverse"] = 1.0 - out["digital_access_gap_state_year"]
    if "time_with_spouse_minutes_state_year" in out.columns:
        out["time_with_spouse_minutes_state_year_inverse"] = -out["time_with_spouse_minutes_state_year"]
    if "commute_burden_index" in out.columns:
        out["commute_burden_index_inverse"] = -out["commute_burden_index"]
    if "care_burden_minutes_state_year" in out.columns:
        out["care_burden_minutes_state_year_inverse"] = -out["care_burden_minutes_state_year"]
    return out


def _build_region_commute_proxy_from_atus(atus_df: pd.DataFrame | None) -> pd.DataFrame:
    if atus_df is None or atus_df.empty or "commuting_minutes" not in atus_df.columns:
        return pd.DataFrame(columns=["region", "year", "region_commute_minutes_proxy"])

    atus = atus_df.copy()
    atus["year"] = pd.to_numeric(atus["year"], errors="coerce").astype("Int64")
    atus["commuting_minutes"] = pd.to_numeric(atus["commuting_minutes"], errors="coerce")

    region_rows = (
        atus.loc[atus["geography_type"].eq("region"), ["region", "year", "commuting_minutes"]]
        .dropna(subset=["region", "year", "commuting_minutes"])
        .drop_duplicates(subset=["region", "year"])
        .rename(columns={"commuting_minutes": "atus_region_commuting_minutes"})
    )
    national_rows = (
        atus.loc[atus["geography_type"].eq("national"), ["year", "commuting_minutes"]]
        .dropna(subset=["year", "commuting_minutes"])
        .drop_duplicates(subset=["year"])
        .rename(columns={"commuting_minutes": "atus_national_commuting_minutes"})
    )
    if region_rows.empty:
        return pd.DataFrame(columns=["region", "year", "region_commute_minutes_proxy"])

    proxy = region_rows.merge(national_rows, on="year", how="left")
    national_default = float(national_rows["atus_national_commuting_minutes"].median()) if not national_rows.empty else np.nan
    proxy["atus_national_commuting_minutes"] = proxy["atus_national_commuting_minutes"].fillna(national_default)
    proxy["region_commute_minutes_proxy"] = np.where(
        proxy["atus_region_commuting_minutes"].gt(0) & proxy["atus_national_commuting_minutes"].gt(0),
        COMMUTE_FALLBACK_NATIONAL_ANCHOR_MINUTES
        * proxy["atus_region_commuting_minutes"]
        / proxy["atus_national_commuting_minutes"],
        np.nan,
    )
    proxy["year"] = proxy["year"].astype(int)
    return proxy[["region", "year", "region_commute_minutes_proxy"]]


def _assign_commute_minutes_with_quality(
    panel: pd.DataFrame,
    atus_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = panel.copy()
    if "mean_commute_minutes_state_year" not in out.columns:
        out["mean_commute_minutes_state_year"] = np.nan
    out["mean_commute_minutes_state_year"] = pd.to_numeric(out["mean_commute_minutes_state_year"], errors="coerce")

    if "long_commute_share_state_year" in out.columns:
        out["long_commute_share_state_year"] = pd.to_numeric(out["long_commute_share_state_year"], errors="coerce")
        out.loc[out["mean_commute_minutes_state_year"].isna(), "long_commute_share_state_year"] = np.nan

    observed_mask = out["mean_commute_minutes_state_year"].gt(0)
    out[COMMUTE_QUALITY_COLUMN] = np.where(observed_mask, "observed", None)
    out[COMMUTE_SOURCE_COLUMN] = np.where(
        observed_mask,
        "State-year ACS commute minutes observed in the local processed panel.",
        None,
    )

    recent_state = (
        out.loc[observed_mask, ["state_fips", "year", "mean_commute_minutes_state_year"]]
        .sort_values(["state_fips", "year"])
        .groupby("state_fips")["mean_commute_minutes_state_year"]
        .apply(lambda series: float(series.tail(3).mean()))
        .reset_index(name="state_recent_commute_minutes")
    )
    if not recent_state.empty:
        out = out.merge(recent_state, on="state_fips", how="left")
        state_mask = out["mean_commute_minutes_state_year"].isna() & out["state_recent_commute_minutes"].notna()
        out.loc[state_mask, "mean_commute_minutes_state_year"] = out.loc[state_mask, "state_recent_commute_minutes"]
        out.loc[state_mask, COMMUTE_QUALITY_COLUMN] = "state_smoothed"
        out.loc[state_mask, COMMUTE_SOURCE_COLUMN] = (
            "Filled from the state's latest observed ACS commute average "
            "(three-year mean when multiple observed years are available)."
        )
    else:
        out["state_recent_commute_minutes"] = np.nan

    region_proxy = _build_region_commute_proxy_from_atus(atus_df)
    if not region_proxy.empty and "region" in out.columns:
        out = out.merge(region_proxy, on=["region", "year"], how="left")
        out["region_commute_minutes_proxy"] = out.groupby("region", sort=False)["region_commute_minutes_proxy"].transform(
            lambda series: series.ffill().bfill()
        )
        region_mask = out["mean_commute_minutes_state_year"].isna() & out["region_commute_minutes_proxy"].notna()
        out.loc[region_mask, "mean_commute_minutes_state_year"] = out.loc[region_mask, "region_commute_minutes_proxy"]
        out.loc[region_mask, COMMUTE_QUALITY_COLUMN] = "region_fallback"
        out.loc[region_mask, COMMUTE_SOURCE_COLUMN] = (
            "Filled from a region-year commute proxy built from ATUS commuting minutes, "
            "rescaled so the national mean matches the 25-minute dashboard anchor."
        )
    else:
        out["region_commute_minutes_proxy"] = np.nan

    national_mask = out["mean_commute_minutes_state_year"].isna()
    out.loc[national_mask, "mean_commute_minutes_state_year"] = COMMUTE_FALLBACK_NATIONAL_ANCHOR_MINUTES
    out.loc[national_mask, COMMUTE_QUALITY_COLUMN] = "national_fallback"
    out.loc[national_mask, COMMUTE_SOURCE_COLUMN] = (
        "Filled from the 25-minute national commute anchor because no state or region fallback was available."
    )
    out["mean_commute_minutes_state_year"] = out["mean_commute_minutes_state_year"].clip(lower=1.0)
    return out.drop(columns=["state_recent_commute_minutes", "region_commute_minutes_proxy"], errors="ignore")


def _build_atus_state_year_features(panel: pd.DataFrame, atus_df: pd.DataFrame | None) -> pd.DataFrame:
    if atus_df is None or atus_df.empty:
        out = panel.copy()
        for metric in ATUS_METRICS:
            out[f"{metric}_state_year"] = np.nan
            out[f"{metric}_status"] = "modeled"
        out["digital_social_proxy_value"] = np.nan
        out["digital_social_proxy_mode"] = "manual_assumption"
        return out

    base = panel[["state_fips", "year", "region"]].drop_duplicates().copy()
    atus = atus_df.copy()
    atus["year"] = pd.to_numeric(atus["year"], errors="coerce").astype(int)

    state_rows = atus[atus["state_fips"].notna()].copy()
    for metric in ATUS_METRICS:
        pooled_col = f"{metric}_pooled"
        if pooled_col in state_rows.columns:
            state_rows[f"{metric}_state_choice"] = state_rows[metric]
            pooled_mask = state_rows[f"{metric}_state_choice"].isna() & state_rows[pooled_col].notna()
            state_rows.loc[pooled_mask, f"{metric}_state_choice"] = state_rows.loc[pooled_mask, pooled_col]
            pooled_indicator = state_rows["is_pooled_estimate"] if "is_pooled_estimate" in state_rows.columns else False
            mode_series = pd.Series(np.where(pooled_indicator, "imputed", "observed"), index=state_rows.index, dtype=object)
            mode_series = mode_series.where(state_rows[f"{metric}_state_choice"].notna(), None)
            state_rows[f"{metric}_state_mode"] = mode_series
        else:
            state_rows[f"{metric}_state_choice"] = state_rows.get(metric)
            state_rows[f"{metric}_state_mode"] = pd.Series(
                np.where(state_rows[f"{metric}_state_choice"].notna(), "observed", None),
                index=state_rows.index,
                dtype=object,
            )

    keep_cols = ["state_fips", "year"] + [
        col
        for metric in ATUS_METRICS
        for col in (f"{metric}_state_choice", f"{metric}_state_mode")
        if col in state_rows.columns
    ]
    state_merge = state_rows[keep_cols].drop_duplicates(subset=["state_fips", "year"])
    base = base.merge(state_merge, on=["state_fips", "year"], how="left")

    region_rows = (
        atus[atus["geography_type"].eq("region")][["region", "year", *[metric for metric in ATUS_METRICS if metric in atus.columns]]]
        .drop_duplicates(subset=["region", "year"])
        .rename(columns={metric: f"{metric}_region" for metric in ATUS_METRICS if metric in atus.columns})
    )
    base = base.merge(region_rows, on=["region", "year"], how="left")

    national_rows = (
        atus[atus["geography_type"].eq("national")][["year", *[metric for metric in ATUS_METRICS if metric in atus.columns]]]
        .drop_duplicates(subset=["year"])
        .rename(columns={metric: f"{metric}_national" for metric in ATUS_METRICS if metric in atus.columns})
    )
    base = base.merge(national_rows, on="year", how="left")

    remote_z = _safe_zscore_column(panel, "remote_work_share_state_year")
    prevalence_z = _safe_zscore_column(panel, "internet_use_rate_state_year")
    attention_z = _safe_zscore_column(panel, "digital_attention_proxy_index")
    partnered_z = _safe_zscore_column(panel, "married_or_partnered_share_state_year")
    commute_z = _safe_zscore_column(panel, "mean_commute_minutes_state_year")
    state_adjustments = panel[["state_fips", "year"]].copy()
    state_adjustments["remote_z"] = remote_z
    state_adjustments["prevalence_z"] = prevalence_z
    state_adjustments["attention_z"] = attention_z
    state_adjustments["partnered_z"] = partnered_z
    state_adjustments["commute_z"] = commute_z
    base = base.merge(state_adjustments, on=["state_fips", "year"], how="left")

    adjustment_map = {
        "digital_media_minutes_narrow": lambda df: 6.0 * _safe_mean([df["attention_z"], df["prevalence_z"]]),
        "screen_leisure_minutes_broad": lambda df: 10.0 * _safe_mean([df["attention_z"], df["prevalence_z"]]),
        "digital_distraction_minutes": lambda df: 10.0 * _safe_mean([df["attention_z"], df["prevalence_z"]]),
        "face_to_face_social_minutes": lambda df: -6.0 * df["attention_z"] + 4.0 * df["partnered_z"],
        "in_person_social_minutes": lambda df: -6.0 * df["attention_z"] + 4.0 * df["partnered_z"],
        "work_at_home_minutes": lambda df: 20.0 * df["remote_z"],
        "work_away_minutes": lambda df: -18.0 * df["remote_z"] + 6.0 * df["commute_z"],
        "commuting_minutes": lambda df: 6.0 * df["commute_z"] - 5.0 * df["remote_z"],
        "away_from_home_minutes": lambda df: -5.0 * df["attention_z"] + 4.0 * df["partnered_z"],
        "household_work_minutes": lambda df: 2.0 * df["remote_z"] + 2.0 * df["partnered_z"],
        "unpaid_care_minutes": lambda df: 3.0 * df["remote_z"] + 2.0 * df["partnered_z"],
        "care_burden_minutes": lambda df: 5.0 * df["remote_z"] + 4.0 * df["partnered_z"],
        "time_alone_minutes": lambda df: 8.0 * df["attention_z"],
        "time_with_spouse_only_minutes": lambda df: 3.0 * df["partnered_z"] + 2.0 * df["remote_z"],
        "time_with_friends_minutes": lambda df: -4.0 * df["attention_z"] + 2.0 * df["partnered_z"],
        "time_with_nonhousehold_minutes": lambda df: -4.0 * df["attention_z"] + 2.0 * df["partnered_z"],
        "time_with_family_minutes": lambda df: 2.0 * df["remote_z"] + 2.0 * df["partnered_z"],
        "time_with_children_minutes": lambda df: 3.0 * df["remote_z"] + 2.0 * df["partnered_z"],
        "time_with_spouse_minutes": lambda df: 3.0 * df["partnered_z"] + 1.5 * df["remote_z"],
    }

    for metric in ATUS_METRICS:
        state_col = f"{metric}_state_choice"
        region_col = f"{metric}_region"
        national_col = f"{metric}_national"
        output_col = f"{metric}_state_year"
        status_col = f"{metric}_status"
        modeled_base = base[region_col] if region_col in base.columns else pd.Series(np.nan, index=base.index)
        if national_col in base.columns:
            modeled_base = modeled_base.fillna(base[national_col])
        adjustment = adjustment_map.get(metric, lambda df: 0.0)(base)
        base[output_col] = base[state_col] if state_col in base.columns else np.nan
        state_status = base.get(f"{metric}_state_mode", pd.Series(np.nan, index=base.index))
        fill_mask = base[output_col].isna()
        base.loc[fill_mask, output_col] = modeled_base.loc[fill_mask] + adjustment.loc[fill_mask]
        base[status_col] = np.where(
            base[output_col].isna(),
            "missing",
            np.where(pd.notna(state_status), state_status, "modeled"),
        )

    base["digital_social_proxy_value"] = base.get("time_with_spouse_only_minutes_state_year")
    base["digital_social_proxy_mode"] = np.where(
        base["digital_social_proxy_value"].notna(),
        base.get("time_with_spouse_only_minutes_status", "modeled"),
        "manual_assumption",
    )
    return panel.merge(
        base.drop(columns=["region", "remote_z", "prevalence_z", "attention_z", "partnered_z", "commute_z"], errors="ignore"),
        on=["state_fips", "year"],
        how="left",
    )


def _combine_index(df: pd.DataFrame, index_name: str) -> pd.DataFrame:
    out = df.copy()
    component_specs = INDEX_COMPONENTS[index_name]
    component_columns = []
    weighted_parts = []
    weights = []
    status_columns = []

    for column, weight in component_specs:
        if column not in out.columns:
            continue
        component_columns.append(column)
        standardized = zscore_by_year(out.assign(**{column: pd.to_numeric(out[column], errors="coerce")}), column)
        weighted_parts.append(standardized * weight)
        weights.append(weight)
        status_col = f"{column}_status"
        if status_col in out.columns:
            status_columns.append(status_col)

    if weighted_parts:
        numerator = pd.concat(weighted_parts, axis=1).sum(axis=1, skipna=True)
        denominator = sum(weights)
        out[index_name] = numerator / denominator if denominator else np.nan
    else:
        out[index_name] = np.nan

    mode_col = f"{index_name}_mode"
    if status_columns:
        def pick_mode(row: pd.Series) -> str:
            values = {str(value) for value in row if pd.notna(value)}
            if "observed" in values:
                return "observed"
            if "imputed" in values:
                return "imputed"
            if "user_provided" in values:
                return "user_provided"
            if "modeled" in values:
                return "modeled"
            return "missing"

        out[mode_col] = out[status_columns].apply(pick_mode, axis=1)
    else:
        out[mode_col] = _infer_component_status(out[index_name])

    out[f"{index_name}_components"] = ", ".join(component_columns)
    return out


def add_exposure_indices(panel: pd.DataFrame) -> pd.DataFrame:
    out = _prepare_prevalence_inputs(panel)
    for index_name in EXPOSURE_INDEX_COLUMNS:
        out = _combine_index(out, index_name)
        if index_name == "commute_burden_index":
            out["commute_burden_index_inverse"] = -out["commute_burden_index"]
        if index_name == "digital_access_index" and "digital_access_index_mode" not in out.columns:
            out["digital_access_index_mode"] = _infer_component_status(out[index_name], fallback="observed")
    return out


def _build_controls_json(row: pd.Series) -> str:
    controls = {
        "labor_force_participation_rate": row.get("labor_force_participation_rate"),
        "female_employment_rate": row.get("female_employment_rate"),
        "married_or_partnered_share_state_year": row.get("married_or_partnered_share_state_year"),
        "mean_commute_minutes_state_year": row.get("mean_commute_minutes_state_year"),
        "long_commute_share_state_year": row.get("long_commute_share_state_year"),
        COMMUTE_QUALITY_COLUMN: row.get(COMMUTE_QUALITY_COLUMN),
        "region": row.get("region"),
    }
    return json.dumps({key: value for key, value in controls.items() if pd.notna(value)})


def _build_quality_flags(row: pd.Series) -> str:
    flags = {
        "acs_warning": row.get("acs_warning"),
        "source_used": row.get("source_used"),
        "proxy_mode": row.get("proxy_mode"),
        "measurement_note": row.get("measurement_note"),
        COMMUTE_QUALITY_COLUMN: row.get(COMMUTE_QUALITY_COLUMN),
        COMMUTE_SOURCE_COLUMN: row.get(COMMUTE_SOURCE_COLUMN),
    }
    flags["index_modes"] = {
        index_name: row.get(f"{index_name}_mode")
        for index_name in EXPOSURE_INDEX_COLUMNS
        if pd.notna(row.get(f"{index_name}_mode"))
    }
    cleaned = {}
    for key, value in flags.items():
        if value is None or value == "" or value == {}:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        cleaned[key] = value
    return json.dumps(cleaned)


def _add_age_specific_rates(panel: pd.DataFrame, age_specific_fertility: pd.DataFrame | None) -> pd.DataFrame:
    if age_specific_fertility is None or age_specific_fertility.empty:
        return panel
    if not {"state_fips", "year", "mother_age_group", "age_specific_fertility_rate"}.issubset(age_specific_fertility.columns):
        return panel
    age_wide = age_specific_fertility.copy()
    age_wide["age_specific_fertility_rate"] = pd.to_numeric(age_wide["age_specific_fertility_rate"], errors="coerce")
    age_wide["mother_age_group"] = age_wide["mother_age_group"].astype(str).str.replace("-", "_", regex=False)
    age_wide = (
        age_wide.pivot_table(
            index=["state_fips", "year"],
            columns="mother_age_group",
            values="age_specific_fertility_rate",
            aggfunc="mean",
        )
        .reset_index()
        .rename(columns=lambda col: f"age_specific_fertility_rate_{col}" if col not in {"state_fips", "year"} else col)
    )
    return panel.merge(age_wide, on=["state_fips", "year"], how="left")


def build_modeling_state_year_panel(
    acs_df: pd.DataFrame,
    fertility_df: pd.DataFrame,
    population_df: pd.DataFrame,
    atus_df: pd.DataFrame | None = None,
    digital_access_df: pd.DataFrame | None = None,
    digital_prevalence_df: pd.DataFrame | None = None,
    attention_proxy_df: pd.DataFrame | None = None,
    age_specific_fertility_df: pd.DataFrame | None = None,
    save_path: str | None = None,
) -> pd.DataFrame:
    acs = construct_remote_work_metrics(acs_df) if acs_df is not None and not acs_df.empty else pd.DataFrame()
    panel = merge_state_year_metrics(
        acs,
        fertility_df if fertility_df is not None else pd.DataFrame(),
        population_df if population_df is not None else pd.DataFrame(),
        digital_access_df,
        digital_prevalence_df,
        attention_proxy_df,
    )
    if panel.empty:
        return panel

    panel = _build_atus_state_year_features(panel, atus_df)
    panel = _assign_commute_minutes_with_quality(panel, atus_df=atus_df)
    if "general_fertility_rate" in panel.columns:
        panel["fertility_rate"] = panel["general_fertility_rate"]
    if "population_total" in panel.columns:
        panel["total_population"] = panel["population_total"]
    if "births" not in panel.columns and "natural_increase" in panel.columns:
        panel["births"] = np.nan
    if "state_name" not in panel.columns:
        panel["state_name"] = panel["state_fips"].map(STATE_FIPS_TO_NAME)
    else:
        panel["state_name"] = panel["state_name"].fillna(panel["state_fips"].map(STATE_FIPS_TO_NAME))
    panel["female_population_15_44"] = pd.to_numeric(panel.get("female_population_15_44"), errors="coerce")
    if "source_used_x" in panel.columns and "source_used" not in panel.columns:
        panel["source_used"] = panel["source_used_x"]
    if "search_interest_online_dating_state_year" not in panel.columns:
        panel["search_interest_online_dating_state_year"] = np.nan

    if "sample_size" in panel.columns:
        panel["sample_size"] = pd.to_numeric(panel["sample_size"], errors="coerce")
        panel["sample_size_status"] = np.where(panel["sample_size"].ge(MIN_ATUS_STATE_SAMPLE), "observed", "imputed")
    if "digital_access_index_raw" in panel.columns:
        panel["digital_access_index_raw_status"] = np.where(panel["digital_access_index_raw"].notna(), "observed", "missing")
    if "internet_use_rate_state_year" in panel.columns:
        panel["internet_use_rate_state_year_status"] = np.where(
            panel["internet_use_rate_state_year"].notna(),
            "observed",
            "missing",
        )
    if "digital_attention_proxy_index" in panel.columns:
        proxy_source = panel.get("source_used", pd.Series("", index=panel.index)).astype(str).str.contains("user", case=False, na=False)
        panel["digital_attention_proxy_index_status"] = np.where(
            panel["digital_attention_proxy_index"].notna(),
            np.where(proxy_source, "user_provided", "modeled"),
            "missing",
        )

    panel = add_exposure_indices(panel)
    if "work_family_compatibility_proxy" in panel.columns:
        panel["remote_work_time_saved_proxy"] = panel["work_family_compatibility_proxy"]
    panel = _add_age_specific_rates(panel, age_specific_fertility_df)
    panel["controls"] = panel.apply(_build_controls_json, axis=1)
    panel["source_quality_flags"] = panel.apply(_build_quality_flags, axis=1)
    panel = panel.sort_values(["state_fips", "year"]).reset_index(drop=True)

    for column in MODEL_REQUIRED_COLUMNS:
        if column not in panel.columns:
            panel[column] = np.nan

    save_target = Path(save_path) if save_path else PROCESSED_DATA_DIR / "modeling_state_year_panel.parquet"
    cache_dataframe(panel, save_target)
    return panel


def load_default_modeling_state_year_panel(
    save_path: str | None = None,
) -> pd.DataFrame:
    def maybe_read(name: str) -> pd.DataFrame | None:
        parquet_path = PROCESSED_DATA_DIR / f"{name}.parquet"
        csv_path = PROCESSED_DATA_DIR / f"{name}.csv"
        if parquet_path.exists():
            return pd.read_parquet(parquet_path)
        if csv_path.exists():
            return pd.read_csv(csv_path)
        return None

    acs_df = maybe_read("acs_state_year_from_acs")
    if acs_df is None:
        acs_df = maybe_read("acs_state_year")
    if acs_df is not None and not acs_df.empty:
        acs_df = restrict_to_dashboard_acs_window(acs_df)
    fertility_df = maybe_read("fertility_metrics")
    population_df = maybe_read("population_metrics")
    panel = build_modeling_state_year_panel(
        acs_df=acs_df if acs_df is not None else pd.DataFrame(),
        fertility_df=fertility_df if fertility_df is not None else pd.DataFrame(),
        population_df=population_df if population_df is not None else pd.DataFrame(),
        atus_df=maybe_read("atus_metrics"),
        digital_access_df=maybe_read("digital_access"),
        digital_prevalence_df=maybe_read("digital_prevalence"),
        attention_proxy_df=maybe_read("digital_attention"),
        age_specific_fertility_df=maybe_read("age_specific_fertility"),
        save_path=save_path,
    )
    return panel


def build_executive_summary_metrics(
    state_year_panel: pd.DataFrame,
    atus_national: pd.DataFrame | None = None,
    fertility_df: pd.DataFrame | None = None,
) -> dict[str, float | str]:
    if state_year_panel.empty or "year" not in state_year_panel.columns:
        return {}

    def latest_mean(column: str) -> float:
        if column not in state_year_panel.columns:
            return np.nan
        observed = state_year_panel.loc[state_year_panel[column].notna(), ["year", column]]
        if observed.empty:
            return np.nan
        latest_year_for_metric = int(observed["year"].max())
        return observed.loc[observed["year"].eq(latest_year_for_metric), column].mean()

    latest_year = int(state_year_panel["year"].max())
    latest_national_fertility = latest_mean("fertility_rate")
    if fertility_df is not None and not fertility_df.empty:
        state_series = fertility_df.get("state_fips", pd.Series(dtype=str))
        gfr_series = fertility_df.get("general_fertility_rate", pd.Series(dtype=float))
        national_rows = fertility_df.loc[state_series.eq("00") & gfr_series.notna()]
        if not national_rows.empty:
            national_latest_year = int(national_rows["year"].max())
            latest_national_fertility = float(
                national_rows.loc[national_rows["year"].eq(national_latest_year), "general_fertility_rate"].iloc[0]
            )

    result = {
        "latest_year": latest_year,
        "latest_national_work_from_home_share": latest_mean("remote_work_share_state_year"),
        "latest_national_average_commute_time": latest_mean("mean_commute_minutes_state_year"),
        "latest_national_remote_work_time_saved": latest_mean("remote_work_time_saved_roundtrip_minutes_state_year"),
        "latest_national_fertility_rate": latest_national_fertility,
        "latest_national_population_growth_rate": latest_mean("population_growth_rate"),
        "latest_remote_work_exposure_index": latest_mean("remote_work_exposure_index"),
        "latest_digital_use_prevalence_index": latest_mean("digital_use_prevalence_index"),
        "latest_digital_distraction_index": latest_mean("digital_distraction_index"),
        "latest_in_person_social_index": latest_mean("in_person_social_index"),
    }
    if atus_national is not None and not atus_national.empty:
        atus_latest = atus_national.loc[atus_national["year"].eq(atus_national["year"].max())]
        result["latest_measured_digital_media_minutes_narrow"] = atus_latest.get("digital_media_minutes_narrow", pd.Series(dtype=float)).mean()
        result["latest_measured_screen_leisure_minutes_broad"] = atus_latest.get("screen_leisure_minutes_broad", pd.Series(dtype=float)).mean()
        result["latest_measured_social_interaction_minutes"] = atus_latest["in_person_social_minutes"].mean()
    else:
        result["latest_measured_digital_media_minutes_narrow"] = np.nan
        result["latest_measured_screen_leisure_minutes_broad"] = np.nan
        result["latest_measured_social_interaction_minutes"] = np.nan
    return result
