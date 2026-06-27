from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from pytrends.request import TrendReq

from .config import EXPECTED_COLUMNS, RAW_DATA_DIR


class DataDownloadError(RuntimeError):
    """Raised when a source cannot be downloaded and no local fallback is available."""


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def validate_columns(df: pd.DataFrame, expected_columns: Iterable[str], dataset_name: str) -> None:
    missing = [column for column in expected_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} is missing expected columns: {missing}")


def cache_dataframe(df: pd.DataFrame, path: Path) -> Path:
    ensure_parent(path)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path


def load_cached_dataframe(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def get_json(url: str, cache_path: Path | None = None, params: dict | None = None, timeout: int = 120) -> dict:
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if cache_path:
        ensure_parent(cache_path)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def get_csv(url: str, cache_path: Path | None = None, params: dict | None = None, timeout: int = 120) -> pd.DataFrame:
    cached = load_cached_dataframe(cache_path) if cache_path else None
    if cached is not None:
        return cached

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text))
    if cache_path:
        cache_dataframe(df, cache_path)
    return df


def load_local_csv_or_raise(path: str | Path, expected_columns: Iterable[str], dataset_name: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise DataDownloadError(
            f"{dataset_name} could not be downloaded automatically. Please provide a local CSV at {csv_path}."
        )
    df = pd.read_csv(csv_path)
    validate_columns(df, expected_columns, dataset_name)
    return df


def fetch_acs_api(
    year: int,
    dataset: str,
    variables: list[str],
    geography: str = "state:*",
    cache_name: str | None = None,
) -> pd.DataFrame:
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise DataDownloadError(
            "Census API key not found. Set CENSUS_API_KEY or load local ACS extracts instead."
        )
    url = f"https://api.census.gov/data/{year}/acs/{dataset}"
    params = {"get": ",".join(["NAME", *variables]), "for": geography, "key": api_key}
    cache_path = RAW_DATA_DIR / "acs_api" / (cache_name or f"{dataset}_{year}.json")
    payload = get_json(url, cache_path=cache_path, params=params)
    df = pd.DataFrame(payload[1:], columns=payload[0])
    return df


def fetch_census_population_api(year: int, variables: list[str], dataset: str = "pep/population") -> pd.DataFrame:
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        raise DataDownloadError(
            "Census API key not found. Set CENSUS_API_KEY or load local Census population CSV files."
        )
    url = f"https://api.census.gov/data/{year}/{dataset}"
    params = {"get": ",".join(["NAME", *variables]), "for": "state:*", "key": api_key}
    cache_path = RAW_DATA_DIR / "census_population" / f"{dataset.replace('/', '_')}_{year}.json"
    payload = get_json(url, cache_path=cache_path, params=params)
    return pd.DataFrame(payload[1:], columns=payload[0])


def fetch_world_bank_indicator(indicator_id: str, country: str = "USA") -> pd.DataFrame:
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator_id}"
    payload = get_json(
        url,
        cache_path=RAW_DATA_DIR / "world_bank" / f"{country}_{indicator_id}.json",
        params={"format": "json", "per_page": 500},
    )
    if not isinstance(payload, list) or len(payload) < 2:
        raise DataDownloadError(f"World Bank payload for {indicator_id} was not in the expected format.")
    df = pd.DataFrame(payload[1])
    if df.empty:
        raise DataDownloadError(f"World Bank indicator {indicator_id} returned no rows.")
    return df


def fetch_google_trends_state_interest(
    keywords: list[str],
    timeframe: str = "today 12-m",
    geo: str = "US",
) -> pd.DataFrame:
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    state_df = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True)
    state_df = state_df.reset_index().rename(columns={"geoName": "state_name"})
    history = pytrends.interest_over_time().reset_index()
    cache_dataframe(state_df, RAW_DATA_DIR / "google_trends" / f"state_interest_{'_'.join(keywords)}.csv")
    cache_dataframe(history, RAW_DATA_DIR / "google_trends" / f"history_{'_'.join(keywords)}.csv")
    return state_df


def load_ntia_state_csv(path: str | Path) -> pd.DataFrame:
    return load_local_csv_or_raise(path, EXPECTED_COLUMNS["ntia_state"], "NTIA/CPS Internet Use Survey")


def load_cdc_wonder_csv(path: str | Path) -> pd.DataFrame:
    return load_local_csv_or_raise(path, EXPECTED_COLUMNS["cdc_wonder_fertility"], "CDC WONDER fertility export")


def load_population_csv(path: str | Path) -> pd.DataFrame:
    return load_local_csv_or_raise(path, EXPECTED_COLUMNS["population_estimates"], "Census population data")


def load_commercial_media_template(path: str | Path) -> pd.DataFrame:
    return load_local_csv_or_raise(
        path,
        EXPECTED_COLUMNS["commercial_digital_media_template"],
        "commercial digital media template",
    )


def write_commercial_media_template(path: str | Path) -> Path:
    template_path = Path(path)
    template_df = pd.DataFrame(columns=EXPECTED_COLUMNS["commercial_digital_media_template"])
    cache_dataframe(template_df, template_path)
    return template_path

