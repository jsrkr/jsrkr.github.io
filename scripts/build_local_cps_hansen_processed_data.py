from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_acs import build_weighted_acs_state_year_panel_from_dta
from src.clean_cps import (
    build_cps_wfh_state_year_panel,
    build_hansen_remote_postings_yearly,
    merge_hansen_with_cps_state_panel,
)
from src.config import PROCESSED_DATA_DIR
from src.data_download import cache_dataframe


DEFAULT_CPS_WFH_PATH = Path(r"D:\cps_00005.dta\cps_00005_wfh.dta")
DEFAULT_ACS_PATH = Path(r"D:\usa_00010.dta\usa_00010.dta")
DEFAULT_HANSEN_PATH = Path(r"D:\remote_work_in_job_ads_public_data.xlsx")


def _append_quality_rows(new_rows: pd.DataFrame) -> None:
    quality_path = PROCESSED_DATA_DIR / "measurement_quality.parquet"
    if quality_path.exists():
        quality_df = pd.read_parquet(quality_path)
        combined = pd.concat([quality_df, new_rows], ignore_index=True, sort=False)
        combined = combined.drop_duplicates(
            subset=["source_used", "measurement_type", "geography_level", "estimate_mode"],
            keep="last",
        )
    else:
        combined = new_rows
    cache_dataframe(combined, quality_path)


def _append_source_audit(rows: list[dict]) -> None:
    audit_path = PROCESSED_DATA_DIR / "local_source_audit.csv"
    new_df = pd.DataFrame(rows)
    if audit_path.exists():
        audit_df = pd.read_csv(audit_path)
        combined = pd.concat([audit_df, new_df], ignore_index=True, sort=False).drop_duplicates()
    else:
        combined = new_df
    cache_dataframe(combined, audit_path)


def _load_or_build_acs_panel() -> pd.DataFrame:
    processed_path = PROCESSED_DATA_DIR / "acs_state_year_from_acs.parquet"
    if processed_path.exists():
        return pd.read_parquet(processed_path)
    if not DEFAULT_ACS_PATH.exists():
        return pd.DataFrame()
    panel = build_weighted_acs_state_year_panel_from_dta(DEFAULT_ACS_PATH, min_year=2010, chunk_rows=1000000)
    cache_dataframe(panel, processed_path)
    return panel


def _coalesce(left: pd.Series | None, right: pd.Series | None) -> pd.Series:
    if left is None and right is None:
        return pd.Series(dtype=float)
    if left is None:
        return right.copy()
    if right is None:
        return left.copy()
    return left.combine_first(right)


def _merged_column(frame: pd.DataFrame, column: str, preferred_suffix: str | None = None) -> pd.Series | None:
    if preferred_suffix and f"{column}_{preferred_suffix}" in frame.columns:
        return frame[f"{column}_{preferred_suffix}"]
    if column in frame.columns:
        return frame[column]
    for suffix in ("acs", "cps"):
        candidate = f"{column}_{suffix}"
        if candidate in frame.columns:
            return frame[candidate]
    return None


def _combine_acs_and_cps_panels(acs_panel: pd.DataFrame, cps_panel: pd.DataFrame) -> pd.DataFrame:
    if acs_panel.empty:
        out = cps_panel.copy()
        out["acs_warning"] = (
            "Local ACS microdata are unavailable for this build, so remote-work and related controls rely on CPS/Hansen fallback estimates."
        )
        return out

    merged = cps_panel.merge(
        acs_panel,
        on=["state_fips", "year"],
        how="outer",
        suffixes=("_cps", "_acs"),
    )
    out = pd.DataFrame()
    out["state_fips"] = _coalesce(merged.get("state_fips"), None)
    out["year"] = pd.to_numeric(merged["year"], errors="coerce").astype(int)
    out["region"] = _coalesce(merged.get("region_acs"), merged.get("region_cps"))

    prefer_acs_cols = [
        "remote_work_share_state_year",
        "observed_remote_work_share_acs",
        "on_site_work_share_state_year",
        "usual_hours_all_workers",
        "usual_hours_wfh_workers",
        "telework_hours_mean_among_remote",
        "remote_work_hours_proxy",
        "mean_commute_minutes_state_year",
        "long_commute_share_state_year",
        "female_employment_rate",
        "labor_force_participation_rate",
        "married_or_partnered_share_state_year",
        "sample_size",
    ]
    for column in prefer_acs_cols:
        out[column] = _coalesce(
            _merged_column(merged, column, preferred_suffix="acs"),
            _merged_column(merged, column, preferred_suffix="cps"),
        )

    passthrough_cps_cols = [
        "observed_remote_work_share_cps",
        "remote_posting_share_year",
        "remote_posting_proxy_state_year",
        "wfh_share_2019_occ_mix",
        "wfh_share_post_2023_2024_occ_mix",
        "has_public_wfh_coverage_share",
        "labor_force_participation_rate_partnered_sample",
        "female_employment_rate_partnered_sample",
        "married_or_partnered_share_partnered_sample",
    ]
    for column in passthrough_cps_cols:
        source_col = _merged_column(merged, column, preferred_suffix="cps")
        if source_col is not None:
            out[column] = source_col

    out["source_used"] = np.where(
        merged.get("remote_work_share_state_year_acs").notna(),
        "IPUMS ACS microdata",
        "Local CPS WFH extract + Hansen remote-postings workbook",
    )
    out["proxy_mode"] = np.where(
        merged.get("remote_work_share_state_year_acs").notna(),
        "observed_acs",
        _merged_column(merged, "proxy_mode", preferred_suffix="cps").fillna("missing"),
    )
    out["measurement_note"] = np.where(
        merged.get("remote_work_share_state_year_acs").notna(),
        "ACS is the primary source for remote-work share, commute burden, work hours, and broad state-year work/family controls for years available in the local IPUMS extract.",
        "CPS telework responses are used when observed; Hansen remote-posting shares provide a state-scaled fallback for remote-work exposure outside ACS coverage.",
    )
    out["source_warning"] = np.where(
        merged.get("remote_work_share_state_year_acs").notna(),
        "ACS coverage in the local extract begins in 2014, so ACS directly supports years 2014-2024 in this dashboard build.",
        "Years outside ACS coverage use CPS/Hansen fallback estimates; CPS fields come from a married-sample analytic extract rather than a full population ACS panel.",
    )
    out["acs_warning"] = _coalesce(
        merged.get("acs_warning_acs"),
        pd.Series(
            np.where(
                merged.get("remote_work_share_state_year_acs").isna(),
                "Local ACS extract does not cover this state-year, so CPS/Hansen fallback values are used where available.",
                "",
            ),
            index=merged.index,
            dtype=object,
        ),
    )
    return out.sort_values(["state_fips", "year"]).reset_index(drop=True)


def main() -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_CPS_WFH_PATH.exists():
        raise FileNotFoundError(f"CPS WFH file not found: {DEFAULT_CPS_WFH_PATH}")
    if not DEFAULT_HANSEN_PATH.exists():
        raise FileNotFoundError(f"Hansen workbook not found: {DEFAULT_HANSEN_PATH}")

    acs_panel = _load_or_build_acs_panel()
    cps_panel = build_cps_wfh_state_year_panel(DEFAULT_CPS_WFH_PATH)
    hansen_yearly = build_hansen_remote_postings_yearly(DEFAULT_HANSEN_PATH)
    cps_hansen_panel = merge_hansen_with_cps_state_panel(cps_panel, hansen_yearly)
    state_year_panel = _combine_acs_and_cps_panels(acs_panel, cps_hansen_panel)
    state_year_panel["data_quality_note"] = (
        "ACS is the primary source for years covered in the local IPUMS extract. CPS telework responses and Hansen remote-posting shares fill years or fields not covered by ACS."
    )

    quality_rows = pd.DataFrame(
        [
            {
                "source_used": "IPUMS ACS microdata",
                "is_representative": True,
                "measurement_type": "state_year_work_commute_controls",
                "geography_level": "state",
                "latest_year": int(acs_panel["year"].max()) if not acs_panel.empty else np.nan,
                "estimate_mode": "direct weighted state-year estimates from local ACS microdata where available",
                "sample_size": float(acs_panel["sample_size"].median()) if not acs_panel.empty else np.nan,
                "warning_flags": "The local ACS extract covers 2014-2024 rather than the full 2010-2025 dashboard window, so earlier years still rely on fallback sources.",
            },
            {
                "source_used": "Local CPS WFH extract",
                "is_representative": False,
                "measurement_type": "remote_work_fallback",
                "geography_level": "state",
                "latest_year": int(state_year_panel["year"].max()),
                "estimate_mode": "direct CPS telework for the married-sample extract when observed; used mainly outside ACS coverage or for retained fallback fields",
                "sample_size": float(cps_hansen_panel["sample_size"].median()),
                "warning_flags": "The CPS WFH file is a married-sample analytic extract, not a full population-representative ACS replacement.",
            },
            {
                "source_used": "Hansen remote-work job-postings workbook",
                "is_representative": False,
                "measurement_type": "national remote-posting share",
                "geography_level": "national",
                "latest_year": int(hansen_yearly["year"].max()),
                "estimate_mode": "direct national series, state-scaled by occupational exposure",
                "sample_size": float("nan"),
                "warning_flags": "This is a postings-based remote-work proxy, not a direct state household survey estimate.",
            },
        ]
    )

    cache_dataframe(state_year_panel, PROCESSED_DATA_DIR / "acs_state_year.parquet")
    if not acs_panel.empty:
        cache_dataframe(acs_panel, PROCESSED_DATA_DIR / "acs_state_year_from_acs.parquet")
    cache_dataframe(hansen_yearly, PROCESSED_DATA_DIR / "hansen_remote_postings_yearly.parquet")
    _append_quality_rows(quality_rows)
    _append_source_audit(
        [
            {
                "source": str(DEFAULT_ACS_PATH),
                "status": "used",
                "reason": "Built direct weighted ACS state-year measures for 2014-2024 from the local IPUMS extract.",
            },
            {
                "source": str(DEFAULT_CPS_WFH_PATH),
                "status": "used",
                "reason": "Used CPS telework responses as fallback remote-work evidence outside ACS coverage and retained CPS-specific fallback fields.",
            },
            {
                "source": str(DEFAULT_HANSEN_PATH),
                "status": "used",
                "reason": "Used Hansen national remote-posting shares to scale fallback state remote-work exposure where direct survey coverage is incomplete.",
            },
        ]
    )

    print(f"Wrote {PROCESSED_DATA_DIR / 'acs_state_year.parquet'}")
    if not acs_panel.empty:
        print(f"Wrote {PROCESSED_DATA_DIR / 'acs_state_year_from_acs.parquet'}")
    print(f"Wrote {PROCESSED_DATA_DIR / 'hansen_remote_postings_yearly.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'measurement_quality.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'local_source_audit.csv'}")
    print("Years covered in combined ACS/CPS panel:", sorted(state_year_panel["year"].dropna().unique().tolist()))


if __name__ == "__main__":
    main()
