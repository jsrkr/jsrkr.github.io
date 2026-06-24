# Digital Life vs In-Person Life Dashboard Blueprint

## Objective
Build a state-year U.S. panel that separates digital life exposure from in-person life exposure, then uses baseline, statistical, tree-based, and neural-network models to project fertility and population under alternative scenarios.

## Source Hierarchy
- `ACS/IPUMS ACS microdata`
  Purpose: state-year work structure, remote work, commute burden, and demographic controls.
- `ATUS/IPUMS ATUS raw files`
  Purpose: time-use minutes for digital distraction, social interaction, work at home, work away, and commuting.
- `Google Trends`
  Purpose: state-year dating-app and digital-attention proxies.
- `CDC fertility panel`
  Purpose: general fertility rate, total fertility rate, births where available.
- `Population panel`
  Purpose: total population, female population 15-44, deaths, migration where available.

## Required Processing Modules

### 1. ACS Work and Control Builder
File: `src/clean_acs.py`

Core functions:
- `summarize_acs_year_coverage(df)`
- `validate_modern_acs_years(df, min_year=2010)`
- `build_weighted_acs_state_year_panel(df, min_year=2010)`

State-year measures to output:
- `remote_work_share_state_year`
- `on_site_work_share_state_year`
- `usual_hours_all_workers`
- `usual_hours_wfh_workers`
- `remote_work_hours_proxy`
- `mean_commute_minutes_state_year`
- `long_commute_share_state_year`
- `female_employment_rate`
- `labor_force_participation_rate`
- `married_or_partnered_share_state_year`
- `sample_size`

Implementation rule:
- Use ACS person weights.
- Restrict work metrics to employed workers.
- Restrict female employment denominator to women 15-44.
- Fail clearly if the ACS extract does not cover the modern dashboard period.

### 2. ATUS Time-Use Builder
File: `src/clean_atus.py`

Core functions:
- `build_atus_respondent_day(base_dir, year)`
- `_aggregate_atus_groups(df, group_cols, geography_type, min_state_sample)`
- `pool_small_state_estimates(df, window=3, min_state_sample=MIN_ATUS_STATE_SAMPLE)`
- `build_atus_aggregates_from_raw(base_dir, years, min_state_sample=MIN_ATUS_STATE_SAMPLE)`

State-year or pooled measures to output:
- `digital_distraction_minutes`
- `face_to_face_social_minutes`
- `commuting_minutes`
- `work_at_home_minutes`
- `work_away_minutes`
- `away_from_home_minutes`
- `time_alone_minutes`
- `time_with_spouse_only_minutes`
- `time_with_friends_minutes`
- `time_with_nonhousehold_minutes`
- `time_with_family_minutes`
- `time_with_children_minutes`
- `time_with_spouse_minutes`
- `in_person_social_minutes`
- `sample_size`
- `estimate_status`

Implementation rule:
- Use ATUS final weights.
- Direct state-year values only when sample size is sufficient.
- Otherwise use pooled estimates and flag them.
- Keep national and regional estimates as benchmark anchors.

### 3. Proxy Builder
Files:
- `src/clean_digital_media.py`
- `scripts/build_google_trends_state_year_data.py`

Proxy measures:
- `search_interest_online_dating_state_year`
- `search_interest_genai_state_year`
- `digital_attention_proxy_index`

Implementation rule:
- Treat these as proxies only.
- Never label them as direct use or direct minutes.

### 4. Exposure Index Constructor
File: `src/metrics.py`

Indices:
- `remote_work_exposure_index`
- `in_person_work_exposure_index`
- `digital_distraction_index`
- `digital_social_index`
- `in_person_social_index`
- `digital_access_index`
- `digital_use_prevalence_index`
- `commute_burden_index`
- `work_family_compatibility_proxy`
- `gendered_care_risk_proxy`

Implementation rule:
- Standardize components within year across states.
- Preserve raw components.
- Store a mode flag for each index: `observed`, `imputed`, `modeled`, or `user_provided`.

### 5. ML Panel Builder
File: `src/ml_dataset.py`

Outputs:
- `data/processed/ml_state_year_panel.parquet`
- `outputs/ml_data_dictionary.csv`

Derived features:
- lag 1, 2, 3 for all exposure indices
- rolling 3-year averages
- fertility lags and rolling means
- state history descriptors
- year trend variables
- transparent imputation flags

### 6. Forecasting Layer
Files:
- `src/ml_models.py`
- `src/scenarios.py`
- `src/projections.py`
- `src/explainability.py`

Forecast model families:
- naive carry-forward
- recent trend continuation
- regularized statistical model
- tree-based ML model
- temporal neural network

Scenario outputs:
- baseline continuation
- distraction dominant
- remote-work dominant
- digital-social substitution
- in-person revival
- gendered-care penalty
- user-defined scenario

Explainability outputs:
- global permutation importance
- optional SHAP
- local perturbation-based contributions
- temporal importance via lag perturbation

## Review Build Reality
- Local ACS file currently available at `D:\usa_00010.dta\usa_00010.dta` is 1980-only and not suitable for the modern panel.
- The review dashboard therefore uses:
  - ATUS for time use
  - CPS fallback remote-work panel for modern state-year work-from-home exposure
  - CDC fertility panel
  - population totals
  - Google Trends dating-app and GenAI proxies

## Run Order
1. `python scripts/build_local_atus_fred_processed_data.py`
2. `python scripts/build_local_cps_hansen_processed_data.py`
3. `python scripts/build_manual_fertility_processed_data.py`
4. `python scripts/build_google_trends_state_year_data.py`
5. build modeling panel and ML artifacts
6. `python scripts/build_static_dashboard_bundle.py`

## Honest Interpretation Rule
The dashboard is a scenario-based predictive framework. It is not a structural causal model and should never present neural-network forecasts as causal effects.
