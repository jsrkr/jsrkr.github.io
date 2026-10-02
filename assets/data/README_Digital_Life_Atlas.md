# Digital Life Atlas: Data and Methods

## Data files and source inputs

The website publishes one row for each of the 50 states and the District of Columbia in 2016–2019 and 2021–2023: **357 state-year observations**. There is no 2020 value and none is interpolated. The final downloadable files contain **48 variables**:

- [`digital_life_state_year.csv`](digital_life_state_year.csv)
- [`state-year-digital-life-index.dta`](state-year-digital-life-index.dta)

The website build uses two upstream files. `D:\digital_life_state_new.dta` supplies the current ACS remote-work and ATUS leisure measures and has 357 observations and 35 variables. `D:\state-year-digital-life-index.dta` supplies the ACS household access shares and their standardized values; it has 357 observations and 17 variables. The latter file also contains an older PCA index, but its `pc1` and `digital_life_index` fields are not used to construct the current primary index. Neither upstream file is modified by the website build.

The build script is [`../../scripts/build_digital_life_atlas_data.py`](../../scripts/build_digital_life_atlas_data.py). Recreate both downloads from the upstream inputs with:

```powershell
python scripts\build_digital_life_atlas_data.py --source-dta "D:\digital_life_state_new.dta" --access-source-dta "D:\state-year-digital-life-index.dta"
```

The final public Stata file has SHA-256 `d1a171e70d3f43aaffed4b54586d53800637acaf30aec1d9022b2085eff31401`; the CSV has SHA-256 `8ad1c7068506949776133e177fea9f0a6abb32e47d60b960e252c76c9ebd8f08`. The upstream Stata hashes are `be5b0b0cea5ef99226792affd4d1c892c77bdbb35ad8576929ca6550a630b455` for `D:\digital_life_state_new.dta` and `d7fad6a6723d50829982ba5496824ede9e6a776b08b61e3f1189d02aeec9c199` for `D:\state-year-digital-life-index.dta`.

The named `D:\state-year-digital-life-index.dta` input is an older PCA-based file: its stored `digital_life_index` matches the pooled min-max rescaling of `pc1` to within 0.00000003, and its Stata label says “Digital Life Index (PCA, 0-1).” The newer input also supplies a `digital_life_index`, but it has no `pc1` or construction formula, and its values do not reproduce the equal-weight formula below. The current builder therefore constructs the primary index directly from the three verified dimensions and computes a separate, reproducible PCA alternative from those same current dimensions.

## Variable inventory

The table reports the final downloadable Stata variable names, storage types, and labels. A dash means the Stata variable has no label. Descriptions identify the field's role in the published data. Shares remain stored as fractions from 0 to 1.

| Variable | Stata type | Stata label | Description |
| --- | --- | --- | --- |
| `state_fips` | double | — | State or District of Columbia FIPS identifier. |
| `state_abbr` | str3 | — | State or District of Columbia abbreviation. |
| `state_name` | str21 | — | State or District of Columbia name. |
| `year` | double | — | Survey year. |
| `television_movie_minutes_mean` | double | — | ATUS weighted mean minutes per day for television and movie leisure. |
| `television_movie_minutes_mean_se` | double | — | Standard error for the television/movie mean. |
| `television_movie_minutes_mean_l9` | double | `television_movie_minutes_mean_l95` | Lower 95% confidence limit for the television/movie mean; `_l9` is the Stata-safe shortened name. |
| `television_movie_minutes_mean_u9` | double | `television_movie_minutes_mean_u95` | Upper 95% confidence limit for the television/movie mean; `_u9` is the Stata-safe shortened name. |
| `television_movie_minutes_mean_cv` | double | — | Coefficient of variation for the television/movie mean. |
| `digital_leisure_minutes_mean` | double | — | ATUS weighted mean minutes per day for the digital-leisure activity definition below. |
| `digital_leisure_minutes_mean_se` | double | — | Standard error for the digital-leisure mean. |
| `digital_leisure_minutes_mean_l95` | double | — | Lower 95% confidence limit for the digital-leisure mean. |
| `digital_leisure_minutes_mean_u95` | double | — | Upper 95% confidence limit for the digital-leisure mean. |
| `digital_leisure_minutes_mean_cv` | double | — | Coefficient of variation for the digital-leisure mean. |
| `share_any_television_movie` | double | — | ATUS weighted share with any television/movie leisure time. |
| `share_any_television_movie_se` | double | — | Standard error for the television/movie participation share. |
| `share_any_television_movie_l95` | double | — | Lower 95% confidence limit for the television/movie participation share. |
| `share_any_television_movie_u95` | double | — | Upper 95% confidence limit for the television/movie participation share. |
| `share_any_television_movie_cv` | double | — | Coefficient of variation for the television/movie participation share. |
| `share_any_digital_leisure` | double | — | ATUS weighted share with any minutes in either included digital-leisure activity. |
| `share_any_digital_leisure_se` | double | — | Standard error for the digital-leisure participation share. |
| `share_any_digital_leisure_l95` | double | — | Lower 95% confidence limit for the digital-leisure participation share. |
| `share_any_digital_leisure_u95` | double | — | Upper 95% confidence limit for the digital-leisure participation share. |
| `share_any_digital_leisure_cv` | double | — | Coefficient of variation for the digital-leisure participation share. |
| `sh_gt_p50_digital_leisure` | double | — | ATUS weighted share above the national, year-specific weighted median for digital-leisure minutes. |
| `sh_gt_p50_digital_leisure_se` | double | — | Standard error for the above-median share. |
| `sh_gt_p50_digital_leisure_l95` | double | — | Lower 95% confidence limit for the above-median share. |
| `sh_gt_p50_digital_leisure_u95` | double | — | Upper 95% confidence limit for the above-median share. |
| `sh_gt_p50_digital_leisure_cv` | double | — | Coefficient of variation for the above-median share. |
| `television_movie_minutes_users` | double | — | Mean television/movie leisure minutes among respondents with positive time in that activity. |
| `remote_share` | double | — | ACS person-weighted share of workers age 16 or older who usually work from home. |
| `digital_access` | double | Mean of z_internet, z_highspeed, and z_cellular | Mean of the three standardized ACS household-access measures. |
| `digital_access_score_z` | double | Standardized values of digital_access | Standardized Digital Accessibility dimension used in the index. |
| `digital_work_score_z` | double | Standardized values of remote_share | Standardized Digital Work dimension used in the index. |
| `digital_life_index` | double | Digital Life Index (equal-weight, 0-1) | Primary equal-weight Digital Life Index, min-max scaled over all 357 state-year observations. |
| `share_cellular_data_plan` | double | Share households with cellular data plan | ACS household-weighted share with a cellular data plan. |
| `share_internet` | double | Share households with internet access | ACS household-weighted share with internet access. |
| `share_highspeed` | double | Share households with high-speed broadband | ACS household-weighted share with high-speed broadband. |
| `z_cellular` | double | Standardized values of share_cellular_data_plan | Pooled state-year standardized cellular data-plan share. |
| `z_internet` | double | Standardized values of share_internet | Pooled state-year standardized internet-access share. |
| `z_highspeed` | double | Standardized values of share_highspeed | Pooled state-year standardized high-speed broadband share. |
| `digital_leisure_score_z` | double | Standardized values of digital_leisure_minutes_mean | Standardized Digital Leisure dimension used in the index. |
| `digital_life_raw` | double | Equal-weight mean of the three standardized dimensions | Equal-weight composite before min-max scaling. |
| `pc1` | double | First principal-component score of the three standardized dimensions | PCA robustness score; not the primary index. |
| `digital_life_index_pca` | double | PCA alternative Digital Life Index (0-1) | Min-max scaled PCA alternative; not used in Figures 1–3. |
| `digital_work_score_01` | double | Pooled state-year min-max display score from digital_work_score_z | Figure 1–3 display transformation of `digital_work_score_z`. |
| `digital_leisure_score_01` | double | Pooled state-year min-max display score from digital_leisure_score_z | Figure 1–3 display transformation of `digital_leisure_score_z`. |
| `digital_access_score_01` | double | Pooled state-year min-max display score from digital_access_score_z | Figure 1–3 display transformation of `digital_access_score_z`. |

## Data and component definitions

The index combines ACS measures of remote work and household access with ATUS measures of digital leisure.

### Digital Work

Digital Work is `remote_share`, the person-weighted share of workers age 16 or older whose ACS `tranwork` response is 80 (usually working from home). The source construction keeps records with `tranwork != 0`, weights workers by `perwt`, and calculates the state-year ratio of weighted work-from-home workers to weighted workers. `digital_work_score_z` is its pooled state-year standardization.

### Digital Leisure

The ATUS construction file defines digital leisure as the sum of `TRCODE=120303` (television and movies, not religious) and `TRCODE=120308` (computer use for leisure, excluding games). The former includes television/video entertainment, including streaming; the latter includes leisure computer use such as personal-interest browsing and social media. Public ATUS codes do not separate device-specific games, and the builder excludes `TRCODE=120307` because it combines digital and nondigital games.

The measure covers adults age 18–64, all employment statuses. State estimates require a valid state, a positive ATUS final respondent weight, and a complete 1,440-minute diary. A valid diary with zero minutes in either included activity contributes zero. `digital_leisure_minutes_mean` is the weighted mean minutes per day; `share_any_digital_leisure` is a separate descriptive participation measure. `sh_gt_p50_digital_leisure` is a separate descriptive share above the national, year-specific weighted median. Neither participation measure enters the index. The ATUS construction documentation is `D:\ATUS\digital_life_outputs\README_ATUS_Digital_Leisure.md`.

### Digital Accessibility

Digital Accessibility represents household internet access, high-speed broadband access, and cellular data-plan access. ACS household shares are stored in `share_internet`, `share_highspeed`, and `share_cellular_data_plan`; household proportions use `hhwt`, with each measure's denominator restricted to nonmissing responses. The pooled standardized fields are `z_internet`, `z_highspeed`, and `z_cellular`, using the pooled sample standard deviation (N−1). The dimension is:

`digital_access = (z_internet + z_highspeed + z_cellular) / 3`

Each household-access measure therefore receives equal weight within Digital Accessibility. The dimension is then standardized across the pooled state-year sample as `digital_access_score_z` before it enters the primary index.

## Index construction

The three dimensions are standardized over the pooled 357-observation state-year sample using the sample standard deviation (N−1). The primary composite uses equal weights:

`digital_life_raw = (digital_work_score_z + digital_leisure_score_z + digital_access_score_z) / 3`

The index is the pooled min-max rescaling of that composite:

`digital_life_index = (digital_life_raw - pooled minimum) / (pooled maximum - pooled minimum)`

For this release, `digital_life_raw` ranges from **-1.5993671916** to **2.5494686511**. The resulting `digital_life_index` ranges from 0 to 1. Equal weighting captures the three distinct dimensions without giving greater weight to any one dimension.

The Digital Life Index is a **score, not a percentage**. Higher scores indicate greater digital-life intensity based on digital work, digital leisure, and digital accessibility. A value of 0.75 does not mean that 75% of people are digitally engaged. Since the 0–1 transformation uses the pooled observed state-year distribution, interpret it for comparisons within this dataset.

### PCA robustness measure

The downloadable data also retain a PCA alternative based on the same three standardized dimensions. With the orientation chosen so the Digital Work and Digital Accessibility coefficients are positive, the current first-component scoring coefficients are **0.6675671** for `digital_work_score_z`, **-0.3093505** for `digital_leisure_score_z`, and **0.6772418** for `digital_access_score_z`. `pc1` stores the resulting component score, and `digital_life_index_pca` is its pooled 0–1 min-max rescaling. This is an alternative weighting approach; it is not the primary `digital_life_index` and is not used in Figures 1–3.

## Figure 1–3 display transformations

Figures 1–3 show the primary index and component display scores on a common 0–1 scale. The index is already on that scale. The three component display fields use pooled min-max transformations:

`display_score = (source value - pooled minimum) / (pooled maximum - pooled minimum)`

| Display field | Source field | Pooled minimum | Pooled maximum |
| --- | --- | ---: | ---: |
| `digital_life_index` | `digital_life_index` | 0.000000 | 1.000000 |
| `digital_work_score_01` | `digital_work_score_z` | -1.191710 | 6.558906 |
| `digital_leisure_score_01` | `digital_leisure_score_z` | -2.870208 | 4.969967 |
| `digital_access_score_01` | `digital_access_score_z` | -3.489293 | 1.812069 |

These display transformations do not alter the underlying source variables. They are used for visualization and comparability, are not additional indices, and must not be interpreted as percentages.

## Underlying state-level measures: Figure 4

Figure 4 uses the original source measures, not normalized component or index fields. Share fields are stored as fractions and multiplied by 100 for chart display; the downloaded data remain fractions. Digital-leisure time is shown in minutes per day.

| Figure 4 measure | Source field | Stored unit | Observed range in source units | Display range |
| --- | --- | --- | ---: | ---: |
| Remote workers | `remote_share` | Fraction | 0.022943–0.475081 | 2.29%–47.51% |
| Digital leisure | `digital_leisure_minutes_mean` | Minutes per day | 59.750256–323.313812 | 59.75–323.31 minutes/day |
| Any digital leisure | `share_any_digital_leisure` | Fraction | 0.434506–1.000000 | 43.45%–100.00% |
| Digital leisure above P50 | `sh_gt_p50_digital_leisure` | Fraction | 0.098858–0.880814 | 9.89%–88.08% |
| Households with internet | `share_internet` | Fraction | 0.744537–0.974211 | 74.45%–97.42% |
| Households with high-speed internet | `share_highspeed` | Fraction | 0.636310–0.895798 | 63.63%–89.58% |
| Households with cellular data plan | `share_cellular_data_plan` | Fraction | 0.679959–0.962709 | 68.00%–96.27% |
| Any television or movie leisure | `share_any_television_movie` | Fraction | 0.338459–1.000000 | 33.85%–100.00% |

Figure 4 includes all available states and the District of Columbia for the selected year, ordered from highest to lowest. Participation measures are descriptive underlying measures and do not enter the primary index.

## Figure calculations and coverage

- **Figure 1:** arithmetic means across the 50 states and DC within each observed year; each geography receives equal weight. It shows only observed years. The gap from 2019 to 2021 reflects the absence of 2020 data.
- **Figure 2:** the Digital Life Index or selected component across all 50 states and DC. Each metric's color scale is based on its full pooled state-year distribution and stays fixed when the selected year changes.
- **Figure 3:** the primary Digital Life Index and its three component display scores for the selected state and year. Displayed state ranks are calculated within the selected year; ties share a rank.
- **Figure 4:** underlying measures in their original units. Share fields are displayed as percentages and digital leisure as minutes per day; normalized index values are not used.
- **2020:** no observation is included or interpolated because ATUS did not provide a comparable full-year estimate.

## Reproducibility notes

The website's active data build is the Python script linked above. It joins the ACS access fields by state FIPS and year, checks that the three standardized access fields reproduce `digital_access`, recalculates all three standardized dimensions and the equal-weight primary index, and computes the PCA alternative from the same dimensions. It does not use the legacy `pc1` or `digital_life_index` fields in `D:\state-year-digital-life-index.dta` or the undocumented supplied index in `D:\digital_life_state_new.dta`.

The `D:\Digital_life_Atlas.do` and index-construction block in `D:\ACS_Internet.do` have been aligned to the equal-weight primary formula and retain PCA as `digital_life_index_pca`. The obsolete `share_cellular_data` reference in the latter was changed to the source field `share_cellular_data_plan`. These Stata files are not called by the website's Python build. The original `D:\state-year-digital-life-index.dta` remains an unchanged historical PCA file; the website builder uses it only for its ACS access measures. The ATUS activity definitions and sample restrictions above were verified against the current ATUS construction script and its README; no activity definition was inferred from the website data alone.

## License

The Digital Life Index uses separate licenses for code and research materials.

- Original project code is licensed under the MIT License. See [LICENSE-DIGITAL-LIFE-CODE](../../LICENSE-DIGITAL-LIFE-CODE).
- Original derived datasets, figures, and documentation are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0). See [LICENSE-DIGITAL-LIFE-DATA.md](../../LICENSE-DIGITAL-LIFE-DATA.md).

These licenses apply only to the Digital Life Index project and do not apply to unrelated content on Jheelum Sarkar's website or to underlying third-party source data. The CC BY 4.0 license covers only original derived materials; source data remain governed by their source agencies' terms and attribution practices. Plotly.js, topology assets, externally loaded fonts, and other third-party materials retain their own licenses or terms.

## Suggested citation

Sarkar, Jheelum. 2026. “Digital Life Index.” [https://jsrkr.github.io/digital-life.html](https://jsrkr.github.io/digital-life.html)
