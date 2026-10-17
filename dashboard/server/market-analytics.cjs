// Listing activity is a supply-side proxy, never a count of buyers or sales.
const {buildYearPrices} = require('./year-price.cjs');
const DAY = 86400000;
const median = (values) => quantile(values, 0.5);
function quantile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const low = Math.floor(pos);
  return Math.round(sorted[low] + (sorted[Math.ceil(pos)] - sorted[low]) * (pos - low));
}
function timestamp(value) {
  if (!value) return NaN;
  const text = String(value);
  // mysql is configured with dateStrings; source dates are stored in KST.
  return Date.parse(/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$/.test(text)
    ? `${text.replace(' ', 'T')}${text.length === 10 ? 'T00:00:00' : ''}+09:00` : text);
}
function summarize(rows, now) {
  const prices = rows.map((r) => r.price);
  const recent = rows.filter((r) => r.date <= now && r.date >= now - 30 * DAY).length;
  const previous = rows.filter((r) => r.date < now - 30 * DAY && r.date >= now - 60 * DAY).length;
  return {
    count: rows.length, recent, previous,
    undatedCount: rows.filter(r=>!Number.isFinite(r.date)).length,
    growthPercent: previous ? Math.round((recent / previous - 1) * 100) : null,
    medianPriceKrw: median(prices), q1PriceKrw: quantile(prices, 0.25), q3PriceKrw: quantile(prices, 0.75),
    medianYear: median(rows.map((r) => r.year).filter(Boolean)),
    sourceCount: new Set(rows.map((r) => r.source)).size,
  };
}
function groups(rows, key) {
  const result = new Map();
  for (const row of rows) {
    const label = key(row);
    if (!label) continue;
    if (!result.has(label)) result.set(label, []);
    result.get(label).push(row);
  }
  return result;
}
function analyzeMarket(input, filters = {}, now = Date.now()) {
  const period = [30, 90, 365].includes(Number(filters.period)) ? Number(filters.period) : 365;
  const minSample = [1, 3, 5, 10, 20].includes(Number(filters.minSample)) ? Number(filters.minSample) : 5;
  const yearFrom = /^\d{4}$/.test(String(filters.yearFrom || '')) ? Number(filters.yearFrom) : null;
  const yearTo = /^\d{4}$/.test(String(filters.yearTo || '')) ? Number(filters.yearTo) : null;
  const includeUndated = String(filters.includeUndated ?? '1') !== '0';
  const rows = input.filter((r) => Number.isFinite(Number(r.price_krw)) && Number(r.price_krw) >= 10000000).map((r) => ({
    ...r, model: String(r.model_norm || '').trim(), source: r.source_site || '',
    category: r.category_name || '', price: Number(r.price_krw), date: timestamp(r.posted_at || r.posted_date),
    year: /^\d{4}/.test(String(r.manufactured_ym || '')) ? Number(String(r.manufactured_ym).slice(0, 4)) : null,
  }));
  const base = rows.filter((r) => ((r.date >= now - period * DAY && r.date <= now) || (includeUndated && !Number.isFinite(r.date)))
    && (!filters.source || r.source === filters.source)
    && (!filters.category || r.category === filters.category)
    && (!yearFrom || r.year >= yearFrom) && (!yearTo || (r.year && r.year <= yearTo)));
  const known = base.filter((r) => r.model && r.country && r.country !== '국가 미상');
  const selected = base.filter((r) => (!filters.country || r.country === filters.country)
    && (!filters.model || r.model === filters.model));
  const selectedKnown = selected.filter((r) => r.model && r.country && r.country !== '국가 미상');
  const countryGroups = groups(known, (r) => r.country);
  const modelGroups = groups(known, (r) => r.model);
  const pairGroups = groups(selectedKnown, (r) => JSON.stringify([r.country, r.model]));
  const ranking = [...pairGroups].map(([key, items]) => {
    const [country, model] = JSON.parse(key);
    const countryRows = countryGroups.get(country) || [];
    const globalRows = modelGroups.get(model) || [];
    const others = globalRows.filter((r) => r.country !== country);
    const otherMedian = median(others.map((r) => r.price));
    const stats = summarize(items, now);
    const share = items.length / countryRows.length;
    return { country, model, ...stats, sharePercent: share * 100,
      concentration: known.length && globalRows.length ? share / (globalRows.length / known.length) : null,
      referenceCount: others.length, referenceMedianPriceKrw: otherMedian,
      pricePremiumPercent: others.length >= minSample && items.length >= minSample && otherMedian
        ? Math.round((stats.medianPriceKrw / otherMedian - 1) * 100) : null,
      sufficient: items.length >= minSample,
    };
  }).filter((r) => r.sufficient);
  const sortKeys = { count: 'count', recent: 'recent', concentration: 'concentration', premium: 'pricePremiumPercent' };
  const sortKey = sortKeys[filters.sort] || 'count';
  ranking.sort((a, b) => (b[sortKey] ?? -Infinity) - (a[sortKey] ?? -Infinity) || b.count - a.count
    || a.country.localeCompare(b.country, 'ko') || a.model.localeCompare(b.model));
  const countrySummary = [...groups(base.filter((r) => !filters.model || r.model === filters.model), (r) => r.country)]
    .filter(([country]) => country !== '국가 미상').map(([label, items]) => ({ label, ...summarize(items, now),
      modelCount: new Set(items.map((r) => r.model).filter(Boolean)).size,
    })).sort((a, b) => b.count - a.count);
  const modelSummary = [...groups(selectedKnown, (r) => r.model)].map(([label, items]) => ({label, ...summarize(items, now)}))
    .filter((r) => r.count >= minSample).sort((a, b) => b.count - a.count).slice(0, 12);
  const heatCountries = (filters.country ? [filters.country] : countrySummary.slice(0, 8).map((r) => r.label));
  const heatModels = filters.model ? [filters.model] : modelSummary.slice(0, 10).map((r) => r.label);
  const heatPairs = groups(known, (r) => JSON.stringify([r.country, r.model]));
  const heatmap = { countries: heatCountries, models: heatModels, cells: heatModels.flatMap((model) => heatCountries.map((country) => {
    const count = (heatPairs.get(JSON.stringify([country, model])) || []).length;
    const countryCount = (countryGroups.get(country) || []).length;
    return {country, model, count, sharePercent: countryCount ? count / countryCount * 100 : 0, sufficient: count >= minSample};
  })) };
  const trendGroups = groups(selectedKnown.filter(r=>Number.isFinite(r.date)), (r) => new Date(r.date + 9 * 3600000).toISOString().slice(0, 7));
  const trend = [];
  const first = new Date(now - period * DAY + 9 * 3600000);
  const end = new Date(now + 9 * 3600000);
  for (let month = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1)); month <= end; month.setUTCMonth(month.getUTCMonth() + 1)) {
    const label = month.toISOString().slice(0, 7);
    trend.push({ label, ...summarize(trendGroups.get(label) || [], now),
      partial: label === first.toISOString().slice(0, 7) || label === end.toISOString().slice(0, 7) });
  }
  const priceComparison = filters.model ? [...groups(known.filter((r) => r.model === filters.model), (r) => r.country)]
    .map(([label, items]) => ({label, ...summarize(items, now)})).filter((r) => r.count >= minSample)
    .sort((a, b) => b.medianPriceKrw - a.medianPriceKrw) : [];
  return {
    generatedAt: new Date(now).toISOString(),
    yearComparison: buildYearPrices(rows, quantile, now),
    filters: { country: filters.country || '', model: filters.model || '', period, minSample, includeUndated,
      countries: [...new Set(base.map((r) => r.country).filter((v) => v && v !== '국가 미상'))].sort((a,b)=>a.localeCompare(b,'ko')),
      models: [...new Set(base.filter((r) => !filters.country || r.country === filters.country).map((r) => r.model).filter(Boolean))].sort(),
      sources: [...new Set(rows.map((r) => r.source))].sort(), categories: [...new Set(rows.map((r)=>r.category).filter(Boolean))].sort(),
    },
    summary: {...summarize(selected, now), normalizedCount: selectedKnown.length,
      modelCount: new Set(selectedKnown.map((r) => r.model)).size,
      countryCount: new Set(selected.filter(r=>r.country && r.country!=='국가 미상').map((r) => r.country)).size,
      modelCoveragePercent: selected.length ? selected.filter((r) => r.model).length / selected.length * 100 : 0,
      missingModelCount: selected.filter((r) => !r.model).length,
      missingCountryCount: selected.filter((r) => !r.country || r.country === '국가 미상').length,
    },
    coverage: { totalStored: rows.length, missingDateCount: rows.filter((r)=>!Number.isFinite(r.date)).length,
      excludedByPeriod: rows.filter((r)=>Number.isFinite(r.date) && (r.date < now-period*DAY || r.date>now)).length,
      includedUndatedCount: base.filter(r=>!Number.isFinite(r.date)).length,
      datedScope: 'source-posted-date', demandMeasured: false },
    ranking: ranking.slice(0, 100), rankingTotal: ranking.length,
    countries: countrySummary.slice(0, 30), models: modelSummary, heatmap, trend, priceComparison,
    examples: [...selected].sort((a,b)=>(Number.isFinite(b.date)?b.date:0)-(Number.isFinite(a.date)?a.date:0)).slice(0, 8).map((r)=>({
      id:r.id, model:r.model || r.model_name || '모델 미확인', modelNormalized:!!r.model, country:r.country, source:r.source, priceKrw:r.price, year:r.year,
      title:r.listing_name, url:r.detail_url, postedDate:Number.isFinite(r.date)?new Date(r.date+9*3600000).toISOString().slice(0,10):null,
    })),
  };
}
module.exports = {analyzeMarket, quantile};
