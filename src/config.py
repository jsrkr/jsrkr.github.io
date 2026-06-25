from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MODEL_ARTIFACTS_DIR = OUTPUTS_DIR / "model_artifacts"

ACS_2020_WARNING = (
    "ACS 2020 1-year estimates were released as experimental estimates because of pandemic-era data "
    "collection disruptions. Treat 2020 comparisons cautiously."
)

ATUS_SMALL_STATE_WARNING = (
    "ATUS is best used for national and regional time-use minutes. State-level ATUS estimates are shown "
    "only when pooled samples pass minimum thresholds; otherwise values are hidden or pooled."
)

DIGITAL_SOCIAL_WARNING = (
    "Digital-social interaction is not cleanly observed in most public time-use files. This dashboard "
    "separates directly measured digital time from digital-social scenario assumptions."
)

MIN_ATUS_STATE_SAMPLE = 150
DEFAULT_MOVING_AVERAGE_YEARS = 3
DEFAULT_PROJECTION_HORIZON = 2030
DEFAULT_FORECAST_END_YEAR = 2060
DEFAULT_SEQUENCE_LENGTH = 3
SHORT_GAP_IMPUTATION_LIMIT = 2

OBSERVATION_MODES = ("observed", "imputed", "modeled", "user_provided")
EXPOSURE_INDEX_COLUMNS = [
    "remote_work_exposure_index",
    "in_person_work_exposure_index",
    "digital_distraction_index",
    "digital_social_index",
    "in_person_social_index",
    "digital_access_index",
    "digital_use_prevalence_index",
    "commute_burden_index",
    "work_family_compatibility_proxy",
    "gendered_care_risk_proxy",
]
ML_LAG_YEARS = (1, 2, 3)

AGE_GROUPS = ["15-24", "25-34", "35-44", "45-54"]
FERTILITY_AGE_GROUPS = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44"]

SCENARIO_DEFAULTS = {
    "digital_distraction_growth": 0.02,
    "remote_work_growth": 0.01,
    "face_to_face_change": -0.01,
    "digital_social_growth": 0.005,
    "fertility_effect_distraction_per_hour": -0.04,
    "fertility_effect_social_per_hour": 0.02,
    "fertility_effect_remote_per_10pp": 0.03,
    "gendered_care_penalty": 0.015,
    "projection_horizon": DEFAULT_PROJECTION_HORIZON,
    "uncertainty_multiplier_low": 0.5,
    "uncertainty_multiplier_mid": 1.0,
    "uncertainty_multiplier_high": 1.5,
    "in_person_social_growth": -0.005,
    "in_person_work_growth": -0.002,
    "commute_burden_growth": -0.002,
    "work_family_compatibility_growth": 0.003,
    "gendered_care_risk_growth": 0.002,
}

SCENARIO_SPECS = {
    "baseline_continuation": {
        "label": "Scenario 1: Baseline continuation",
        "growth_overrides": {},
    },
    "distraction_dominant": {
        "label": "Scenario 2: Distraction-dominant digital life",
        "growth_overrides": {
            "digital_distraction_index": 0.04,
            "digital_social_index": 0.01,
            "in_person_social_index": -0.02,
            "remote_work_exposure_index": 0.002,
        },
    },
    "remote_work_dominant": {
        "label": "Scenario 3: Remote-work dominant digital life",
        "growth_overrides": {
            "remote_work_exposure_index": 0.03,
            "commute_burden_index": -0.02,
            "digital_distraction_index": 0.005,
            "work_family_compatibility_proxy": 0.02,
        },
    },
    "digital_social_substitution": {
        "label": "Scenario 4: Digital-social substitution",
        "growth_overrides": {
            "digital_social_index": 0.03,
            "in_person_social_index": -0.015,
            "digital_distraction_index": 0.01,
        },
    },
    "in_person_revival": {
        "label": "Scenario 5: In-person revival",
        "growth_overrides": {
            "in_person_social_index": 0.025,
            "in_person_work_exposure_index": 0.015,
            "digital_distraction_index": -0.01,
            "remote_work_exposure_index": 0.005,
        },
    },
    "gendered_care_penalty": {
        "label": "Scenario 6: Gendered-care penalty",
        "growth_overrides": {
            "remote_work_exposure_index": 0.02,
            "work_family_compatibility_proxy": 0.01,
            "gendered_care_risk_proxy": 0.025,
        },
    },
    "user_defined": {
        "label": "Scenario 7: User-defined scenario",
        "growth_overrides": {},
    },
}

MODEL_REQUIRED_COLUMNS = [
    "state_fips",
    "state_name",
    "year",
    "fertility_rate",
    "births",
    "total_population",
    "female_population_15_44",
    *EXPOSURE_INDEX_COLUMNS,
    "source_quality_flags",
]

DIGITAL_INPUT_OPTIONS = {
    "acs_access": "ACS digital access trend",
    "ntia_prevalence": "NTIA/CPS digital-use prevalence trend",
    "atus_minutes": "ATUS digital-time trend",
    "commercial_minutes": "Commercial media-consumption data",
    "proxy_attention": "Google Trends / Meta proxy trend",
}

MEASUREMENT_TYPES = {
    "digital_access": "access",
    "digital_use_prevalence": "prevalence",
    "digital_time": "minutes",
    "digital_attention": "attention",
}


@dataclass(frozen=True)
class StateRecord:
    fips: str
    abbreviation: str
    name: str
    region: str


STATE_RECORDS = [
    StateRecord("01", "AL", "Alabama", "South"),
    StateRecord("02", "AK", "Alaska", "West"),
    StateRecord("04", "AZ", "Arizona", "West"),
    StateRecord("05", "AR", "Arkansas", "South"),
    StateRecord("06", "CA", "California", "West"),
    StateRecord("08", "CO", "Colorado", "West"),
    StateRecord("09", "CT", "Connecticut", "Northeast"),
    StateRecord("10", "DE", "Delaware", "South"),
    StateRecord("11", "DC", "District of Columbia", "South"),
    StateRecord("12", "FL", "Florida", "South"),
    StateRecord("13", "GA", "Georgia", "South"),
    StateRecord("15", "HI", "Hawaii", "West"),
    StateRecord("16", "ID", "Idaho", "West"),
    StateRecord("17", "IL", "Illinois", "Midwest"),
    StateRecord("18", "IN", "Indiana", "Midwest"),
    StateRecord("19", "IA", "Iowa", "Midwest"),
    StateRecord("20", "KS", "Kansas", "Midwest"),
    StateRecord("21", "KY", "Kentucky", "South"),
    StateRecord("22", "LA", "Louisiana", "South"),
    StateRecord("23", "ME", "Maine", "Northeast"),
    StateRecord("24", "MD", "Maryland", "South"),
    StateRecord("25", "MA", "Massachusetts", "Northeast"),
    StateRecord("26", "MI", "Michigan", "Midwest"),
    StateRecord("27", "MN", "Minnesota", "Midwest"),
    StateRecord("28", "MS", "Mississippi", "South"),
    StateRecord("29", "MO", "Missouri", "Midwest"),
    StateRecord("30", "MT", "Montana", "West"),
    StateRecord("31", "NE", "Nebraska", "Midwest"),
    StateRecord("32", "NV", "Nevada", "West"),
    StateRecord("33", "NH", "New Hampshire", "Northeast"),
    StateRecord("34", "NJ", "New Jersey", "Northeast"),
    StateRecord("35", "NM", "New Mexico", "West"),
    StateRecord("36", "NY", "New York", "Northeast"),
    StateRecord("37", "NC", "North Carolina", "South"),
    StateRecord("38", "ND", "North Dakota", "Midwest"),
    StateRecord("39", "OH", "Ohio", "Midwest"),
    StateRecord("40", "OK", "Oklahoma", "South"),
    StateRecord("41", "OR", "Oregon", "West"),
    StateRecord("42", "PA", "Pennsylvania", "Northeast"),
    StateRecord("44", "RI", "Rhode Island", "Northeast"),
    StateRecord("45", "SC", "South Carolina", "South"),
    StateRecord("46", "SD", "South Dakota", "Midwest"),
    StateRecord("47", "TN", "Tennessee", "South"),
    StateRecord("48", "TX", "Texas", "South"),
    StateRecord("49", "UT", "Utah", "West"),
    StateRecord("50", "VT", "Vermont", "Northeast"),
    StateRecord("51", "VA", "Virginia", "South"),
    StateRecord("53", "WA", "Washington", "West"),
    StateRecord("54", "WV", "West Virginia", "South"),
    StateRecord("55", "WI", "Wisconsin", "Midwest"),
    StateRecord("56", "WY", "Wyoming", "West"),
]

STATE_FIPS_TO_NAME = {record.fips: record.name for record in STATE_RECORDS}
STATE_NAME_TO_FIPS = {record.name: record.fips for record in STATE_RECORDS}
STATE_FIPS_TO_ABBR = {record.fips: record.abbreviation for record in STATE_RECORDS}
STATE_ABBR_TO_FIPS = {record.abbreviation: record.fips for record in STATE_RECORDS}
STATE_FIPS_TO_REGION = {record.fips: record.region for record in STATE_RECORDS}


EXPECTED_COLUMNS = {
    "ntia_state": ["state_fips", "year", "internet_use_rate_state_year"],
    "commercial_digital_media_template": [
        "geography_type",
        "geography_id",
        "geography_name",
        "year",
        "month",
        "age_group",
        "sex",
        "education",
        "digital_media_minutes_per_day",
        "social_media_minutes_per_day",
        "streaming_minutes_per_day",
        "gaming_minutes_per_day",
        "online_dating_use_rate",
        "video_calling_use_rate",
        "source_name",
        "sample_size",
        "weight_variable",
        "standard_error",
    ],
    "cdc_wonder_fertility": ["state_fips", "year", "births"],
    "population_estimates": ["state_fips", "year", "population_total"],
}
