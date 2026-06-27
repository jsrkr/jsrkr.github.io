from __future__ import annotations

import pandas as pd

from src.ml_dataset import add_lagged_features, sort_state_year_panel
from tests.conftest import build_synthetic_ml_panel, build_synthetic_modeling_panel


def test_state_year_sorting():
    df = build_synthetic_modeling_panel().sample(frac=1.0, random_state=42)
    sorted_df = sort_state_year_panel(df)
    assert list(sorted_df[["state_fips", "year"]].head(3).itertuples(index=False, name=None)) == [
        ("01", 2016),
        ("01", 2017),
        ("01", 2018),
    ]


def test_lag_creation():
    panel = build_synthetic_modeling_panel()
    lagged = add_lagged_features(panel, ["remote_work_exposure_index"])
    target = lagged[(lagged["state_fips"] == "01") & (lagged["year"] == 2018)].iloc[0]
    assert round(target["remote_work_exposure_index_lag1"], 6) == 0.21
    assert round(target["remote_work_exposure_index_lag2"], 6) == 0.20


def test_no_future_leakage_in_fertility_lags():
    ml_panel = build_synthetic_ml_panel()
    row_2020 = ml_panel[(ml_panel["state_fips"] == "01") & (ml_panel["year"] == 2020)].iloc[0]
    prev_row = ml_panel[(ml_panel["state_fips"] == "01") & (ml_panel["year"] == 2019)].iloc[0]
    next_row = ml_panel[(ml_panel["state_fips"] == "01") & (ml_panel["year"] == 2021)].iloc[0]
    assert row_2020["fertility_rate_lag1"] == prev_row["fertility_rate"]
    assert row_2020["fertility_rate_lag1"] != next_row["fertility_rate"]
