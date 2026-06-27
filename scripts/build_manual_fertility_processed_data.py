from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_fertility import clean_state_year_fertility_rates
from src.config import PROCESSED_DATA_DIR
from src.data_download import cache_dataframe


RAW_FERTILITY_PATH = PROJECT_ROOT / "data" / "raw" / "manual_state_fertility_rates_2016_2023.csv"


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
    if not RAW_FERTILITY_PATH.exists():
        raise FileNotFoundError(f"Manual fertility CSV not found: {RAW_FERTILITY_PATH}")

    raw_df = pd.read_csv(RAW_FERTILITY_PATH)
    fertility_metrics = clean_state_year_fertility_rates(raw_df)
    cache_dataframe(fertility_metrics, PROCESSED_DATA_DIR / "fertility_metrics.parquet")

    quality_rows = pd.DataFrame(
        [
            {
                "source_used": "CDC NCHS Stats of the States manual state-year rates",
                "is_representative": True,
                "measurement_type": "fertility_rate",
                "geography_level": "state/national",
                "latest_year": int(fertility_metrics["year"].max()),
                "estimate_mode": "manual entry from user-supplied CDC state-year GFR and TFR table",
                "sample_size": float("nan"),
                "warning_flags": "This panel includes general fertility rate and total fertility rate only. Birth counts and age-specific fertility rates still need CDC WONDER exports.",
            }
        ]
    )
    _append_quality_rows(quality_rows)

    _append_source_audit(
        [
            {
                "source": str(RAW_FERTILITY_PATH),
                "status": "used",
                "reason": "Processed user-supplied 2016-2023 state general fertility rates and total fertility rates into the dashboard fertility panel.",
            }
        ]
    )

    print(f"Wrote {PROCESSED_DATA_DIR / 'fertility_metrics.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'measurement_quality.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'local_source_audit.csv'}")
    print("Years processed:", sorted(fertility_metrics["year"].unique().tolist()))


if __name__ == "__main__":
    main()
