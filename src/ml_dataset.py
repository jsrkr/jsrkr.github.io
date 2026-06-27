from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    EXPOSURE_INDEX_COLUMNS,
    ML_LAG_YEARS,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    SHORT_GAP_IMPUTATION_LIMIT,
)
from .data_download import cache_dataframe


ML_PANEL_PATH = PROCESSED_DATA_DIR / "ml_state_year_panel.parquet"
ML_DICT_PATH = OUTPUTS_DIR / "ml_data_dictionary.csv"


def load_modeling_panel(path: str | Path | None = None) -> pd.DataFrame:
    target = Path(path) if path else PROCESSED_DATA_DIR / "modeling_state_year_panel.parquet"
    if not target.exists():
        raise FileNotFoundError(f"Modeling panel not found at {target}. Build `modeling_state_year_panel.parquet` first.")
    return pd.read_parquet(target) if target.suffix == ".parquet" else pd.read_csv(target)


def sort_state_year_panel(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype(int)
    return out.sort_values(["state_fips", "year"]).reset_index(drop=True)


def _transparent_impute_series(series: pd.Series, max_gap: int = SHORT_GAP_IMPUTATION_LIMIT) -> tuple[pd.Series, pd.Series, pd.Series]:
    numeric = pd.to_numeric(series, errors="coerce")
    original_missing = numeric.isna()
    interpolated = numeric.interpolate(limit=max_gap, limit_area="inside")
    filled = interpolated.ffill(limit=max_gap)
    imputed = original_missing & filled.notna()
    long_gap = original_missing & filled.isna()
    return filled, imputed.astype(int), long_gap.astype(int)


def transparent_impute_within_state(
    df: pd.DataFrame,
    columns: list[str],
    max_gap: int = SHORT_GAP_IMPUTATION_LIMIT,
) -> pd.DataFrame:
    out = sort_state_year_panel(df)
    for column in columns:
        if column not in out.columns:
            continue
        filled_parts = []
        imputed_parts = []
        long_gap_parts = []
        for _, group in out.groupby("state_fips", sort=False):
            filled, imputed_flag, long_gap_flag = _transparent_impute_series(group[column], max_gap=max_gap)
            filled_parts.append(pd.Series(filled.values, index=group.index))
            imputed_parts.append(pd.Series(imputed_flag.values, index=group.index))
            long_gap_parts.append(pd.Series(long_gap_flag.values, index=group.index))
        out[column] = pd.concat(filled_parts).sort_index()
        out[f"{column}_imputed_flag"] = pd.concat(imputed_parts).sort_index().astype(int)
        out[f"{column}_long_gap_flag"] = pd.concat(long_gap_parts).sort_index().astype(int)
    return out


def add_lagged_features(
    df: pd.DataFrame,
    feature_columns: list[str],
    group_col: str = "state_fips",
    year_col: str = "year",
    lags: tuple[int, ...] = ML_LAG_YEARS,
    rolling_window: int = 3,
) -> pd.DataFrame:
    out = sort_state_year_panel(df)
    grouped = out.groupby(group_col, sort=False)
    for column in feature_columns:
        if column not in out.columns:
            continue
        for lag in lags:
            out[f"{column}_lag{lag}"] = grouped[column].shift(lag)
        out[f"{column}_rolling{rolling_window}"] = grouped[column].transform(
            lambda series: series.shift(1).rolling(rolling_window, min_periods=1).mean()
        )
    out = out.sort_values([group_col, year_col]).reset_index(drop=True)
    return out


def create_state_fixed_attributes(df: pd.DataFrame) -> pd.DataFrame:
    out = sort_state_year_panel(df)
    grouped = out.groupby("state_fips", sort=False)
    out["state_history_mean_fertility"] = grouped["fertility_rate"].transform("mean")
    if "remote_work_exposure_index" in out.columns:
        out["state_history_mean_remote_work"] = grouped["remote_work_exposure_index"].transform("mean")
    if "total_population" in out.columns:
        out["state_log_population_baseline"] = np.log(grouped["total_population"].transform("first").replace(0, np.nan))
    return out


def create_year_features(df: pd.DataFrame) -> pd.DataFrame:
    out = sort_state_year_panel(df)
    min_year = int(out["year"].min())
    out["year_index"] = out["year"] - min_year
    out["year_index_sq"] = out["year_index"] ** 2
    out["post_2020"] = (out["year"] >= 2020).astype(int)
    out["post_2020_trend"] = np.where(out["year"] >= 2020, out["year"] - 2020, 0)
    out["region_id"] = pd.factorize(out.get("region", pd.Series("Unknown", index=out.index)))[0]
    return out


def create_ml_data_dictionary(df: pd.DataFrame, output_path: str | Path = ML_DICT_PATH) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        note = "derived"
        if column in EXPOSURE_INDEX_COLUMNS:
            note = "state-year exposure index"
        elif column.endswith("_lag1") or column.endswith("_lag2") or column.endswith("_lag3"):
            note = "lagged feature"
        elif column.endswith("_rolling3"):
            note = "rolling historical average"
        elif column.endswith("_imputed_flag"):
            note = "transparent imputation flag"
        elif column.endswith("_long_gap_flag"):
            note = "gap remains unfilled"
        elif column in {"fertility_rate", "births", "total_population", "female_population_15_44"}:
            note = "core target or accounting input"
        rows.append(
            {
                "column_name": column,
                "dtype": str(df[column].dtype),
                "description": note,
            }
        )
    dictionary = pd.DataFrame(rows)
    cache_dataframe(dictionary, Path(output_path))
    return dictionary


def prepare_ml_state_year_panel(
    modeling_panel: pd.DataFrame,
    save_path: str | Path = ML_PANEL_PATH,
    dictionary_path: str | Path = ML_DICT_PATH,
) -> pd.DataFrame:
    panel = sort_state_year_panel(modeling_panel)
    panel["region"] = panel.get("region", pd.Series("Unknown", index=panel.index)).fillna("Unknown")
    panel["state_name"] = panel.get("state_name", panel["state_fips"])

    impute_columns = [
        column
        for column in (
            EXPOSURE_INDEX_COLUMNS
            + [
                "fertility_rate",
                "births",
                "female_population_15_44",
                "total_population",
                "population_growth_rate",
                "labor_force_participation_rate",
                "female_employment_rate",
                "married_or_partnered_share_state_year",
            ]
        )
        if column in panel.columns
    ]
    panel = transparent_impute_within_state(panel, impute_columns)

    panel = add_lagged_features(panel, [column for column in EXPOSURE_INDEX_COLUMNS if column in panel.columns])
    fertility_features = [column for column in ["fertility_rate"] if column in panel.columns]
    panel = add_lagged_features(panel, fertility_features)
    if "fertility_rate_lag1" not in panel.columns and "fertility_rate" in panel.columns:
        panel["fertility_rate_lag1"] = panel.groupby("state_fips")["fertility_rate"].shift(1)
    if "fertility_rate_lag2" not in panel.columns and "fertility_rate" in panel.columns:
        panel["fertility_rate_lag2"] = panel.groupby("state_fips")["fertility_rate"].shift(2)
    if "fertility_rate_rolling3" not in panel.columns and "fertility_rate" in panel.columns:
        panel["fertility_rate_rolling3"] = panel.groupby("state_fips")["fertility_rate"].transform(
            lambda series: series.shift(1).rolling(3, min_periods=1).mean()
        )

    panel = create_state_fixed_attributes(panel)
    panel = create_year_features(panel)
    panel["source_quality_flags"] = panel.get("source_quality_flags", pd.Series("{}", index=panel.index)).fillna("{}")
    panel["ml_feature_manifest"] = panel.apply(
        lambda row: json.dumps(
            {
                "lags": [f"{feature}_lag{lag}" for feature in EXPOSURE_INDEX_COLUMNS for lag in ML_LAG_YEARS if f"{feature}_lag{lag}" in panel.columns],
                "year_features": ["year_index", "year_index_sq", "post_2020", "post_2020_trend"],
                "region": row.get("region"),
            }
        ),
        axis=1,
    )

    save_target = Path(save_path)
    cache_dataframe(panel, save_target)
    create_ml_data_dictionary(panel, output_path=dictionary_path)
    return panel


def load_or_build_ml_state_year_panel(
    modeling_panel: pd.DataFrame | None = None,
    save_path: str | Path = ML_PANEL_PATH,
) -> pd.DataFrame:
    save_target = Path(save_path)
    if save_target.exists():
        return pd.read_parquet(save_target) if save_target.suffix == ".parquet" else pd.read_csv(save_target)
    if modeling_panel is None:
        modeling_panel = load_modeling_panel()
    return prepare_ml_state_year_panel(modeling_panel, save_path=save_target)
