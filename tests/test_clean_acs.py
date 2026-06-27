import pandas as pd

from src.clean_acs import restrict_to_dashboard_acs_window


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
