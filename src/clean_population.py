from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
import requests

from .config import STATE_ABBR_TO_FIPS, STATE_FIPS_TO_REGION
from .data_download import validate_columns


def clean_population_estimates(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, ["state_fips", "year", "population_total"], "population estimates")
    out = df.copy()
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype(int)
    value_cols = [
        "population_total",
        "births",
        "deaths",
        "domestic_migration",
        "international_migration",
        "female_population_15_44",
        "female_population",
    ]
    for column in value_cols:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.sort_values(["state_fips", "year"])
    out["population_growth_rate"] = out.groupby("state_fips")["population_total"].pct_change()
    if {"births", "deaths"}.issubset(out.columns):
        out["natural_increase"] = out["births"] - out["deaths"]
    else:
        out["natural_increase"] = np.nan
    migration_cols = [column for column in ["domestic_migration", "international_migration"] if column in out.columns]
    out["net_migration"] = out[migration_cols].sum(axis=1) if migration_cols else np.nan
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    return out


def clean_population_projections(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, ["state_fips", "year", "population_total"], "population projections")
    out = clean_population_estimates(df)
    out["projection_type"] = "external_projection"
    return out


def fetch_fred_state_population(release_url: str = "https://fred.stlouisfed.org/release?rid=118&t=state&ob=pv&od=desc") -> pd.DataFrame:
    html = requests.get(release_url, timeout=60).text
    series_ids = sorted(set(re.findall(r"/series/([A-Z0-9_]+)", html)))
    population_series = [series_id for series_id in series_ids if series_id.endswith("POP") and len(series_id) in {5, 6}]

    rows: list[pd.DataFrame] = []
    for series_id in population_series:
        csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        response = requests.get(csv_url, timeout=60)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        if df.empty or series_id not in df.columns:
            continue
        date_col = next((column for column in ["DATE", "date", "observation_date"] if column in df.columns), None)
        if date_col is None:
            continue
        state_abbr = series_id.replace("POP", "")
        if state_abbr not in STATE_ABBR_TO_FIPS:
            continue
        series = df.rename(columns={date_col: "date", series_id: "population_total"}).copy()
        series["population_total"] = pd.to_numeric(series["population_total"], errors="coerce")
        series = series.dropna(subset=["population_total"])
        series["date"] = pd.to_datetime(series["date"], errors="coerce")
        series = series.dropna(subset=["date"])
        series["year"] = series["date"].dt.year.astype(int)
        series["state_fips"] = STATE_ABBR_TO_FIPS[state_abbr]
        series["source_used"] = "FRED release 118"
        rows.append(series[["state_fips", "year", "population_total", "source_used"]])

    if not rows:
        raise ValueError("No state population series could be parsed from the FRED release page.")
    out = pd.concat(rows, ignore_index=True)
    out = out.sort_values(["state_fips", "year"]).drop_duplicates(["state_fips", "year"], keep="last")
    out["region"] = out["state_fips"].map(STATE_FIPS_TO_REGION)
    out["population_growth_rate"] = out.groupby("state_fips")["population_total"].pct_change()
    return out
