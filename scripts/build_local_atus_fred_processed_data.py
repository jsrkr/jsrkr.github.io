from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_atus import build_atus_aggregates_from_raw
from src.clean_population import fetch_fred_state_population
from src.config import PROCESSED_DATA_DIR
from src.data_download import cache_dataframe


DEFAULT_ATUS_DIR = Path(r"D:\ATUS")
DEFAULT_ATUS_YEARS = list(range(2016, 2024))


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


def main() -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_ATUS_DIR.exists():
        raise FileNotFoundError(f"ATUS directory not found: {DEFAULT_ATUS_DIR}")

    atus_metrics = build_atus_aggregates_from_raw(DEFAULT_ATUS_DIR, DEFAULT_ATUS_YEARS)
    atus_metrics["source_note"] = (
        "ATUS is the benchmark source for digital media, screen leisure, in-person social, and care-burden minutes. "
        "State values are shown only when annual or pooled samples pass minimum thresholds."
    )
    atus_metrics["has_state_geography"] = atus_metrics["geography_type"].eq("state")
    cache_dataframe(atus_metrics, PROCESSED_DATA_DIR / "atus_metrics.parquet")

    population_metrics = fetch_fred_state_population()
    population_metrics["natural_increase"] = np.nan
    population_metrics["net_migration"] = np.nan
    population_metrics["source_note"] = (
        "FRED state population series support total population and growth trends, but not births, deaths, migration components, or female age denominators."
    )
    cache_dataframe(population_metrics, PROCESSED_DATA_DIR / "population_metrics.parquet")

    quality_rows = pd.DataFrame(
        [
            {
                "source_used": "Local ATUS raw files",
                "is_representative": True,
                "measurement_type": "digital_time",
                "geography_level": "national",
                "latest_year": int(atus_metrics["year"].max()),
                "estimate_mode": "direct national time-use estimate",
                "sample_size": float(
                    atus_metrics.loc[atus_metrics["geography_type"].eq("national"), "sample_size"].median()
                ),
                "warning_flags": "Best benchmark for time-use minutes. Digital-social interaction remains not directly observed.",
                "notes": "Digital media narrow uses ATUS 120308; broad screen leisure uses 120308, 120303, and 120307.",
            },
            {
                "source_used": "Local ATUS raw files",
                "is_representative": True,
                "measurement_type": "digital_time",
                "geography_level": "region/state pooled",
                "latest_year": int(atus_metrics["year"].max()),
                "estimate_mode": "direct regional estimates; state estimates pooled or hidden when samples are small",
                "sample_size": float(
                    atus_metrics.loc[atus_metrics["geography_type"].eq("state"), "sample_size"].median()
                )
                if atus_metrics["geography_type"].eq("state").any()
                else np.nan,
                "warning_flags": "Small state ATUS cells are pooled or hidden. The local 2022-2023 folders do not currently contain extracted ATUS-CPS geography files, so those years are national-only in this build.",
                "notes": "State-year ATUS estimates are annual when sample sizes are large enough and otherwise use pooled or broader-geography substitutes.",
            },
            {
                "source_used": "FRED release 118 state population series",
                "is_representative": True,
                "measurement_type": "population_total",
                "geography_level": "state",
                "latest_year": int(population_metrics["year"].max()),
                "estimate_mode": "direct annual state population totals from official FRED-hosted series",
                "sample_size": np.nan,
                "warning_flags": "Useful for total population and growth only. Female age groups, births, deaths, and migration components still need Census or CDC files.",
            },
        ]
    )
    _append_quality_rows(quality_rows)

    _append_source_audit(
        [
            {
                "source": str(DEFAULT_ATUS_DIR),
                "status": "used",
                "reason": "Processed local ATUS raw files into national, regional, and state-pooled time-use metrics for 2016-2023 where files are available.",
            },
            {
                "source": "https://fred.stlouisfed.org/release?rid=118&t=state&ob=pv&od=desc",
                "status": "used",
                "reason": "Parsed official FRED state population series into annual state population totals and growth rates.",
            },
        ]
    )

    print(f"Wrote {PROCESSED_DATA_DIR / 'atus_metrics.parquet'}")
    print(f"Wrote {PROCESSED_DATA_DIR / 'population_metrics.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'measurement_quality.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'local_source_audit.csv'}")
    print("ATUS years processed:", sorted(atus_metrics["year"].dropna().unique().tolist()))
    print("Population years processed:", sorted(population_metrics["year"].dropna().unique().tolist())[:3], "...")


if __name__ == "__main__":
    main()
