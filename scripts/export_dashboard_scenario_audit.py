from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCENARIO_SOURCE_MAP = {
    "reference_path": "baseline_continuation",
    "remote_work_saves_time": "remote_work_dominant",
    "digital_distraction_crowds_out": "distraction_dominant",
    "online_life_helps_matching": "digital_social_substitution",
    "home_centered_digital_life_increases_care_work": "gendered_care_penalty",
}

# Old public scenario key kept as an alias so old bookmarked audit commands keep working.
SCENARIO_ID_ALIASES = {
    "remote_work_increases_care_burden": "home_centered_digital_life_increases_care_work",
}


def load_dashboard_bundle() -> dict:
    raw = (PROJECT_ROOT / "ai-work-fertility-dashboard-data.js").read_text(encoding="utf-8")
    payload = raw.split("=", 1)[1].rsplit(";", 1)[0]
    return json.loads(payload)


def build_audit_frame(model: str, scenario: str, year: int) -> pd.DataFrame:
    bundle = load_dashboard_bundle()
    rows = pd.DataFrame(bundle["forecast_records"])
    rows = rows[
        rows.get("geography_type", "state").eq("state")
        & rows["model"].eq(model)
        & rows["scenario"].eq(scenario)
        & rows["year"].astype(int).eq(year)
    ].copy()
    if rows.empty:
        return rows
    ordered_cols = [
        "state_name",
        "state_fips",
        "year",
        "model",
        "scenario",
        "reference_path",
        "scenario_path",
        "scenario_difference",
        "scenario_shift_component",
        "legacy_model_scenario_difference",
        "remote_work_share",
        "remote_work_time_saved",
        "digital_media_minutes_narrow",
        "screen_leisure_minutes_broad",
        "in_person_social_minutes",
        "care_burden_minutes",
        "contribution_remote_work_time_saved",
        "contribution_remote_work_share",
        "contribution_digital_media_minutes_narrow",
        "contribution_screen_leisure_minutes_broad",
        "contribution_in_person_social_minutes",
        "contribution_care_burden_minutes",
        "scenario_adjustment_pre_lag",
        "scenario_adjustment_post_lag",
        "recursive_lag_multiplier",
        "clamping_flag",
        "main_driver",
    ]
    ordered_cols = [column for column in ordered_cols if column in rows.columns]
    remaining = [column for column in rows.columns if column not in ordered_cols]
    return rows[ordered_cols + remaining].sort_values("scenario_difference").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="statistical_ridge")
    parser.add_argument("--scenario", default="remote_work_saves_time")
    parser.add_argument("--year", type=int, default=2035)
    args = parser.parse_args()
    scenario = SCENARIO_ID_ALIASES.get(args.scenario, args.scenario)

    audit = build_audit_frame(args.model, scenario, args.year)
    if audit.empty:
        raise SystemExit("No matching dashboard rows were found for the requested audit.")

    out_dir = PROJECT_ROOT / "outputs" / "dashboard_audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.model}_{scenario}_{args.year}_state_audit"
    csv_path = out_dir / f"{stem}.csv"
    json_path = out_dir / f"{stem}_summary.json"

    audit.to_csv(csv_path, index=False)

    diffs = audit["scenario_difference"].astype(float)
    summary = {
        "model": args.model,
        "scenario": args.scenario,
        "year": args.year,
        "n_states": int(len(audit)),
        "min_scenario_difference": float(diffs.min()),
        "max_scenario_difference": float(diffs.max()),
        "mean_scenario_difference": float(diffs.mean()),
        "std_scenario_difference": float(diffs.std(ddof=0)),
        "unique_scenario_difference_values_3dp": int(diffs.round(3).nunique()),
        "positive_states": int((diffs > 0.05).sum()),
        "negative_states": int((diffs < -0.05).sum()),
        "zero_or_near_zero_states": int((diffs.abs() < 0.05).sum()),
        "share_abs_lt_0_05": float((diffs.abs() < 0.05).mean()),
        "share_abs_lt_0_10": float((diffs.abs() < 0.10).mean()),
        "share_abs_lt_0_50": float((diffs.abs() < 0.50).mean()),
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
