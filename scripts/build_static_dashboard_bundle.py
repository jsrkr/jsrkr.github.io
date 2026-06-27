from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_acs import restrict_to_dashboard_acs_window
from src.config import MODEL_ARTIFACTS_DIR, SCENARIO_DEFAULTS, STATE_FIPS_TO_ABBR, STATE_FIPS_TO_NAME, STATE_RECORDS
from src.ml_models import RECURSIVE_FORECAST_CEILING, RECURSIVE_FORECAST_FLOOR


DASHBOARD_SCENARIOS = [
    {
        "id": "reference_path",
        "source_scenario": "baseline_continuation",
        "label": "Reference path",
        "short_label": "Reference path",
        "hypothesis": "Observed state trends and current covariates continue without an additional scenario shift.",
    },
    {
        "id": "remote_work_saves_time",
        "source_scenario": "remote_work_dominant",
        "label": "Remote work saves time",
        "short_label": "Remote work saves time",
        "hypothesis": "A theory-guided scenario where higher remote-work share saves commuting time and raises schedule flexibility. The displayed adjustment uses the change in remote-work time saved relative to the reference path and is calibrated to CPS remote-work fertility benchmarks.",
    },
    {
        "id": "digital_distraction_crowds_out",
        "source_scenario": "distraction_dominant",
        "label": "Screen leisure crowds out in-person life",
        "short_label": "Screen leisure",
        "hypothesis": "Uses ATUS-based screen-leisure minutes as a broad proxy for digital leisure. Higher screen leisure can reduce time available for in-person interaction.",
    },
    {
        "id": "online_life_helps_matching",
        "source_scenario": "digital_social_substitution",
        "label": "Online life helps matching",
        "short_label": "Online life helps matching",
        "hypothesis": "Digital social tools and online-dating search attention may help people meet partners or maintain relationships. The displayed adjustment uses the change in a Google Trends online-dating search-interest proxy relative to the reference path.",
    },
    {
        "id": "home_centered_digital_life_increases_care_work",
        "source_scenario": "gendered_care_penalty",
        "label": "More time at home increases care work",
        "short_label": "Care work at home",
        "hypothesis": "Remote work, online services and shopping, and digital entertainment can all reduce the need to go outside and increase time spent at home. This scenario uses ATUS-based household-work and unpaid-care minutes (plus a small ATUS screen-leisure component and an offsetting remote-work flexibility credit) to show whether the added at-home/care burden pushes fertility below the reference path.",
    },
]

# Renamed dashboard scenario IDs, kept so old bookmarked links and downloads built against the
# previous scenario key keep resolving to the same scenario instead of silently failing.
SCENARIO_ID_ALIASES = {
    "remote_work_increases_care_burden": "home_centered_digital_life_increases_care_work",
}

DASHBOARD_MODELS = [
    {
        "id": "statistical_ridge",
        "label": "Statistical baseline",
        "kind": "statistical",
        "metadata_file": "statistical_ridge_metadata.json",
        "note": "Traditional statistical reference path built from observed state trends and covariates.",
    },
    {
        "id": "tree_gradient_boosting",
        "label": "Tree ML benchmark",
        "kind": "tree_ml",
        "metadata_file": "tree_gradient_boosting_metadata.json",
        "note": "Flexible predictive benchmark for nonlinear patterns.",
    },
    {
        "id": "temporal_neural_net",
        "label": "Neural network benchmark",
        "kind": "neural_network",
        "metadata_file": "temporal_neural_net_metadata.json",
        "note": "Exploratory nonlinear predictive benchmark.",
    },
]

MECHANISM_LABELS = {
    "mechanism_remote_work_flexibility": "remote-work time saved",
    "mechanism_digital_distraction": "screen leisure",
    "mechanism_online_matching": "online matching / digital social life",
    "mechanism_in_person_social": "in-person social interaction",
    "mechanism_care_burden": "care burden",
}

REMOTE_WORK_CPS_CALIBRATION_OPTIONS = {
    "conservative": {
        "label": "Conservative",
        "births_per_1000_per_1sd": 0.256923795041114,
        "period": "post2022plus_vs_precovid",
        "description": "Post-pandemic CPS benchmark",
    },
    "medium": {
        "label": "Medium",
        "births_per_1000_per_1sd": (0.256923795041114 + 0.4991124948174195) / 2.0,
        "period": "average_of_post_and_pandemic",
        "description": "Average of post-pandemic and pandemic CPS benchmarks",
    },
    "high": {
        "label": "High",
        "births_per_1000_per_1sd": 0.4991124948174195,
        "period": "during2020_2021_vs_precovid",
        "description": "Pandemic CPS benchmark",
    },
}
REMOTE_WORK_DEFAULT_CALIBRATION = "conservative"
REMOTE_WORK_SCENARIO_UNIT = "average round-trip commute minutes saved per employed worker per workday"
REMOTE_WORK_CALIBRATION_SOURCE = {
    "file": "data/wfh_exposure/cps_icpsr_remote_fertility_results/did_results_remote_mean_only.csv",
    "outcome": "birth_event_detected",
    "exposure": "remote_mean_occ2010",
    "fe_type": "state",
    "default_term": "exp_post2022plus",
    "high_term": "exp_during2020_2021",
}

SCENARIO_ADJUSTMENT_SPECS = {
    "remote_work_saves_time": {
        "formula_type": "delta_remote_work_time_saved_only",
        "mechanism": "mechanism_remote_work_flexibility",
        "calibration_level": REMOTE_WORK_DEFAULT_CALIBRATION,
        "beta_remote": REMOTE_WORK_CPS_CALIBRATION_OPTIONS[REMOTE_WORK_DEFAULT_CALIBRATION]["births_per_1000_per_1sd"],
        "unit": REMOTE_WORK_SCENARIO_UNIT,
    },
    "digital_distraction_crowds_out": [
        {"column": "screen_leisure_minutes_broad_state_year", "theta": 0.24, "sign": -1.0, "mechanism": "mechanism_digital_distraction"},
        {"column": "digital_media_minutes_narrow_state_year", "theta": 0.10, "sign": -1.0, "mechanism": "mechanism_digital_distraction"},
        {"column": "in_person_social_minutes_state_year", "theta": 0.12, "sign": 1.0, "mechanism": "mechanism_in_person_social"},
    ],
    # Calibrated so a one-standard-deviation rise in online-dating search attention relative to the
    # reference path lifts the general fertility rate by ~0.35 births per 1,000 women. This puts the
    # matching channel on a comparable, visible footing with the other transparent scenarios (whose
    # combined thetas land near 0.3-0.45) instead of collapsing to a near-zero shift, while staying a
    # modest, clearly-labeled assumption rather than a causal estimate.
    "online_life_helps_matching": [
        {"column": "search_interest_online_dating_state_year", "theta": 0.35, "sign": 1.0, "mechanism": "mechanism_online_matching"},
    ],
    "home_centered_digital_life_increases_care_work": [
        {"column": "care_burden_minutes_state_year", "theta": 0.20, "sign": -1.0, "mechanism": "mechanism_care_burden"},
        {"column": "screen_leisure_minutes_broad_state_year", "theta": 0.05, "sign": -1.0, "mechanism": "mechanism_care_burden"},
        {"column": "remote_work_share_state_year", "theta": 0.05, "sign": 1.0, "mechanism": "mechanism_remote_work_flexibility"},
    ],
}

PUBLIC_INPUT_LABELS = {
    "remote_work_share_state_year": "remote_work_share",
    "remote_work_time_saved_roundtrip_minutes_state_year": "remote_work_time_saved",
    "mean_commute_minutes_state_year": "mean_commute_minutes_state_year",
    "digital_media_minutes_narrow_state_year": "digital_media_minutes_narrow",
    "screen_leisure_minutes_broad_state_year": "screen_leisure_minutes_broad",
    "in_person_social_minutes_state_year": "in_person_social_minutes",
    "care_burden_minutes_state_year": "care_burden_minutes",
    "unpaid_care_minutes_state_year": "unpaid_care_minutes",
    "household_work_minutes_state_year": "household_work_minutes",
    "search_interest_online_dating_state_year": "dating_search_interest",
}

PUBLIC_FORECAST_RECORD_COLUMNS = [
    "geography_type",
    "state_fips",
    "state_abbr",
    "state_name",
    "year",
    "model",
    "scenario",
    "reference_path",
    "scenario_path",
    "scenario_difference",
    "legacy_model_scenario_difference",
    "main_driver",
    "commute_minutes_quality_state_year",
    *MECHANISM_LABELS.keys(),
]


def _series_rows(df: pd.DataFrame, value_cols: list[str]) -> list[dict]:
    keep_cols = ["year", *value_cols]
    subset = df[keep_cols].copy().sort_values("year")
    return json.loads(subset.to_json(orient="records"))


def _latest_non_null(df: pd.DataFrame, value_col: str) -> tuple[int | None, float | None]:
    subset = df.loc[df[value_col].notna(), ["year", value_col]].sort_values("year")
    if subset.empty:
        return None, None
    row = subset.iloc[-1]
    return int(row["year"]), float(row[value_col])


def _load_preferred_acs_panel() -> pd.DataFrame:
    preferred_path = PROJECT_ROOT / "data" / "processed" / "acs_state_year_from_acs.parquet"
    fallback_path = PROJECT_ROOT / "data" / "processed" / "acs_state_year.parquet"
    if preferred_path.exists():
        return restrict_to_dashboard_acs_window(pd.read_parquet(preferred_path))
    return restrict_to_dashboard_acs_window(pd.read_parquet(fallback_path))


def _load_model_metadata(metadata_file: str) -> dict:
    path = MODEL_ARTIFACTS_DIR / metadata_file
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_delta(frame: pd.DataFrame, current_col: str, baseline_col: str) -> pd.Series:
    return frame[current_col].fillna(0.0) - frame[baseline_col].fillna(0.0)


def _max_abs_label(row: pd.Series) -> str:
    best_key = None
    best_value = -1.0
    for key in MECHANISM_LABELS:
        value = abs(float(row.get(key, 0.0) or 0.0))
        if value > best_value:
            best_value = value
            best_key = key
    if not best_key or best_value <= 1e-10:
        return "observed state trend"
    return MECHANISM_LABELS[best_key]


def _safe_std(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    std = float(numeric.std(ddof=0)) if numeric.notna().any() else float("nan")
    return std if pd.notna(std) and std > 0 else 1.0


def _remote_work_calibration_metadata() -> dict:
    default = REMOTE_WORK_CPS_CALIBRATION_OPTIONS[REMOTE_WORK_DEFAULT_CALIBRATION]
    return {
        "default_level": REMOTE_WORK_DEFAULT_CALIBRATION,
        "default_label": default["label"],
        "default_births_per_1000_per_1sd": default["births_per_1000_per_1sd"],
        "unit": REMOTE_WORK_SCENARIO_UNIT,
        "source": REMOTE_WORK_CALIBRATION_SOURCE,
        "options": REMOTE_WORK_CPS_CALIBRATION_OPTIONS,
        "formula": (
            "scenario_adjustment = beta_remote * standardized(delta_remote_work_time_saved), "
            "where delta_remote_work_time_saved = "
            "(remote_work_share_scenario - remote_work_share_reference) * "
            "reference_mean_commute_minutes_state_year * 2"
        ),
    }


def _summarize_commute_quality(values: pd.Series) -> str:
    non_null = values.dropna().astype(str)
    if non_null.empty:
        return "national fallback"
    unique = list(dict.fromkeys(non_null.tolist()))
    label_map = {
        "observed": "state-specific ACS values",
        "state_smoothed": "smoothed state values",
        "region_fallback": "region fallback",
        "national_fallback": "national fallback",
    }
    translated = [label_map.get(value, value.replace("_", " ")) for value in unique]
    return ", ".join(translated)


def _scenario_adjustment_input_columns() -> list[str]:
    columns = {
        "state_fips",
        "state_name",
        "year",
        "scenario_name",
        "remote_work_share_state_year",
        "mean_commute_minutes_state_year",
        "commute_minutes_quality_state_year",
        "commute_minutes_source_state_year",
        "remote_work_time_saved_roundtrip_minutes_state_year",
        "digital_media_minutes_narrow_state_year",
        "screen_leisure_minutes_broad_state_year",
        "in_person_social_minutes_state_year",
        "care_burden_minutes_state_year",
        "unpaid_care_minutes_state_year",
        "household_work_minutes_state_year",
        "search_interest_online_dating_state_year",
        "sample_size",
        "respondent_count_unweighted",
    }
    return sorted(columns)


def _build_scenario_mechanism_frame(scenario_covariates: pd.DataFrame) -> pd.DataFrame:
    scenario_lookup = {item["source_scenario"]: item for item in DASHBOARD_SCENARIOS}
    selected_sources = list(scenario_lookup)
    scenario_subset = scenario_covariates.loc[
        scenario_covariates["scenario_name"].isin(selected_sources),
        [column for column in _scenario_adjustment_input_columns() if column in scenario_covariates.columns],
    ].copy()

    baseline = scenario_subset.loc[scenario_subset["scenario_name"].eq("baseline_continuation")].copy()
    baseline_scale_lookup = {
        column: _safe_std(baseline[column])
        for column in scenario_subset.columns
        if column not in {"state_fips", "state_name", "year", "scenario_name"} and column in baseline.columns
    }
    baseline = baseline.rename(
        columns={
            **{column: f"reference_{column}" for column in baseline.columns if column not in {"state_fips", "state_name", "year", "scenario_name"}},
            "scenario_name": "reference_scenario_name",
        }
    )

    merged = scenario_subset.merge(baseline, on=["state_fips", "year"], how="left")
    for mechanism in MECHANISM_LABELS:
        merged[mechanism] = 0.0

    for source_name, definition in scenario_lookup.items():
        scenario_id = definition["id"]
        mask = merged["scenario_name"].eq(source_name)
        component_specs = SCENARIO_ADJUSTMENT_SPECS.get(scenario_id, [])

        if scenario_id == "remote_work_saves_time":
            remote_spec = SCENARIO_ADJUSTMENT_SPECS["remote_work_saves_time"]
            share_col = "remote_work_share_state_year"
            reference_share_col = f"reference_{share_col}"
            commute_col = "reference_mean_commute_minutes_state_year"
            if share_col in merged.columns and reference_share_col in merged.columns and commute_col in merged.columns:
                delta_share = _safe_delta(merged, share_col, reference_share_col)
                reference_commute = pd.to_numeric(merged[commute_col], errors="coerce").fillna(0.0)
                delta_remote_work_time_saved = delta_share * reference_commute * 2.0
                scale = baseline_scale_lookup.get("remote_work_time_saved_roundtrip_minutes_state_year", 1.0)
                contribution = remote_spec["beta_remote"] * (delta_remote_work_time_saved / scale)
                merged.loc[mask, remote_spec["mechanism"]] = contribution.loc[mask].astype(float)
                merged.loc[mask, "contribution_remote_work_time_saved"] = contribution.loc[mask].astype(float)
                merged.loc[mask, "delta_remote_work_time_saved"] = delta_remote_work_time_saved.loc[mask].astype(float)
                merged.loc[mask, "delta_remote_work_share"] = delta_share.loc[mask].astype(float)
                merged.loc[mask, "remote_work_share"] = pd.to_numeric(merged.loc[mask, share_col], errors="coerce")
                merged.loc[mask, "reference_remote_work_share"] = pd.to_numeric(
                    merged.loc[mask, reference_share_col],
                    errors="coerce",
                )
                merged.loc[mask, "remote_work_time_saved"] = pd.to_numeric(
                    merged.loc[mask, "remote_work_time_saved_roundtrip_minutes_state_year"],
                    errors="coerce",
                )
                merged.loc[mask, "reference_remote_work_time_saved"] = pd.to_numeric(
                    merged.loc[mask, "reference_remote_work_time_saved_roundtrip_minutes_state_year"],
                    errors="coerce",
                )
                merged.loc[mask, "mean_commute_minutes_state_year"] = pd.to_numeric(
                    merged.loc[mask, "mean_commute_minutes_state_year"],
                    errors="coerce",
                )
                merged.loc[mask, "reference_mean_commute_minutes_state_year"] = pd.to_numeric(
                    merged.loc[mask, commute_col],
                    errors="coerce",
                )
                merged.loc[mask, "remote_work_scenario_adjustment_formula"] = remote_spec["formula_type"]
                merged.loc[mask, "remote_work_scenario_calibration_level"] = remote_spec["calibration_level"]
                merged.loc[mask, "remote_work_scenario_beta_remote"] = remote_spec["beta_remote"]
                merged.loc[mask, "remote_work_time_saved_unit"] = remote_spec["unit"]
            continue

        for spec in component_specs:
            current_col = spec["column"]
            reference_col = f"reference_{current_col}"
            if current_col not in merged.columns or reference_col not in merged.columns:
                continue
            scale = baseline_scale_lookup.get(current_col, 1.0)
            contribution = spec["sign"] * spec["theta"] * (
                _safe_delta(merged, current_col, reference_col) / scale
            )
            merged.loc[mask, spec["mechanism"]] = merged.loc[mask, spec["mechanism"]].astype(float) + contribution.loc[mask].astype(float)
            public_label = PUBLIC_INPUT_LABELS.get(current_col, current_col)
            merged.loc[mask, f"contribution_{public_label}"] = contribution.loc[mask].astype(float)
            merged.loc[mask, f"delta_{public_label}"] = _safe_delta(merged, current_col, reference_col).loc[mask].astype(float)
            merged.loc[mask, public_label] = pd.to_numeric(merged.loc[mask, current_col], errors="coerce")
            merged.loc[mask, f"reference_{public_label}"] = pd.to_numeric(merged.loc[mask, reference_col], errors="coerce")

    merged["scenario_adjustment_pre_lag"] = merged[list(MECHANISM_LABELS.keys())].sum(axis=1)
    merged["scenario_adjustment_post_lag"] = merged["scenario_adjustment_pre_lag"]
    merged["recursive_lag_multiplier"] = 1.0
    merged["clamping_flag"] = False

    merged["scenario"] = merged["scenario_name"].map(lambda name: scenario_lookup[name]["id"])
    merged["scenario_label"] = merged["scenario_name"].map(lambda name: scenario_lookup[name]["label"])
    merged["main_driver"] = merged.apply(_max_abs_label, axis=1)
    if "state_name" not in merged.columns:
        for candidate in ["state_name_x", "state_name_y", "reference_state_name"]:
            if candidate in merged.columns:
                merged["state_name"] = merged[candidate]
                break
    if "respondent_count_unweighted" not in merged.columns and "sample_size" in merged.columns:
        merged["respondent_count_unweighted"] = merged["sample_size"]

    reference_mask = merged["scenario"].eq("reference_path")
    for column in MECHANISM_LABELS:
        merged.loc[reference_mask, column] = 0.0
    merged.loc[reference_mask, "main_driver"] = "observed state trend"

    keep_cols = [
        "state_fips",
        "state_name",
        "year",
        "scenario_name",
        "scenario",
        "scenario_label",
        "main_driver",
        "scenario_adjustment_pre_lag",
        "scenario_adjustment_post_lag",
        "recursive_lag_multiplier",
        "clamping_flag",
        "sample_size",
        "respondent_count_unweighted",
        *MECHANISM_LABELS.keys(),
    ]
    remaining = [
        column for column in merged.columns
        if (
            column.startswith("contribution_")
            or column.startswith("delta_")
            or column.startswith("reference_")
            or column in PUBLIC_INPUT_LABELS.values()
            or column
            in {
                "commute_minutes_quality_state_year",
                "reference_commute_minutes_quality_state_year",
                "commute_minutes_source_state_year",
                "reference_commute_minutes_source_state_year",
                "remote_work_scenario_adjustment_formula",
                "remote_work_scenario_calibration_level",
                "remote_work_scenario_beta_remote",
                "remote_work_time_saved_unit",
            }
        )
        and column not in keep_cols
    ]
    keep_cols = [column for column in keep_cols if column in merged.columns]
    return merged[keep_cols + remaining].copy()


# A model whose recursive forecast pins this share (or more) of its forecast state-years at the
# floor/ceiling clamp is producing mechanically degenerate paths: reference and scenario paths
# collapse onto the same clamped value, so scenario differences become meaningless. Such a model
# is flagged unreliable in the bundle so the dashboard can warn or hide it.
FORECAST_CLAMP_UNRELIABLE_SHARE = 0.25


def _compute_model_forecast_clamp_shares(predictions: pd.DataFrame, selected_models: list[str]) -> dict[str, dict]:
    forecast = predictions.loc[
        predictions["split"].eq("forecast") & predictions["model_name"].isin(selected_models),
        ["model_name", "predicted_fertility_rate"],
    ].copy()
    shares: dict[str, dict] = {}
    for model_name, group in forecast.groupby("model_name", sort=False):
        values = pd.to_numeric(group["predicted_fertility_rate"], errors="coerce").dropna()
        n = int(len(values))
        if n == 0:
            shares[model_name] = {
                "forecast_clamp_share": None,
                "forecast_clamp_share_ceiling": None,
                "forecast_clamp_share_floor": None,
                "forecast_clamped_heavily": False,
            }
            continue
        at_ceiling = float((values >= RECURSIVE_FORECAST_CEILING - 1e-3).mean())
        at_floor = float((values <= RECURSIVE_FORECAST_FLOOR + 1e-3).mean())
        total = at_ceiling + at_floor
        shares[model_name] = {
            "forecast_clamp_share": total,
            "forecast_clamp_share_ceiling": at_ceiling,
            "forecast_clamp_share_floor": at_floor,
            "forecast_clamped_heavily": bool(total >= FORECAST_CLAMP_UNRELIABLE_SHARE),
        }
    return shares


def _build_forecast_records() -> tuple[list[dict], list[dict], list[dict], list[dict], list[int], str | None]:
    predictions_path = PROJECT_ROOT / "data" / "processed" / "ml_predictions.parquet"
    metrics_path = PROJECT_ROOT / "data" / "processed" / "ml_model_metrics.parquet"
    scenario_covariates_path = PROJECT_ROOT / "data" / "processed" / "scenario_covariates.parquet"

    if not predictions_path.exists() or not scenario_covariates_path.exists():
        return [], [], [], [], [], "Precomputed model outputs have not been added."

    predictions = pd.read_parquet(predictions_path)
    scenario_covariates = pd.read_parquet(scenario_covariates_path)
    metrics = pd.read_parquet(metrics_path) if metrics_path.exists() else pd.DataFrame()

    model_lookup = {item["id"]: item for item in DASHBOARD_MODELS}
    scenario_lookup = {item["source_scenario"]: item for item in DASHBOARD_SCENARIOS}
    selected_models = list(model_lookup)
    selected_scenarios = list(scenario_lookup)

    legacy_forecast = predictions.loc[
        predictions["split"].eq("forecast")
        & predictions["model_name"].isin(selected_models)
        & predictions["scenario_name"].isin(selected_scenarios),
        ["state_fips", "state_name", "year", "model_name", "scenario_name", "predicted_fertility_rate"],
    ].copy()
    if legacy_forecast.empty:
        return [], [], [], [], [], "Precomputed model outputs have not been added."

    reference = legacy_forecast.loc[legacy_forecast["scenario_name"].eq("baseline_continuation")].copy()
    reference = reference.rename(columns={"predicted_fertility_rate": "reference_path"})
    reference = reference.drop(columns=["scenario_name"]).rename(columns={"state_name": "reference_state_name"})

    mechanisms = _build_scenario_mechanism_frame(scenario_covariates)
    merged = reference[["state_fips", "year", "model_name", "reference_path", "reference_state_name"]].merge(
        mechanisms,
        on=["state_fips", "year"],
        how="left",
    )
    legacy_alt = legacy_forecast.rename(columns={"predicted_fertility_rate": "legacy_model_scenario_path"})
    merged = merged.merge(
        legacy_alt[["state_fips", "year", "model_name", "scenario_name", "legacy_model_scenario_path"]],
        on=["state_fips", "year", "model_name", "scenario_name"],
        how="left",
    )
    merged["state_name"] = merged["state_name"].fillna(merged["reference_state_name"])
    merged = merged.drop(columns=["reference_state_name"])

    merged["model"] = merged["model_name"]
    merged["model_label"] = merged["model_name"].map(lambda name: model_lookup[name]["label"])
    merged["legacy_model_scenario_path"] = pd.to_numeric(merged["legacy_model_scenario_path"], errors="coerce")
    merged.loc[merged["scenario"].eq("reference_path"), "legacy_model_scenario_path"] = merged.loc[
        merged["scenario"].eq("reference_path"),
        "reference_path",
    ]
    merged["legacy_model_scenario_difference"] = merged["legacy_model_scenario_path"] - merged["reference_path"]
    merged["scenario_path_unclamped"] = (
        pd.to_numeric(merged["reference_path"], errors="coerce")
        + pd.to_numeric(merged["scenario_adjustment_post_lag"], errors="coerce").fillna(0.0)
    )
    merged["scenario_path"] = merged["scenario_path_unclamped"].clip(RECURSIVE_FORECAST_FLOOR, RECURSIVE_FORECAST_CEILING)
    merged["scenario_difference"] = merged["scenario_path"] - merged["reference_path"]
    merged["scenario_shift_component"] = merged["scenario_difference"]
    merged["manual_adjustment_component"] = 0.0
    merged["clamping_flag"] = (
        pd.to_numeric(merged["scenario_path"], errors="coerce")
        != pd.to_numeric(merged["scenario_path_unclamped"], errors="coerce")
    )
    merged["geography_type"] = "state"
    merged["state_abbr"] = merged["state_fips"].map(STATE_FIPS_TO_ABBR)
    merged["state_name"] = merged["state_name"].fillna(merged["state_fips"].map(STATE_FIPS_TO_NAME))

    merged = merged.sort_values(["state_fips", "model_name", "scenario_name", "year"])
    scenario_diagnostics = _build_scenario_diagnostics(merged)
    forecast_records = json.loads(merged[PUBLIC_FORECAST_RECORD_COLUMNS].to_json(orient="records"))

    available_years = sorted({int(value) for value in merged["year"].dropna().astype(int).tolist()})

    metric_rows: list[dict] = []
    if not metrics.empty:
        metric_subset = metrics.loc[
            metrics["group_type"].eq("overall")
            & metrics["model_name"].isin(selected_models)
            & metrics["split"].isin(["validation", "test", "train"]),
            ["model_name", "split", "rmse", "mae", "mape", "r_squared", "n_obs"],
        ].copy()
        metric_subset["model"] = metric_subset["model_name"]
        metric_subset["model_label"] = metric_subset["model_name"].map(lambda name: model_lookup[name]["label"])
        metric_subset = metric_subset.sort_values(["model_name", "split"])
        metric_rows = json.loads(
            metric_subset[
                ["model", "model_label", "split", "rmse", "mae", "mape", "r_squared", "n_obs"]
            ].to_json(orient="records")
        )

    clamp_shares = _compute_model_forecast_clamp_shares(predictions, selected_models)

    def _test_r_squared(model_id: str) -> float | None:
        if metrics.empty:
            return None
        subset = metrics.loc[
            metrics["group_type"].eq("overall")
            & metrics["model_name"].eq(model_id)
            & metrics["split"].eq("test"),
            "r_squared",
        ]
        if subset.empty:
            return None
        value = float(subset.iloc[0])
        return value if pd.notna(value) else None

    model_rows: list[dict] = []
    available_models = set(merged["model"].dropna().tolist())
    metric_models = set(metrics["model_name"].dropna().tolist()) if not metrics.empty else set()
    for definition in DASHBOARD_MODELS:
        metadata = _load_model_metadata(definition["metadata_file"])
        available = definition["id"] in available_models
        clamp_info = clamp_shares.get(definition["id"], {})
        clamped_heavily = bool(clamp_info.get("forecast_clamped_heavily", False))
        test_r2 = _test_r_squared(definition["id"])
        reliable = (not clamped_heavily) and (test_r2 is None or test_r2 > 0.0)
        performance_note = definition["note"]
        if definition["id"] == "temporal_neural_net":
            if clamped_heavily:
                performance_note = (
                    "Unreliable benchmark: the recursive forecast pins most state-years at the forecast "
                    "clamp, so reference and scenario paths collapse onto the same value. Interpret with caution."
                )
            elif test_r2 is not None and test_r2 >= 0.85:
                performance_note = (
                    "Exploratory nonlinear benchmark. Held-out test performance is now comparable to the "
                    "tree benchmark, but it remains a predictive comparison, not a causal estimate."
                )
            else:
                performance_note = "Exploratory nonlinear predictive benchmark."
        elif clamped_heavily:
            performance_note = (
                "Unreliable benchmark: most forecast state-years sit at the forecast clamp, so scenario "
                "differences are mechanically suppressed."
            )
        model_rows.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "kind": definition["kind"],
                "available": available,
                "has_metrics": definition["id"] in metric_models,
                "description": metadata.get("description", definition["note"]),
                "performance_note": performance_note,
                "train_years": metadata.get("train_years", []),
                "validation_years": metadata.get("validation_years", []),
                "test_years": metadata.get("test_years", []),
                "feature_count": metadata.get("feature_count"),
                "forecast_clamp_share": clamp_info.get("forecast_clamp_share"),
                "forecast_clamp_share_ceiling": clamp_info.get("forecast_clamp_share_ceiling"),
                "forecast_clamp_share_floor": clamp_info.get("forecast_clamp_share_floor"),
                "forecast_clamped_heavily": clamped_heavily,
                "reliable": reliable,
            }
        )

    return forecast_records, scenario_diagnostics, metric_rows, model_rows, available_years, None


def _build_scenario_diagnostics(forecast_source: pd.DataFrame | list[dict]) -> list[dict]:
    if isinstance(forecast_source, pd.DataFrame):
        frame = forecast_source.copy()
    else:
        if not forecast_source:
            return []
        frame = pd.DataFrame(forecast_source)

    if frame.empty:
        return []
    frame = frame[frame.get("geography_type", "state").eq("state")].copy()
    diagnostics: list[dict] = []
    delta_columns = [column for column in frame.columns if column.startswith("delta_")]

    for (model, scenario, year), group in frame.groupby(["model", "scenario", "year"], sort=False):
        diffs = pd.to_numeric(group["scenario_difference"], errors="coerce")
        legacy_diffs = pd.to_numeric(group.get("legacy_model_scenario_difference"), errors="coerce")
        near_zero = diffs.abs() < 0.05
        tiny = diffs.abs() < 0.10
        modest = diffs.abs() < 0.50
        positive = diffs > 0.05
        negative = diffs < -0.05
        input_change = float(group[delta_columns].abs().mean(axis=1, skipna=True).mean()) if delta_columns else float("nan")
        input_dispersion = float(group[delta_columns].std(ddof=0).mean(skipna=True)) if delta_columns else float("nan")

        if scenario == "remote_work_saves_time" and legacy_diffs.notna().any() and float(legacy_diffs.mean()) < -0.01:
            reason = (
                "The earlier negative statistical result came from the legacy predictive scenario package, "
                "which mixed opaque remote-work and screen-life proxies; the current dashboard instead uses "
                "a direct calibration anchored to the change in remote-work time saved relative to the reference path."
            )
        elif near_zero.mean() >= 0.8 and pd.notna(input_change) and input_change < 0.05:
            reason = "Scenario inputs barely change relative to the reference path at this horizon."
        elif near_zero.mean() >= 0.8 and pd.notna(input_dispersion) and input_dispersion < 0.02:
            reason = "Scenario inputs move only slightly across states, so differences behave like a small common shift."
        elif near_zero.mean() >= 0.8:
            reason = "The transparent adjustment is intentionally modest at this horizon, so many state differences remain close to zero."
        else:
            reason = "State-year scenario inputs vary enough to create a visible spread around the reference path."

        diagnostics.append(
            {
                "model": model,
                "scenario": scenario,
                "year": int(year),
                "min_scenario_difference": float(diffs.min()),
                "max_scenario_difference": float(diffs.max()),
                "mean_scenario_difference": float(diffs.mean()),
                "std_scenario_difference": float(diffs.std(ddof=0)),
                "unique_scenario_difference_values_3dp": int(diffs.round(3).nunique()),
                "positive_states": int(positive.sum()),
                "negative_states": int(negative.sum()),
                "zero_or_near_zero_states": int(near_zero.sum()),
                "share_abs_lt_0_05": float(near_zero.mean()),
                "share_abs_lt_0_10": float(tiny.mean()),
                "share_abs_lt_0_50": float(modest.mean()),
                "legacy_mean_scenario_difference": float(legacy_diffs.mean()) if legacy_diffs.notna().any() else None,
                "diagnostic_reason": reason,
            }
        )
    return diagnostics


def _build_atus_screen_leisure_quality_row() -> dict | None:
    # Documents the geography level of the ATUS screen-leisure / digital-media / in-person-social
    # inputs that drive the screen-leisure scenario, so the dashboard never implies these are
    # cleanly observed state-year values when many state-years are modeled or imputed.
    panel_path = PROJECT_ROOT / "data" / "processed" / "ml_state_year_panel.parquet"
    if not panel_path.exists():
        return None
    panel = pd.read_parquet(panel_path, columns=None)
    status_col = "digital_distraction_minutes_status"
    if status_col not in panel.columns:
        return None
    counts = panel[status_col].value_counts(dropna=False).to_dict()
    observed = int(counts.get("observed", 0))
    modeled = int(counts.get("modeled", 0))
    imputed = int(counts.get("imputed", 0))
    missing = int(counts.get("missing", 0))
    latest_year = None
    populated = panel.loc[panel[status_col].isin(["observed", "modeled", "imputed"]), "year"]
    if not populated.empty:
        latest_year = int(populated.max())
    return {
        "source_used": "ATUS time-use activity files",
        "measurement_type": "screen_leisure_and_time_use_minutes",
        "geography_level": "state-year (mix of observed and modeled)",
        "latest_year": latest_year,
        "estimate_mode": (
            f"State-year minutes for screen leisure, narrow digital media, and in-person social time: "
            f"{observed} observed, {modeled} modeled, {imputed} imputed, {missing} filled by region/year/national fallback."
        ),
        "warning_flags": (
            "ATUS is most reliable at the national and regional level. State-year screen-leisure values vary "
            "by state and year but blend directly observed state cells with modeled and fallback values, so "
            "state differences should be read as indicative rather than precise survey estimates."
        ),
    }


def build_bundle() -> dict:
    acs = _load_preferred_acs_panel()
    fertility = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "fertility_metrics.parquet")
    population = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "population_metrics.parquet")
    atus = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "atus_metrics.parquet")
    quality = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "measurement_quality.parquet")
    digital_attention_path = PROJECT_ROOT / "data" / "processed" / "digital_attention.parquet"
    digital_attention = pd.read_parquet(digital_attention_path) if digital_attention_path.exists() else pd.DataFrame()

    remote_rows = []
    for year, group in acs.loc[acs["remote_work_share_state_year"].notna(), ["year", "remote_work_share_state_year", "sample_size"]].groupby("year"):
        remote_rows.append(
            {
                "year": int(year),
                "remote_work_share": float((group["remote_work_share_state_year"] * group["sample_size"]).sum() / group["sample_size"].sum()),
            }
        )
    remote_by_year = pd.DataFrame(remote_rows).sort_values("year")
    us_fertility = fertility.loc[fertility["state_fips"].eq("00")].copy().sort_values("year")
    pop_states = population.loc[population["state_fips"].ne("00") & population["year"].ge(2016)].copy()
    us_population = pop_states.groupby("year", as_index=False)["population_total"].sum().sort_values("year")
    us_population["population_growth_rate"] = us_population["population_total"].pct_change()

    atus_national = atus.loc[atus["geography_type"].eq("national")].copy().sort_values("year")

    latest_remote_year, latest_remote_value = _latest_non_null(remote_by_year, "remote_work_share")
    latest_gfr_year, latest_gfr_value = _latest_non_null(us_fertility, "general_fertility_rate")
    latest_tfr_year, latest_tfr_value = _latest_non_null(us_fertility, "total_fertility_rate_approx")
    latest_pop_year, latest_pop_value = _latest_non_null(us_population, "population_growth_rate")
    latest_distraction_year, latest_distraction_value = _latest_non_null(atus_national, "digital_distraction_minutes")
    latest_social_year, latest_social_value = _latest_non_null(atus_national, "face_to_face_social_minutes")
    latest_home_work_year, latest_home_work_value = _latest_non_null(atus_national, "work_at_home_minutes")
    latest_away_work_year, latest_away_work_value = _latest_non_null(atus_national, "work_away_minutes")
    national_attention = digital_attention.loc[digital_attention.get("state_fips", pd.Series(dtype=str)).eq("00")].copy().sort_values("year")
    latest_genai_year, latest_genai_value = _latest_non_null(national_attention, "search_interest_genai_state_year")
    latest_dating_year, latest_dating_value = _latest_non_null(national_attention, "search_interest_online_dating_state_year")

    states: list[dict] = []
    for record in STATE_RECORDS:
        state_fips = record.fips
        remote_state = acs.loc[acs["state_fips"].eq(state_fips) & acs["remote_work_share_state_year"].notna()].copy().sort_values("year")
        fert_state = fertility.loc[fertility["state_fips"].eq(state_fips)].copy().sort_values("year")
        pop_state = pop_states.loc[
            pop_states["state_fips"].eq(state_fips) & pop_states["population_growth_rate"].notna()
        ].copy().sort_values("year")
        attention_state = digital_attention.loc[digital_attention.get("state_fips", pd.Series(dtype=str)).eq(state_fips)].copy().sort_values("year")

        remote_year, remote_value = _latest_non_null(remote_state, "remote_work_share_state_year")
        gfr_year, gfr_value = _latest_non_null(fert_state, "general_fertility_rate")
        tfr_year, tfr_value = _latest_non_null(fert_state, "total_fertility_rate_approx")
        pop_year, pop_value = _latest_non_null(pop_state, "population_growth_rate")
        genai_year, genai_value = _latest_non_null(attention_state, "search_interest_genai_state_year")
        dating_year, dating_value = _latest_non_null(attention_state, "search_interest_online_dating_state_year")

        states.append(
            {
                "state_fips": state_fips,
                "state_abbr": record.abbreviation,
                "state_name": record.name,
                "region": record.region,
                "latest": {
                    "remote_work_share": remote_value,
                    "remote_work_year": remote_year,
                    "general_fertility_rate": gfr_value,
                    "fertility_year": gfr_year,
                    "total_fertility_rate": tfr_value,
                    "tfr_year": tfr_year,
                    "population_growth_rate": pop_value,
                    "population_year": pop_year,
                    "genai_search_interest": genai_value,
                    "genai_year": genai_year,
                    "dating_search_interest": dating_value,
                    "dating_year": dating_year,
                },
                "fertility_series": _series_rows(fert_state, ["general_fertility_rate", "total_fertility_rate_approx"]),
            }
        )

    quality_rows = []
    for _, row in quality.iterrows():
        quality_rows.append(
            {
                "source_used": row.get("source_used"),
                "measurement_type": row.get("measurement_type"),
                "geography_level": row.get("geography_level"),
                "latest_year": None if pd.isna(row.get("latest_year")) else int(row.get("latest_year")),
                "estimate_mode": row.get("estimate_mode"),
                "warning_flags": row.get("warning_flags"),
            }
        )

    atus_quality_row = _build_atus_screen_leisure_quality_row()
    if atus_quality_row is not None:
        quality_rows.append(atus_quality_row)

    forecast_records, scenario_diagnostics, model_metrics, model_options, available_years, benchmark_note = _build_forecast_records()
    remote_work_forecast = pd.DataFrame(
        [
            record
            for record in forecast_records
            if record.get("scenario") == "remote_work_saves_time" and record.get("geography_type", "state") == "state"
        ]
    )
    commute_quality_summary = _summarize_commute_quality(
        remote_work_forecast.get("commute_minutes_quality_state_year", pd.Series(dtype=object))
    )
    remote_work_calibration = _remote_work_calibration_metadata() | {
        "commute_input_summary": commute_quality_summary,
    }
    horizon_years = [year for year in [2030, 2035, 2040, 2045, 2050, 2055, 2060] if year in available_years]
    if not horizon_years:
        horizon_years = available_years[:]

    bundle = {
        "metadata": {
            "title": "Can digital life reshape fertility?",
            "version": "State scenario dashboard",
            "last_updated": pd.Timestamp.now().strftime("%B %d, %Y"),
            "scope_note": (
                "This is a transparent scenario dashboard, not a causal forecast. It combines observed "
                "state fertility trends, predictive models, and user-chosen scenario assumptions to show "
                "how fertility paths change under different digital-life futures."
            ),
            "scenario_note": (
                "Displayed scenario paths equal the selected model's reference path plus a transparent, theory-guided "
                "scenario adjustment. Remote-work scenarios use the change in remote-work time saved relative to the "
                "reference path, measured in average round-trip commute minutes saved per employed worker per workday; "
                "screen scenarios use ATUS-based digital-media and screen-leisure minutes."
            ),
            "badge": "Scenario tool - not a causal forecast",
            "relationship_note": (
                "Google Trends proxies capture broad state-level online attention, not direct measures of "
                "relationship quality or fertility intentions."
            ),
            "benchmark_note": benchmark_note,
            "remote_work_scenario": remote_work_calibration,
        },
        "scenario_defaults": SCENARIO_DEFAULTS,
        "horizon_years": horizon_years,
        "scenario_options": DASHBOARD_SCENARIOS,
        "scenario_id_aliases": SCENARIO_ID_ALIASES,
        "model_options": model_options,
        "outcome_options": [
            {
                "id": "scenario_difference",
                "label": "Scenario difference from reference path",
                "scale": "delta",
            },
            {
                "id": "scenario_path",
                "label": "Scenario path (GFR level)",
                "scale": "level",
            },
            {
                "id": "reference_path",
                "label": "Reference path (GFR level)",
                "scale": "level",
            },
        ],
        "national": {
            "kpis": [
                {
                    "id": "remote_work_share",
                    "label": "Remote-work share",
                    "value": latest_remote_value,
                    "year": latest_remote_year,
                    "unit": "percent",
                    "note": "Sample-weighted mean across state remote-work shares from the local IPUMS ACS extract for 2014-2024.",
                },
                {
                    "id": "general_fertility_rate",
                    "label": "General fertility rate",
                    "value": latest_gfr_value,
                    "year": latest_gfr_year,
                    "unit": "rate",
                    "note": "Official U.S. fertility rate for women ages 15–44 from the CDC state-year table.",
                },
                {
                    "id": "total_fertility_rate",
                    "label": "Total fertility rate",
                    "value": latest_tfr_value,
                    "year": latest_tfr_year,
                    "unit": "tfr",
                    "note": "Official U.S. total fertility rate from the same CDC state-year table.",
                },
                {
                    "id": "population_growth_rate",
                    "label": "Population growth",
                    "value": latest_pop_value,
                    "year": latest_pop_year,
                    "unit": "percent",
                    "note": "Computed from summed FRED state population totals.",
                },
                {
                    "id": "screen_leisure_minutes_broad",
                    "label": "Screen leisure minutes",
                    "value": latest_distraction_value,
                    "year": latest_distraction_year,
                    "unit": "minutes",
                    "note": "National ATUS broad screen-leisure minutes built from activity codes 120308, 120303, and 120307.",
                },
                {
                    "id": "in_person_social_minutes",
                    "label": "In-person social minutes",
                    "value": latest_social_value,
                    "year": latest_social_year,
                    "unit": "minutes",
                    "note": "National ATUS in-person social minutes from socializing and communicating activities.",
                },
                {
                    "id": "genai_search_interest",
                    "label": "GenAI search proxy",
                    "value": latest_genai_value,
                    "year": latest_genai_year,
                    "unit": "index",
                    "note": "Google Trends proxy for state-calibrated GenAI search attention, aggregated to the U.S. row.",
                },
                {
                    "id": "dating_search_interest",
                    "label": "Dating-app search proxy",
                    "value": latest_dating_value,
                    "year": latest_dating_year,
                    "unit": "index",
                    "note": "Google Trends proxy for state-calibrated online-dating search attention, aggregated to the U.S. row.",
                },
                {
                    "id": "work_at_home_minutes",
                    "label": "Work at home",
                    "value": latest_home_work_value,
                    "year": latest_home_work_year,
                    "unit": "minutes",
                    "note": "National ATUS work-at-home minutes.",
                },
                {
                    "id": "work_away_minutes",
                    "label": "Work away",
                    "value": latest_away_work_value,
                    "year": latest_away_work_year,
                    "unit": "minutes",
                    "note": "National ATUS work-away-from-home minutes.",
                },
            ],
            "remote_series": _series_rows(remote_by_year, ["remote_work_share"]),
            "fertility_series": _series_rows(us_fertility, ["general_fertility_rate", "total_fertility_rate_approx"]),
            "population_series": _series_rows(us_population, ["population_growth_rate", "population_total"]),
            "atus_series": _series_rows(
                atus_national,
                [
                    "digital_media_minutes_narrow",
                    "screen_leisure_minutes_broad",
                    "digital_distraction_minutes",
                    "face_to_face_social_minutes",
                    "in_person_social_minutes",
                    "work_at_home_minutes",
                    "work_away_minutes",
                    "time_alone_minutes",
                ],
            ),
            "attention_series": _series_rows(
                national_attention,
                ["search_interest_genai_state_year", "search_interest_online_dating_state_year", "digital_attention_proxy_index"],
            ),
        },
        "states": states,
        "forecast_records": forecast_records,
        "scenario_diagnostics": scenario_diagnostics,
        "model_metrics": model_metrics,
        "quality_panel": quality_rows,
        "state_lookup": {
            "fips_to_abbr": STATE_FIPS_TO_ABBR,
            "fips_to_name": STATE_FIPS_TO_NAME,
        },
    }
    return bundle


def main() -> None:
    bundle = build_bundle()
    out_js = PROJECT_ROOT / "ai-work-fertility-dashboard-data.js"
    payload = "window.AI_WORK_FERTILITY_DASHBOARD_V1=" + json.dumps(bundle, separators=(",", ":")) + ";\n"
    out_js.write_text(payload, encoding="utf-8")
    print(f"Wrote {out_js}")


if __name__ == "__main__":
    main()
