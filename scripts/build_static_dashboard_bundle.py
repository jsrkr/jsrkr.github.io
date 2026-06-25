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
        "hypothesis": "Less commuting and more flexibility may support family formation.",
    },
    {
        "id": "digital_distraction_crowds_out",
        "source_scenario": "distraction_dominant",
        "label": "Digital distraction crowds out in-person life",
        "short_label": "Digital distraction",
        "hypothesis": "More online leisure may reduce dating, couple time, and face-to-face interaction.",
    },
    {
        "id": "online_life_helps_matching",
        "source_scenario": "digital_social_substitution",
        "label": "Online life helps matching",
        "short_label": "Online life helps matching",
        "hypothesis": "Digital social tools may help people meet partners or maintain relationships.",
    },
    {
        "id": "remote_work_increases_care_burden",
        "source_scenario": "gendered_care_penalty",
        "label": "Remote work increases care burden",
        "short_label": "Care burden",
        "hypothesis": "Working from home may increase unpaid care expectations, especially for women.",
    },
]

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
    "mechanism_remote_work_flexibility": "remote work flexibility",
    "mechanism_digital_distraction": "digital distraction",
    "mechanism_online_matching": "online matching / digital social life",
    "mechanism_in_person_social": "in-person social interaction",
    "mechanism_care_burden": "care burden",
}


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


def _build_scenario_mechanism_frame(scenario_covariates: pd.DataFrame) -> pd.DataFrame:
    scenario_lookup = {item["source_scenario"]: item for item in DASHBOARD_SCENARIOS}
    selected_sources = list(scenario_lookup)
    scenario_subset = scenario_covariates.loc[
        scenario_covariates["scenario_name"].isin(selected_sources),
        [
            "state_fips",
            "year",
            "scenario_name",
            "remote_work_exposure_index",
            "digital_distraction_index",
            "digital_social_index",
            "in_person_social_index",
            "commute_burden_index",
            "work_family_compatibility_proxy",
            "gendered_care_risk_proxy",
        ],
    ].copy()

    baseline = scenario_subset.loc[scenario_subset["scenario_name"].eq("baseline_continuation")].copy()
    baseline = baseline.rename(
        columns={
            "remote_work_exposure_index": "baseline_remote_work_exposure_index",
            "digital_distraction_index": "baseline_digital_distraction_index",
            "digital_social_index": "baseline_digital_social_index",
            "in_person_social_index": "baseline_in_person_social_index",
            "commute_burden_index": "baseline_commute_burden_index",
            "work_family_compatibility_proxy": "baseline_work_family_compatibility_proxy",
            "gendered_care_risk_proxy": "baseline_gendered_care_risk_proxy",
        }
    )
    baseline = baseline.drop(columns=["scenario_name"])

    merged = scenario_subset.merge(baseline, on=["state_fips", "year"], how="left")
    merged["mechanism_remote_work_flexibility"] = (
        _safe_delta(merged, "work_family_compatibility_proxy", "baseline_work_family_compatibility_proxy")
        + 0.6 * _safe_delta(merged, "remote_work_exposure_index", "baseline_remote_work_exposure_index")
        - 0.4 * _safe_delta(merged, "commute_burden_index", "baseline_commute_burden_index")
    )
    merged["mechanism_digital_distraction"] = -_safe_delta(
        merged,
        "digital_distraction_index",
        "baseline_digital_distraction_index",
    )
    merged["mechanism_online_matching"] = _safe_delta(
        merged,
        "digital_social_index",
        "baseline_digital_social_index",
    )
    merged["mechanism_in_person_social"] = _safe_delta(
        merged,
        "in_person_social_index",
        "baseline_in_person_social_index",
    )
    merged["mechanism_care_burden"] = -_safe_delta(
        merged,
        "gendered_care_risk_proxy",
        "baseline_gendered_care_risk_proxy",
    )

    merged["scenario"] = merged["scenario_name"].map(lambda name: scenario_lookup[name]["id"])
    merged["scenario_label"] = merged["scenario_name"].map(lambda name: scenario_lookup[name]["label"])
    merged["main_driver"] = merged.apply(_max_abs_label, axis=1)

    reference_mask = merged["scenario"].eq("reference_path")
    for column in MECHANISM_LABELS:
        merged.loc[reference_mask, column] = 0.0
    merged.loc[reference_mask, "main_driver"] = "observed state trend"

    keep_cols = [
        "state_fips",
        "year",
        "scenario_name",
        "scenario",
        "scenario_label",
        "main_driver",
        *MECHANISM_LABELS.keys(),
    ]
    return merged[keep_cols].copy()


def _build_forecast_records() -> tuple[list[dict], list[dict], list[dict], list[int], str | None]:
    predictions_path = PROJECT_ROOT / "data" / "processed" / "ml_predictions.parquet"
    metrics_path = PROJECT_ROOT / "data" / "processed" / "ml_model_metrics.parquet"
    scenario_covariates_path = PROJECT_ROOT / "data" / "processed" / "scenario_covariates.parquet"

    if not predictions_path.exists() or not scenario_covariates_path.exists():
        return [], [], [], [], "Precomputed model outputs have not been added."

    predictions = pd.read_parquet(predictions_path)
    scenario_covariates = pd.read_parquet(scenario_covariates_path)
    metrics = pd.read_parquet(metrics_path) if metrics_path.exists() else pd.DataFrame()

    model_lookup = {item["id"]: item for item in DASHBOARD_MODELS}
    scenario_lookup = {item["source_scenario"]: item for item in DASHBOARD_SCENARIOS}
    selected_models = list(model_lookup)
    selected_scenarios = list(scenario_lookup)

    forecast = predictions.loc[
        predictions["split"].eq("forecast")
        & predictions["model_name"].isin(selected_models)
        & predictions["scenario_name"].isin(selected_scenarios),
        ["state_fips", "state_name", "year", "model_name", "scenario_name", "predicted_fertility_rate"],
    ].copy()
    if forecast.empty:
        return [], [], [], [], "Precomputed model outputs have not been added."

    reference = forecast.loc[forecast["scenario_name"].eq("baseline_continuation")].copy()
    reference = reference.rename(columns={"predicted_fertility_rate": "reference_path"})
    reference = reference.drop(columns=["scenario_name"])

    mechanisms = _build_scenario_mechanism_frame(scenario_covariates)
    merged = forecast.merge(
        reference[["state_fips", "year", "model_name", "reference_path"]],
        on=["state_fips", "year", "model_name"],
        how="left",
    )
    merged = merged.merge(
        mechanisms,
        on=["state_fips", "year", "scenario_name"],
        how="left",
    )

    merged["model"] = merged["model_name"]
    merged["model_label"] = merged["model_name"].map(lambda name: model_lookup[name]["label"])
    merged["scenario_path"] = merged["predicted_fertility_rate"].astype(float)
    merged["scenario_difference"] = merged["scenario_path"] - merged["reference_path"]
    merged["geography_type"] = "state"
    merged["state_abbr"] = merged["state_fips"].map(STATE_FIPS_TO_ABBR)
    merged["state_name"] = merged["state_name"].fillna(merged["state_fips"].map(STATE_FIPS_TO_NAME))

    forecast_records = []
    keep_cols = [
        "geography_type",
        "state_fips",
        "state_abbr",
        "state_name",
        "year",
        "model",
        "model_label",
        "scenario",
        "scenario_label",
        "reference_path",
        "scenario_path",
        "scenario_difference",
        "main_driver",
        *MECHANISM_LABELS.keys(),
    ]
    merged = merged.sort_values(["state_fips", "model_name", "scenario_name", "year"])
    for row in json.loads(merged[keep_cols].to_json(orient="records")):
        forecast_records.append(row)

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

    model_rows: list[dict] = []
    available_models = set(merged["model"].dropna().tolist())
    metric_models = set(metrics["model_name"].dropna().tolist()) if not metrics.empty else set()
    for definition in DASHBOARD_MODELS:
        metadata = _load_model_metadata(definition["metadata_file"])
        available = definition["id"] in available_models
        performance_note = definition["note"]
        if definition["id"] == "temporal_neural_net":
            performance_note = (
                "Exploratory benchmark. Current validation and test performance are materially weaker "
                "than the simpler tree benchmark."
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
            }
        )

    return forecast_records, metric_rows, model_rows, available_years, None


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
                "remote_series": _series_rows(remote_state, ["remote_work_share_state_year"]),
                "fertility_series": _series_rows(fert_state, ["general_fertility_rate", "total_fertility_rate_approx"]),
                "population_series": _series_rows(pop_state, ["population_growth_rate", "population_total"]),
                "attention_series": _series_rows(
                    attention_state,
                    ["search_interest_genai_state_year", "search_interest_online_dating_state_year", "digital_attention_proxy_index"],
                ),
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

    forecast_records, model_metrics, model_options, available_years, benchmark_note = _build_forecast_records()
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
            "badge": "Scenario tool - not a causal forecast",
            "relationship_note": (
                "Google Trends proxies capture broad state-level online attention, not direct measures of "
                "relationship quality or fertility intentions."
            ),
            "benchmark_note": benchmark_note,
        },
        "scenario_defaults": SCENARIO_DEFAULTS,
        "horizon_years": horizon_years,
        "scenario_options": DASHBOARD_SCENARIOS,
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
                    "note": "Official U.S. fertility rate for women ages 15-44 from the CDC state-year table.",
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
                    "id": "digital_distraction_minutes",
                    "label": "Digital distraction",
                    "value": latest_distraction_value,
                    "year": latest_distraction_year,
                    "unit": "minutes",
                    "note": "National ATUS minutes in leisure screen activities.",
                },
                {
                    "id": "face_to_face_social_minutes",
                    "label": "Face-to-face social time",
                    "value": latest_social_value,
                    "year": latest_social_year,
                    "unit": "minutes",
                    "note": "National ATUS socializing and communicating minutes.",
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
                    "digital_distraction_minutes",
                    "face_to_face_social_minutes",
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
    payload = "window.AI_WORK_FERTILITY_DASHBOARD_V1 = " + json.dumps(bundle, indent=2) + ";\n"
    out_js.write_text(payload, encoding="utf-8")
    print(f"Wrote {out_js}")


if __name__ == "__main__":
    main()
