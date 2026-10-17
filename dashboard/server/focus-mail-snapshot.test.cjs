const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {createRequire}=require('node:module');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{transformSync}=require('esbuild');
const {mailSnapshot,ensureMailSnapshotColumn,registerFocusScan}=require('./focus-scan.cjs');

test('snapshot API allowlist keeps saved data and excludes raw metadata',()=>{
  const value={version:1,captured_at:'2026-10-17T19:00:00+09:00',model_name:'EW145B',contact:'010-0000-0000',contact_status:'available',price:'3,000만원',seller:'판매자',raw:{secret:'excluded'}};
  for(const input of [value,JSON.stringify(value)]){
    const result=mailSnapshot(input);
    assert.equal(result.contact,value.contact);assert.equal(result.model_name,value.model_name);
    assert.equal(result.price,value.price);assert.equal(result.captured_at,value.captured_at);
    assert.ok(!('raw' in result));assert.ok(!JSON.stringify(result).includes('excluded'));
  }
});
test('legacy, malformed, and unsupported snapshots stay nullable',()=>{
  for(const value of [null,undefined,'bad JSON','null','[]',[],{},true,1,{version:2}])assert.equal(mailSnapshot(value),null);
});
test('non-text fields and unknown contact outcomes are safe',()=>{
  const value=mailSnapshot({version:1,model_name:{},contact:[],price:true,contact_status:'__proto__'});
  assert.equal(value.contact,null);assert.equal(value.model_name,null);assert.equal(value.price,null);
  assert.equal(value.contact_status,'unavailable');
});
test('schema migration is additive and skipped when column exists',async()=>{
  const calls=[];await ensureMailSnapshotColumn({query:async sql=>{calls.push(sql);return [[{Field:'listing_snapshot_json'}]]}});
  assert.equal(calls.length,1);assert.match(calls[0],/SHOW COLUMNS/);
});
test('schema migration adds nullable JSON only once',async()=>{
  const calls=[];await ensureMailSnapshotColumn({query:async sql=>{calls.push(sql);return [[]]}});
  assert.equal(calls.length,2);assert.equal(calls[1],'ALTER TABLE focus_mail_history ADD COLUMN listing_snapshot_json JSON NULL');
});
test('schema migration tolerates duplicate-column races but rejects other failures',async()=>{
  for(const error of [{code:'ER_DUP_FIELDNAME'},{errno:1060}])await ensureMailSnapshotColumn({query:async sql=>{if(sql.startsWith('ALTER'))throw error;return [[]]}});
  await assert.rejects(ensureMailSnapshotColumn({query:async sql=>{if(sql.startsWith('ALTER'))throw Error('denied');return [[]]}}),/denied/);
});
test('mail history API serves legacy and new records together without raw JSON',async()=>{
  const routes={},queries=[],saved={version:1,model_name:'EW145B',contact:'010-0000-0000',contact_status:'available'};
  const app=Object.fromEntries(['get','put','post','patch','delete'].map(method=>[method,(route,handler)=>{routes[method+' '+route]=handler}]));
  const pool={query:async(sql,args)=>{
    queries.push([sql,args]);
    if(sql.startsWith('SHOW COLUMNS'))return [[{Field:'listing_snapshot_json'}]];
    if(sql.startsWith('SHOW TABLES'))return [[]];
    if(sql.startsWith('SELECT name FROM focus_migrations'))return [[{name:'legacy-rules-imported'}]];
    if(sql.startsWith('SELECT COUNT(*) total'))return [[{total:2}]];
    if(sql.startsWith('SELECT id,rule_id,recipient'))return [[{id:2,condition_json:'{}',listing_snapshot_json:JSON.stringify(saved)},{id:1,condition_json:{},listing_snapshot_json:null}]];
    return [[]];
  }};
  registerFocusScan(app,()=>pool);
  let payload;const res={set(){return this},status(code){throw Error('unexpected HTTP '+code)},json(value){payload=JSON.parse(JSON.stringify(value))}};
  await routes['get /api/focus-mail-history']({query:{page:'1',q:'EW'}},res);
  assert.equal(payload.total,2);assert.equal(payload.rows[0].listing_snapshot.contact,saved.contact);
  assert.equal(payload.rows[1].listing_snapshot,null);assert.ok(!('listing_snapshot_json' in payload.rows[0]));
  assert.ok(queries.some(([sql])=>sql.includes("WHERE status='sent'")));
});

const file=path.resolve(__dirname,'../src/MailListingSnapshot.jsx');
const compiled=transformSync(fs.readFileSync(file,'utf8'),{loader:'jsx',jsx:'automatic',format:'cjs'}).code;
const context={exports:{}};vm.runInNewContext(compiled,{module:context,exports:context.exports,require:createRequire(file)});
const Snapshot=context.exports.default,render=snapshot=>renderToStaticMarkup(React.createElement(Snapshot,{snapshot}));
test('snapshot view renders saved contact and core listing fields',()=>{
  const html=render({version:1,contact:'010-0000-0000',model_name:'EW145B',price:'3,000만원',manufactured_ym:'20.05',seller:'판매자',captured_at:'2026-10-17T19:00:00+09:00'});
  for(const text of ['010-0000-0000','EW145B','3,000만원','20.05','판매자','2026-10-17T19:00:00+09:00'])assert.ok(html.includes(text));
  assert.match(html,/<details>/);assert.match(html,/발송 당시 매물 주요정보/);
});
test('snapshot view clearly labels legacy rows',()=>{
  for(const value of [null,undefined,{},[],{version:2}])assert.match(render(value),/이전 기록: 상세정보·연락처 스냅샷이 없습니다/);
});
test('snapshot view distinguishes missing and failed contact collection',()=>{
  assert.match(render({version:1,contact_status:'missing'}),/매물 상세페이지에 연락처가 없습니다/);
  assert.match(render({version:1,contact_status:'fetch_failed'}),/상세 조회 실패/);
});
test('snapshot view ignores prototype properties as contact status',()=>{
  for(const contact_status of ['__proto__','constructor','toString',{},null])assert.match(render({version:1,contact_status}),/연락처를 확인할 수 없습니다/);
});
test('snapshot view escapes untrusted listing content',()=>{
  const html=render({version:1,contact:'<script>alert(1)</script>',description:'<img src=x onerror=alert(1)>',model_name:'<b>unsafe</b>'});
  assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img'));
  assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;b&gt;unsafe/);
});
