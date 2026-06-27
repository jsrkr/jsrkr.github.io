from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_acs import build_weighted_acs_state_year_panel_from_dta
from src.config import PROCESSED_DATA_DIR
from src.data_download import cache_dataframe


DEFAULT_ACS_PATH = Path(r"D:\usa_00010.dta\usa_00010.dta")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build weighted ACS state-year measures from a local IPUMS ACS extract.")
    parser.add_argument("--acs-path", default=str(DEFAULT_ACS_PATH))
    parser.add_argument("--min-year", type=int, default=2010)
    parser.add_argument("--chunk-rows", type=int, default=1000000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel = build_weighted_acs_state_year_panel_from_dta(
        args.acs_path,
        min_year=args.min_year,
        chunk_rows=args.chunk_rows,
    )
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = PROCESSED_DATA_DIR / "acs_state_year_from_acs.parquet"
    cache_dataframe(panel, target)
    print(f"Wrote {target}")
    print("ACS years processed:", sorted(panel["year"].dropna().astype(int).unique().tolist()))


if __name__ == "__main__":
    main()
