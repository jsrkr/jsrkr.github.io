from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_BUNDLE_PATH = PROJECT_ROOT / "ai-work-fertility-dashboard-data.js"
HTML_PATH = PROJECT_ROOT / "ai-work-fertility-dashboard.html"
SCRIPT_PATH = PROJECT_ROOT / "ai-work-fertility-dashboard.js"
STYLE_PATH = PROJECT_ROOT / "style.css"


def load_dashboard_bundle() -> dict:
    raw = DATA_BUNDLE_PATH.read_text(encoding="utf-8")
    payload = raw.split("=", 1)[1].rsplit(";", 1)[0]
    return json.loads(payload)


def load_dashboard_html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


def load_dashboard_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def load_dashboard_styles() -> str:
    return STYLE_PATH.read_text(encoding="utf-8")


def js_display_extent(values: list[float]) -> tuple[float, float]:
    max_abs = max(abs(value) for value in values)
    return -max_abs, max_abs


def js_signed_display(value: float, digits: int) -> str:
    rounded = round(value, digits)
    if rounded == 0:
        rounded = 0.0
    prefix = "+" if rounded > 0 else ""
    return f"{prefix}{rounded:.{digits}f}"


def current_view_rows(bundle: dict, model: str, scenario: str, year: int) -> list[dict]:
    return [
        record for record in bundle["forecast_records"]
        if record.get("geography_type", "state") == "state"
        and record["model"] == model
        and record["scenario"] == scenario
        and int(record["year"]) == year
    ]


def scenario_rows(bundle: dict, model: str, scenario: str) -> list[dict]:
    return [
        record for record in bundle["forecast_records"]
        if record.get("geography_type", "state") == "state"
        and record["model"] == model
        and record["scenario"] == scenario
    ]


def python_build_ranking_rows(rows: list[dict], mode: str, tolerance: float = 0.05) -> list[dict]:
    filtered = [row for row in rows if math.isfinite(float(row["scenario_difference"]))]
    if mode == "upward":
        filtered = [row for row in filtered if float(row["scenario_difference"]) > tolerance]
        filtered.sort(key=lambda row: (-float(row["scenario_difference"]), row["state_name"]))
    elif mode == "downward":
        filtered = [row for row in filtered if float(row["scenario_difference"]) < -tolerance]
        filtered.sort(key=lambda row: (float(row["scenario_difference"]), row["state_name"]))
    else:
        filtered.sort(key=lambda row: (abs(float(row["scenario_difference"])), row["state_name"]))
    return filtered[:5]


def test_dashboard_model_options_match_bundle_records_and_metrics() -> None:
    bundle = load_dashboard_bundle()
    model_ids = {model["id"] for model in bundle["model_options"]}
    record_model_ids = {record["model"] for record in bundle["forecast_records"]}
    metric_model_ids = {metric["model"] for metric in bundle["model_metrics"]}

    assert model_ids == record_model_ids
    assert model_ids == metric_model_ids


def test_dashboard_state_coverage_is_complete_for_each_model_scenario_year() -> None:
    bundle = load_dashboard_bundle()
    state_records = [
        record for record in bundle["forecast_records"]
        if record.get("geography_type", "state") == "state"
    ]
    expected_state_count = len(
        {
            str(record.get("state_fips") or record.get("geography_id")).zfill(2)
            for record in state_records
        }
    )

    counts = Counter(
        (record["model"], record["scenario"], int(record["year"]))
        for record in state_records
    )

    assert counts
    assert all(count == expected_state_count for count in counts.values())


def test_dashboard_bundle_has_no_missing_values_and_preserves_identity() -> None:
    bundle = load_dashboard_bundle()

    for record in bundle["forecast_records"]:
        reference_path = float(record["reference_path"])
        scenario_path = float(record["scenario_path"])
        scenario_difference = float(record["scenario_difference"])

        assert math.isfinite(reference_path)
        assert math.isfinite(scenario_path)
        assert math.isfinite(scenario_difference)
        assert abs((scenario_path - reference_path) - scenario_difference) < 1e-8


def test_dashboard_inline_info_tooltip_copy_and_accessibility_hooks_are_present() -> None:
    script = load_dashboard_script()

    required_copy = [
        'label: "Statistical baseline"',
        'A traditional statistical projection based on observed fertility trends and available state-level predictors.',
        'label: "Tree ML benchmark"',
        'A tree-based machine-learning benchmark that captures nonlinear relationships. It is used as a predictive comparison, not a causal estimate.',
        'label: "Neural network benchmark"',
        'A neural-network predictive benchmark. If performance is weaker than simpler models, interpret it as exploratory.',
        'label: "Scenario difference from reference path"',
        'The selected scenario path minus the model-based reference path, measured in births per 1,000 women aged " + WOMEN_AGE_LABEL + ".',
        'label: "Scenario path (GFR level)"',
        'The projected General Fertility Rate under the selected scenario, measured as live births per 1,000 women aged " + WOMEN_AGE_LABEL + ".',
        'label: "Reference path (GFR level)"',
        "The projected General Fertility Rate under the model-based reference path before any additional scenario shift.",
        'label: "Remote work saves time"',
        'Scenario interpretation: this scenario assumes that remote work saves commuting time and increases flexibility. The adjustment is based on the change in remote-work time saved relative to the reference path.',
        'label: "Screen leisure crowds out in-person life"',
        'Scenario interpretation: ATUS-based screen leisure is used as a broad proxy for digital leisure. It captures screen time broadly, not pure social media use.',
        'label: "Online life helps matching"',
        'Scenario interpretation: this scenario assumes that online social tools and dating-app search attention make it easier for people to meet partners or maintain relationships.',
        'label: "More time at home increases care work"',
        'Scenario interpretation: more digital life - remote work, online services and shopping, and digital entertainment - can keep people at home more and raise unpaid care and household burdens.',
        'aria-controls="',
        'aria-describedby="',
        'renderControlInfoSummaries();',
        'buildInlineInfoLabelHtml(scenario.id, scenario.label)',
    ]

    for needle in required_copy:
        assert needle in script


def test_dashboard_header_uses_top_utility_nav_and_removes_hero_badge() -> None:
    html = load_dashboard_html()

    required_markup = [
        'class="scenario-dashboard-hero"',
        'class="scenario-utility-nav"',
        'aria-label="Dashboard information and downloads"',
        ">About</summary>",
        ">Data &amp; Methods</summary>",
        ">Download</summary>",
        'id="download-current-view-button"',
        'id="download-all-data-button"',
        'id="download-rankings-button"',
        'id="copy-summary-button"',
        'id="copy-link-button"',
    ]
    for needle in required_markup:
        assert needle in html

    assert "Scenario exercise &mdash; not a causal estimate" not in html


def test_figure1_scenario_difference_uses_symmetric_zero_centered_display_scale() -> None:
    bundle = load_dashboard_bundle()
    script = load_dashboard_script()

    required_script_wiring = [
        'const scenarioExtent = getScenarioDifferenceExtent(scenarioDiffs);',
        'zmin: dashboardState.selectedOutcome === "scenario_difference" ? scenarioExtent.min : undefined,',
        'zmax: dashboardState.selectedOutcome === "scenario_difference" ? scenarioExtent.max : undefined,',
        'const extent = getScenarioDifferenceExtent(scenarioDiffs);',
        'formatSignedValue(extent.min, 1) + " to " + formatSignedValue(extent.max, 1)',
        'const prefix = cleanValue > 0 ? "+" : "";',
    ]
    for needle in required_script_wiring:
        assert needle in script

    rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", 2035)
    assert rows

    diffs = [float(record["scenario_difference"]) for record in rows]
    display_min, display_max = js_display_extent(diffs)

    assert math.isclose(display_min, -max(abs(value) for value in diffs), rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(display_max, max(abs(value) for value in diffs), rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(abs(display_min), abs(display_max), rel_tol=0.0, abs_tol=1e-12)

    caption_range = f"{js_signed_display(display_min, 1)} to {js_signed_display(display_max, 1)}"
    assert caption_range.startswith("-")
    assert caption_range.endswith(js_signed_display(display_max, 1))


def test_rankings_use_sign_safe_groups_and_separate_closest_card() -> None:
    bundle = load_dashboard_bundle()
    script = load_dashboard_script()
    rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", 2035)

    upward = python_build_ranking_rows(rows, "upward")
    downward = python_build_ranking_rows(rows, "downward")
    closest = python_build_ranking_rows(rows, "closest")

    assert "States closest to the reference path" in script
    assert "closest_to_reference_path_upward_fallback" not in script
    assert "closest_to_reference_path_downward_fallback" not in script
    assert all(float(row["scenario_difference"]) > 0.05 for row in upward)
    assert all(float(row["scenario_difference"]) < -0.05 for row in downward)
    assert closest == sorted(closest, key=lambda row: (abs(float(row["scenario_difference"])), row["state_name"]))


def test_rankings_use_higher_precision_than_map_caption() -> None:
    bundle = load_dashboard_bundle()
    script = load_dashboard_script()
    rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", 2035)
    diffs = [float(row["scenario_difference"]) for row in rows]

    assert "const RANKING_DISPLAY_DIGITS = 3;" in script
    assert "describeRankingDifference" in script
    assert "formatSignedValue(cleanValue, RANKING_DISPLAY_DIGITS)" in script
    assert len({round(value, 3) for value in diffs}) > len({round(value, 1) for value in diffs})


def test_remote_work_statistical_scenario_is_not_a_constant_shift_in_2035() -> None:
    bundle = load_dashboard_bundle()
    rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", 2035)
    diffs = [float(row["scenario_difference"]) for row in rows]

    assert len({round(value, 6) for value in diffs}) > 10
    assert math.isfinite(sum(diffs) / len(diffs))
    assert max(diffs) - min(diffs) > 0.01


def test_dashboard_bundle_exports_shift_components() -> None:
    script = load_dashboard_script()
    required_fields = [
        "scenario_shift_component",
        "manual_adjustment_component",
        'ranking_group: "closest_to_reference_path"',
    ]
    for needle in required_fields:
        assert needle in script


def test_dashboard_inline_info_styles_exist_for_compact_control_markers() -> None:
    styles = load_dashboard_styles()

    required_selectors = [
        ".scenario-info-button",
        ".scenario-info-popover",
        ".scenario-control-heading",
        ".scenario-control-selection",
        ".scenario-inline-label",
    ]

    for needle in required_selectors:
        assert needle in styles


def test_scenario_difference_equals_scenario_path_minus_reference_path_for_every_year() -> None:
    bundle = load_dashboard_bundle()
    for record in bundle["forecast_records"]:
        expected = float(record["scenario_path"]) - float(record["reference_path"])
        assert abs(expected - float(record["scenario_difference"])) < 1e-8


def test_alabama_remote_work_saves_time_matches_raw_paths_for_every_horizon_year() -> None:
    bundle = load_dashboard_bundle()
    horizon_years = bundle["horizon_years"]
    alabama_rows = [
        record for record in bundle["forecast_records"]
        if record["geography_type"] == "state"
        and record["state_abbr"] == "AL"
        and record["model"] == "statistical_ridge"
        and record["scenario"] == "remote_work_saves_time"
    ]
    found_years = {record["year"] for record in alabama_rows}
    assert set(horizon_years).issubset(found_years)

    for record in alabama_rows:
        if record["year"] not in horizon_years:
            continue
        assert math.isclose(
            float(record["scenario_path"]) - float(record["reference_path"]),
            float(record["scenario_difference"]),
            abs_tol=1e-8,
        )
        # Alabama's reference and scenario paths must come from the same model/scenario pair,
        # not a mismatched lookup.
        assert record["model"] == "statistical_ridge"
        assert record["scenario"] == "remote_work_saves_time"


def test_remote_work_saves_time_sign_pattern_across_all_horizon_years() -> None:
    bundle = load_dashboard_bundle()
    horizon_years = bundle["horizon_years"]
    tolerance = 0.05

    for year in horizon_years:
        rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", year)
        assert rows
        diffs = [float(row["scenario_difference"]) for row in rows]
        positive = sum(1 for value in diffs if value > tolerance)
        negative = sum(1 for value in diffs if value < -tolerance)
        near_zero = len(diffs) - positive - negative

        assert negative == 0, f"year {year} unexpectedly has {negative} states below the reference path"
        assert sum(diffs) / len(diffs) > 0
        assert positive + near_zero == len(diffs)


def test_remote_work_saves_time_sign_pattern_across_all_available_years() -> None:
    bundle = load_dashboard_bundle()
    tolerance = 0.05
    rows = scenario_rows(bundle, "statistical_ridge", "remote_work_saves_time")
    years = sorted({int(row["year"]) for row in rows})

    assert years
    for year in years:
        year_rows = [row for row in rows if int(row["year"]) == year]
        diffs = [float(row["scenario_difference"]) for row in year_rows]
        positive = sum(1 for value in diffs if value > tolerance)
        negative = sum(1 for value in diffs if value < -tolerance)
        near_zero = len(diffs) - positive - negative

        assert negative == 0, f"year {year} unexpectedly has {negative} states below the reference path"
        assert sum(diffs) / len(diffs) > 0
        assert positive + near_zero == len(diffs)


def test_remote_work_saves_time_is_not_a_constant_shift_in_any_horizon_year() -> None:
    bundle = load_dashboard_bundle()
    horizon_years = bundle["horizon_years"]

    for year in horizon_years:
        rows = current_view_rows(bundle, "statistical_ridge", "remote_work_saves_time", year)
        diffs = [float(row["scenario_difference"]) for row in rows]
        n_unique = len({round(value, 6) for value in diffs})
        # At the most distant horizon (2060) a subset of states legitimately saturate at the
        # dashboard's forecast floor for both the reference and scenario path, which collapses
        # their difference to exactly 0 -- that's the safety clamp, not a constant-shift bug.
        # Outside states still vary, so unique values should stay well above 1.
        assert n_unique > 5, f"year {year} looks like a constant shift across states ({n_unique} unique values)"


def test_map_colorscale_orders_negative_to_positive_as_red_to_teal() -> None:
    script = load_dashboard_script()
    # zmin/zmax come from the actual scenario-difference extent and zmid pins the neutral color
    # to zero, so stop 0 (zmin, the negative end) must be the red/brick color and stop 1 (zmax,
    # the positive end) must be teal -- the map must never recolor a negative value as positive.
    assert '[[0, "#8b3a22"], [0.5, "#f6f1e8"], [1, "#1f6b75"]]' in script
    assert 'zmid: dashboardState.selectedOutcome === "scenario_difference" ? 0 : undefined' in script


def test_no_hardcoded_sign_flip_for_remote_work_saves_time_in_script() -> None:
    script = load_dashboard_script()
    # Guard against a future regression that manually negates or special-cases this scenario's
    # sign instead of letting it fall out of scenario_path - reference_path.
    forbidden_patterns = [
        "remote_work_saves_time\" ? -1",
        "remote_work_saves_time\" ? -",
        "-scenario_difference",
        "scenario_difference * -1",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in script


def test_dashboard_scenario_maps_to_the_intended_source_scenario() -> None:
    build_script = (PROJECT_ROOT / "scripts" / "build_static_dashboard_bundle.py").read_text(encoding="utf-8")
    assert '"id": "remote_work_saves_time"' in build_script
    assert '"source_scenario": "remote_work_dominant"' in build_script
    # The two must appear as one scenario block, not be split across unrelated entries.
    block_start = build_script.index('"id": "remote_work_saves_time"')
    block = build_script[block_start:block_start + 300]
    assert '"source_scenario": "remote_work_dominant"' in block


def test_missing_scenario_predictions_are_dropped_not_negative_filled() -> None:
    bundle = load_dashboard_bundle()
    for record in bundle["forecast_records"]:
        scenario_path = record["scenario_path"]
        reference_path = record["reference_path"]
        assert math.isfinite(float(scenario_path))
        assert math.isfinite(float(reference_path))
        # A silent negative-default fill (e.g. -1, -999) would show up as an implausible GFR level.
        assert float(scenario_path) >= 0
        assert float(reference_path) >= 0


def test_alabama_remote_work_saves_time_stays_nonnegative_in_any_available_year() -> None:
    bundle = load_dashboard_bundle()
    alabama_rows = [
        record for record in scenario_rows(bundle, "statistical_ridge", "remote_work_saves_time")
        if record["state_abbr"] == "AL"
    ]

    assert alabama_rows
    assert all(float(record["scenario_difference"]) >= 0 for record in alabama_rows)
    assert any(float(record["scenario_difference"]) > 0.05 for record in alabama_rows)


def test_remote_work_scenario_exports_bounded_shares_positive_commute_and_nonnegative_delta() -> None:
    bundle = load_dashboard_bundle()
    rows = scenario_rows(bundle, "statistical_ridge", "remote_work_saves_time")
    assert rows
    for record in rows:
        scenario_share = float(record["remote_work_share"])
        reference_share = float(record["reference_remote_work_share"])
        commute_minutes = float(record["mean_commute_minutes_state_year"])
        delta_time_saved = float(record["delta_remote_work_time_saved"])
        assert 0.0 <= scenario_share <= 1.0
        assert 0.0 <= reference_share <= 1.0
        assert scenario_share >= reference_share
        assert commute_minutes > 0
        assert delta_time_saved >= 0


def test_remote_work_scenario_metadata_documents_formula_calibration_and_commute_quality() -> None:
    bundle = load_dashboard_bundle()
    meta = bundle["metadata"]["remote_work_scenario"]
    rows = scenario_rows(bundle, "statistical_ridge", "remote_work_saves_time")

    assert meta["default_level"] == "conservative"
    assert math.isclose(float(meta["default_births_per_1000_per_1sd"]), 0.256923795041114, rel_tol=0.0, abs_tol=1e-12)
    assert "delta_remote_work_time_saved" in meta["formula"]
    assert "reference_mean_commute_minutes_state_year" in meta["formula"]
    assert meta["source"]["file"].endswith("did_results_remote_mean_only.csv")
    assert meta["commute_input_summary"] == "region fallback"
    assert all(record["commute_minutes_quality_state_year"] == "region_fallback" for record in rows)
    assert all(record["remote_work_scenario_adjustment_formula"] == "delta_remote_work_time_saved_only" for record in rows)


def test_figure1_note_contains_scenario_specific_interpretation_logic() -> None:
    script = load_dashboard_script()
    required_copy = [
        "buildScenarioInterpretationNote()",
        "buildScenarioCalibrationNote()",
        "buildScenarioCommuteInputNote()",
        'Scenario interpretation: This scenario assumes that remote work saves commuting time and increases flexibility.',
        "Positive values mean the scenario path is above the reference path.",
        "The default calibration is anchored to the ",
        "Commute-time inputs use ",
        'Scenario interpretation: this scenario uses ATUS-based screen leisure and digital media minutes as proxies for screen-based distraction.',
        'Scenario interpretation: this scenario assumes that online social life and digital matching tools make it easier for people to meet or maintain relationships.',
        'Scenario interpretation: this scenario assumes that more digital life - remote work, online services and shopping, and digital entertainment - keeps more activities inside the home and increases unpaid care or household-work burdens.',
    ]
    for needle in required_copy:
        assert needle in script


def test_no_undocumented_legacy_remote_work_coefficients_remain_in_dashboard_files() -> None:
    script = load_dashboard_script()
    build_script = (PROJECT_ROOT / "scripts" / "build_static_dashboard_bundle.py").read_text(encoding="utf-8")
    for needle in ["1.35", "0.36"]:
        assert needle not in script
        assert needle not in build_script


def test_public_dashboard_text_does_not_expose_raw_proxy_names() -> None:
    script = load_dashboard_script()
    html = load_dashboard_html()
    forbidden = [
        "work_family_compatibility_proxy",
        "digital_distraction_index",
        "digital_social_index",
        "gendered_care_risk_proxy",
        "search_interest_online_dating_state_year",
    ]
    for needle in forbidden:
        assert needle not in html
        assert needle not in script


def test_online_life_helps_matching_is_not_identical_to_reference_path() -> None:
    bundle = load_dashboard_bundle()
    for model in {record["model"] for record in bundle["forecast_records"]}:
        rows = scenario_rows(bundle, model, "online_life_helps_matching")
        assert rows
        diffs = [float(row["scenario_difference"]) for row in rows]
        assert any(abs(value) > 1e-6 for value in diffs), (
            f"online_life_helps_matching is mechanically equal to the reference path for model {model}"
        )


def test_online_life_helps_matching_varies_meaningfully_by_state() -> None:
    bundle = load_dashboard_bundle()
    rows = current_view_rows(bundle, "statistical_ridge", "online_life_helps_matching", 2035)
    diffs = [float(row["scenario_difference"]) for row in rows]
    assert len({round(value, 6) for value in diffs}) > 5


def test_home_centered_care_work_scenario_uses_new_id_and_label() -> None:
    bundle = load_dashboard_bundle()
    scenario_ids = {scenario["id"] for scenario in bundle["scenario_options"]}
    assert "home_centered_digital_life_increases_care_work" in scenario_ids
    assert "remote_work_increases_care_burden" not in scenario_ids

    care_scenario = next(
        scenario for scenario in bundle["scenario_options"]
        if scenario["id"] == "home_centered_digital_life_increases_care_work"
    )
    assert care_scenario["label"] == "More time at home increases care work"

    rows = scenario_rows(bundle, "statistical_ridge", "home_centered_digital_life_increases_care_work")
    assert rows


def test_old_care_burden_scenario_key_resolves_through_alias() -> None:
    script = load_dashboard_script()
    bundle = load_dashboard_bundle()
    assert "remote_work_increases_care_burden" in script
    assert "home_centered_digital_life_increases_care_work" in script
    assert "function resolveScenarioId" in script
    assert bundle["scenario_id_aliases"]["remote_work_increases_care_burden"] == (
        "home_centered_digital_life_increases_care_work"
    )


def test_care_work_scenario_varies_meaningfully_by_state_and_is_fertility_reducing() -> None:
    bundle = load_dashboard_bundle()
    rows = current_view_rows(bundle, "statistical_ridge", "home_centered_digital_life_increases_care_work", 2035)
    assert rows
    diffs = [float(row["scenario_difference"]) for row in rows]
    assert len({round(value, 6) for value in diffs}) > 5
    assert all(value <= 0 for value in diffs)
    assert any(value < -0.01 for value in diffs)


def test_figure2_line_series_use_the_same_raw_paths_as_the_map_for_every_scenario() -> None:
    # Figure 2 (buildPathSeries) must read record.scenario_path / record.reference_path directly,
    # the same fields the map trace's customdata uses -- not a derived or differently-sourced value.
    script = load_dashboard_script()
    assert "value: Number(useScenarioPath ? record.scenario_path : record.reference_path) + manualAdjustment" in script
    assert "return [row.geography_id, row.geography_name, row.reference_path, row.scenario_path, row.scenario_difference, row.main_driver || \"\"];" in script


def test_neural_network_forecast_is_not_mostly_clamped_at_the_ceiling() -> None:
    bundle = load_dashboard_bundle()
    nn_rows = [
        record for record in bundle["forecast_records"]
        if record.get("geography_type", "state") == "state"
        and record["model"] == "temporal_neural_net"
    ]
    assert nn_rows
    # reference_path is the underlying model prediction; if the recursive forecast had exploded it
    # would pin most paths at the 150.0 ceiling and collapse scenario differences to zero.
    ceiling = 150.0
    floor = 5.0
    paths = [float(record["reference_path"]) for record in nn_rows]
    at_ceiling = sum(1 for value in paths if value >= ceiling - 1e-3)
    at_floor = sum(1 for value in paths if value <= floor + 1e-3)
    clamp_share = (at_ceiling + at_floor) / len(paths)
    assert clamp_share < 0.05, f"neural-network forecast is {clamp_share:.0%} clamped"


def test_model_options_carry_clamping_reliability_diagnostics() -> None:
    bundle = load_dashboard_bundle()
    by_id = {model["id"]: model for model in bundle["model_options"]}
    for model in bundle["model_options"]:
        assert "forecast_clamp_share" in model
        assert "forecast_clamped_heavily" in model
        assert "reliable" in model
    # The neural network is fixed: it must not be flagged as heavily clamped and must be reliable.
    nn = by_id["temporal_neural_net"]
    assert nn["forecast_clamped_heavily"] is False
    assert nn["reliable"] is True
    assert float(nn["forecast_clamp_share"]) < 0.05


def test_dashboard_flags_or_excludes_heavily_clamped_models() -> None:
    # If any model is heavily clamped (reference and scenario paths collapse onto one value), the
    # dashboard must flag it as unreliable so users cannot compare scenarios with a degenerate model.
    bundle = load_dashboard_bundle()
    script = load_dashboard_script()
    assert "buildModelReliabilityNote" in script
    for model in bundle["model_options"]:
        if model.get("forecast_clamped_heavily"):
            assert model.get("reliable") is False


def test_scenario_differences_are_not_mechanically_zero_from_clipping() -> None:
    bundle = load_dashboard_bundle()
    scenario_ids = {
        scenario["id"] for scenario in bundle["scenario_options"]
        if scenario["id"] != "reference_path"
    }
    for model in {record["model"] for record in bundle["forecast_records"]}:
        for scenario_id in scenario_ids:
            rows = scenario_rows(bundle, model, scenario_id)
            assert rows
            diffs = [float(row["scenario_difference"]) for row in rows]
            nonzero = [value for value in diffs if abs(value) > 1e-6]
            assert nonzero, (
                f"{scenario_id} for {model} collapsed to exactly zero everywhere (likely a clipping artifact)"
            )


def test_online_life_helps_matching_is_meaningfully_nonzero_not_just_near_zero() -> None:
    bundle = load_dashboard_bundle()
    rows = current_view_rows(bundle, "statistical_ridge", "online_life_helps_matching", 2035)
    assert rows
    diffs = [float(row["scenario_difference"]) for row in rows]
    mean_abs = sum(abs(value) for value in diffs) / len(diffs)
    # The adjustment must be visible, not a sub-0.01 rounding-level shift.
    assert mean_abs > 0.03, f"online matching mean |difference| is only {mean_abs:.4f}"
    assert max(diffs) - min(diffs) > 0.005
    assert all(value > 0 for value in diffs), "online matching should place fertility above the reference path"


def test_screen_leisure_inputs_are_populated_and_geography_is_documented() -> None:
    bundle = load_dashboard_bundle()
    rows = current_view_rows(bundle, "statistical_ridge", "digital_distraction_crowds_out", 2035)
    assert rows
    screen_values = [
        float(row["screen_leisure_minutes_broad"])
        for row in rows
        if row.get("screen_leisure_minutes_broad") is not None
    ]
    media_values = [
        float(row["digital_media_minutes_narrow"])
        for row in rows
        if row.get("digital_media_minutes_narrow") is not None
    ]
    assert screen_values, "screen-leisure minutes are not populated on the scenario records"
    assert media_values, "narrow digital-media minutes are not populated on the scenario records"
    # The inputs must vary by state, not be a single flat national value.
    assert len({round(value, 3) for value in screen_values}) > 5

    atus_quality = [
        row for row in bundle["quality_panel"]
        if "ATUS" in str(row.get("source_used", ""))
        and "screen_leisure" in str(row.get("measurement_type", ""))
    ]
    assert atus_quality, "screen-leisure geography level is not documented in the quality panel"
    assert "state-year" in str(atus_quality[0]["geography_level"]).lower()


def test_map_and_figure2_agree_in_sign_for_every_scenario_state_and_horizon_year() -> None:
    bundle = load_dashboard_bundle()
    horizon_years = bundle["horizon_years"]
    scenario_ids = {scenario["id"] for scenario in bundle["scenario_options"] if scenario["id"] != "reference_path"}

    for scenario_id in scenario_ids:
        for year in horizon_years:
            rows = current_view_rows(bundle, "statistical_ridge", scenario_id, year)
            assert rows, f"no rows for {scenario_id} in {year}"
            for row in rows:
                reference_path = float(row["reference_path"])
                scenario_path = float(row["scenario_path"])
                scenario_difference = float(row["scenario_difference"])
                # The map's color sign and Figure 2's line ordering both fall out of this same
                # comparison, so they cannot disagree as long as this identity holds.
                if scenario_difference > 1e-9:
                    assert scenario_path > reference_path
                elif scenario_difference < -1e-9:
                    assert scenario_path < reference_path
                else:
                    assert math.isclose(scenario_path, reference_path, abs_tol=1e-6)
