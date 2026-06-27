from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.config import (
    ACS_2020_WARNING,
    ATUS_SMALL_STATE_WARNING,
    DEFAULT_FORECAST_END_YEAR,
    OUTPUTS_DIR,
    PROCESSED_DATA_DIR,
    SCENARIO_SPECS,
    STATE_FIPS_TO_ABBR,
)
from src.explainability import build_explanations
from src.metrics import build_executive_summary_metrics, load_default_modeling_state_year_panel
from src.ml_dataset import load_or_build_ml_state_year_panel, prepare_ml_state_year_panel
from src.ml_models import train_all_models
from src.plots import (
    make_bar_chart,
    make_choropleth,
    make_importance_chart,
    make_line_chart,
    make_prediction_vs_actual_plot,
    make_quality_table,
    make_scatter_chart,
    make_temporal_importance_chart,
    make_uncertainty_fan,
)
from src.projections import add_uncertainty_bands, project_population_scenarios
from src.scenarios import SCENARIO_FEATURE_MAP, build_future_covariate_scenarios


st.set_page_config(
    page_title="Digital Life, In-Person Life, Fertility, and Population Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)


def inject_app_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(26, 102, 116, 0.10), transparent 30%),
                linear-gradient(180deg, #f5f3ea 0%, #fbfaf6 100%);
        }
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.5rem;
            max-width: 1360px;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(11, 66, 76, 0.10);
            border-radius: 14px;
            padding: 0.8rem 1rem;
            box-shadow: 0 14px 36px rgba(24, 54, 62, 0.08);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #103c43 0%, #0f4e59 100%);
        }
        [data-testid="stSidebar"] * {
            color: #f6f4ed;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            background: rgba(16, 60, 67, 0.08);
            padding: 0.4rem 0.95rem;
        }
        .stTabs [aria-selected="true"] {
            background: #103c43 !important;
            color: #f6f4ed !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_read(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_processed_frame(name: str) -> pd.DataFrame | None:
    parquet_path = PROCESSED_DATA_DIR / f"{name}.parquet"
    csv_path = PROCESSED_DATA_DIR / f"{name}.csv"
    parquet_df = _safe_read(parquet_path)
    if parquet_df is not None:
        return parquet_df
    return _safe_read(csv_path)


@st.cache_data(show_spinner=False)
def load_outputs_frame(name: str) -> pd.DataFrame | None:
    csv_path = OUTPUTS_DIR / f"{name}.csv"
    parquet_path = OUTPUTS_DIR / f"{name}.parquet"
    parquet_df = _safe_read(parquet_path)
    if parquet_df is not None:
        return parquet_df
    return _safe_read(csv_path)


def load_dashboard_bundle() -> dict[str, pd.DataFrame | None]:
    return {
        "modeling_panel": load_processed_frame("modeling_state_year_panel"),
        "ml_panel": load_processed_frame("ml_state_year_panel"),
        "scenario_covariates": load_processed_frame("scenario_covariates"),
        "ml_predictions": load_processed_frame("ml_predictions"),
        "ml_metrics": load_processed_frame("ml_model_metrics"),
        "population_projection_scenarios": load_processed_frame("population_projection_scenarios"),
        "explanations_global": load_processed_frame("ml_explanations_global"),
        "explanations_local": load_processed_frame("ml_explanations_local"),
        "quality_panel": load_processed_frame("measurement_quality"),
        "fertility_metrics": load_processed_frame("fertility_metrics"),
    }


def build_all_dashboard_artifacts(user_growth_rates: dict[str, float] | None = None) -> None:
    modeling_panel = load_default_modeling_state_year_panel()
    ml_panel = prepare_ml_state_year_panel(modeling_panel)
    scenario_frames = []
    for scenario_name in SCENARIO_SPECS:
        overrides = user_growth_rates if scenario_name == "user_defined" else None
        scenario_frames.append(
            build_future_covariate_scenarios(
                ml_panel,
                scenario_name=scenario_name,
                annual_growth_overrides=overrides,
                end_year=DEFAULT_FORECAST_END_YEAR,
            )
        )
    scenario_covariates = pd.concat(scenario_frames, ignore_index=True, sort=False)
    model_bundles, predictions, _ = train_all_models(ml_panel, scenario_covariates=scenario_covariates)
    forecast_inputs = predictions[predictions["split"].eq("forecast")].merge(
        scenario_covariates[["state_fips", "state_name", "region", "year", "scenario_name", "female_population_15_44", "total_population"]],
        on=["state_fips", "state_name", "region", "year", "scenario_name"],
        how="left",
    )
    population_history = load_processed_frame("population_metrics")
    if population_history is not None and not population_history.empty:
        project_population_scenarios(forecast_inputs, population_history)
    build_explanations(model_bundles, ml_panel, forecast_rows=predictions[predictions["split"].eq("forecast")].copy())
    st.cache_data.clear()


def build_sidebar(bundle: dict[str, pd.DataFrame | None]) -> dict[str, object]:
    st.sidebar.title("Controls")
    st.sidebar.caption("Observed data, modeled exposures, scenario assumptions, ML predictions, and population accounting are shown separately.")

    modeling_panel = bundle["modeling_panel"]
    available_states = ["All states"]
    if modeling_panel is not None and not modeling_panel.empty:
        state_names = modeling_panel["state_name"].dropna().astype(str).unique().tolist()
        available_states += sorted(state_names)

    selected_state = st.sidebar.selectbox("State", available_states)
    selected_scenario = st.sidebar.selectbox(
        "Scenario",
        list(SCENARIO_SPECS.keys()),
        format_func=lambda key: SCENARIO_SPECS[key]["label"],
    )
    selected_model = st.sidebar.selectbox(
        "Model",
        ["baseline_recent_trend", "statistical_ridge", "tree_gradient_boosting", "temporal_neural_net"],
    )
    selected_year = st.sidebar.selectbox("Future year", [2030, 2040, 2050], index=0)
    projection_horizon = st.sidebar.selectbox("Projection horizon", [2030, 2040, 2050], index=2)

    st.sidebar.subheader("User-defined growth assumptions")
    user_growth_rates = {}
    for control_name in SCENARIO_FEATURE_MAP:
        user_growth_rates[control_name] = st.sidebar.slider(
            control_name.replace("_", " ").title(),
            min_value=-0.05,
            max_value=0.05,
            value=0.0,
            step=0.005,
        )

    return {
        "selected_state": selected_state,
        "selected_scenario": selected_scenario,
        "selected_model": selected_model,
        "selected_year": selected_year,
        "projection_horizon": projection_horizon,
        "user_growth_rates": user_growth_rates,
        "refresh_requested": st.sidebar.button("Build / Refresh ML Dashboard Artifacts", use_container_width=True),
    }


def filter_state(df: pd.DataFrame | None, selected_state: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if selected_state == "All states":
        return df.copy()
    return df[df["state_name"].eq(selected_state)].copy()


def latest_observed_value(df: pd.DataFrame, column: str, selected_state: str) -> float:
    frame = filter_state(df, selected_state)
    if frame.empty or column not in frame.columns:
        return np.nan
    observed = frame.dropna(subset=[column]).copy()
    if observed.empty:
        return np.nan
    latest_year = int(observed["year"].max())
    return float(observed[observed["year"].eq(latest_year)][column].mean())


def render_metric_card(column, label: str, value: float, suffix: str = "") -> None:
    if pd.isna(value):
        column.metric(label, "NA")
    else:
        column.metric(label, f"{value:.2f}{suffix}")


def render_missing_artifact_warning(names: list[str]) -> None:
    st.warning(
        "Some derived ML/dashboard files are missing: "
        + ", ".join(names)
        + ". Use the sidebar button to build them from the existing processed sources."
    )


def render_executive_summary(bundle: dict[str, pd.DataFrame | None], controls: dict[str, object]) -> None:
    modeling_panel = bundle["modeling_panel"]
    predictions = bundle["ml_predictions"]
    population_projection = bundle["population_projection_scenarios"]
    if modeling_panel is None or modeling_panel.empty:
        st.warning("The modeling state-year panel is not available yet.")
        return

    summary = build_executive_summary_metrics(modeling_panel, fertility_df=bundle["fertility_metrics"])
    selected_state = str(controls["selected_state"])
    selected_scenario = str(controls["selected_scenario"])
    selected_model = str(controls["selected_model"])

    forecast_slice = pd.DataFrame()
    if predictions is not None and not predictions.empty:
        forecast_slice = predictions[
            predictions["split"].eq("forecast")
            & predictions["model_name"].eq(selected_model)
            & predictions["scenario_name"].eq(selected_scenario)
        ].copy()
        if selected_state != "All states":
            forecast_slice = forecast_slice[forecast_slice["state_name"].eq(selected_state)]

    population_slice = pd.DataFrame()
    if population_projection is not None and not population_projection.empty:
        population_slice = population_projection[population_projection["scenario_name"].eq(selected_scenario)].copy()
        if selected_state != "All states":
            population_slice = population_slice[population_slice["state_fips"].isin(modeling_panel[modeling_panel["state_name"].eq(selected_state)]["state_fips"].unique())]

    columns = st.columns(8)
    render_metric_card(columns[0], "Latest observed fertility", latest_observed_value(modeling_panel, "fertility_rate", selected_state))
    render_metric_card(columns[1], "Latest pop. growth", latest_observed_value(modeling_panel, "population_growth_rate", selected_state), suffix="")
    render_metric_card(columns[2], "Latest remote-work share", latest_observed_value(modeling_panel, "remote_work_share_state_year", selected_state), suffix="")
    render_metric_card(columns[3], "Latest digital-use prevalence", latest_observed_value(modeling_panel, "digital_use_prevalence_index", selected_state))
    render_metric_card(columns[4], "Latest screen leisure minutes", latest_observed_value(modeling_panel, "screen_leisure_minutes_broad_state_year", selected_state))
    render_metric_card(columns[5], "Latest in-person social minutes", latest_observed_value(modeling_panel, "in_person_social_minutes_state_year", selected_state))
    columns[6].metric("Scenario", SCENARIO_SPECS[selected_scenario]["label"].replace("Scenario ", ""))
    columns[7].metric("Model", selected_model)

    target_cols = st.columns(3)
    for idx, year in enumerate([2030, 2040, 2050]):
        if forecast_slice.empty:
            target_cols[idx].metric(f"{selected_model} fertility {year}", "NA")
        else:
            year_df = forecast_slice[forecast_slice["year"].eq(year)]
            value = year_df["predicted_fertility_rate"].mean() if not year_df.empty else np.nan
            render_metric_card(target_cols[idx], f"{selected_model} fertility {year}", value)

    if not population_slice.empty:
        final_year = int(population_slice["year"].max())
        projected_population = population_slice[population_slice["year"].eq(final_year)]["population_next_year"].mean()
        st.metric(f"Projected population under selected scenario ({final_year})", f"{projected_population:,.0f}")
    st.info("Scenario-based machine-learning projections are predictive simulations, not causal forecasts.")
    st.caption(f"Observed summary latest year: {summary.get('latest_year', 'NA')}. {ACS_2020_WARNING}")


def render_historical_trends(bundle: dict[str, pd.DataFrame | None], controls: dict[str, object]) -> None:
    panel = filter_state(bundle["modeling_panel"], str(controls["selected_state"]))
    if panel.empty:
        st.warning("Historical state-year panel unavailable.")
        return

    for metric, title in [
        ("fertility_rate", "Fertility by state-year"),
        ("remote_work_share_state_year", "Remote-work share"),
        ("remote_work_time_saved_roundtrip_minutes_state_year", "Remote-work time saved (round trip minutes)"),
        ("screen_leisure_minutes_broad_state_year", "Screen leisure minutes"),
        ("digital_social_index", "Digital social exposure"),
        ("in_person_social_minutes_state_year", "In-person social minutes"),
        ("in_person_work_exposure_index", "In-person work exposure"),
        ("population_growth_rate", "Population growth"),
    ]:
        if metric not in panel.columns:
            continue
        color = "state_name" if controls["selected_state"] == "All states" else None
        st.plotly_chart(make_line_chart(panel, x="year", y=metric, color=color, title=title), use_container_width=True)


def render_state_maps(bundle: dict[str, pd.DataFrame | None], controls: dict[str, object]) -> None:
    panel = bundle["modeling_panel"]
    predictions = bundle["ml_predictions"]
    population_projection = bundle["population_projection_scenarios"]
    if panel is None or panel.empty:
        st.warning("State map data unavailable.")
        return

    latest_year = int(panel["year"].max())
    latest_panel = panel[panel["year"].eq(latest_year)].copy()
    latest_panel["state_abbr"] = latest_panel["state_fips"].map(STATE_FIPS_TO_ABBR)
    latest_panel["digital_life_exposure_index"] = latest_panel[
        [column for column in ["remote_work_exposure_index", "digital_distraction_index", "digital_social_index", "digital_access_index", "digital_use_prevalence_index"] if column in latest_panel.columns]
    ].mean(axis=1)
    latest_panel["in_person_life_exposure_index"] = latest_panel[
        [column for column in ["in_person_work_exposure_index", "in_person_social_index"] if column in latest_panel.columns]
    ].mean(axis=1)

    st.plotly_chart(make_choropleth(latest_panel, "state_abbr", "fertility_rate", f"Current fertility rate ({latest_year})"), use_container_width=True)

    if predictions is not None and not predictions.empty:
        future = predictions[
            predictions["split"].eq("forecast")
            & predictions["model_name"].eq(str(controls["selected_model"]))
            & predictions["scenario_name"].eq(str(controls["selected_scenario"]))
            & predictions["year"].eq(int(controls["selected_year"]))
        ].copy()
        if not future.empty:
            future["state_abbr"] = future["state_fips"].map(STATE_FIPS_TO_ABBR)
            baseline = latest_panel[["state_fips", "fertility_rate"]].rename(columns={"fertility_rate": "latest_fertility_rate"})
            future = future.merge(baseline, on="state_fips", how="left")
            future["projected_change"] = future["predicted_fertility_rate"] - future["latest_fertility_rate"]
            st.plotly_chart(make_choropleth(future, "state_abbr", "predicted_fertility_rate", f"Projected fertility ({controls['selected_year']})"), use_container_width=True)
            st.plotly_chart(make_choropleth(future, "state_abbr", "projected_change", f"Projected fertility change ({controls['selected_year']})"), use_container_width=True)

    if population_projection is not None and not population_projection.empty:
        pop_future = population_projection[
            population_projection["scenario_name"].eq(str(controls["selected_scenario"]))
            & population_projection["year"].eq(int(controls["selected_year"]))
        ].copy()
        if not pop_future.empty:
            pop_future["state_abbr"] = pop_future["state_fips"].map(STATE_FIPS_TO_ABBR)
            pop_future["projected_population_growth"] = (
                pop_future["population_next_year"] - pop_future["population_current"]
            ) / pop_future["population_current"].replace(0, np.nan)
            st.plotly_chart(make_choropleth(pop_future, "state_abbr", "projected_population_growth", f"Projected population growth ({controls['selected_year']})"), use_container_width=True)

    st.plotly_chart(make_choropleth(latest_panel, "state_abbr", "digital_life_exposure_index", f"Digital life exposure ({latest_year})"), use_container_width=True)
    st.plotly_chart(make_choropleth(latest_panel, "state_abbr", "in_person_life_exposure_index", f"In-person life exposure ({latest_year})"), use_container_width=True)


def render_scenario_simulator(bundle: dict[str, pd.DataFrame | None], controls: dict[str, object]) -> None:
    predictions = bundle["ml_predictions"]
    population_projection = bundle["population_projection_scenarios"]
    scenario_covariates = bundle["scenario_covariates"]
    if predictions is None or predictions.empty or scenario_covariates is None or scenario_covariates.empty:
        render_missing_artifact_warning(["ml_predictions.parquet", "scenario_covariates.parquet"])
        return

    selected_state = str(controls["selected_state"])
    selected_model = str(controls["selected_model"])
    horizon = int(controls["projection_horizon"])

    future = predictions[
        predictions["split"].eq("forecast")
        & predictions["model_name"].eq(selected_model)
        & predictions["year"].le(horizon)
    ].copy()
    if selected_state != "All states":
        future = future[future["state_name"].eq(selected_state)]

    if future.empty:
        st.warning("No forecast rows are available for the current model/scenario filter.")
        return

    st.plotly_chart(
        make_line_chart(
            future,
            x="year",
            y="predicted_fertility_rate",
            color="scenario_name",
            title="Scenario comparison: projected fertility rate",
        ),
        use_container_width=True,
    )

    forecast_inputs = future.merge(
        scenario_covariates[["state_fips", "year", "scenario_name", "female_population_15_44"]],
        on=["state_fips", "year", "scenario_name"],
        how="left",
    )
    forecast_inputs["projected_births"] = (
        forecast_inputs["predicted_fertility_rate"] / 1000.0 * forecast_inputs["female_population_15_44"]
    )
    births_summary = forecast_inputs.groupby(["scenario_name", "year"], as_index=False)["projected_births"].sum()
    if selected_state != "All states":
        births_summary = forecast_inputs.groupby(["scenario_name", "year"], as_index=False)["projected_births"].sum()
    st.plotly_chart(
        make_line_chart(
            births_summary,
            x="year",
            y="projected_births",
            color="scenario_name",
            title="Projected births",
        ),
        use_container_width=True,
    )

    selected_scenario = str(controls["selected_scenario"])
    scenario_only = forecast_inputs[forecast_inputs["scenario_name"].eq(selected_scenario)].copy()
    if not scenario_only.empty:
        uncertainty = add_uncertainty_bands(
            scenario_only.groupby("year", as_index=False)["projected_births"].sum().rename(columns={"projected_births": "projected_births"})
        )
        st.plotly_chart(
            make_uncertainty_fan(uncertainty, x="year", mid="births_mid", low="births_low", high="births_high", title=f"Uncertainty band: {SCENARIO_SPECS[selected_scenario]['label']}"),
            use_container_width=True,
        )

    if population_projection is not None and not population_projection.empty:
        pop_future = population_projection[population_projection["year"].le(horizon)].copy()
        if selected_state != "All states":
            state_fips_values = scenario_covariates[scenario_covariates["state_name"].eq(selected_state)]["state_fips"].unique().tolist()
            pop_future = pop_future[pop_future["state_fips"].isin(state_fips_values)]
        st.plotly_chart(
            make_line_chart(
                pop_future,
                x="year",
                y="population_next_year",
                color="scenario_name",
                title="Projected population",
            ),
            use_container_width=True,
        )


def render_neural_forecast(bundle: dict[str, pd.DataFrame | None]) -> None:
    predictions = bundle["ml_predictions"]
    metrics = bundle["ml_metrics"]
    if predictions is None or predictions.empty or metrics is None or metrics.empty:
        render_missing_artifact_warning(["ml_predictions.parquet", "ml_model_metrics.parquet"])
        return

    st.subheader("Architecture")
    st.code(
        "Temporal feed-forward neural network on lagged state-year features\n"
        "Input: exposure indices, fertility lags, year trends, and state history\n"
        "Validation: time-based split only (no random row split)"
    )

    test_predictions = predictions[(predictions["split"].eq("test")) & (predictions["model_name"].eq("temporal_neural_net"))].copy()
    if not test_predictions.empty:
        st.plotly_chart(
            make_prediction_vs_actual_plot(test_predictions, title="Neural network: predicted vs actual"),
            use_container_width=True,
        )
        state_errors = test_predictions.copy()
        state_errors["absolute_error"] = (state_errors["predicted_fertility_rate"] - state_errors["actual_fertility_rate"]).abs()
        state_errors = state_errors.groupby("state_name", as_index=False)["absolute_error"].mean().sort_values("absolute_error", ascending=False).head(15)
        st.plotly_chart(
            make_bar_chart(state_errors, x="absolute_error", y="state_name", title="Largest state-level neural forecast errors", orientation="h"),
            use_container_width=True,
        )

    metric_view = metrics[
        metrics["model_name"].eq("temporal_neural_net")
        & metrics["group_type"].eq("overall")
    ].copy()
    st.dataframe(metric_view, use_container_width=True)

    forecast_view = predictions[(predictions["split"].eq("forecast")) & (predictions["model_name"].eq("temporal_neural_net"))].copy()
    if not forecast_view.empty:
        st.plotly_chart(
            make_line_chart(
                forecast_view,
                x="year",
                y="predicted_fertility_rate",
                color="scenario_name",
                title="Neural-network forecast chart",
            ),
            use_container_width=True,
        )


def render_why_prediction(bundle: dict[str, pd.DataFrame | None], controls: dict[str, object]) -> None:
    local = bundle["explanations_local"]
    global_exp = bundle["explanations_global"]
    predictions = bundle["ml_predictions"]
    population_projection = bundle["population_projection_scenarios"]
    if local is None or local.empty or global_exp is None or global_exp.empty:
        render_missing_artifact_warning(["ml_explanations_global.parquet", "ml_explanations_local.parquet"])
        return

    selected_state = str(controls["selected_state"])
    selected_model = str(controls["selected_model"])
    explanation_rows = local[local["model_name"].eq(selected_model)].copy()
    if selected_state != "All states":
        explanation_rows = explanation_rows[explanation_rows["state_name"].eq(selected_state)]
    if explanation_rows.empty:
        st.warning("No local explanation rows are available for the current selection.")
        return

    available_years = sorted(explanation_rows["year"].dropna().astype(int).unique().tolist())
    selected_explanation_year = st.selectbox("Explanation year", available_years, index=max(0, len(available_years) - 1))
    selected_rows = explanation_rows[explanation_rows["year"].eq(selected_explanation_year)].copy()
    selected_rows = selected_rows.sort_values("importance_rank")

    prediction_row = pd.DataFrame()
    if predictions is not None and not predictions.empty:
        prediction_row = predictions[
            predictions["model_name"].eq(selected_model)
            & predictions["year"].eq(selected_explanation_year)
        ].copy()
        if selected_state != "All states":
            prediction_row = prediction_row[prediction_row["state_name"].eq(selected_state)]

    if not prediction_row.empty:
        value = prediction_row["predicted_fertility_rate"].mean()
        st.metric("Projected fertility rate", f"{value:.2f}")

    if population_projection is not None and not population_projection.empty:
        pop_row = population_projection[population_projection["year"].eq(selected_explanation_year)].copy()
        if selected_state != "All states":
            state_fips_values = prediction_row["state_fips"].unique().tolist() if not prediction_row.empty else []
            pop_row = pop_row[pop_row["state_fips"].isin(state_fips_values)]
        if not pop_row.empty:
            st.metric("Projected births", f"{pop_row['projected_births'].sum():,.0f}")
            st.metric("Projected population effect", f"{(pop_row['population_next_year'] - pop_row['population_current']).sum():,.0f}")

    top_positive = selected_rows[selected_rows["direction"].eq("positive")].head(5)
    top_negative = selected_rows[selected_rows["direction"].eq("negative")].head(5)
    col1, col2 = st.columns(2)
    col1.dataframe(top_positive[["feature", "contribution", "plain_english"]], use_container_width=True)
    col2.dataframe(top_negative[["feature", "contribution", "plain_english"]], use_container_width=True)

    global_model = global_exp[global_exp["model_name"].eq(selected_model)].sort_values("importance_value", ascending=False).head(15)
    st.plotly_chart(make_importance_chart(global_model, title="Global feature importance"), use_container_width=True)
    st.plotly_chart(make_temporal_importance_chart(selected_rows, title="Temporal importance from lagged features"), use_container_width=True)

    families = selected_rows.groupby("feature_family", as_index=False)["contribution"].sum().sort_values("contribution")
    st.plotly_chart(make_bar_chart(families, x="contribution", y="feature_family", title="Feature-family contribution", orientation="h"), use_container_width=True)

    narrative = (
        f"For {selected_state if selected_state != 'All states' else 'the selected states'} in {selected_explanation_year}, "
        f"the {selected_model} projection is driven most by "
        f"{', '.join(global_model['feature'].head(3).tolist())}. "
        "Positive and negative local contributors above show how remote work, digital distraction, digital social exposure, "
        "in-person social interaction, in-person work, fertility lags, and state trend/history combine in this predictive scenario."
    )
    st.info(narrative)


def render_data_quality(bundle: dict[str, pd.DataFrame | None]) -> None:
    quality = bundle["quality_panel"]
    modeling_panel = bundle["modeling_panel"]
    if quality is not None and not quality.empty:
        st.plotly_chart(make_quality_table(quality), use_container_width=True)
    if modeling_panel is not None and not modeling_panel.empty:
        mode_columns = [column for column in modeling_panel.columns if column.endswith("_mode")]
        if mode_columns:
            latest = modeling_panel.sort_values("year").groupby("state_fips", as_index=False).tail(1)
            latest_modes = latest[[column for column in ["state_name", "year", *mode_columns] if column in latest.columns]].head(25)
            st.dataframe(latest_modes, use_container_width=True)
    st.warning(ACS_2020_WARNING)
    st.warning(ATUS_SMALL_STATE_WARNING)
    st.caption("ATUS state-year minutes are often modeled or pooled rather than directly observed. Digital-media minutes remain proxied unless user-provided or paid data are added.")


def main() -> None:
    inject_app_css()
    st.title("U.S. Digital Life, In-Person Life, Fertility, and Population Dashboard")
    st.caption(
        "Observed data, interpolated/imputed values, scenario assumptions, machine-learning projections, and population accounting are intentionally separated."
    )

    bundle = load_dashboard_bundle()
    if bundle["modeling_panel"] is None:
        try:
            bundle["modeling_panel"] = load_default_modeling_state_year_panel()
        except Exception:
            bundle["modeling_panel"] = None
    if bundle["ml_panel"] is None and bundle["modeling_panel"] is not None:
        try:
            bundle["ml_panel"] = load_or_build_ml_state_year_panel(bundle["modeling_panel"])
        except Exception:
            bundle["ml_panel"] = None

    controls = build_sidebar(bundle)
    if bool(controls["refresh_requested"]):
        with st.spinner("Building modeling panel, ML panel, scenarios, forecasts, and explanations..."):
            build_all_dashboard_artifacts(user_growth_rates=dict(controls["user_growth_rates"]))
        st.success("Artifacts refreshed.")
        bundle = load_dashboard_bundle()
        if bundle["modeling_panel"] is None:
            try:
                bundle["modeling_panel"] = load_default_modeling_state_year_panel()
            except Exception:
                bundle["modeling_panel"] = None
        if bundle["ml_panel"] is None and bundle["modeling_panel"] is not None:
            try:
                bundle["ml_panel"] = load_or_build_ml_state_year_panel(bundle["modeling_panel"])
            except Exception:
                bundle["ml_panel"] = None

    missing = [name for name, frame in bundle.items() if frame is None]
    if missing:
        st.info("Base dashboard can still run even if some ML artifacts are missing.")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Executive Summary",
            "Historical Trends",
            "State Map",
            "Scenario Simulator",
            "Neural Network Forecast",
            "Why This Prediction?",
            "Data Quality",
        ]
    )

    with tab1:
        render_executive_summary(bundle, controls)
    with tab2:
        render_historical_trends(bundle, controls)
    with tab3:
        render_state_maps(bundle, controls)
    with tab4:
        render_scenario_simulator(bundle, controls)
    with tab5:
        render_neural_forecast(bundle)
    with tab6:
        render_why_prediction(bundle, controls)
    with tab7:
        render_data_quality(bundle)


if __name__ == "__main__":
    main()
