from __future__ import annotations

import numpy as np
import pandas as pd

from .config import EXPECTED_COLUMNS, MEASUREMENT_TYPES, STATE_FIPS_TO_REGION, STATE_NAME_TO_FIPS
from .data_download import validate_columns


def clean_ntia_state_data(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, EXPECTED_COLUMNS["ntia_state"], "NTIA/CPS state data")
    out = df.copy()
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2)
    out["year"] = out["year"].astype(int)
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    prevalence_cols = [
        "internet_use_rate_state_year",
        "mobile_device_use_rate_state_year",
        "online_activity_index_state_year",
        "digital_access_gap_state_year",
    ]
    for column in prevalence_cols:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out["measurement_concept"] = "digital_use_prevalence"
    out["measurement_type"] = MEASUREMENT_TYPES["digital_use_prevalence"]
    out["is_representative"] = True
    out["geography_level"] = "state"
    return out


def clean_acs_internet_tables(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, ["state_fips", "year"], "ACS digital access tables")
    out = df.copy()
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2)
    out["year"] = out["year"].astype(int)
    access_cols = [
        "broadband_subscription_rate",
        "smartphone_or_computer_access_rate",
        "no_internet_rate",
    ]
    for column in access_cols:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if set(access_cols).issubset(out.columns):
        out["digital_access_index"] = (
            out["broadband_subscription_rate"]
            + out["smartphone_or_computer_access_rate"]
            + (1.0 - out["no_internet_rate"])
        ) / 3.0
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    out["measurement_concept"] = "digital_access"
    out["measurement_type"] = MEASUREMENT_TYPES["digital_access"]
    out["is_representative"] = True
    out["geography_level"] = "state"
    return out


def clean_commercial_media_data(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, EXPECTED_COLUMNS["commercial_digital_media_template"], "commercial digital media data")
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    for column in [
        "digital_media_minutes_per_day",
        "social_media_minutes_per_day",
        "streaming_minutes_per_day",
        "gaming_minutes_per_day",
        "online_dating_use_rate",
        "video_calling_use_rate",
        "sample_size",
        "standard_error",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["measurement_concept"] = "digital_time"
    out["measurement_type"] = np.where(
        out["digital_media_minutes_per_day"].notna(),
        MEASUREMENT_TYPES["digital_time"],
        MEASUREMENT_TYPES["digital_use_prevalence"],
    )
    out["is_representative"] = False
    out["geography_level"] = out["geography_type"]
    out["imputation_note"] = np.where(
        out["geography_type"].str.upper() == "DMA",
        "DMA-to-state approximation requires a county-population crosswalk.",
        "",
    )
    return out


def clean_google_trends_proxy(df: pd.DataFrame, keyword_to_measure: dict[str, str]) -> pd.DataFrame:
    if "state_name" not in df.columns:
        raise ValueError("Google Trends state proxy data must include state_name.")
    out = df.copy()
    out["measurement_concept"] = "digital_attention"
    out["measurement_type"] = MEASUREMENT_TYPES["digital_attention"]
    out["is_representative"] = False
    out["geography_level"] = "state"
    for keyword, output_column in keyword_to_measure.items():
        if keyword in out.columns:
            out[output_column] = pd.to_numeric(out[keyword], errors="coerce")
    proxy_columns = [column for column in keyword_to_measure.values() if column in out.columns]
    if proxy_columns:
        standardized = []
        for column in proxy_columns:
            series = out[column]
            standardized.append((series - series.mean()) / series.std(ddof=0) if series.std(ddof=0) else series * 0)
        out["digital_attention_proxy_index"] = np.nanmean(standardized, axis=0)
    out["warning_flag"] = "Proxy measure of attention only; not representative digital-media consumption."
    return out


def build_google_trends_state_year_proxy(df: pd.DataFrame, keyword_groups: dict[str, list[str]]) -> pd.DataFrame:
    validate_columns(
        df,
        ["state_name", "year", "keyword", "regional_interest", "national_year_interest"],
        "Google Trends state-year keyword panel",
    )
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype(int)
    out["regional_interest"] = pd.to_numeric(out["regional_interest"], errors="coerce")
    out["national_year_interest"] = pd.to_numeric(out["national_year_interest"], errors="coerce")
    out["state_name"] = out["state_name"].astype(str)
    out["state_fips"] = out["state_name"].map(STATE_NAME_TO_FIPS)
    out.loc[out["state_name"].eq("United States"), "state_fips"] = "00"
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION).fillna("National")
    out["scaled_interest"] = (out["regional_interest"] / 100.0) * out["national_year_interest"]

    panel = out[["state_fips", "state_name", "region", "year"]].drop_duplicates().copy()
    for output_column, keywords in keyword_groups.items():
        subset = out[out["keyword"].isin(keywords)].copy()
        grouped = (
            subset.groupby(["state_fips", "state_name", "region", "year"], as_index=False)["scaled_interest"]
            .mean()
            .rename(columns={"scaled_interest": output_column})
        )
        panel = panel.merge(grouped, on=["state_fips", "state_name", "region", "year"], how="left")

    concept_cols = list(keyword_groups.keys())
    if concept_cols:
        panel["digital_attention_proxy_index"] = panel[concept_cols].mean(axis=1, skipna=True)
    panel["measurement_concept"] = "digital_attention"
    panel["measurement_type"] = MEASUREMENT_TYPES["digital_attention"]
    panel["is_representative"] = False
    panel["geography_level"] = np.where(panel["state_fips"].eq("00"), "national", "state")
    panel["warning_flag"] = (
        "Google Trends is a proxy for search attention, not direct app use or time use. "
        "State-year values are calibrated by combining within-year state interest with each keyword's national annual intensity."
    )
    panel["source_used"] = "Google Trends via pytrends"
    panel["estimate_mode"] = "state cross-sections scaled by keyword-specific national annual intensity"
    return panel


def build_measurement_quality_panel(*frames: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for frame in frames:
        if frame is None or frame.empty:
            continue
        rows.append(
            {
                "source_used": frame.attrs.get("source_used", "user/local"),
                "is_representative": bool(frame.get("is_representative", pd.Series([False])).iloc[0]),
                "measurement_type": frame.get("measurement_type", pd.Series(["unknown"])).iloc[0],
                "geography_level": frame.get("geography_level", pd.Series(["unknown"])).iloc[0],
                "latest_year": int(pd.to_numeric(frame["year"], errors="coerce").dropna().max()) if "year" in frame.columns else np.nan,
                "estimate_mode": frame.attrs.get("estimate_mode", "direct"),
                "sample_size": float(pd.to_numeric(frame.get("sample_size", pd.Series(dtype=float)), errors="coerce").median())
                if "sample_size" in frame.columns
                else np.nan,
                "warning_flags": frame.get("warning_flag", pd.Series([""])).iloc[0]
                if "warning_flag" in frame.columns
                else "",
            }
        )
    return pd.DataFrame(rows)
