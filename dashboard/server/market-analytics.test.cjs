const test = require('node:test');
const assert = require('node:assert/strict');
const {analyzeMarket,quantile} = require('./market-analytics.cjs');
const now = Date.parse('2026-09-20T03:00:00Z');
const row=(id,country,model,price=20000000,days=5)=>({id,country,model_norm:model,price_krw:price,source_site:'Mascus Global',category_name:'Excavators',manufactured_ym:'2020',posted_at:new Date(now-days*86400000).toISOString()});
test('median and IQR avoid mean distortion',()=>{assert.equal(quantile([10,20,30,1000],.5),25);assert.equal(quantile([],.5),null);});
test('scope filters and minimum samples apply to ranked pairs',()=>{
  const rows=[row(1,'미국','CAT320'),row(2,'미국','CAT320'),row(3,'독일','CAT320',30000000),row(4,'미국','',20000000),row(5,'미국','CAT330',20000000,500),row(6,'미국','CAT320',9000000)];
  const data=analyzeMarket(rows,{minSample:3},now);
  assert.equal(data.summary.count,4);assert.equal(data.ranking.length,0);assert.equal(data.summary.missingModelCount,1);
  assert.equal(data.coverage.excludedByPeriod,1);assert.equal(data.coverage.demandMeasured,false);
});
test('country filter keeps same-model cross-country price comparison',()=>{
  const rows=[...Array.from({length:5},(_,i)=>row(i,'미국','CAT320',20000000)),...Array.from({length:5},(_,i)=>row(10+i,'독일','CAT320',30000000))];
  const data=analyzeMarket(rows,{country:'미국',model:'CAT320',minSample:5},now);
  assert.equal(data.summary.count,5);assert.equal(data.priceComparison.length,2);assert.equal(data.ranking[0].pricePremiumPercent,-33);
  assert.equal(data.ranking[0].referenceCount,5);assert.equal(data.ranking[0].concentration,1);
});
test('missing dates can contribute to inventory but never registration trend',()=>{
  const data=analyzeMarket([row(1,'미국','CAT320'),{...row(2,'미국','CAT320'),posted_at:null}],{minSample:1},now);
  assert.equal(data.summary.growthPercent,null);assert.equal(data.summary.count,2);assert.equal(data.coverage.missingDateCount,1);
  assert.equal(data.summary.undatedCount,1);assert.equal(data.summary.recent,1);
  assert.equal(data.examples.find(r=>r.id===2).postedDate,null);
  assert.ok(data.trend.some(r=>r.count===0));assert.equal(data.trend.reduce((n,r)=>n+r.count,0),1);
});
test('explicit date-only filter excludes unknown dates',()=>{
  const data=analyzeMarket([row(1,'미국','CAT320'),{...row(2,'미국','CAT320'),posted_at:null}],{minSample:1,includeUndated:'0'},now);
  assert.equal(data.summary.count,1);assert.equal(data.coverage.includedUndatedCount,0);
});
test('unknown model still appears in country coverage and source examples',()=>{
  const data=analyzeMarket([{...row(1,'미국',''),model_name:'TL1255D',posted_at:null}],{minSample:1},now);
  assert.equal(data.summary.countryCount,1);assert.equal(data.summary.modelCount,0);
  assert.equal(data.examples[0].model,'TL1255D');assert.equal(data.examples[0].modelNormalized,false);
  assert.equal(data.ranking.length,0);
});
test('year and source filter operate before concentration denominator',()=>{
  const data=analyzeMarket([row(1,'미국','CAT320'),{...row(2,'독일','CAT320'),manufactured_ym:'2010'}],{minSample:1,yearFrom:'2019'},now);
  assert.equal(data.summary.count,1);assert.equal(data.ranking[0].pricePremiumPercent,null);
});
