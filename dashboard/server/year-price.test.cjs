const test = require('node:test');
const assert = require('node:assert/strict');
const {analyzeMarket} = require('./market-analytics.cjs');
const now = Date.parse('2026-09-20T03:00:00Z');
const row=(model,country,year,price=20000000)=>({model_norm:model,country,manufactured_ym:year,price_krw:price,source_site:'source',posted_at:null});
test('three-variable cohorts compare only exact model, country and manufacture year',()=>{
  const data=analyzeMarket([row('CAT320','미국','2020',20000000),row('CAT320','미국','2020',40000000),row('CAT320','미국','2019',10000000),row('CAT320','독일','2020',60000000),row('CAT320D','미국','2020',80000000)],{},now).yearComparison;
  const model=data.models.find(m=>m.model==='CAT320');
  const cell=model.countries.find(c=>c.country==='미국').cells.find(c=>c.year===2020);
  assert.deepEqual(cell,{year:2020,count:2,median:30000000,q1:25000000,q3:35000000,sourceCount:1});
  assert.equal(model.count,4);assert.equal(model.countryCount,2);
});
test('top 30 are stable across lower-page filters and break ties deterministically',()=>{
  const rows=Array.from({length:35},(_,i)=>Array.from({length:40-i},()=>row(`M${i.toString().padStart(2,'0')}`,'독일','2020'))).flat();
  const a=analyzeMarket(rows,{},now).yearComparison;
  const b=analyzeMarket(rows,{country:'미국',model:'missing',yearFrom:'2025',source:'missing'},now).yearComparison;
  assert.deepEqual(a,b);assert.equal(a.models.length,30);assert.equal(a.models[0].count,40);assert.equal(a.models[29].model,'M29');
});
test('unknown or invalid years remain in ranking but never become chart dates',()=>{
  const rows=['',null,'0000','1940','2028','2020'].map(y=>row('3CX','영국',y));
  rows.push(row('', '영국','2020'),row('4CX','국가 미상','2020'),row('cheap','영국','2020',9000000));
  const data=analyzeMarket(rows,{},now).yearComparison;
  assert.equal(data.models.length,1);assert.equal(data.models[0].count,6);
  assert.equal(data.models[0].usableCount,1);assert.equal(data.models[0].missingYearCount,5);
  assert.deepEqual(data.models[0].countries[0].cells.map(c=>c.year),[2020]);
});
test('country cap reports omitted coverage and sparse samples remain explicit',()=>{
  const data=analyzeMarket(Array.from({length:10},(_,i)=>row('3CX',`C${i}`,'2020')),{},now).yearComparison.models[0];
  assert.equal(data.countryCount,10);assert.equal(data.countries.length,8);assert.equal(data.displayedCount,8);
  assert.equal(data.countries[0].cells[0].count,1);
});
