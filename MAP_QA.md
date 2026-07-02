# MAP_QA

## A. Rebuild and automated tests

Run:

```powershell
node --check ai-work-fertility-dashboard.js
python scripts/build_static_dashboard_bundle.py
pytest tests/test_county_cbsa_display_layer.py -q
pytest tests/test_ai_work_fertility_dashboard_bundle.py -q
pytest tests/test_dashboard_scenario_integrity.py -q
pytest tests/test_build_msa_year_dashboard_outputs.py -q
```

## B. Start local server

Run:

```powershell
cd "C:\Users\jheel\Documents\GitHub\jsrkr.github.io"
python -m http.server 8000
```

## C. Runtime asset checks

Open or request these URLs and verify `200`:

- `http://localhost:8000/ai-work-fertility-dashboard.html`
- `http://localhost:8000/ai-work-fertility-dashboard.js`
- `http://localhost:8000/style.css`
- `http://localhost:8000/ai-work-fertility-dashboard-data.js`
- `http://localhost:8000/data/geo/us_msa_cbsa_simplified.js`
- `http://localhost:8000/data/geo/us_counties_cbsa_context_simplified.js`

## D. Four critical browser smoke-test URLs

State non-reference:

`http://localhost:8000/ai-work-fertility-dashboard.html?geo=state&model=statistical_ridge&scenario=remote_work_saves_time&year=2035&outcome=scenario_difference&debug=1`

State reference-path neutral:

`http://localhost:8000/ai-work-fertility-dashboard.html?geo=state&model=statistical_ridge&scenario=reference_path&year=2035&outcome=scenario_difference&debug=1`

MSA non-reference:

`http://localhost:8000/ai-work-fertility-dashboard.html?geo=msa&model=tree_gradient_boosting&scenario=remote_work_saves_time&year=2035&outcome=scenario_difference&debug=1`

MSA reference-path neutral:

`http://localhost:8000/ai-work-fertility-dashboard.html?geo=msa&model=tree_gradient_boosting&scenario=reference_path&year=2035&outcome=scenario_difference&debug=1`

## E. Expected behavior for all four URLs

For each:

- map appears
- map contains an SVG
- no message says `This chart could not be rendered for the selected view`
- no oversized blank gap appears where the map should be
- legend appears
- ranking cards populate
- summary card populates
- no red console errors
- no failed network requests

## F. Additional checks for reference_path + scenario_difference

Expected:

- map still renders
- all places are neutral/zero
- ranking cards say no places are above or below reference path
- summary is `0.00` for State and `0.000` for MSA
- debug console indicates neutral reference mode is active

## G. Additional MSA checks

Expected:

- county background/context layers appear
- estimated MSA counties are colored
- hover text differs between estimated counties and context-only counties
- clicking an estimated county changes the selected MSA
- caption says `Displayed by county; estimated at MSA level`
- no `County map is preparing` text remains after render
- debug console confirms `MSA county geometry loaded successfully`

## H. If a map fails, check in this order

1. Network tab for missing:
- `ai-work-fertility-dashboard-data.js`
- `data/geo/us_msa_cbsa_simplified.js`
- `data/geo/us_counties_cbsa_context_simplified.js`

2. Console for:
- JS runtime errors
- geometry load errors
- invalid map values
- Plotly/SVG/render errors if relevant

3. `debug=1` logs for:
- selected geo/model/scenario/year/outcome
- map record count
- State vs MSA branch
- neutral reference fallback
- MSA geometry success/failure

4. Determine whether the issue is:
- missing asset
- stale browser cache
- reference_path zero-domain issue
- MSA geometry join issue
- map container selector/layout issue
