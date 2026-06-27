from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_FORECAST_END_YEAR, EXPOSURE_INDEX_COLUMNS, PROCESSED_DATA_DIR, SCENARIO_SPECS
from .data_download import cache_dataframe


SCENARIO_FEATURE_MAP = {
    "remote_work_exposure": "remote_work_exposure_index",
    "digital_distraction": "digital_distraction_index",
    "digital_social_exposure": "digital_social_index",
    "in_person_work": "in_person_work_exposure_index",
    "in_person_social_interaction": "in_person_social_index",
    "commute_burden": "commute_burden_index",
    "work_family_compatibility": "work_family_compatibility_proxy",
    "gendered_care_penalty": "gendered_care_risk_proxy",
}

SCENARIO_SAVE_PATH = PROCESSED_DATA_DIR / "scenario_covariates.parquet"
TRANSPARENT_SCENARIO_COLUMNS = [
    "remote_work_share_state_year",
    "mean_commute_minutes_state_year",
    "remote_work_time_saved_one_way_minutes_state_year",
    "remote_work_time_saved_roundtrip_minutes_state_year",
    "commute_time_saved_by_remote_work",
    "digital_media_minutes_narrow_state_year",
    "screen_leisure_minutes_broad_state_year",
    "in_person_social_minutes_state_year",
    "household_work_minutes_state_year",
    "unpaid_care_minutes_state_year",
    "care_burden_minutes_state_year",
    "search_interest_online_dating_state_year",
]

TRANSPARENT_SCENARIO_GROWTH_OVERRIDES = {
    "baseline_continuation": {},
    "distraction_dominant": {
        "screen_leisure_minutes_broad_state_year": 3.0,
        "digital_media_minutes_narrow_state_year": 1.25,
        "in_person_social_minutes_state_year": -1.5,
    },
    "remote_work_dominant": {
        "remote_work_share_state_year": 0.004,
        "digital_media_minutes_narrow_state_year": 0.2,
        "screen_leisure_minutes_broad_state_year": 0.5,
        "in_person_social_minutes_state_year": 0.25,
    },
    "digital_social_substitution": {
        "digital_media_minutes_narrow_state_year": 0.75,
        "screen_leisure_minutes_broad_state_year": 1.0,
        "in_person_social_minutes_state_year": -0.5,
        "search_interest_online_dating_state_year": 0.5,
    },
    "in_person_revival": {
        "screen_leisure_minutes_broad_state_year": -1.5,
        "digital_media_minutes_narrow_state_year": -0.5,
        "in_person_social_minutes_state_year": 2.0,
    },
    "gendered_care_penalty": {
        "remote_work_share_state_year": 0.0025,
        "household_work_minutes_state_year": 1.5,
        "unpaid_care_minutes_state_year": 1.5,
        "screen_leisure_minutes_broad_state_year": 0.5,
    },
    "user_defined": {},
}

# Growth overrides are annual increments expressed in standardized-index units. Applying one
# constant increment every year through the 2060 forecast end year would let a scenario drift
# unboundedly far from the historical range it was estimated on (and, recursively, drag the
# forecast far outside the model's training domain). Decaying the increment geometrically lets
# each override ramp in at full strength and then asymptote to a finite total shift instead of
# compounding forever.
OVERRIDE_DECAY_RATE = 0.92
SHARE_EPSILON = 1e-4


def _percentile_rank(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(0.5, index=series.index, dtype=float)
    return numeric.rank(pct=True, method="average").fillna(0.5).astype(float)


def _mean_rank_component(
    frame: pd.DataFrame,
    columns: list[str],
    invert_columns: set[str] | None = None,
) -> pd.Series:
    invert_columns = invert_columns or set()
    parts: list[pd.Series] = []
    for column in columns:
        if column not in frame.columns:
            continue
        ranked = _percentile_rank(frame[column])
        if column in invert_columns:
            ranked = 1.0 - ranked
        parts.append(ranked)
    if not parts:
        return pd.Series(0.5, index=frame.index, dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1).astype(float)


def _bounded_state_scale(component: pd.Series, min_scale: float = 0.7, max_scale: float = 1.3) -> pd.Series:
    clean = pd.to_numeric(component, errors="coerce").fillna(0.5).clip(0.0, 1.0)
    return (min_scale + (max_scale - min_scale) * clean).clip(min_scale, max_scale).astype(float)


def _clip_share(series: pd.Series | float) -> pd.Series | float:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce").clip(SHARE_EPSILON, 1.0 - SHARE_EPSILON)
    return float(np.clip(float(series), SHARE_EPSILON, 1.0 - SHARE_EPSILON))


def _logit(series: pd.Series) -> pd.Series:
    clipped = _clip_share(series)
    return np.log(clipped / (1.0 - clipped))


def _expit(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-value)))


def _ensure_transparent_measure_columns(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    fill_candidates = [
        "mean_commute_minutes_state_year",
        "digital_media_minutes_narrow_state_year",
        "screen_leisure_minutes_broad_state_year",
        "in_person_social_minutes_state_year",
        "household_work_minutes_state_year",
        "unpaid_care_minutes_state_year",
        "care_burden_minutes_state_year",
        "search_interest_online_dating_state_year",
    ]
    if {
        "remote_work_share_state_year",
        "mean_commute_minutes_state_year",
    }.issubset(out.columns):
        out["remote_work_share_state_year"] = _clip_share(out["remote_work_share_state_year"])
        out["remote_work_time_saved_one_way_minutes_state_year"] = (
            pd.to_numeric(out["remote_work_share_state_year"], errors="coerce")
            * pd.to_numeric(out["mean_commute_minutes_state_year"], errors="coerce")
        )
        out["remote_work_time_saved_roundtrip_minutes_state_year"] = out["remote_work_time_saved_one_way_minutes_state_year"] * 2.0
        out["commute_time_saved_by_remote_work"] = out["remote_work_time_saved_roundtrip_minutes_state_year"]
    if "digital_media_minutes_narrow_state_year" not in out.columns and "digital_media_minutes_narrow" in out.columns:
        out["digital_media_minutes_narrow_state_year"] = out["digital_media_minutes_narrow"]
    if "screen_leisure_minutes_broad_state_year" not in out.columns:
        if "screen_leisure_minutes_broad" in out.columns:
            out["screen_leisure_minutes_broad_state_year"] = out["screen_leisure_minutes_broad"]
        elif "digital_distraction_minutes_state_year" in out.columns:
            out["screen_leisure_minutes_broad_state_year"] = out["digital_distraction_minutes_state_year"]
    if "in_person_social_minutes_state_year" not in out.columns and "face_to_face_social_minutes_state_year" in out.columns:
        out["in_person_social_minutes_state_year"] = out["face_to_face_social_minutes_state_year"]
    if "mean_commute_minutes_state_year" in out.columns and "mean_commute_baseline" in out.columns:
        out["mean_commute_minutes_state_year"] = pd.to_numeric(out["mean_commute_minutes_state_year"], errors="coerce").fillna(
            pd.to_numeric(out["mean_commute_baseline"], errors="coerce")
        )
    if "household_work_minutes_state_year" not in out.columns and "household_work_minutes" in out.columns:
        out["household_work_minutes_state_year"] = out["household_work_minutes"]
    if "unpaid_care_minutes_state_year" not in out.columns and "unpaid_care_minutes" in out.columns:
        out["unpaid_care_minutes_state_year"] = out["unpaid_care_minutes"]
    if "care_burden_minutes_state_year" not in out.columns:
        care_parts = [
            column for column in ["household_work_minutes_state_year", "unpaid_care_minutes_state_year"] if column in out.columns
        ]
        if care_parts:
            out["care_burden_minutes_state_year"] = out[care_parts].sum(axis=1, min_count=1)
    for column in fill_candidates:
        if column not in out.columns:
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce")
        out[column] = out.groupby("state_fips")[column].transform(lambda series: series.ffill().bfill())
        if "region" in out.columns:
            out[column] = out[column].fillna(out.groupby(["region", "year"])[column].transform("mean"))
        out[column] = out[column].fillna(out.groupby("year")[column].transform("mean"))
        out[column] = out[column].fillna(out[column].mean())
        if column == "mean_commute_minutes_state_year":
            out[column] = out[column].fillna(pd.to_numeric(out.get("mean_commute_baseline"), errors="coerce"))
            out[column] = out[column].fillna(25.0)
    if "remote_work_share_state_year" in out.columns:
        out["remote_work_share_state_year"] = _clip_share(out["remote_work_share_state_year"])
    if {
        "remote_work_share_state_year",
        "mean_commute_minutes_state_year",
    }.issubset(out.columns):
        out["remote_work_time_saved_one_way_minutes_state_year"] = (
            pd.to_numeric(out["remote_work_share_state_year"], errors="coerce")
            * pd.to_numeric(out["mean_commute_minutes_state_year"], errors="coerce")
        )
        out["remote_work_time_saved_roundtrip_minutes_state_year"] = out["remote_work_time_saved_one_way_minutes_state_year"] * 2.0
        out["commute_time_saved_by_remote_work"] = out["remote_work_time_saved_roundtrip_minutes_state_year"]
    return out


SCENARIOS_WITH_STATE_SPECIFIC_SCALING = {
    "remote_work_dominant",
    "distraction_dominant",
    "digital_social_substitution",
    "in_person_revival",
    "gendered_care_penalty",
}


def _build_state_specific_override_scales(
    baseline_rows: pd.DataFrame,
    scenario_name: str,
) -> pd.DataFrame:
    scale_cols = baseline_rows[["state_fips"]].copy()
    default_scale = pd.Series(1.0, index=baseline_rows.index, dtype=float)
    scale_targets = list(dict.fromkeys(EXPOSURE_INDEX_COLUMNS + TRANSPARENT_SCENARIO_COLUMNS))

    if scenario_name not in SCENARIOS_WITH_STATE_SPECIFIC_SCALING:
        for column in scale_targets:
            scale_cols[f"scenario_scale_{column}"] = default_scale
        return scale_cols

    # digital_access_index and digital_use_prevalence_index are excluded here on purpose: no raw
    # NTIA/ACS digital-access table is wired into the pipeline, so both columns are 100% missing in
    # every panel. _mean_rank_component would silently fill them with a neutral 0.5 rank, diluting
    # these state-specific scales toward the mean instead of contributing real signal. Once a real
    # source populates them, they can be added back here.
    remote_readiness = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["remote_work_exposure_index"],
        )
    )
    commute_relief = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["commute_burden_index", "in_person_work_exposure_index", "population_growth_rate"],
        )
    )
    flexibility_gain = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["remote_work_exposure_index", "work_family_compatibility_proxy"],
            invert_columns={"work_family_compatibility_proxy"},
        )
    )
    distraction_intensity = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["digital_distraction_index"],
        ),
        min_scale=0.8,
        max_scale=1.25,
    )
    online_matching = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["digital_social_index", "married_or_partnered_share_state_year"],
        ),
        min_scale=0.8,
        max_scale=1.25,
    )
    in_person_rebound = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["in_person_social_index", "married_or_partnered_share_state_year", "population_growth_rate"],
        )
    )
    care_pressure = _bounded_state_scale(
        _mean_rank_component(
            baseline_rows,
            ["care_burden_minutes_state_year", "remote_work_share_state_year", "female_employment_rate"],
        )
    )

    scale_map = {
        "remote_work_exposure_index": remote_readiness,
        "remote_work_share_state_year": remote_readiness,
        "in_person_work_exposure_index": commute_relief,
        "mean_commute_minutes_state_year": commute_relief,
        "remote_work_time_saved_roundtrip_minutes_state_year": commute_relief,
        "remote_work_time_saved_one_way_minutes_state_year": commute_relief,
        "commute_time_saved_by_remote_work": commute_relief,
        "digital_distraction_index": distraction_intensity,
        "digital_media_minutes_narrow_state_year": distraction_intensity,
        "screen_leisure_minutes_broad_state_year": distraction_intensity,
        "digital_social_index": online_matching,
        "search_interest_online_dating_state_year": online_matching,
        "in_person_social_index": in_person_rebound,
        "in_person_social_minutes_state_year": in_person_rebound,
        # digital_access_index / digital_use_prevalence_index are intentionally left out of this
        # map (see comment above): they stay all-missing legacy columns and fall through to
        # default_scale=1.0, which is a no-op since their underlying values are never finite anyway.
        "commute_burden_index": commute_relief,
        "work_family_compatibility_proxy": flexibility_gain,
        "gendered_care_risk_proxy": care_pressure,
        "household_work_minutes_state_year": care_pressure,
        "unpaid_care_minutes_state_year": care_pressure,
        "care_burden_minutes_state_year": care_pressure,
    }
    for column in scale_targets:
        scale_cols[f"scenario_scale_{column}"] = scale_map.get(column, default_scale)
    return scale_cols


def _state_recent_slope(df: pd.DataFrame, column: str, recent_years: int = 5) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    rows = []
    for state_fips, group in df[["state_fips", "year", column]].dropna().groupby("state_fips", sort=False):
        recent = group.sort_values("year").tail(recent_years)
        if len(recent) < 2:
            slope = 0.0
        else:
            x = recent["year"].to_numpy(dtype=float)
            y = recent[column].to_numpy(dtype=float)
            slope = np.polyfit(x, y, deg=1)[0]
        rows.append({"state_fips": state_fips, f"{column}_baseline_slope": float(slope)})
    return pd.DataFrame(rows)


def _state_recent_share_logit_slope(df: pd.DataFrame, column: str, recent_years: int = 5) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=["state_fips", f"{column}_logit_baseline_slope"])
    rows = []
    for state_fips, group in df[["state_fips", "year", column]].dropna().groupby("state_fips", sort=False):
        recent = group.sort_values("year").tail(recent_years).copy()
        if len(recent) < 2:
            slope = 0.0
        else:
            x = recent["year"].to_numpy(dtype=float)
            y = _logit(recent[column]).to_numpy(dtype=float)
            slope = np.polyfit(x, y, deg=1)[0]
        rows.append({"state_fips": state_fips, f"{column}_logit_baseline_slope": float(slope)})
    return pd.DataFrame(rows)


def _state_recent_growth_rate(df: pd.DataFrame, column: str, recent_years: int = 5) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=["state_fips", f"{column}_baseline_growth"])
    rows = []
    for state_fips, group in df[["state_fips", "year", column]].dropna().groupby("state_fips", sort=False):
        series = group.sort_values("year")[column].pct_change().dropna().tail(max(recent_years - 1, 1))
        rows.append(
            {
                "state_fips": state_fips,
                f"{column}_baseline_growth": float(series.mean()) if not series.empty and np.isfinite(series.mean()) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _prepare_baselines(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["state_fips", "year"]).copy()
    last_rows = out.groupby("state_fips", as_index=False).tail(1).copy()
    for column in list(dict.fromkeys(EXPOSURE_INDEX_COLUMNS + TRANSPARENT_SCENARIO_COLUMNS + ["fertility_rate"])):
        slopes = _state_recent_slope(out, column)
        if not slopes.empty:
            last_rows = last_rows.merge(slopes, on="state_fips", how="left")
    share_logit_slopes = _state_recent_share_logit_slope(out, "remote_work_share_state_year")
    if not share_logit_slopes.empty:
        last_rows = last_rows.merge(share_logit_slopes, on="state_fips", how="left")
    for column in ["female_population_15_44", "total_population"]:
        growth = _state_recent_growth_rate(out, column)
        if not growth.empty:
            last_rows = last_rows.merge(growth, on="state_fips", how="left")
    return last_rows


def _resolve_growth_overrides(
    scenario_name: str,
    annual_growth_overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    annual_growth_overrides = annual_growth_overrides or {}
    if scenario_name == "user_defined":
        return {
            SCENARIO_FEATURE_MAP[key]: value
            for key, value in annual_growth_overrides.items()
            if key in SCENARIO_FEATURE_MAP
        }
    spec = SCENARIO_SPECS.get(scenario_name, SCENARIO_SPECS["baseline_continuation"])
    return dict(spec.get("growth_overrides", {}))


def _resolve_transparent_growth_overrides(scenario_name: str) -> dict[str, float]:
    return dict(TRANSPARENT_SCENARIO_GROWTH_OVERRIDES.get(scenario_name, {}))


def build_future_covariate_scenarios(
    panel: pd.DataFrame,
    scenario_name: str = "baseline_continuation",
    annual_growth_overrides: dict[str, float] | None = None,
    end_year: int = DEFAULT_FORECAST_END_YEAR,
    save_path: str | Path | None = None,
) -> pd.DataFrame:
    historical = _ensure_transparent_measure_columns(panel.sort_values(["state_fips", "year"]).copy())
    if historical.empty:
        return historical
    latest_year = int(historical["year"].max())
    baseline_rows = _prepare_baselines(historical)
    overrides = _resolve_growth_overrides(scenario_name, annual_growth_overrides=annual_growth_overrides)
    transparent_overrides = _resolve_transparent_growth_overrides(scenario_name)
    override_scales = _build_state_specific_override_scales(baseline_rows, scenario_name)
    baseline_rows = baseline_rows.merge(override_scales, on="state_fips", how="left")

    rows = []
    for _, last_row in baseline_rows.iterrows():
        current = last_row.copy()
        state_fips = str(last_row["state_fips"]).zfill(2)
        for years_elapsed, year in enumerate(range(latest_year, end_year + 1)):
            record = current.to_dict()
            record["state_fips"] = state_fips
            record["state_name"] = last_row.get("state_name")
            record["region"] = last_row.get("region")
            record["year"] = year
            record["scenario_name"] = scenario_name
            record["scenario_label"] = SCENARIO_SPECS.get(scenario_name, SCENARIO_SPECS["baseline_continuation"])["label"]
            record["scenario_input_type"] = "user_defined" if scenario_name == "user_defined" else "template"
            record["covariate_status"] = "user_specified_scenario_assumption" if year > latest_year else "observed_anchor"
            rows.append(record)

            decay = OVERRIDE_DECAY_RATE ** years_elapsed
            next_values = current.copy()
            for column in EXPOSURE_INDEX_COLUMNS:
                slope = float(current.get(f"{column}_baseline_slope", 0.0) or 0.0)
                override = float(overrides.get(column, 0.0))
                override_scale = float(current.get(f"scenario_scale_{column}", 1.0) or 1.0)
                current_value = float(current.get(column, np.nan))
                if np.isfinite(current_value):
                    next_values[column] = current_value + slope + (override * override_scale * decay)
            for column in TRANSPARENT_SCENARIO_COLUMNS:
                if column in {
                    "remote_work_share_state_year",
                    "remote_work_time_saved_one_way_minutes_state_year",
                    "remote_work_time_saved_roundtrip_minutes_state_year",
                    "commute_time_saved_by_remote_work",
                    "care_burden_minutes_state_year",
                }:
                    continue
                slope = float(current.get(f"{column}_baseline_slope", 0.0) or 0.0)
                override = float(transparent_overrides.get(column, 0.0))
                override_scale = float(current.get(f"scenario_scale_{column}", 1.0) or 1.0)
                current_value = float(current.get(column, np.nan))
                if np.isfinite(current_value):
                    next_values[column] = current_value + slope + (override * override_scale * decay)
            current_share = float(current.get("remote_work_share_state_year", np.nan))
            if np.isfinite(current_share):
                share_logit = float(np.log(_clip_share(current_share) / (1.0 - _clip_share(current_share))))
                share_slope = float(current.get("remote_work_share_state_year_logit_baseline_slope", 0.0) or 0.0)
                baseline_next_share = _expit(share_logit + share_slope)
                share_override = float(transparent_overrides.get("remote_work_share_state_year", 0.0))
                share_override_scale = float(current.get("scenario_scale_remote_work_share_state_year", 1.0) or 1.0)
                bounded_next_share = baseline_next_share + (share_override * share_override_scale * decay)
                next_values["remote_work_share_state_year"] = _clip_share(bounded_next_share)
            remote_share = float(next_values.get("remote_work_share_state_year", np.nan))
            commute_minutes = float(next_values.get("mean_commute_minutes_state_year", np.nan))
            if np.isfinite(remote_share) and np.isfinite(commute_minutes):
                next_values["remote_work_time_saved_one_way_minutes_state_year"] = remote_share * commute_minutes
                next_values["remote_work_time_saved_roundtrip_minutes_state_year"] = remote_share * commute_minutes * 2.0
                next_values["commute_time_saved_by_remote_work"] = next_values["remote_work_time_saved_roundtrip_minutes_state_year"]
            household_work = float(next_values.get("household_work_minutes_state_year", np.nan))
            unpaid_care = float(next_values.get("unpaid_care_minutes_state_year", np.nan))
            if np.isfinite(household_work) or np.isfinite(unpaid_care):
                next_values["care_burden_minutes_state_year"] = np.nansum([household_work, unpaid_care])
            if np.isfinite(float(next_values.get("screen_leisure_minutes_broad_state_year", np.nan))):
                next_values["digital_distraction_minutes_state_year"] = next_values["screen_leisure_minutes_broad_state_year"]
            if np.isfinite(float(next_values.get("in_person_social_minutes_state_year", np.nan))):
                next_values["face_to_face_social_minutes_state_year"] = next_values["in_person_social_minutes_state_year"]
            fertility_slope = float(current.get("fertility_rate_baseline_slope", 0.0) or 0.0)
            current_fertility = float(current.get("fertility_rate", np.nan))
            if np.isfinite(current_fertility):
                next_values["fertility_rate_baseline_seed"] = current_fertility + fertility_slope
                next_values["fertility_rate"] = current_fertility + fertility_slope
            for column in ["female_population_15_44", "total_population"]:
                current_value = float(current.get(column, np.nan))
                growth = float(current.get(f"{column}_baseline_growth", 0.0) or 0.0)
                if np.isfinite(current_value):
                    next_values[column] = current_value * (1.0 + growth)
            current = next_values

    scenarios = pd.DataFrame(rows).sort_values(["scenario_name", "state_fips", "year"]).reset_index(drop=True)
    target = Path(save_path) if save_path else SCENARIO_SAVE_PATH
    cache_dataframe(scenarios, target)
    return scenarios
