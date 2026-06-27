from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clean_digital_media import build_google_trends_state_year_proxy
from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.data_download import cache_dataframe


YEARS = list(range(2016, 2025))
KEYWORD_GROUPS = {
    "search_interest_genai_state_year": ["chatgpt", "claude ai", "gemini ai"],
    "search_interest_online_dating_state_year": ["tinder", "bumble", "hinge"],
}
RAW_CACHE_PATH = RAW_DATA_DIR / "google_trends_state_year_raw.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Google Trends state-year proxy data for U.S. GenAI and online dating.")
    parser.add_argument("--sleep-seconds", type=float, default=1.25, help="Seconds to wait between Google Trends state-year requests.")
    parser.add_argument("--cache-only", action="store_true", help="Skip new Google Trends requests and rebuild processed output from the cached raw CSV only.")
    return parser.parse_args()


def _request_with_retry(pytrends: TrendReq, keywords: list[str], timeframe: str, geo: str = "US", retries: int = 4) -> None:
    for attempt in range(retries):
        try:
            pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 + attempt)


def _annual_national_series(pytrends: TrendReq, keyword: str) -> pd.DataFrame:
    _request_with_retry(pytrends, [keyword], timeframe="2016-01-01 2024-12-31", geo="US")
    history = pytrends.interest_over_time().reset_index()
    if history.empty or keyword not in history.columns:
        raise ValueError(f"Google Trends returned no history for keyword: {keyword}")
    history["year"] = pd.to_datetime(history["date"], errors="coerce").dt.year
    out = history.groupby("year", as_index=False)[keyword].mean().rename(columns={keyword: "national_year_interest"})
    out["keyword"] = keyword
    return out[["keyword", "year", "national_year_interest"]]


def _state_cross_section(pytrends: TrendReq, keyword: str, year: int) -> pd.DataFrame:
    timeframe = f"{year}-01-01 {year}-12-31"
    _request_with_retry(pytrends, [keyword], timeframe=timeframe, geo="US")
    state_df = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True).reset_index()
    if state_df.empty or "geoName" not in state_df.columns or keyword not in state_df.columns:
        raise ValueError(f"Google Trends returned no state cross-section for keyword={keyword}, year={year}")
    out = state_df.rename(columns={"geoName": "state_name", keyword: "regional_interest"}).copy()
    out["keyword"] = keyword
    out["year"] = year
    return out[["state_name", "year", "keyword", "regional_interest"]]


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


def _load_existing_raw() -> pd.DataFrame:
    if RAW_CACHE_PATH.exists():
        return pd.read_csv(RAW_CACHE_PATH)
    return pd.DataFrame(columns=["state_name", "year", "keyword", "regional_interest", "national_year_interest"])


def _raw_has_national(existing_raw: pd.DataFrame, keyword: str) -> bool:
    if existing_raw.empty:
        return False
    subset = existing_raw.loc[existing_raw["keyword"].eq(keyword) & existing_raw["national_year_interest"].notna(), "year"]
    return set(pd.to_numeric(subset, errors="coerce").dropna().astype(int).tolist()) >= set(YEARS)


def _raw_has_state_year(existing_raw: pd.DataFrame, keyword: str, year: int) -> bool:
    if existing_raw.empty:
        return False
    subset = existing_raw.loc[
        existing_raw["keyword"].eq(keyword)
        & pd.to_numeric(existing_raw["year"], errors="coerce").eq(year)
        & existing_raw["state_name"].ne("United States")
    ]
    return subset["state_name"].nunique() >= 51


def _persist_and_process(raw_panel: pd.DataFrame) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_dataframe(raw_panel, RAW_CACHE_PATH)

    digital_attention = build_google_trends_state_year_proxy(raw_panel, KEYWORD_GROUPS)
    cache_dataframe(digital_attention, PROCESSED_DATA_DIR / "digital_attention.parquet")

    quality_rows = pd.DataFrame(
        [
            {
                "source_used": "Google Trends via pytrends",
                "is_representative": False,
                "measurement_type": "digital_attention",
                "geography_level": "state/national",
                "latest_year": int(digital_attention["year"].max()),
                "estimate_mode": "state cross-sections scaled by keyword-specific national annual intensity",
                "sample_size": float("nan"),
                "warning_flags": digital_attention["warning_flag"].iloc[0],
            }
        ]
    )
    _append_quality_rows(quality_rows)

    _append_source_audit(
        [
            {
                "source": "Google Trends via pytrends",
                "status": "used",
                "reason": "Built state-year search-attention proxies for GenAI and online dating in the United States for 2016-2024.",
            }
        ]
    )

    print(f"Wrote {RAW_CACHE_PATH}")
    print(f"Wrote {PROCESSED_DATA_DIR / 'digital_attention.parquet'}")
    print(f"Updated {PROCESSED_DATA_DIR / 'measurement_quality.parquet'}")


def main() -> None:
    args = parse_args()
    existing_raw = _load_existing_raw()

    if args.cache_only:
        if existing_raw.empty:
            raise FileNotFoundError(f"No cached raw Google Trends file found at {RAW_CACHE_PATH}")
        _persist_and_process(existing_raw)
        print("Rebuilt processed digital attention data from cached raw Google Trends rows only.")
        return

    pytrends = TrendReq(hl="en-US", tz=360)
    keywords = sorted({keyword for group in KEYWORD_GROUPS.values() for keyword in group})

    national_frames = []
    state_frames = []
    try:
        for keyword in keywords:
            if not _raw_has_national(existing_raw, keyword):
                national_frames.append(_annual_national_series(pytrends, keyword))
                time.sleep(args.sleep_seconds)
            for year in YEARS:
                if _raw_has_state_year(existing_raw, keyword, year):
                    continue
                state_frames.append(_state_cross_section(pytrends, keyword, year))
                time.sleep(args.sleep_seconds)
    except TooManyRequestsError:
        print("Google Trends returned HTTP 429 (rate limit). Reusing cached rows and any rows fetched before the rate limit hit.")

    fresh_national = pd.concat(national_frames, ignore_index=True) if national_frames else pd.DataFrame(columns=["keyword", "year", "national_year_interest"])
    fresh_state = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame(columns=["state_name", "year", "keyword", "regional_interest"])

    state_rows_existing = existing_raw.loc[existing_raw["state_name"].ne("United States"), ["state_name", "year", "keyword", "regional_interest"]].copy()
    national_rows_existing = existing_raw.loc[:, ["keyword", "year", "national_year_interest"]].dropna().drop_duplicates().copy()

    state_year = pd.concat([state_rows_existing, fresh_state], ignore_index=True, sort=False).drop_duplicates(
        subset=["state_name", "year", "keyword"],
        keep="last",
    )
    national_year = pd.concat([national_rows_existing, fresh_national], ignore_index=True, sort=False).drop_duplicates(
        subset=["keyword", "year"],
        keep="last",
    )

    if state_year.empty or national_year.empty:
        raise RuntimeError("No Google Trends rows were available. Wait a bit and retry, or rerun later with --cache-only if a raw CSV already exists.")

    raw_panel = state_year.merge(national_year, on=["keyword", "year"], how="left")
    national_rows = national_year.copy()
    national_rows["state_name"] = "United States"
    national_rows["regional_interest"] = 100.0
    raw_panel = pd.concat(
        [raw_panel, national_rows[["state_name", "year", "keyword", "regional_interest", "national_year_interest"]]],
        ignore_index=True,
        sort=False,
    )

    _persist_and_process(raw_panel)
    print("Keywords:", ", ".join(keywords))
    print("Tip: if Google rate-limits you again, rerun with `--cache-only` to rebuild from the saved raw CSV without making new requests.")


if __name__ == "__main__":
    main()
