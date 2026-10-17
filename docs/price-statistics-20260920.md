# Country/model price statistics

The country/model page now contains only relative-price analysis: country comparisons, inexpensive country/model combinations, a price-gap heatmap, and matched-year price detail. Supply concentration, registration activity, raw mixed-model medians and demand proxies are removed from the page.

## Method

- International construction listings priced at least KRW 10 million; source/category/year filters apply to both the target and reference populations.
- Rank the 30 most-listed known normalized models in that scope. Keep exact normalized model variants separate. Only valid manufacture years from 1950 through the current year enter comparisons.
- Each country/model/year cell requires at least 3 listings by default (5/10 selectable). At least two countries must qualify in the same model/year.
- For each target country, reference price is the median of the other qualifying countries' price medians. The target is excluded. Large countries do not dominate the reference by listing volume.
- Model price ratio is the median of matched-year ratios, with equal year weights. Minimum matched years defaults to 1 (2/3 selectable).
- Country price ratio is the median of its model ratios, with equal model weights. Show country-wide candidates only with 3+ comparable models; narrower results are explicitly limited.
- Gap is `(ratio - 1) * 100`. Negative is cheaper. Country baskets/reference markets can differ, so the result is an exploratory comparison, not a definitive identical-basket global ranking.
- Details show exact target/reference medians, target IQR, individual reference-country medians/counts and matched sample sizes. These are asking prices, not transactions or investment returns. Condition, hours, specifications, tax, freight and cross-site duplicates are not controlled.

## Compatibility and verification

- New authenticated read-only endpoint: `/api/international-price-statistics`.
- Existing `/api/international-price-analytics` remains compatible for already-open old clients. Both reuse the same 15-second raw-row cache/query.
- No database migrations, data rewriting/deletion, crawler restarts or schedule changes.
- Node tests cover age-composition reversal, exact variants/years, target exclusion, equal weights, sparse data, top-30 scope, all eligible countries, invalid/missing values, filters, empty results and initial/data rendering.
- CSS explicitly preserves matrix/detail tables against the dashboard's global mobile stacked-table rules; horizontal scrolling is confined to chart/table containers.
