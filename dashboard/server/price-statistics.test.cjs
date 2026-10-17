const test = require('node:test');
const assert = require('node:assert/strict');
const {analyzePriceMarkets, quantile} = require('./price-statistics.cjs');
const now = Date.parse('2026-09-20T00:00:00Z');
const rows = (country, model, year, price, count = 3, extra = {}) => Array.from({length: count}, () => ({country, model_norm: model, manufactured_ym: String(year), price_krw: price, source_site: 'A', category_name: '굴삭기', ...extra}));
const analyze = (input, filters = {}) => analyzePriceMarkets(input, filters, now);
const pair = (data, country, model = 'CAT320') => data.pairs.find(item => item.country === country && item.model === model);

test('exact model-year matching avoids a misleading age-composition reversal', () => {
  const input = [...rows('한국', 'CAT320', 2000, 20000000, 30), ...rows('한국', 'CAT320', 2020, 80000000),
    ...rows('미국', 'CAT320', 2000, 10000000), ...rows('미국', 'CAT320', 2020, 40000000, 30)];
  assert.ok(quantile(input.filter(r => r.country === '한국').map(r => r.price_krw), .5) < quantile(input.filter(r => r.country === '미국').map(r => r.price_krw), .5));
  const result = analyze(input);
  assert.equal(pair(result, '한국').gapPercent, 100);
  assert.equal(pair(result, '미국').gapPercent, -50);
  assert.equal(result.coverage.comparedCount, input.length);
});
test('benchmark excludes target and weights reference countries equally', () => {
  const result = analyze([...rows('한국', 'CAT320', 2020, 20000000), ...rows('미국', 'CAT320', 2020, 40000000, 90), ...rows('영국', 'CAT320', 2020, 80000000)]);
  const target = pair(result, '한국');
  assert.equal(target.years[0].referenceMedian, 60000000);
  assert.equal(target.gapPercent, -66.7);
  assert.equal(target.referenceCount, 93);
  assert.equal(target.referenceCountryCount, 2);
  assert.equal(target.years[0].referenceCountries.some(r => r.country === '한국'), false);
});
test('country aggregation weights models equally and flags narrow coverage', () => {
  const input = ['CAT320', 'CAT330', 'CAT340'].flatMap((model, i) => [...rows('한국', model, 2020, [80000000, 20000000, 20000000][i], i === 0 ? 100 : 3), ...rows('미국', model, 2020, 40000000)]);
  const result = analyze(input);
  const country = result.countries.find(r => r.country === '한국');
  assert.equal(country.gapPercent, -50); assert.equal(country.cheapModelCount, 2); assert.equal(country.broadEnough, true);
  assert.equal(analyze(input, {minSample: 5}).countries.length, 0);
  assert.equal(analyze(input.filter(r => r.model_norm === 'CAT320')).countries[0].broadEnough, false);
});
test('single countries, unmatched years, variants and sparse reference countries never match', () => {
  const input = [...rows('한국', 'CAT320', 2020, 20000000), ...rows('미국', 'CAT320', 2019, 40000000),
    ...rows('영국', 'CAT320D', 2020, 40000000), ...rows('독일', 'CAT320', 2020, 40000000, 2)];
  assert.equal(analyze(input).pairs.length, 0);
});
test('invalid price/model/country/year rows are excluded without inventing matches', () => {
  const input = [...rows('한국', 'CAT320', 2020, 20000000), ...rows('미국', 'CAT320', 2020, 40000000),
    ...rows('한국', '', 2020, 20000000), ...rows('국가 미상', 'CAT320', 2020, 20000000),
    ...rows('한국', 'CAT320', 2030, 20000000), ...rows('한국', 'CAT320', '', 20000000),
    ...rows('한국', 'CAT320', 2020, 9000000), ...rows('한국', 'CAT320', 2020, null), ...rows('한국', 'CAT320', 2020, 'invalid')];
  const result = analyze(input);
  assert.equal(result.coverage.comparedCount, 6);
  assert.equal(result.coverage.missingModelCount, 3); assert.equal(result.coverage.missingCountryCount, 3);
  assert.equal(result.coverage.missingYearCount, 6); assert.equal(result.coverage.totalStored, 18);
  assert.equal(pair(result, '한국').yearCount, 1);
});
test('minimum matched years and year/source/category filters apply to both sides', () => {
  const input = [2019, 2020].flatMap(year => [...rows('한국', 'CAT320', year, 20000000), ...rows('미국', 'CAT320', year, 40000000, 3, {source_site: 'B'})]);
  assert.equal(analyze(input, {minYears: 2}).pairs.length, 2);
  assert.equal(analyze(input, {minYears: 3}).pairs.length, 0);
  assert.equal(analyze(input, {yearFrom: '2020'}).pairs[0].yearCount, 1);
  assert.equal(analyze(input, {yearTo: '2018'}).pairs.length, 0);
  assert.equal(analyze(input, {source: 'A'}).pairs.length, 0);
  assert.equal(analyze(input, {category: '지게차'}).pairs.length, 0);
  assert.equal(analyze(input, {minSample: '1'}).filters.minSample, 3);
  assert.equal(analyze(input, {country: '한국'}).pairs.length, 2, 'UI focus cannot change benchmark');
});
test('rank at most 30 models and include all eligible countries, not just top eight', () => {
  const input = Array.from({length: 32}, (_, i) => Array.from({length: 10}, (_, c) => rows(`C${c}`, `M${String(i).padStart(2, '0')}`, 2020, 20000000 + c * 1000000)).flat()).flat();
  const result = analyze(input);
  assert.equal(result.models.length, 30); assert.equal(result.models[29].model, 'M29');
  assert.equal(result.countries.length, 10); assert.equal(result.pairs.length, 300);
  assert.equal(JSON.stringify(result).includes('M31'), false);
});
test('matched years have equal weight and robust medians ignore one extreme listing', () => {
  const input = [...rows('한국', 'CAT320', 2020, 20000000, 30), ...rows('미국', 'CAT320', 2020, 40000000),
    ...rows('한국', 'CAT320', 2021, 80000000), ...rows('미국', 'CAT320', 2021, 40000000), ...rows('한국', 'CAT320', 2020, 999999999, 1)];
  const target = pair(analyze(input), '한국');
  assert.equal(target.years[0].median, 20000000); assert.equal(target.gapPercent, 25); assert.equal(target.cheapYearPercent, 50);
});
test('empty input returns a complete finite response', () => {
  const result = analyze([]);
  assert.deepEqual(result.pairs, []); assert.deepEqual(result.countries, []);
  assert.equal(result.coverage.comparedCount, 0); assert.equal(result.models.length, 0);
  assert.doesNotMatch(JSON.stringify(result), /NaN|Infinity/);
});
