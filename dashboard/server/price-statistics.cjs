// Relative asking prices, matched on exact normalized model and manufacture year.
// Each reference country, matched year, and model gets equal weight at its level.
function quantile(values, fraction) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * fraction;
  const low = Math.floor(position), high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}
const median = values => quantile(values, .5);
const round = value => Math.round(value * 10) / 10;
function groupBy(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const label = key(row);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(row);
  }
  return groups;
}
const strings = values => [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
function summarize(rows) {
  const prices = rows.map(row => row.price);
  return { count: rows.length, median: Math.round(median(prices)), q1: Math.round(quantile(prices, .25)),
    q3: Math.round(quantile(prices, .75)), sourceCount: new Set(rows.map(row => row.source)).size };
}
function analyzePriceMarkets(input, filters = {}, now = Date.now()) {
  const minSample = [3, 5, 10].includes(Number(filters.minSample)) ? Number(filters.minSample) : 3;
  const minYears = [1, 2, 3].includes(Number(filters.minYears)) ? Number(filters.minYears) : 1;
  const currentYear = new Date(now).getUTCFullYear();
  const validBound = value => /^\d{4}$/.test(String(value || '')) && +value >= 1950 && +value <= currentYear ? +value : null;
  const yearFrom = validBound(filters.yearFrom), yearTo = validBound(filters.yearTo);
  const rows = input.filter(row => Number.isFinite(Number(row.price_krw)) && Number(row.price_krw) >= 10000000)
    .map(row => {
      const yearText = String(row.manufactured_ym || '');
      const year = /^\d{4}(?:\D|$)/.test(yearText) ? Number(yearText.slice(0, 4)) : null;
      return { model: String(row.model_norm || '').trim(), country: String(row.country || '').trim(),
        source: row.source_site || '', category: row.category_name || '', price: Number(row.price_krw),
        year: year >= 1950 && year <= currentYear ? year : null };
    });
  const scoped = rows.filter(row => (!filters.source || row.source === filters.source)
    && (!filters.category || row.category === filters.category)
    && (!yearFrom || (row.year && row.year >= yearFrom)) && (!yearTo || (row.year && row.year <= yearTo)));
  const known = scoped.filter(row => row.model && row.country && row.country !== '국가 미상');
  const rankedModels = [...groupBy(known, row => row.model)].map(([model, items]) => ({
    model, count: items.length, validYearCount: items.filter(row => row.year).length,
  })).sort((a, b) => b.count - a.count || a.model.localeCompare(b.model)).slice(0, 30);
  const topModels = new Set(rankedModels.map(row => row.model));
  const usable = known.filter(row => topModels.has(row.model) && row.year);
  const cohortGroups = groupBy(usable, row => JSON.stringify([row.model, row.year]));
  const pairGroups = new Map();
  let matchedCount = 0;
  for (const [key, cohortRows] of cohortGroups) {
    const [model, year] = JSON.parse(key);
    const countries = [...groupBy(cohortRows, row => row.country)].map(([country, items]) => ({country, ...summarize(items)}))
      .filter(country => country.count >= minSample);
    if (countries.length < 2) continue;
    matchedCount += countries.reduce((sum, country) => sum + country.count, 0);
    for (const country of countries) {
      const others = countries.filter(other => other.country !== country.country);
      // Leave the target country out. Do not let a large source country dominate the benchmark.
      const referenceMedian = median(others.map(other => other.median));
      const ratio = country.median / referenceMedian;
      const pairKey = JSON.stringify([model, country.country]);
      if (!pairGroups.has(pairKey)) pairGroups.set(pairKey, {model, country: country.country, years: []});
      pairGroups.get(pairKey).years.push({year, ...country, ratio, gapPercent: round((ratio - 1) * 100),
        referenceMedian: Math.round(referenceMedian), referenceCount: others.reduce((sum, other) => sum + other.count, 0),
        referenceCountries: others.sort((a, b) => a.median - b.median)});
    }
  }
  const pairs = [...pairGroups.values()].filter(pair => pair.years.length >= minYears).map(pair => {
    const ratios = pair.years.map(year => year.ratio);
    const ratio = median(ratios);
    return {...pair, years: pair.years.sort((a, b) => a.year - b.year), ratio,
      gapPercent: round((ratio - 1) * 100), priceIndex: round(ratio * 100),
      yearCount: pair.years.length, count: pair.years.reduce((sum, year) => sum + year.count, 0),
      referenceCount: pair.years.reduce((sum, year) => sum + year.referenceCount, 0),
      referenceCountryCount: new Set(pair.years.flatMap(year => year.referenceCountries.map(other => other.country))).size,
      cheapYearPercent: Math.round(pair.years.filter(year => year.ratio < 1).length / pair.years.length * 100),
      gapQ1: round((quantile(ratios, .25) - 1) * 100), gapQ3: round((quantile(ratios, .75) - 1) * 100),
    };
  }).sort((a, b) => a.ratio - b.ratio || b.count - a.count || a.model.localeCompare(b.model) || a.country.localeCompare(b.country));
  const countries = [...groupBy(pairs, pair => pair.country)].map(([country, items]) => {
    const ratio = median(items.map(pair => pair.ratio));
    return {country, ratio, gapPercent: round((ratio - 1) * 100), priceIndex: round(ratio * 100),
      modelCount: items.length, count: items.reduce((sum, pair) => sum + pair.count, 0),
      cohortCount: items.reduce((sum, pair) => sum + pair.yearCount, 0),
      cheapModelCount: items.filter(pair => pair.ratio < 1).length,
      cheapModelPercent: Math.round(items.filter(pair => pair.ratio < 1).length / items.length * 100),
      broadEnough: items.length >= 3,
    };
  }).sort((a, b) => a.ratio - b.ratio || b.modelCount - a.modelCount || a.country.localeCompare(b.country));
  const comparedModels = new Set(pairs.map(pair => pair.model));
  return {generatedAt: new Date(now).toISOString(), version: 'matched-price-v1',
    filters: {minSample, minYears, yearFrom, yearTo, source: filters.source || '', category: filters.category || '',
      sources: strings(rows.map(row => row.source)), categories: strings(rows.map(row => row.category))},
    models: rankedModels.map((model, i) => ({...model, rank: i + 1, comparable: comparedModels.has(model.model)})),
    countries, pairs,
    coverage: {totalStored: rows.length, scopedCount: scoped.length, knownCount: known.length,
      missingModelCount: scoped.filter(row => !row.model).length,
      missingCountryCount: scoped.filter(row => !row.country || row.country === '국가 미상').length,
      missingYearCount: known.filter(row => !row.year).length, validTopModelCount: usable.length,
      matchedCount, comparedCount: pairs.reduce((sum, pair) => sum + pair.count, 0),
      comparedModelCount: comparedModels.size, comparedCountryCount: countries.length,
      broadCountryCount: countries.filter(country => country.broadEnough).length,
      pairCount: pairs.length, modelLimit: 30},
  };
}
module.exports = {analyzePriceMarkets, quantile};
