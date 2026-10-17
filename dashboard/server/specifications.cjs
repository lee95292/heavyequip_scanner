'use strict';
// Authenticated, read-only catalog. Registration MUST follow requireDashboardAuth.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { promisify } = require('node:util');
const gunzip = promisify(zlib.gunzip);
const DEFAULT_ROOT = path.resolve(__dirname, '..', 'data', 'specifications');
const MAX_DETAIL_BYTES = 40 * 1024 * 1024;
const MAX_CACHE_BYTES = 60 * 1024 * 1024;
const FACET_KEYS = ['operating_weight_kg','engine_power_kw','rated_payload_kg','bucket_capacity_m3','max_digging_depth_mm','max_reach_mm','travel_speed_kmh'];
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
function problem(status, message) { const e = new Error(message); e.status = status; return e; }
function scalar(v, max = 120) { if (v == null) return ''; if (typeof v !== 'string' || v.length > max) throw problem(400,'검색 조건이 올바르지 않습니다.'); return v.trim(); }
function integer(v, fallback, max) { if (v == null || v === '') return fallback; if (typeof v !== 'string' || !/^\d+$/.test(v) || Number(v) < 1 || Number(v) > max) throw problem(400,'페이지 값이 올바르지 않습니다.'); return Number(v); }
function bound(v) { if (v == null || v === '') return null; if (typeof v !== 'string' || !/^\d+(?:\.\d+)?$/.test(v) || !Number.isFinite(Number(v)) || Number(v) > 1e10) throw problem(400,'수치 범위를 확인해 주세요.'); return Number(v); }
function publicModel(m, query) {
 const facets=Object.fromEntries(Object.entries(m.facets).map(([k,values])=>[k,[{min:Math.min(...values.map(v=>v.min)),max:Math.max(...values.map(v=>v.max)),alternatives:values.length}]]));
 const matched_facets={};for(const [key,{min,max}] of Object.entries(query.ranges)){const vals=(m.facets[key]||[]).filter(v=>(key!=='engine_power_kw'||!query.power_type||v.power_type===query.power_type)&&(min==null||v.max>=min)&&(max==null||v.min<=max));matched_facets[key]={count:vals.length,values:vals.slice(0,3)};}
 return {...m,facets,matched_facets};
}
function parseQuery(q) {
 const filters = { q: scalar(q.q).toLocaleLowerCase(), manufacturer: scalar(q.manufacturer), category: scalar(q.category), quality: scalar(q.quality), kind: scalar(q.kind), power_type: scalar(q.power_type), page: integer(q.page,1,100000), limit: integer(q.limit,24,60), ranges: {} };
 if (filters.power_type && !['net','gross','rated','unspecified'].includes(filters.power_type)) throw problem(400,'출력 종류를 확인해 주세요.');
 if (filters.kind && !['individual_model','application_variant','assembly'].includes(filters.kind)) throw problem(400,'레코드 종류를 확인해 주세요.');
 for (const k of FACET_KEYS) { const min = bound(q[k+'_min']), max = bound(q[k+'_max']); if (min != null && max != null && min > max) throw problem(400,'최솟값은 최댓값보다 클 수 없습니다.'); if (min != null || max != null) filters.ranges[k] = { min, max }; }
 return filters;
}
function matchModel(m, q) {
 if (q.q && !`${m.manufacturer} ${m.model_name} ${m.base_model || ''}`.toLocaleLowerCase().includes(q.q)) return false;
 if (q.manufacturer && m.manufacturer !== q.manufacturer || q.category && m.category !== q.category || q.quality && m.quality_stage !== q.quality) return false;
 if (q.kind && (q.kind === 'assembly' ? !m.is_assembly : m.is_assembly || m.record_kind !== q.kind)) return false;
 if (q.power_type && !(m.facets.engine_power_kw || []).some(v => v.power_type === q.power_type)) return false;
 return Object.entries(q.ranges).every(([key,{min,max}]) => (m.facets[key] || []).some(v => (key !== 'engine_power_kw' || !q.power_type || v.power_type === q.power_type) && (min == null || v.max >= min) && (max == null || v.min <= max)));
}
function aggregate(models, property) { const count = new Map(); for (const m of models) count.set(m[property],(count.get(m[property])||0)+1); return [...count].filter(([v]) => v).map(([value,count]) => ({value,count})).sort((a,b)=>a.value.localeCompare(b.value,'ko')); }
function createCatalog(root = DEFAULT_ROOT) {
 let state = null, loading = null; const cache = new Map(); let cacheBytes = 0;
 async function catalog() {
  let pointer;
  try { const p = await fs.readFile(path.join(root,'current.json'),'utf8'); if (p.length>2000) throw Error(); pointer=JSON.parse(p); } catch { throw problem(503,'제원 데이터가 아직 준비되지 않았습니다.'); }
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(pointer.snapshot_id || '') || !/^[a-f0-9]{64}$/.test(pointer.manifest_sha256 || '')) throw problem(503,'데이터 버전 확인에 실패했습니다.');
  const identity = pointer.snapshot_id+':'+pointer.manifest_sha256;
  if (state?.identity === identity) return state;
  if (loading?.identity === identity) return loading.promise;
  const promise = (async () => {
   const dir=path.join(root,pointer.snapshot_id); const manifestBytes=await fs.readFile(path.join(dir,'manifest.json'));
   if (hash(manifestBytes)!==pointer.manifest_sha256) throw problem(503,'데이터 무결성 확인에 실패했습니다.');
   const manifest=JSON.parse(manifestBytes); if(manifest.schema_version!==1 || manifest.snapshot_id!==pointer.snapshot_id) throw problem(503,'지원하지 않는 데이터 버전입니다.');
   const files=new Map(manifest.files.map(f=>[f.path,f])); const info=files.get('index.json');
   const indexBytes=await fs.readFile(path.join(dir,'index.json')); if(!info || indexBytes.length!==info.bytes || hash(indexBytes)!==info.sha256 || indexBytes.length>20*1024*1024) throw problem(503,'검색 색인 확인에 실패했습니다.');
   const index=JSON.parse(indexBytes); if(index.schema_version!==1 || index.snapshot_id!==pointer.snapshot_id || !Array.isArray(index.models)) throw problem(503,'검색 색인 형식 오류입니다.');
   const byId=new Map(index.models.map(m=>[m.id,m])); if(byId.size!==index.models.length || index.models.some(m=>!/^[a-f0-9]{24}$/.test(m.id))) throw problem(503,'모델 식별자 오류입니다.');
   const next={identity,dir,index,byId,files}; state=next;cache.clear();cacheBytes=0;return next;
  })().finally(()=>{if(loading?.identity===identity)loading=null;}); loading={identity,promise};return promise;
 }
 async function detail(s,id) {
  if(!/^[a-f0-9]{24}$/.test(id) || !s.byId.has(id))throw problem(404,'모델을 찾을 수 없습니다.');
  const key=s.identity+':'+id;
  if(cache.has(key)){const hit=cache.get(key);cache.delete(key);cache.set(key,hit);return hit.data;}
  const relative='models/'+id+'.json.gz',info=s.files.get(relative);if(!info || info.bytes>20*1024*1024)throw problem(503,'모델 데이터 확인에 실패했습니다.');
  const bytes=await fs.readFile(path.join(s.dir,relative));if(bytes.length!==info.bytes||hash(bytes)!==info.sha256)throw problem(503,'모델 데이터 무결성 오류입니다.');
  const raw=await gunzip(bytes,{maxOutputLength:MAX_DETAIL_BYTES});const data=JSON.parse(raw);if(data.id!==id)throw problem(503,'모델 식별자가 일치하지 않습니다.');
  while(cacheBytes+raw.length>MAX_CACHE_BYTES&&cache.size){const oldest=cache.keys().next().value;cacheBytes-=cache.get(oldest).bytes;cache.delete(oldest);}
  if(raw.length<=MAX_CACHE_BYTES){cache.set(key,{data,bytes:raw.length});cacheBytes+=raw.length;}return data;
 }
 async function list(query) {
  const q=parseQuery(query);const s=await catalog(),idx=s.index;
  const matched=idx.models.filter(m=>matchModel(m,q));const total=matched.length;const pages=Math.max(1,Math.ceil(total/q.limit));const page=Math.min(q.page,pages);
  // Facet availability follows manufacturer/category/search, but ignores numeric filters.
  const context=idx.models.filter(m=>matchModel(m,{...q,ranges:{},power_type:''}));
  return {snapshot_id:idx.snapshot_id,updated_at:idx.built_from_updated_at,scope:idx.scope,inventory_total:idx.model_count,individual_model_count:idx.individual_model_count,application_variant_count:idx.application_variant_count,fact_count:idx.fact_count,reference_facts_excluded:idx.excluded_reference_fact_count,total,page,pages,limit:q.limit,items:matched.slice((page-1)*q.limit,page*q.limit).map(m=>publicModel(m,q)),options:{manufacturers:aggregate(idx.models,'manufacturer'),categories:aggregate(q.manufacturer?idx.models.filter(m=>m.manufacturer===q.manufacturer):idx.models,'category'),qualities:aggregate(idx.models,'quality_stage')},facets: Object.fromEntries(FACET_KEYS.map(k=>[k,{...idx.facets[k],available:context.filter(m=>m.facets[k]?.length).length}]))};
 }
 async function model(id,query) {
  const s=await catalog();if(query.snapshot && scalar(query.snapshot,80)!==s.index.snapshot_id)throw problem(409,'데이터가 갱신되었습니다. 모델 목록을 새로고침해 주세요.');
  const d=await detail(s,id);const section=scalar(query.section || 'facts',40);const q=scalar(query.q,120).toLocaleLowerCase();const pageRequested=integer(query.page,1,100000),limit=integer(query.limit,40,60);
  if(section!=='facts' && !Object.hasOwn(d.sections,section))throw problem(400,'지원하지 않는 제원 항목입니다.');
  let rows=section==='facts'?d.facts:d.records.filter(r=>r.section===section);
  if(section==='facts'&&scalar(query.matched,1)==='1'){
   const filters=parseQuery(query),ids=new Set();
   for(const[key,values]of Object.entries(d.facets||{})){const range=filters.ranges[key];if(!range&&!(key==='engine_power_kw'&&filters.power_type))continue;for(const v of values){if(key==='engine_power_kw'&&filters.power_type&&v.power_type!==filters.power_type)continue;if(range&&((range.min!=null&&v.max<range.min)||(range.max!=null&&v.min>range.max)))continue;ids.add(v.fact_id);}}
   rows=rows.filter(f=>ids.has(f.fact_id));
  }
  if(q)rows=rows.filter(r=>JSON.stringify(r).toLocaleLowerCase().includes(q));
  const pages=Math.max(1,Math.ceil(rows.length/limit)),page=Math.min(pageRequested,pages);
  const {facts,records,facets,...metadata}=d;
  return {snapshot_id:s.index.snapshot_id,model:metadata,section,total:rows.length,page,pages,limit,rows:rows.slice((page-1)*limit,page*limit)};
 }
 return {list,model,catalog};
}
function registerSpecifications(app,options={}) {
 const service=createCatalog(options.root);
 const handle=fn=>async(req,res)=>{res.set('Cache-Control','no-store');try{res.json(await fn(req));}catch(e){const status=e.status||503;if(status>=500)console.error('[specifications]',e.code||e.message);res.status(status).json({error:e.status?e.message:'제원 데이터를 읽지 못했습니다. 잠시 후 다시 시도해 주세요.'});}};
 app.get('/api/specifications',handle(req=>service.list(req.query)));
 app.get('/api/specifications/:id',handle(req=>service.model(req.params.id,req.query)));
 return service;
}
module.exports={createCatalog,registerSpecifications,parseQuery,matchModel,FACET_KEYS};
