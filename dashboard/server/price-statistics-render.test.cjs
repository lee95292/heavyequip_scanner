const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const {createRequire} = require('node:module');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const {transformSync} = require('esbuild');
const {analyzePriceMarkets} = require('./price-statistics.cjs');
const file = path.resolve(__dirname, '../src/MarketAnalytics.jsx');
const compiled = transformSync(fs.readFileSync(file, 'utf8').replace(/import '\.\/market-analytics.css';/, ''), {loader: 'jsx', jsx: 'automatic', format: 'cjs'}).code;
const context = {exports: {}};
vm.runInNewContext(compiled, {module: context, exports: context.exports, require: createRequire(file)});
const Page = context.exports.default, Content = context.exports.PriceAnalysisContent;
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const input = ['CAT320', 'CAT330', 'CAT340'].flatMap(model => ['한국', '미국'].flatMap(country => [2020, 2021].flatMap(year => Array.from({length: 3}, () => ({model_norm: model, country, manufactured_ym: String(year), price_krw: country === '한국' ? 20000000 : 40000000, source_site: 'A'})))));
const data = analyzePriceMarkets(input);
test('initial page renders safely before request resolves', () => {
  const html = render(Page, {});
  assert.match(html, /동일 모델·연식의 국가별 가격 차이를 계산/); assert.match(html, /어디서, 어떤 모델/);
});
test('price-only sections render data, chart and exact benchmark without legacy activity sections', () => {
  const html = render(Content, {data, focus: '', selection: '', onSelect() {}, onFocus() {}});
  for (const text of ['어느 국가가 전반적으로', '특히 저렴한 모델', '국가 × 모델 가격차 지도', '타국 기준가격', '-50.0%', '2,000만원', '4,000만원', '<svg']) assert.ok(html.includes(text), text);
  for (const text of ['등록 흐름', '모델 집중도', '최근 30일 등록', '수요 탐색을 위한 대리지표', '등록월별']) assert.ok(!html.includes(text), text);
  assert.doesNotMatch(html, /NaN|Infinity|undefined/);
});
test('country focus keeps benchmark and limits selected model options to focused country', () => {
  const html = render(Content, {data, focus: '미국', selection: '', onSelect() {}, onFocus() {}});
  assert.match(html, /미국 · CAT320/); assert.match(html, /\+100.0%/);
  assert.match(html, /한국 2,000만원/); assert.match(html, /저렴한 국가·모델 조합이 없습니다/);
});
test('empty and narrow comparisons explicitly withhold country-wide conclusions', () => {
  const empty = render(Content, {data: analyzePriceMarkets([]), focus: '', onSelect() {}, onFocus() {}});
  assert.match(empty, /종합 판단 보류/); assert.match(empty, /표본이 부족합니다/);
  const narrow = render(Content, {data: analyzePriceMarkets(input.filter(row => row.model_norm === 'CAT320')), focus: '', onSelect() {}, onFocus() {}});
  assert.match(narrow, /종합 판단 제외/); assert.match(narrow, /종합 판단 보류/);
});
