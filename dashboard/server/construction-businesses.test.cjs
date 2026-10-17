const test=require('node:test');
const assert=require('node:assert/strict');
const {normalize,parseResponse,filters}=require('./construction-businesses.cjs');
const example={bplcNm:'예시사업자',lctnRoadNmAddr:'경기도 부천시 테스트로 1',bizKndNm:'대여업',regNo:'123',insttCode:'3860000',dataCrtrYmd:'2026-06-30'};
test('actual camel-case fields map to all source columns',()=>{
 const row=normalize(example);assert.equal(row.name,'예시사업자');assert.equal(row.provider_code,'3860000');assert.equal(row.region,'경기도');assert.equal(row.reference_date,'2026-06-30');
 assert.deepEqual(JSON.parse(row.raw_json),example);
});
test('registration identity survives address and phone updates',()=>{
 assert.equal(normalize(example).id,normalize({...example,lctnRoadNmAddr:'서울특별시 새 주소',rprsTelno:'123'}).id);
 assert.notEqual(normalize(example).id,normalize({...example,insttCode:'999'}).id);
});
test('fallback identity distinguishes location and registration type',()=>{
 const row={...example,regNo:''};assert.notEqual(normalize(row).id,normalize({...row,regKndSeNm:'법인'}).id);
 assert.notEqual(normalize(row).id,normalize({...row,lctnRoadNmAddr:'다른 주소'}).id);
 assert.equal(normalize(row).id,normalize({...row,dataCrtrYmd:'2026-10-12'}).id);
 assert.notEqual(normalize(row).id,normalize({...row,regYmd:'2020-01-01'}).id);
});
test('actual root response and wrapped legacy formats supported',()=>{
 const p={header:{resultCode:'00'},body:{items:{item:[example]},totalCount:1}};
 assert.equal(parseResponse(p).items.length,1);assert.equal(parseResponse({response:p}).total,1);
});
test('auth error, invalid count, and missing record name fail closed',()=>{
 assert.throws(()=>parseResponse({OpenAPI_ServiceResponse:{}}));
 assert.throws(()=>parseResponse({header:{resultCode:'00'},body:{items:[]}}));
 assert.throws(()=>normalize({}));
});
test('literal SQL wildcard filtering and parameter binding',()=>{
 const q=filters({q:'a%_!',region:"' OR 1=1",business_type:'대여업'});
 assert.ok(!q.where.includes('OR 1=1'));assert.equal(q.values[0],"' OR 1=1");assert.equal(q.values[2],'%a!%!_!!%');
});
