const {test}=require('node:test');const assert=require('node:assert/strict');
const {validateRule,validateScan}=require('./focus-scan.cjs');
const valid={model_contains:'EW145',email:'test@example.invalid',interval_minutes:10,categories:['100105'],enabled:false};
test('valid minimum fields',()=>assert.deepEqual(validateRule(valid).errors,{}));
test('free model includes not predefined choices',()=>assert.deepEqual(validateRule({...valid,model_contains:'ABC123'}).errors,{}));
for(const [field,value] of [['interval_minutes',0],['interval_minutes',1.5],['interval_minutes',1441],['interval_minutes',true],['email','x\n@y.com'],['categories',[]],['categories',['evil']],['enabled','true'],['model_contains','']]){
 test(`reject ${field} ${JSON.stringify(value)}`,()=>assert.ok((['categories','interval_minutes'].includes(field)?validateScan:validateRule)({...valid,enabled:true,[field]:value}).errors[field]));
}
test('inverted prices',()=>assert.ok(validateRule({...valid,price_min_manwon:5000,price_max_manwon:1000}).errors.price_max_manwon));
test('inverted years',()=>assert.ok(validateRule({...valid,year_min:2025,year_max:2020}).errors.year_max));
test('deduplicate categories',()=>assert.deepEqual(validateScan({...valid,categories:['100105','100105']}).value.categories,['100105']));
test('empty bounds nullable',()=>assert.equal(validateRule({...valid,price_min_manwon:''}).value.price_min_manwon,null));
test('one minute is valid',()=>assert.deepEqual(validateScan({...valid,interval_minutes:1}).errors,{}));

test('alert has no schedule or categories',()=>{const {value,errors}=validateRule({model_contains:'DX140',email:'test@example.invalid',enabled:true});assert.deepEqual(errors,{});assert.ok(!('categories' in value));assert.ok(!('interval_minutes' in value));});
test('paused common scan may be empty',()=>assert.deepEqual(validateScan({categories:[],interval_minutes:10,enabled:false}).errors,{}));
test('15 categories allowed; 16 rejected',()=>{const categories=Array.from({length:15},(_,i)=>String(100100+i));assert.deepEqual(validateScan({...valid,categories}).errors,{});assert.ok(validateScan({...valid,categories:[...categories,'100999']}).errors.categories)});
test('request delay 1-30 integer seconds',()=>{for(const v of [1,2,30])assert.deepEqual(validateScan({...valid,request_delay_seconds:v}).errors,{});for(const v of [0,31,1.5,true,''])assert.ok(validateScan({...valid,request_delay_seconds:v}).errors.request_delay_seconds)});

const {logPayload}=require('./focus-scan.cjs');
test('response payload keeps every triple and drops other fields',()=>{
  const rows=Array.from({length:9},(_,i)=>({model_name:'장비'+i,manufactured_ym:'20.05',price:'3,000만원',raw:'private',detail_url:'private'}));
  const result=logPayload(JSON.stringify(rows));
  assert.equal(result.response_rows.length,9);
  assert.deepEqual(result.response_rows[8],{model_name:'장비8',manufactured_ym:'20.05',price:'3,000만원'});
  assert.deepEqual(result.sample_names,[]);
  assert.ok(!JSON.stringify(result).includes('private'));
});
test('old name-only payload remains compatible',()=>{
  assert.deepEqual(logPayload('["DX","EW"]'),{response_rows:[],sample_names:['DX','EW']});
});
test('malformed and missing history cannot break API',()=>{
  for(const value of [null,undefined,'bad JSON','{}',4,{}]) assert.deepEqual(logPayload(value),{response_rows:[],sample_names:[]});
  assert.deepEqual(logPayload([null,[],true,{model_name:{},manufactured_ym:'',price:0}]).response_rows,
    [{model_name:null,manufactured_ym:'',price:'0'}]);
});
