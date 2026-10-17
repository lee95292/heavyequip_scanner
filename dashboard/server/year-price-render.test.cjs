const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {createRequire}=require('node:module');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const {transformSync}=require('esbuild');
const file=path.resolve(__dirname,'../src/YearPriceExplorer.jsx');
const source=fs.readFileSync(file,'utf8').replace(/import '\.\/year-price.css';/, '');
const compiled=transformSync(source,{loader:'jsx',jsx:'automatic',format:'cjs'}).code;
const moduleContext={exports:{}};
vm.runInNewContext(compiled,{module:moduleContext,exports:moduleContext.exports,require:createRequire(file)});
const Explorer=moduleContext.exports.default;
test('mobile year ticks stay evenly spaced even when observations cluster',()=>{
  assert.deepEqual(Array.from(moduleContext.exports.yearTicks([1975,1977,2019,2020,2021,2024,2026],332)),[1975,2001,2026]);
  assert.deepEqual(Array.from(moduleContext.exports.yearTicks([2020],332)),[2020]);
  assert.deepEqual(Array.from(moduleContext.exports.yearTicks([],332)),[]);
});
test('price explorer renders loading, error and empty states before API response',()=>{
  assert.match(renderToStaticMarkup(React.createElement(Explorer,{loading:true})),/분석하고 있습니다/);
  assert.match(renderToStaticMarkup(React.createElement(Explorer,{error:'TEST_ERROR'})),/TEST_ERROR/);
  assert.match(renderToStaticMarkup(React.createElement(Explorer,{data:{models:[]}})),/확인된 매물이 없습니다/);
});
test('price explorer renders initial model and manufacture-year comparison',()=>{
  const data={models:[{model:'3CX',rank:1,count:3,usableCount:3,missingYearCount:0,countryCount:1,countries:[{country:'영국',count:3,cells:[{year:2020,count:3,median:30000000,q1:25000000,q3:40000000,sourceCount:1}]}]}]};
  const html=renderToStaticMarkup(React.createElement(Explorer,{data}));
  assert.match(html,/3CX · 2020년식/);assert.match(html,/국가 간 비교는 아직/);assert.match(html,/3,000만원/);
});
