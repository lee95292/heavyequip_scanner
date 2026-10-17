// Exact normalized-model × source-country × manufacture-year cohorts.
// No regression, invented years, or mixing different year distributions.
function buildYearPrices(rows, quantile, now = Date.now()) {
  const currentYear = new Date(now).getUTCFullYear();
  const known = rows.filter(r => r.model && r.country && r.country !== '국가 미상');
  const grouped = new Map();
  for (const row of known) {
    if (!grouped.has(row.model)) grouped.set(row.model, []);
    grouped.get(row.model).push(row);
  }
  const models = [...grouped].sort((a,b) => b[1].length-a[1].length || a[0].localeCompare(b[0]))
    .slice(0,30).map(([model, items], index) => {
      const dated = items.filter(r => Number.isInteger(r.year) && r.year >= 1950 && r.year <= currentYear);
      const byCountry = new Map();
      for (const row of dated) {
        if (!byCountry.has(row.country)) byCountry.set(row.country, []);
        byCountry.get(row.country).push(row);
      }
      const countries = [...byCountry].sort((a,b) => b[1].length-a[1].length || a[0].localeCompare(b[0], 'ko'))
        .slice(0,8).map(([country, entries]) => {
          const years = [...new Set(entries.map(r=>r.year))].sort((a,b)=>a-b);
          return {country, count: entries.length, cells: years.map(year => {
            const cohort = entries.filter(r=>r.year===year);
            const prices = cohort.map(r=>r.price);
            return {year, count:cohort.length, median:quantile(prices,.5), q1:quantile(prices,.25),
              q3:quantile(prices,.75), sourceCount:new Set(cohort.map(r=>r.source)).size};
          })};
        });
      return {model, rank:index+1, count:items.length, usableCount:dated.length,
        missingYearCount:items.length-dated.length, countryCount:byCountry.size,
        displayedCount:countries.reduce((n,r)=>n+r.count,0), countries};
    });
  return {models, modelLimit:30, countryLimit:8, totalModels:grouped.size,
    knownCount:known.length, totalCount:rows.length, scope:'all-stored-priced-inventory',
    yearBasis:'manufacture-year', priceBasis:'asking-price-krw', generatedAt:new Date(now).toISOString()};
}
module.exports = {buildYearPrices};
