from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

import pandas as pd
import requests
from pytrends.request import TrendReq


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_JSON = DATA_DIR / "ai_work_fertility_sample.json"
OUTPUT_JS = ROOT / "ai-work-fertility-dashboard-data.js"
REMOTE_SNAPSHOT_PATH = DATA_DIR / "us_remote_work_reference.json"
DEFAULT_REMOTE_WORKBOOK = Path(r"D:\remote_work_in_job_ads_public_data.xlsx")

WORLD_BANK_INDICATORS = {
    "fertility_rate": "SP.DYN.TFRT.IN",
    "population_growth": "SP.POP.GROW",
}

REGIONS = {
    "northeast": {
        "name": "Northeast",
        "income_tier": "Dense metro corridor",
        "states": [
            "Connecticut",
            "Maine",
            "Massachusetts",
            "New Hampshire",
            "New Jersey",
            "New York",
            "Pennsylvania",
            "Rhode Island",
            "Vermont",
        ],
    },
    "midwest": {
        "name": "Great Lakes",
        "income_tier": "Manufacturing and services",
        "states": ["Illinois", "Indiana", "Michigan", "Ohio", "Wisconsin"],
    },
    "west": {
        "name": "Plains",
        "income_tier": "Lower-density interior",
        "states": [
            "Iowa",
            "Kansas",
            "Minnesota",
            "Missouri",
            "Nebraska",
            "North Dakota",
            "South Dakota",
        ],
    },
    "south-atlantic": {
        "name": "South Atlantic",
        "income_tier": "Large urban-growth belt",
        "states": [
            "Delaware",
            "District of Columbia",
            "Florida",
            "Georgia",
            "Maryland",
            "North Carolina",
            "South Carolina",
            "Virginia",
            "West Virginia",
        ],
    },
    "south-central": {
        "name": "South Central",
        "income_tier": "More on-site labor mix",
        "states": [
            "Alabama",
            "Arkansas",
            "Kentucky",
            "Louisiana",
            "Mississippi",
            "Oklahoma",
            "Tennessee",
            "Texas",
        ],
    },
    "mountain": {
        "name": "Mountain",
        "income_tier": "Long-distance commute mix",
        "states": [
            "Arizona",
            "Colorado",
            "Idaho",
            "Montana",
            "Nevada",
            "New Mexico",
            "Utah",
            "Wyoming",
        ],
    },
    "pacific": {
        "name": "Pacific",
        "income_tier": "High digital adoption",
        "states": ["Alaska", "California", "Hawaii", "Oregon", "Washington"],
    },
}

PROXIES = {
    "genai_weekly": {
        "label": "GenAI tools",
        "term": "ChatGPT",
        "anchor_share": 0.19,
        "floor": 0.10,
        "ceiling": 0.45,
        "note": "Estimated weekly adult share, anchored to survey usage and refreshed with Google Trends for ChatGPT.",
    },
    "dating_monthly": {
        "label": "Dating apps",
        "term": "Tinder",
        "anchor_share": 0.11,
        "floor": 0.05,
        "ceiling": 0.20,
        "note": "Estimated monthly adult share, anchored to survey usage and refreshed with Google Trends for Tinder.",
    },
    "social_media_daily": {
        "label": "Social media",
        "term": "Instagram",
        "anchor_share": 0.68,
        "floor": 0.45,
        "ceiling": 0.85,
        "note": "Estimated daily adult share, anchored to survey usage and refreshed with Google Trends for Instagram.",
    },
    "in_person_interactions": {
        "label": "In-person social activity",
        "term": "restaurants near me",
        "anchor_share": 0.58,
        "floor": 0.40,
        "ceiling": 0.78,
        "note": "Estimated weekly in-person social anchor, refreshed with Google Trends for local out-of-home activity.",
    },
    "remote_jobs_interest": {
        "label": "Remote jobs search",
        "term": "remote jobs",
        "anchor_share": None,
        "floor": None,
        "ceiling": None,
        "note": "Regional tilt proxy for work-from-home demand, used only to distribute the national on-site work anchor.",
    },
}

SKILLED_KEYWORDS = (
    "computer",
    "mathematical",
    "financial",
    "legal",
    "lawyer",
    "judge",
    "engineer",
    "scientist",
    "business operations",
    "operations specialties",
    "marketing",
    "media and communication",
    "architect",
    "manager",
    "supervisors of office",
)

UNSKILLED_KEYWORDS = (
    "food",
    "cleaning",
    "grounds",
    "construction",
    "helpers, construction",
    "material moving",
    "motor vehicle operators",
    "assemblers",
    "fabricators",
    "retail sales",
    "personal care",
    "home health",
    "nursing assistants",
    "woodworkers",
    "extraction workers",
    "metal workers",
    "production",
    "entertainment attendants",
)


@dataclass
class TrendsProxy:
    term: str
    latest_mean: float
    annual_mean: float
    ratio_to_mean: float
    states: dict[str, float]


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_mean(values: list[float]) -> float:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    if not clean:
        return 0.0
    return mean(clean)


def format_date_label(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y")


def fetch_world_bank_series(indicator_id: str) -> list[dict]:
    url = f"https://api.worldbank.org/v2/country/USA/indicator/{indicator_id}?format=json&per_page=80"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    return [row for row in payload[1] if row.get("value") is not None]


def latest_world_bank_value(indicator_key: str) -> tuple[float, str]:
    series = fetch_world_bank_series(WORLD_BANK_INDICATORS[indicator_key])
    latest = series[0]
    return float(latest["value"]), latest["date"]


def fetch_trends_proxy(pytrends: TrendReq, term: str) -> TrendsProxy:
    for attempt in range(3):
        try:
            pytrends.build_payload([term], timeframe="today 12-m", geo="US")
            history = pytrends.interest_over_time()
            regional = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(4 * (attempt + 1))
    else:
        raise RuntimeError(f"Could not fetch Google Trends data for {term}.")

    if "isPartial" in history.columns:
        history = history[~history["isPartial"]]
    series = history[term].astype(float)
    latest_mean = float(series.tail(4).mean())
    annual_mean = float(series.mean()) or 1.0
    states = {state: float(value) for state, value in regional[term].to_dict().items()}
    return TrendsProxy(
        term=term,
        latest_mean=latest_mean,
        annual_mean=annual_mean,
        ratio_to_mean=latest_mean / annual_mean if annual_mean else 1.0,
        states=states,
    )


def estimate_share(proxy_key: str, proxy: TrendsProxy) -> float:
    config = PROXIES[proxy_key]
    raw = config["anchor_share"] * proxy.ratio_to_mean
    return clip(raw, config["floor"], config["ceiling"])


def load_remote_work_source(workbook_path: Path, snapshot_path: Path) -> dict:
    if workbook_path.exists():
        reference = build_remote_work_reference(workbook_path)
        snapshot_path.write_text(json.dumps(reference, indent=2), encoding="utf-8")
        return reference
    if snapshot_path.exists():
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"Neither {workbook_path} nor {snapshot_path} is available for the remote-work anchor."
    )


def classify_occupation(name: str) -> str | None:
    lowered = name.lower()
    if any(keyword in lowered for keyword in SKILLED_KEYWORDS):
        return "skilled"
    if any(keyword in lowered for keyword in UNSKILLED_KEYWORDS):
        return "unskilled"
    return None


def build_remote_work_reference(workbook_path: Path) -> dict:
    country_df = pd.read_excel(workbook_path, sheet_name="country_by_month")
    country_df = country_df[country_df["Country"] == "USA"].copy()
    latest_country = country_df.sort_values("Year-Month").iloc[-1]
    baseline_2019 = float(country_df[country_df["Year"] == 2019]["Percent_3MA"].mean()) / 100.0

    occ_df = pd.read_excel(workbook_path, sheet_name="us_occ_by_month")
    latest_month = occ_df["Year-Month"].max()
    latest_occ = occ_df[occ_df["Year-Month"] == latest_month].copy()
    latest_occ["bucket"] = latest_occ["SOC 2018 3-Digit Minor Group (Name)"].map(classify_occupation)

    skilled = latest_occ[latest_occ["bucket"] == "skilled"]["Percent_3MA"] / 100.0
    unskilled = latest_occ[latest_occ["bucket"] == "unskilled"]["Percent_3MA"] / 100.0

    top_occupations = [
        {
            "name": row["SOC 2018 3-Digit Minor Group (Name)"],
            "share": round(float(row["Percent_3MA"]) / 100.0, 4),
        }
        for _, row in latest_occ.sort_values("Percent_3MA", ascending=False).head(6).iterrows()
    ]

    return {
        "source": "local_workbook",
        "workbook_path": str(workbook_path),
        "latest_month": month_label(latest_country["Year"], latest_country["Month"]),
        "remote_posting_share": round(float(latest_country["Percent_3MA"]) / 100.0, 4),
        "remote_posting_share_raw": round(float(latest_country["Percent"]) / 100.0, 4),
        "baseline_2019_share": round(baseline_2019, 4),
        "in_person_work_share": round(1.0 - float(latest_country["Percent_3MA"]) / 100.0, 4),
        "skilled_remote_share": round(float(skilled.mean()), 4),
        "unskilled_remote_share": round(float(unskilled.mean()), 4),
        "capability_gap": round(float(skilled.mean() - unskilled.mean()), 4),
        "top_occupations": top_occupations,
    }


def month_label(year: int, month_value: str) -> str:
    month_lookup = {
        "Jan": "January",
        "Feb": "February",
        "Mar": "March",
        "Apr": "April",
        "May": "May",
        "Jun": "June",
        "Jul": "July",
        "Aug": "August",
        "Sep": "September",
        "Oct": "October",
        "Nov": "November",
        "Dec": "December",
    }
    return f"{month_lookup[str(month_value)]} {int(year)}"


def region_average(states_map: dict[str, float], region_states: list[str]) -> float:
    return safe_mean([states_map.get(state) for state in region_states])


def regionalize_share(
    national_share: float,
    proxy_states: dict[str, float],
    region_states: list[str],
    floor: float,
    ceiling: float,
) -> float:
    national_state_mean = safe_mean(list(proxy_states.values())) or 1.0
    region_state_mean = region_average(proxy_states, region_states)
    return clip(national_share * (region_state_mean / national_state_mean), floor, ceiling)


def signed_points(value: float) -> str:
    rounded = round(value, 1)
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded:.1f} pts"


def percent_string(value: float) -> str:
    return f"{value * 100:.1f}%"


def score_string(value: float) -> str:
    return f"{value:.0f}/100"


def work_anchor_from_onsite_share(onsite_share: float) -> float:
    remote_share = 1.0 - onsite_share
    return clip(1.0 - (remote_share / 0.20), 0.0, 1.0)


def build_dataset(remote_workbook: Path, default_region: str) -> dict:
    remote = load_remote_work_source(remote_workbook, REMOTE_SNAPSHOT_PATH)
    pytrends = TrendReq(hl="en-US", tz=360)
    trends = {key: fetch_trends_proxy(pytrends, config["term"]) for key, config in PROXIES.items()}

    fertility_rate, fertility_year = latest_world_bank_value("fertility_rate")
    population_growth, population_year = latest_world_bank_value("population_growth")

    national_shares = {
        "genai_weekly": estimate_share("genai_weekly", trends["genai_weekly"]),
        "dating_monthly": estimate_share("dating_monthly", trends["dating_monthly"]),
        "social_media_daily": estimate_share("social_media_daily", trends["social_media_daily"]),
        "in_person_interactions": estimate_share("in_person_interactions", trends["in_person_interactions"]),
        "in_person_work": float(remote["in_person_work_share"]),
    }
    national_shares["physical_mobility"] = national_shares["in_person_interactions"]
    national_shares["screen_other_than_work"] = clip(
        0.50 * national_shares["social_media_daily"]
        + 0.30 * national_shares["in_person_interactions"]
        + 0.20 * national_shares["genai_weekly"],
        0.45,
        0.82,
    )

    home_digital_national = (
        0.35 * national_shares["genai_weekly"]
        + 0.20 * national_shares["dating_monthly"]
        + 0.45 * national_shares["social_media_daily"]
    )
    national_work_anchor = work_anchor_from_onsite_share(national_shares["in_person_work"])
    in_person_anchor_national = 0.65 * national_shares["in_person_interactions"] + 0.35 * national_work_anchor

    relationship_split = build_relationship_split(national_shares)

    regions = []
    for region_id, region_meta in REGIONS.items():
        shares = {
            "dating_monthly": regionalize_share(
                national_shares["dating_monthly"],
                trends["dating_monthly"].states,
                region_meta["states"],
                0.03,
                0.24,
            ),
            "genai_weekly": regionalize_share(
                national_shares["genai_weekly"],
                trends["genai_weekly"].states,
                region_meta["states"],
                0.08,
                0.45,
            ),
            "social_media_daily": regionalize_share(
                national_shares["social_media_daily"],
                trends["social_media_daily"].states,
                region_meta["states"],
                0.45,
                0.88,
            ),
            "physical_mobility": regionalize_share(
                national_shares["physical_mobility"],
                trends["in_person_interactions"].states,
                region_meta["states"],
                0.38,
                0.80,
            ),
        }
        remote_jobs_ratio = region_average(trends["remote_jobs_interest"].states, region_meta["states"]) / (
            safe_mean(list(trends["remote_jobs_interest"].states.values())) or 1.0
        )
        shares["in_person_work"] = clip(national_shares["in_person_work"] * (1.0 - 0.18 * (remote_jobs_ratio - 1.0)), 0.58, 0.95)

        home_digital = 0.35 * shares["genai_weekly"] + 0.20 * shares["dating_monthly"] + 0.45 * shares["social_media_daily"]
        work_anchor = work_anchor_from_onsite_share(shares["in_person_work"])
        in_person_anchor = 0.65 * shares["physical_mobility"] + 0.35 * work_anchor
        pressure_gap = home_digital - in_person_anchor

        fertility_score = clip(
            50
            - 65 * pressure_gap
            - 30 * (shares["dating_monthly"] - 0.10)
            + 20 * (shares["physical_mobility"] - 0.55)
            + 10 * (work_anchor - 0.50),
            36,
            64,
        )
        projected_tfr = fertility_rate + (fertility_score - 50) * 0.004
        projected_pop_growth = population_growth + (fertility_score - 50) * 0.015

        digital_isolation_shift = (
            40 * pressure_gap
            + 18 * (shares["social_media_daily"] - national_shares["social_media_daily"])
            + 12 * (shares["dating_monthly"] - national_shares["dating_monthly"])
            - 14 * (shares["physical_mobility"] - national_shares["physical_mobility"])
        )
        sadness_shift = 0.8 * digital_isolation_shift + 6 * (shares["genai_weekly"] - national_shares["genai_weekly"])
        care_shift = 0.55 * digital_isolation_shift
        digital_mental_score = clip(50 + digital_isolation_shift, 35, 85)
        in_person_mental_score = clip(55 - sadness_shift + 8 * (shares["physical_mobility"] - 0.55), 30, 80)

        skilled_productivity = clip(
            48
            + 30 * (shares["genai_weekly"] - national_shares["genai_weekly"])
            + 120 * remote["skilled_remote_share"]
            - 12 * max(0.0, pressure_gap),
            35,
            85,
        )
        unskilled_productivity = clip(
            52
            + 18 * (shares["physical_mobility"] - national_shares["physical_mobility"])
            + 110 * remote["unskilled_remote_share"]
            - 24 * max(0.0, pressure_gap),
            25,
            72,
        )

        women_segments = build_women_segments(shares, national_shares)
        region_state_mean = {
            "genai": region_average(trends["genai_weekly"].states, region_meta["states"]),
            "dating": region_average(trends["dating_monthly"].states, region_meta["states"]),
            "social": region_average(trends["social_media_daily"].states, region_meta["states"]),
        }

        regions.append(
            {
                "id": region_id,
                "name": region_meta["name"],
                "income_tier": region_meta["income_tier"],
                "state_count": len(region_meta["states"]),
                "summary": build_region_summary(region_meta["name"], shares, national_shares, pressure_gap),
                "shares": shares,
                "women_segments": women_segments,
                "fertility": {
                    "score": round(fertility_score),
                    "baseline_tfr": f"{fertility_rate:.2f} births/woman ({fertility_year})",
                    "population_growth": f"{population_growth:.2f}% ({population_year})",
                    "projected_direction": f"Model midpoint {projected_tfr:.2f}",
                    "summary": (
                        f"If this home-shift mix persisted, the dashboard model moves the region toward a "
                        f"{projected_tfr:.2f} fertility midpoint and about {projected_pop_growth:.2f}% population growth."
                    ),
                    "takeaway": (
                        "The sign can still reverse: remote flexibility can help partnered households, but heavy digital-at-home substitution "
                        "usually lowers the meeting, matching, and coordination margin."
                    ),
                },
                "mental_health": {
                    "digital_home": round(digital_mental_score),
                    "in_person": round(in_person_mental_score),
                    "days_alone_trend": signed_points(digital_isolation_shift),
                    "sadness_trend": signed_points(sadness_shift),
                    "care_use_trend": signed_points(care_shift),
                    "takeaway": (
                        "This panel follows the Emma Harrington-style margin: days spent alone, sadness or depression, "
                        "and mental-health care use rise when home-based digital time outpaces face-to-face routines."
                    ),
                },
                "productivity": {
                    "skilled": round(skilled_productivity),
                    "unskilled": round(unskilled_productivity),
                    "skilled_trend": signed_points(skilled_productivity - 50),
                    "unskilled_trend": signed_points(unskilled_productivity - 50),
                    "productivity_gap": signed_points(skilled_productivity - unskilled_productivity),
                    "takeaway": (
                        "GenAI looks more complementary in already-remote-capable work, while on-site service and manual jobs "
                        "benefit less from the home shift and can lose coordination or routine."
                    ),
                },
                "debug": {
                    "pressure_gap": round(pressure_gap, 4),
                    "work_anchor": round(work_anchor, 4),
                    "regional_attention": region_state_mean,
                },
            }
        )

    scenarios = build_scenarios(home_digital_national, in_person_anchor_national, remote, fertility_rate)

    last_updated = format_date_label(datetime.now())
    dataset = {
        "metadata": {
            "last_updated": last_updated,
            "status": "Generated U.S. dashboard data",
            "notes": (
                "Observed inputs update from Google Trends, the World Bank API, and the Hansen-style remote-work workbook or its exported snapshot. "
                "Right-side fertility, mental-health, and productivity panels are model-implied pressure scores rather than causal estimates."
            ),
            "status_note": (
                f"Google Trends nowcasts were refreshed on {last_updated}; World Bank fertility and population-growth baselines are {fertility_year} and {population_year}; "
                f"the remote-work anchor uses {percent_string(remote['remote_posting_share'])} remote postings in {remote['latest_month']}."
            ),
        },
        "default_metric": "genai_weekly",
        "default_region": default_region,
        "global_summary": {
            "dating_monthly": national_shares["dating_monthly"],
            "genai_weekly": national_shares["genai_weekly"],
            "in_person_work": national_shares["in_person_work"],
            "physical_mobility": national_shares["physical_mobility"],
        },
        "live_panel": {
            "refresh_label": "Generated from live U.S. inputs",
            "note": (
                "Observed cards mix two kinds of measures: direct anchors from the remote-work workbook and official fertility/population series, "
                "plus Google Trends-based nowcasts for digital and in-person attention. Estimated adult shares are calibration-based, not direct census counts."
            ),
            "current_stats": [
                {
                    "title": "Adults with high non-work screen time daily",
                    "value": national_shares["screen_other_than_work"],
                    "note": "Estimated share built from social, GenAI, and in-person attention mix.",
                },
                {
                    "title": "Adults using GenAI at home weekly",
                    "value": national_shares["genai_weekly"],
                    "note": f"Nowcast from Google Trends for {PROXIES['genai_weekly']['term']}.",
                },
                {
                    "title": "Adults using dating apps monthly",
                    "value": national_shares["dating_monthly"],
                    "note": f"Nowcast from Google Trends for {PROXIES['dating_monthly']['term']}.",
                },
                {
                    "title": "Adults using social media daily",
                    "value": national_shares["social_media_daily"],
                    "note": f"Nowcast from Google Trends for {PROXIES['social_media_daily']['term']}.",
                },
                {
                    "title": "Adults with weekly in-person social routines",
                    "value": national_shares["in_person_interactions"],
                    "note": f"Nowcast from Google Trends for {PROXIES['in_person_interactions']['term']}.",
                },
                {
                    "title": "Workers in primarily in-person jobs",
                    "value": national_shares["in_person_work"],
                    "note": f"1 minus the {percent_string(remote['remote_posting_share'])} remote-postings anchor.",
                },
            ],
            "relationship_split": relationship_split,
            "balance": {
                "home_digital": round(home_digital_national, 4),
                "home_digital_note": "Weighted average of GenAI, dating, and social-media nowcasts.",
                "in_person": round(in_person_anchor_national, 4),
                "in_person_note": "Weighted average of on-site work and in-person social nowcasts.",
                "summary": (
                    "The core margin is simple: when home-based digital intensity rises above in-person anchors, the model tilts toward later partnering, "
                    "more isolation pressure, and a wider productivity gap between AI-complementary and less-complementary work."
                ),
            },
        },
        "metrics": [
            {"id": "dating_monthly", "label": "Dating", "unit": "estimated share"},
            {"id": "genai_weekly", "label": "GenAI", "unit": "estimated share"},
            {"id": "social_media_daily", "label": "Social", "unit": "estimated share"},
            {"id": "in_person_work", "label": "On-site work", "unit": "share of workers"},
            {"id": "physical_mobility", "label": "Going out", "unit": "estimated share"},
        ],
        "regions": regions,
        "scenarios": scenarios,
        "method_snapshot": [
            {
                "title": "Google Trends nowcast",
                "value": "12-month U.S. search attention",
                "text": "Representative terms are ChatGPT, Tinder, Instagram, restaurants near me, and remote jobs. Each proxy is normalized by its own U.S. 12-month mean.",
            },
            {
                "title": "Remote work anchor",
                "value": f"{percent_string(remote['remote_posting_share'])} remote postings",
                "text": f"Pulled from the Hansen-style workbook in {remote['latest_month']}; the dashboard uses 1 minus this share as the national on-site work anchor.",
            },
            {
                "title": "Fertility baseline",
                "value": f"{fertility_rate:.2f} TFR, {population_growth:.2f}% growth",
                "text": f"Official World Bank U.S. baselines for {fertility_year} fertility and {population_year} population growth.",
            },
            {
                "title": "Mental-health outcomes",
                "value": "Days alone, sadness, care use",
                "text": "The projection layer follows the remote-work mental-health margin emphasized in the Emma Harrington coauthored Science paper.",
            },
            {
                "title": "Productivity split",
                "value": f"{percent_string(remote['skilled_remote_share'])} vs {percent_string(remote['unskilled_remote_share'])}",
                "text": "Skilled and unskilled productivity indices are anchored to occupation-level remote-capability differences in the workbook, then tilted by regional GenAI and in-person proxies.",
            },
        ],
    }
    return dataset


def build_relationship_split(national_shares: dict[str, float]) -> list[dict]:
    single = {
        "label": "Single adults",
        "household_context": "Not married or not cohabiting",
        "genai_weekly": clip(national_shares["genai_weekly"] * 1.12, 0.08, 0.55),
        "dating_monthly": clip(national_shares["dating_monthly"] * 1.75, 0.06, 0.32),
        "social_media_daily": clip(national_shares["social_media_daily"] * 1.08, 0.40, 0.90),
        "in_person_interactions": clip(national_shares["in_person_interactions"] * 0.88, 0.30, 0.80),
        "note": (
            "Modeled split: singles are weighted toward app-based matching and solitary digital time, so the mental-health and fertility margins are more exposed when in-person routines thin out."
        ),
    }
    couple = {
        "label": "Married or cohabiting adults",
        "household_context": "Living with a partner",
        "genai_weekly": clip(national_shares["genai_weekly"] * 0.95, 0.08, 0.50),
        "dating_monthly": clip(national_shares["dating_monthly"] * 0.28, 0.01, 0.08),
        "social_media_daily": clip(national_shares["social_media_daily"] * 0.93, 0.35, 0.82),
        "in_person_interactions": clip(national_shares["in_person_interactions"] * 1.08, 0.35, 0.84),
        "note": (
            "Modeled split: partnered adults have less exposure to the matching margin, but fertility timing can still fall if screen-heavy home life crowds out energy, local routines, or community support."
        ),
    }
    return [single, couple]


def build_women_segments(shares: dict[str, float], national_shares: dict[str, float]) -> dict[str, float]:
    ai_complementary = clip(
        0.21 + 0.25 * (shares["genai_weekly"] - national_shares["genai_weekly"]) + 0.08 * (1.0 - shares["in_person_work"]),
        0.14,
        0.38,
    )
    ai_substitutable = clip(
        0.23 + 0.12 * (shares["in_person_work"] - national_shares["in_person_work"]) - 0.10 * (shares["genai_weekly"] - national_shares["genai_weekly"]),
        0.15,
        0.35,
    )
    not_working = clip(
        0.29 + 0.16 * max(0.0, shares["social_media_daily"] - shares["physical_mobility"]),
        0.18,
        0.42,
    )
    return {
        "ai_complementary": round(ai_complementary, 4),
        "ai_substitutable": round(ai_substitutable, 4),
        "not_working": round(not_working, 4),
    }


def build_region_summary(
    region_name: str,
    shares: dict[str, float],
    national_shares: dict[str, float],
    pressure_gap: float,
) -> str:
    genai_tilt = "above" if shares["genai_weekly"] >= national_shares["genai_weekly"] else "below"
    social_tilt = "above" if shares["physical_mobility"] >= national_shares["physical_mobility"] else "below"
    pressure = "stronger" if pressure_gap > 0 else "weaker"
    return (
        f"{region_name} is {genai_tilt} the U.S. GenAI nowcast and {social_tilt} the U.S. in-person activity proxy. "
        f"That leaves a {pressure} home-shift gap than the national balance."
    )


def build_scenarios(
    home_digital_national: float,
    in_person_anchor_national: float,
    remote: dict,
    fertility_rate: float,
) -> list[dict]:
    gap = home_digital_national - in_person_anchor_national
    downside_tfr = fertility_rate - max(0.0, gap) * 0.14
    upside_tfr = fertility_rate + max(0.0, remote["remote_posting_share"] - 0.08) * 0.30
    return [
        {
            "title": "Digital life outruns local routines",
            "trigger": f"Home digital share exceeds in-person anchors by {percent_string(max(gap, 0.0))}",
            "summary": "This is the downside path: more life shifts onto screens without enough local work or social routines to offset it.",
            "fertility": f"Model midpoint slips toward about {downside_tfr:.2f} births per woman.",
            "mental_health": "Days alone and sadness or depression tilt upward fastest for adults living alone.",
            "productivity": "Skilled workers still gain from GenAI, but the skilled-unskilled productivity gap widens.",
        },
        {
            "title": "Flexibility supports coordination",
            "trigger": f"Remote posting anchor stays near {percent_string(remote['remote_posting_share'])} while in-person social routines hold up",
            "summary": "This is the upside path: remote flexibility saves time, but workers still keep face-to-face anchors and community contact.",
            "fertility": f"Model midpoint can edge back toward about {upside_tfr:.2f} births per woman.",
            "mental_health": "The isolation margin softens because digital work does not fully replace coworkers, friends, and outside routines.",
            "productivity": "GenAI complementarity remains positive without as much mental-health drag on the rest of the labor market.",
        },
    ]


def write_outputs(dataset: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    OUTPUT_JS.write_text(
        "window.AI_WORK_FERTILITY_SAMPLE = " + json.dumps(dataset, indent=2) + ";\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the U.S. home-shift dashboard dataset.")
    parser.add_argument(
        "--remote-workbook",
        default=str(DEFAULT_REMOTE_WORKBOOK),
        help="Path to the remote-work workbook. If missing, the script falls back to data/us_remote_work_reference.json.",
    )
    parser.add_argument(
        "--default-region",
        default="northeast",
        choices=sorted(REGIONS.keys()),
        help="Default selected region for the dashboard UI.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = build_dataset(Path(args.remote_workbook), args.default_region)
    write_outputs(dataset)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_JS}")


if __name__ == "__main__":
    main()
