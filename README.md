# U.S. Home-Shift Fertility Dashboard

This project builds an interactive Streamlit dashboard and reproducible data pipeline to study how rising home-based digital time, declining face-to-face interaction, and remote work may affect fertility and population growth in the United States.

## Research Question

How do current trends in digital time, face-to-face social interaction, remote work, fertility, and population growth differ across states and demographic groups, and what happens to fertility and population growth under alternative future scenarios if these trends continue?

## Conceptual Framework

The dashboard separates three distinct digital channels instead of treating all digital time as one exposure.

1. `Digital distraction`
   Solo screen-based leisure, games, computer use for leisure, television, and similar activities. This channel is expected to be anti-natal when it crowds out in-person socializing, partner search, couple time, and intimacy.

2. `Digital social interaction`
   Digitally mediated social contact, communication, or online-to-offline matching. This channel may be neutral or positive for union formation depending on assumptions. Because public data do not observe this cleanly, the dashboard separates measured proxies from user-set scenario assumptions.

3. `Remote work / home-based digital work`
   Work performed from home, reduced commuting, and less on-site work. This channel can raise fertility through flexibility and work-family compatibility, but may become ambiguous or negative when unpaid care burdens rise for women.

The central empirical question is not whether digital exposure rises. It is where the marginal digital hour comes from and what function it serves.

## Data Sources

### Default source hierarchy

- `ACS / Census API or IPUMS ACS`
  Used for work from home, commute patterns, labor force measures, household composition, fertility in the past year where microdata are available, and digital access controls.

- `ATUS / IPUMS ATUS`
  Used as the benchmark source for time-use minutes, including digital distraction, face-to-face social interaction, work at home, work away from home, and social context where available.

- `CDC WONDER Natality`
  Used for state-year births, general fertility rates, age-specific fertility rates, and total fertility rate approximations.

- `Census Population Estimates / Projections`
  Used for state population totals, female population by age group, natural increase, and migration-based accounting.

- `NTIA Internet Use Survey / CPS Computer and Internet Use Supplement`
  Preferred state-level public source for digital-use prevalence.

- `ACS Internet and Computer Use tables`
  Used as digital access and infrastructure controls, not as direct measures of media consumption.

- `Google Trends and other proxy data`
  Used only as attention or reach proxies, never as representative digital-media minutes.

### Paid or user-provided optional sources

The `src/clean_digital_media.py` module supports template ingestion for Comscore, Nielsen, MRI-Simmons, GWI, YouGov Profiles, and similar commercial datasets. The dashboard does not require them to run.

## Variable Definitions

### Remote work intensity

- `remote_work_share_state_year`: share of workers who work from home.
- `commute_savings_proxy`: decline in average commute time relative to the pre-2020 baseline.
- `remote_work_growth`: change in work-from-home share relative to the 2010-2019 baseline.

### Digital access, prevalence, time, and attention

- `digital_access_index`: ACS-based infrastructure layer.
- `internet_use_rate_state_year`: NTIA/CPS prevalence layer.
- `digital_distraction_minutes`: ATUS-based minutes in computer leisure, games, and television/movies.
- `face_to_face_social_minutes`: ATUS-based socializing and communicating minutes.
- `digital_attention_proxy_index`: proxy attention layer from Google Trends or comparable sources.

### Fertility and population

- `general_fertility_rate`: births per 1,000 women ages 15-44.
- `age_specific_fertility_rate`: age-group specific births per 1,000 women.
- `total_fertility_rate_approx`: sum of age-specific fertility rates scaled by age-bin width.
- `population_growth_rate`: annual percent change in state population.
- `natural_increase`: births minus deaths.
- `net_migration`: domestic plus international migration where available.

## Project Structure

- [app.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/app.py)
- [src/config.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/config.py)
- [src/data_download.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/data_download.py)
- [src/clean_acs.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/clean_acs.py)
- [src/clean_atus.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/clean_atus.py)
- [src/clean_digital_media.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/clean_digital_media.py)
- [src/clean_fertility.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/clean_fertility.py)
- [src/clean_population.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/clean_population.py)
- [src/metrics.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/metrics.py)
- [src/projections.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/projections.py)
- [src/plots.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/src/plots.py)
- [tests/test_metrics.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/tests/test_metrics.py)
- [tests/test_projections.py](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/tests/test_projections.py)

## How to Run the Dashboard

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Launch Streamlit:

```bash
streamlit run app.py
```

If processed data files are absent, the app will open with upload widgets and clear warnings instead of fabricating values.

## How to Build Processed Tables

Use the pipeline runner to transform cleaned or exported source files into the processed tables the dashboard reads:

```bash
python scripts/build_streamlit_dashboard_data.py \
  --acs-wfh path/to/acs_wfh.csv \
  --acs-commute path/to/acs_commute.csv \
  --atus path/to/atus_activity.csv \
  --fertility path/to/cdc_wonder_births.csv \
  --female-population path/to/female_population_by_age.csv \
  --population path/to/population_estimates.csv \
  --ntia path/to/ntia_state_prevalence.csv
```

The script writes `.parquet` outputs into `data/processed/`. Missing sources are allowed, but only the corresponding dashboard panels will be available.

### Local CPS + Hansen Shortcut

If you want to use the local D: drive files already available on this machine, run:

```bash
python scripts/build_local_cps_hansen_processed_data.py
```

This currently does three things:

- builds a state-year remote-work panel from `D:\cps_00005.dta\cps_00005_wfh.dta`
- merges in the national Hansen remote-postings series from `D:\remote_work_in_job_ads_public_data.xlsx`
- writes processed outputs to `data/processed/`

It also writes a source audit explaining why `D:\usa_00010.dta\usa_00010.dta` was not used if that ACS extract is not suitable for the modern dashboard period.

### Local ATUS + FRED Shortcut

If you want to build time-use and state population inputs from the local ATUS folders plus official FRED state series, run:

```bash
python scripts/build_local_atus_fred_processed_data.py
```

This currently does four things:

- builds ATUS national time-use metrics for 2016-2023
- builds ATUS regional metrics for 2016-2023 where geography is available
- builds ATUS state-pooled metrics for 2016-2021 where local ATUS-CPS geography is available
- downloads official FRED release 118 state population series and writes population totals plus growth rates

The local 2022-2023 ATUS folders do not currently contain extracted `atuscps` geography files, so those years are treated as national-only in this build.

### Manual CDC Fertility Shortcut

If you want to build the fertility panel from the state-year CDC values stored in this repo, run:

```bash
python scripts/build_manual_fertility_processed_data.py
```

This reads [data/raw/manual_state_fertility_rates_2016_2023.csv](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/data/raw/manual_state_fertility_rates_2016_2023.csv) and writes `data/processed/fertility_metrics.parquet`.

This version currently includes:

- general fertility rate by state and year
- total fertility rate by state and year

It does not yet include:

- birth counts
- age-specific fertility rates
- female population by age group

Those still need CDC WONDER exports and age-specific denominator files for the full projection simulator.

### Static Website Bundle Shortcut

To rebuild the GitHub Pages dashboard bundle from the processed parquet files, run:

```bash
python scripts/build_static_dashboard_bundle.py
```

This writes [ai-work-fertility-dashboard-data.js](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/ai-work-fertility-dashboard-data.js), which the static webpage uses directly. That makes the dashboard work on GitHub Pages and also when opened locally in a browser.

### Google Trends State-Year Proxy Shortcut

To build Google Trends state-year proxy data for U.S. GenAI and online-dating attention for `2016-2024`, run:

```bash
python scripts/build_google_trends_state_year_data.py
```

This currently uses the keyword baskets:

- GenAI: `chatgpt`, `claude ai`, `gemini ai`
- Online dating: `tinder`, `bumble`, `hinge`

The script writes:

- [data/raw/google_trends_state_year_raw.csv](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/data/raw/google_trends_state_year_raw.csv)
- [data/processed/digital_attention.parquet](/C:/Users/jheel/Documents/GitHub/jsrkr.github.io/data/processed/digital_attention.parquet)

Important limitation:

- These are calibrated search-attention proxies, not direct measures of app use, user counts, or time spent.

## How to Update the Data

1. Download or load ACS, ATUS, CDC WONDER, Census population, and NTIA/CPS source files.
2. Standardize them with the cleaning modules in `src/`.
3. Save cleaned outputs to `data/processed/` as `.csv` or `.parquet`.
4. Reopen the Streamlit app.

The data modules cache downloads where possible. If an API fails, the pipeline raises a clear error message and allows local CSV fallback instead.

## Dashboard Tabs

1. `Executive Summary`
   KPI cards for work from home, commute, fertility, population growth, digital distraction minutes, social minutes, and the direction of the selected scenario.

2. `Trends`
   Interactive line charts for remote work, commute, digital indices, fertility, and population growth.

3. `State Map`
   Choropleths for work from home, work-from-home growth, fertility, population growth, natural increase, and net migration. ATUS state maps should only be shown when sample-size thresholds are met.

4. `Digital vs Social Decomposition`
   Shows how digital distraction, digital-social proxy, remote work, and face-to-face interaction move over time.

5. `Fertility Projection Simulator`
   Lets the user choose scenario assumptions and project fertility and births to 2030, 2040, or 2050.

6. `Model Diagnostics and Data Quality`
   Displays source quality, sample-size, geography, warnings, and measurement concept.

## Limitations

- ACS 2020 one-year estimates require special caution.
- ATUS is not reliable for precise annual state-by-state minutes without pooling.
- Public data do not directly observe online dating or social-media minutes well at the state-year level.
- Google Trends and similar tools measure attention, not representative usage.
- CDC WONDER often requires exported CSV workflows rather than a stable public API.
- The default app separates observed metrics from scenario parameters because the behavioral mechanisms are not fully observed.

## Why the Dashboard Uses Scenarios Rather Than Causal Forecasts

The simulator is not a structural causal model. It combines:

- observed historical statistics,
- baseline trend extrapolations,
- user-specified behavioral assumptions,
- and population accounting rules.

This makes the tool useful for transparent stress-testing and comparative scenarios without overstating what the data can prove.
