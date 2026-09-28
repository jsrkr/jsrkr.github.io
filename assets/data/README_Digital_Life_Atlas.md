# Digital Life Atlas: data and methods

## Updated authoritative source

The authoritative file is `D:\state-year-digital-life-index.dta`. The site's downloadable Stata file is a direct byte-for-byte copy (SHA-256: `d7fad6a6723d50829982ba5496824ede9e6a776b08b61e3f1189d02aeec9c199`). The original source was not modified.

The updated source contains **357 observations and 17 variables**: 51 geographies (the 50 states and DC), seven observed years (2016-2019 and 2021-2023), one row per state-year, and no missing values. There is no 2020 row. The public CSV preserves all 17 source variables and appends three display-only normalized component fields.

| Variable | Stata storage type | Variable label |
| --- | --- | --- |
| `statefip` | byte | state (fips code) |
| `year` | int | census year |
| `share_cellular_data_plan` | float | Share households with cellular data plan |
| `state_abbr` | str2 | ? |
| `state_name` | str20 | ? |
| `digital_leisure_minutes_mean` | float | ? |
| `remote_share` | float | ? |
| `share_internet` | float | Share households with internet access |
| `share_highspeed` | float | Share households with high-speed broadband |
| `z_remote` | float | Standardized values of remote_share |
| `z_leisure` | float | Standardized values of digital_leisure_minutes_mean |
| `z_internet` | float | Standardized values of share_internet |
| `z_highspeed` | float | Standardized values of share_highspeed |
| `z_cellular` | float | Standardized values of share_cellular_data_plan |
| `digital_access` | float | ? |
| `pc1` | float | Scores for component 1 |
| `digital_life_index` | float | Digital Life Index (PCA, 0-1) |

A dash means the Stata variable has no label. The revised file does **not** contain `share_cellular_data`; its corresponding underlying measure is named `share_cellular_data_plan`. The dashboard and CSV use the actual revised name and do not add a fabricated alias. No additional source variables are dropped from the CSV.

## Components and index

- **Digital Work** is `z_remote`, standardized from `remote_share`. The inspected ACS construction code defines `remote_share` as the person-weighted share of workers age 16 or older, among records with a nonzero `tranwork`, whose `tranwork` value is 80 (usually working from home).
- **Digital Leisure** is `z_leisure`, standardized from `digital_leisure_minutes_mean`. The revised DTA has no variable label for this raw field, and the inspected current construction files do not document its detailed activity or sample definition. Figure 4 therefore reports the provided measure in minutes per day without adding a more specific definition.
- **Digital Accessibility** is `digital_access = (z_internet + z_highspeed + z_cellular) / 3`. These are standardized household shares of internet access, high-speed broadband, and a cellular data plan.

The stored `digital_life_index` is used directly in the web figures. It is the finalized min-max normalization of stored `pc1`, the first component from a PCA of `z_remote`, `z_leisure`, and `digital_access`. From the updated stored PC1 and inputs, the positive correlation-PCA scoring coefficients are approximately **0.683120, 0.287953, and 0.671141**, respectively (0.6831, 0.2880, and 0.6711 rounded to four decimals). These match the previous four-decimal values; the updated stored data do not indicate a loading change. PC1 ranges from -3.1952683926 to 4.8636875153, and `digital_life_index` ranges from 0 to 1. Recalculating the equal-weight accessibility average differs from stored `digital_access` by at most 0.00000011; recalculating the PC1 min-max transformation differs from stored `digital_life_index` by at most 0.00000003.

**Source-code note:** the PCA block in the inspected `D:\ACS_Internet.do` still refers to the legacy name `share_cellular_data`, while the revised DTA has `share_cellular_data_plan` and labels `z_cellular` as standardized from that revised field. The website follows the authoritative DTA. Align that input name before rerunning the old PCA block. The raw leisure field's detailed construction was not present in the inspected do-files.

## Display transformations

The Digital Life Index and its component scores are relative measures normalized between 0 and 1 over the pooled state-year sample. These scores are **not percentages**.

The finalized index is read from `digital_life_index` without reconstruction. The other three displayed 0-1 fields are recalculated from the updated source using pooled minima and maxima across all 357 observations:

`display = (source value - pooled minimum) / (pooled maximum - pooled minimum)`

| CSV display field | Source field | Pooled minimum | Pooled maximum |
| --- | --- | ---: | ---: |
| `digital_work_score_01` | `z_remote` | -1.1917097569 | 6.5589056015 |
| `digital_leisure_score_01` | `z_leisure` | -1.5978561640 | 6.8247427940 |
| `digital_accessibility_score_01` | `digital_access` | -2.7391426563 | 1.4224991798 |

These display fields do not replace or alter their source variables and are not additional PCA indices. Each score reaches 0 and 1 in the pooled sample. The `digital_life_index` is likewise already on 0-1 in the authoritative source.

## Underlying raw state statistics (Figure 4)

Figure 4 uses the raw source fields below, not the normalized component/index values:

| Figure 4 measure | Source field in updated DTA | Stored range | Figure display units |
| --- | --- | ---: | --- |
| Remote Workers (%) | `remote_share` | 0.022943-0.475081 | Percent; source values are fractions and are multiplied by 100 only for display |
| Digital Leisure (Min/Day) | `digital_leisure_minutes_mean` | 0.814029-142.618164 | Minutes per day; no scaling |
| Households with Internet (%) | `share_internet` | 0.744537-0.974210 | Percent; source values are fractions and are multiplied by 100 only for display |
| Households with High-Speed Internet (%) | `share_highspeed` | 0.636310-0.895798 | Percent; source values are fractions and are multiplied by 100 only for display |
| Households with Cellular Data (%) | `share_cellular_data_plan` | 0.679959-0.962709 | Percent; source values are fractions and are multiplied by 100 only for display |

The source values in both downloads remain unscaled fractions for the share fields. Figure 4 formats those values as percentages and reports leisure in average minutes per day. The share ranges are within 0-1, and the leisure values are nonnegative. It shows all available state/DC observations for the selected year and sorts high to low. If a raw field is absent from a future source file, its control option is omitted.

## Figure calculations

- **Figure 1:** arithmetic mean across the 51 geographies within each observed year; each state and DC has equal weight. The chart uses only available years and marks the 2019-2021 gap when 2020 is absent.
- **Figure 2:** all 51 geographies are plotted. Each metric's color domain is recalculated from that metric's full updated state-year series, then held fixed when the selected year changes. Alaska and Hawaii remain in the Albers USA projection.
- **Figure 3:** the four normalized values for the selected state and map year. Any displayed state rank is recalculated within that selected year; tied values share a rank.
- **Figure 4:** actual underlying measures for all available geographies, shown as percentages or minutes per day as appropriate. It is not a second normalized-score chart. The selected state is outlined subtly when available.
- **2020:** absent from the source and not interpolated. ATUS did not produce a comparable full-year estimate, so the trend caption notes the omission.

## Mailing list

The signup form uses **Buttondown**'s public HTML subscription endpoint. Set the one configuration value `BUTTONDOWN_USERNAME` near the top of `assets/js/digital-life.js` to the username from the Buttondown public newsletter URL. The form then posts directly over HTTPS to `https://buttondown.com/api/emails/embed-subscribe/<username>` using Buttondown's standard HTML form flow and embedded-form field. It does not use JavaScript `fetch`, store email addresses, or require a private API key. Do not put a private API key in this repository.

When the username is blank, the email field remains visible and required, the Subscribe button is disabled, and a setup note is shown. To test a configured form, serve the site locally or use its HTTPS page, confirm the button is enabled and the form action contains the correct public username, then submit an email address you control and complete Buttondown's confirmation flow. Replace Buttondown later by changing the form action and any provider-specific public form fields; the site has no mailing-list backend.

Buttondown's current form instructions are in its [subscriber-base documentation](https://docs.buttondown.com/building-your-subscriber-base#embedding-an-html-form).
