import pandas as pd
import pyreadstat

from src.clean_acs import build_weighted_acs_msa_year_panel_from_dta, restrict_to_dashboard_acs_window


def test_restrict_to_dashboard_acs_window_keeps_acs_backed_2014_2024_rows_only():
    df = pd.DataFrame(
        {
            "state_fips": ["01", "01", "01", "01"],
            "year": [2013, 2014, 2024, 2025],
            "remote_work_share_state_year": [0.03, 0.04, 0.12, 0.13],
            "source_used": [
                "Local CPS WFH extract + Hansen remote-postings workbook",
                "IPUMS ACS microdata",
                "IPUMS ACS microdata",
                "Local CPS WFH extract + Hansen remote-postings workbook",
            ],
        }
    )

    out = restrict_to_dashboard_acs_window(df)

    assert out["year"].tolist() == [2014, 2024]
    assert out["source_used"].tolist() == ["IPUMS ACS microdata", "IPUMS ACS microdata"]


def test_restrict_to_dashboard_acs_window_filters_years_without_source_labels():
    df = pd.DataFrame(
        {
            "state_fips": ["01", "01", "01"],
            "year": [2012, 2016, 2025],
            "remote_work_share_state_year": [0.02, 0.06, 0.14],
        }
    )

    out = restrict_to_dashboard_acs_window(df)

    assert out["year"].tolist() == [2016]


def test_build_weighted_acs_msa_year_panel_from_dta_groups_identifiable_msas(tmp_path):
    df = pd.DataFrame(
        {
            "year": [2022, 2022, 2022, 2022],
            "statefip": [36, 36, 34, 36],
            "met2013": [35620, 35620, 35620, 0],
            "perwt": [2.0, 1.0, 1.0, 3.0],
            "age": [30, 31, 29, 42],
            "sex": [2, 2, 2, 2],
            "empstat": [1, 1, 1, 1],
            "labforce": [2, 2, 2, 2],
            "marst": [1, 1, 2, 1],
            "educ": [11, 11, 11, 11],
            "fertyr": [2, 1, 1, 2],
            "tranwork": [80, 10, 10, 80],
            "trantime": [0, 35, 25, 0],
            "hrswork1": [40, 40, 20, 35],
        }
    )
    path = tmp_path / "acs_test.dta"
    pyreadstat.write_dta(df, path)

    out = build_weighted_acs_msa_year_panel_from_dta(path, min_year=2020, chunk_rows=10)

    assert len(out) == 1
    row = out.iloc[0]
    assert row["cbsa_code"] == "35620"
    assert row["state_fips"] == "36"
    assert row["component_state_fips"] == "34,36"
    assert round(float(row["remote_work_share_state_year"]), 4) == 0.5
    assert round(float(row["mean_commute_minutes_state_year"]), 4) == 30.0
    assert round(float(row["female_population_15_44"]), 4) == 4.0
    assert round(float(row["births"]), 4) == 2.0
    assert round(float(row["general_fertility_rate"]), 4) == 500.0
