#!/usr/bin/env python3
"""Build the read-only scanner catalog from a hash-verified frozen export.
No network calls. No raw source, filename, or caller path is served by the API.
"""
import argparse, collections, gzip, hashlib, json, math, os, re, shutil, tempfile
from pathlib import Path
from urllib.parse import urlparse
VERSION = 1
FACETS = {
 'operating_weight_kg': {'label':'운전 중량','unit':'kg'},
 'engine_power_kw': {'label':'엔진 출력','unit':'kW'},
 'rated_payload_kg': {'label':'정격 적재량','unit':'kg'},
 'bucket_capacity_m3': {'label':'버킷 용량','unit':'m³'},
 'max_digging_depth_mm': {'label':'최대 굴착 깊이','unit':'mm'},
 'max_reach_mm': {'label':'최대 도달 거리','unit':'mm'},
 'travel_speed_kmh': {'label':'주행 속도','unit':'km/h'},
 'overall_length_mm': {'label':'전장','unit':'mm'},
 'overall_width_mm': {'label':'전폭','unit':'mm'},
 'overall_height_mm': {'label':'전고','unit':'mm'},
 'ground_clearance_mm': {'label':'최저 지상고','unit':'mm'},
 'bucket_digging_force_kn': {'label':'버킷 굴착력','unit':'kN'},
 'arm_digging_force_kn': {'label':'암 굴착력','unit':'kN'},
 'rated_operating_capacity_kg': {'label':'정격 작업 용량','unit':'kg'},
 'blade_width_mm': {'label':'블레이드 폭','unit':'mm'},
 'drum_width_mm': {'label':'다짐 드럼 폭','unit':'mm'},
 'turning_radius_mm': {'label':'최소 회전반경','unit':'mm'},

}
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def safe_path(root, rel):
 p=(root/rel).resolve()
 if not p.is_relative_to(root.resolve()) or not p.is_file():raise ValueError('Invalid snapshot path: '+str(rel))
 return p
def dumps(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def text(v):return '' if v is None else v if isinstance(v,str) else dumps(v)
def safe_url(s):
 if not isinstance(s,str) or len(s)>4000:return None
 try:
  u=urlparse(s)
  return s if u.scheme in ('https','http') and u.hostname and not u.username and not u.password else None
 except ValueError:return None

def numeric_range(raw):
 # Deliberately reject inequalities, formulas, notes, unknowns and ambiguous decimal formats.
 if isinstance(raw,bool) or raw is None:return None
 if isinstance(raw,(int,float)):
  return [raw,raw] if math.isfinite(raw) and raw>=0 else None
 s=str(raw).strip().replace('\u00a0',' ').replace('−','-')
 s=re.sub(r'^(?:approx\.?|approximately|maximum|max\.?|minimum|min\.?)\s*','',s,flags=re.I)
 s=re.sub(r'(?<=\d)\s(?=\d{3}(?:\D|$))','',s)
 def n(s):
  s=s.strip()
  if re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?',s):s=s.replace(',','')
  elif ',' in s:return None
  if not re.fullmatch(r'\d+(?:\.\d+)?',s):return None
  # A 3-digit decimal in large weight-style numbers can be a thousands mark.
  if re.fullmatch(r'\d{3,}\.\d{3}',s):return None
  return float(s)
 parts=re.split(r'\s*(?:–|—|\bto\b| - |(?<=\d)-(?=\d))\s*',s)
 if len(parts)>2:return None
 vals=[n(v) for v in parts]
 if any(v is None or not math.isfinite(v) for v in vals):return None
 if len(vals)==2 and vals[0]>vals[1]:return None
 return [min(vals),max(vals)]

def numeric_facet(f, assembly=False):
 if assembly or f.get('applicable_to_record_model') is False:return None
 a=text(f.get('attribute')).lower().replace('_',' ')
 cat=text(f.get('category')).lower(); cfg=text(f.get('configuration')).lower()
 if re.search(r'uncertain|ocr|suspect|incorrect|pending|source_conflict|source_unit_conflict|reference_ambiguity|source_blank',text(f.get('verification')),re.I):return None
 if (f.get('original_fact') or {}).get('conflict_ids'):return None
 key=None;power_type=None
 if re.search(r'operating (weight|mass)',a) and not re.search(r'change|increment|difference|axle|tipping|at operating|shipping|transport|additional|increase|decrease|ballast weight',a):key='operating_weight_kg'
 elif 'power' in a and re.search(r'engine|net|gross|rated',a+' '+cat) and not re.search(r'hydraulic|pump|motor|charger|battery|auxiliary|fan power|speed|torque',a+' '+cat):
  key='engine_power_kw';power_type='net' if 'net' in a else 'gross' if 'gross' in a else 'rated' if 'rated' in a else 'unspecified'
 elif re.search(r'(rated|nominal).*payload|payload.*(rated|nominal)',a):key='rated_payload_kg'
 elif 'bucket' in a and 'capacity' in a and not re.search(r'change|increment|reference|label',a):key='bucket_capacity_m3'
 elif re.search(r'(maximum|max\.?).*digging depth|digging depth.*(?:maximum|max\.)',a) and not re.search(r'vertical|wall|level cut|segment|2[.,]44|2440',a):key='max_digging_depth_mm'
 elif re.search(r'(maximum|max\.?).*(digging reach|reach at ground|ground.level reach)|maximum reach$',a) and not re.search(r'hook|height|arms|tool',a):key='max_reach_mm'
 elif re.search(r'travel speed|maximum.*speed',a) and not re.search(r'swing|engine|rotational|fan|wind',a):key='travel_speed_kmh'
 if not key:
  rules=[('overall_length_mm',r'^(?:overall|transport|shipping) length(?:\s*\([^)]*\))?[*†]?$'),('overall_width_mm',r'^(?:overall|transport|shipping) width(?:\s*\([^)]*\))?[*†]?$'),('overall_height_mm',r'^(?:overall|transport|shipping) height(?:\s*\([^)]*\))?[*†]?$'),('ground_clearance_mm',r'^(?:minimum |min\.? )?ground clearance[*†]?$'),('bucket_digging_force_kn',r'^(?:maximum |max\.? )?bucket (?:digging|breakout) force(?:\s*\([^)]*\))?$'),('arm_digging_force_kn',r'^(?:maximum |max\.? )?(?:arm|stick) (?:digging|crowd) force(?:\s*\([^)]*\))?$'),('rated_operating_capacity_kg',r'^rated operating capacity(?:\s*\([^)]*\))?$'),('blade_width_mm',r'^(?:blade (?:width|length)|length of blade)$'),('drum_width_mm',r'^(?:drum width|width of drum)$'),('turning_radius_mm',r'^(?:minimum|min\.?) turning radius$')]
  key=next((k for k,r in rules if re.search(r,a)),None)
 if not key:return None
 # Attachment tables describe implements, not the complete machine envelope.
 if key in {'overall_length_mm','overall_width_mm','overall_height_mm','ground_clearance_mm','turning_radius_mm'} and re.search(r'^attachment:|bucket operating matrix|fork.*carriage|attachment dimensions',cat):return None
 unit=text(f.get('unit')).lower().strip().replace(' ','').replace('³','3')
 factors={
 'operating_weight_kg':{'kg':1,'t':1000,'tonne':1000,'tonnes':1000,'lb':0.45359237,'lbs':0.45359237},
 'rated_payload_kg':{'kg':1,'t':1000,'tonne':1000,'tonnes':1000,'lb':0.45359237,'lbs':0.45359237},
 'engine_power_kw':{'kw':1,'hp':0.745699872,'hp(metric)':0.73549875,'mhp(ps)':0.73549875,'ps':0.73549875},
 'bucket_capacity_m3':{'m3':1,'yd3':0.764554858},
 'max_digging_depth_mm':{'mm':1,'m':1000,'cm':10,'in':25.4,'ft':304.8},
 'max_reach_mm':{'mm':1,'m':1000,'cm':10,'in':25.4,'ft':304.8},
 'travel_speed_kmh':{'km/h':1,'km/hr':1,'kmh':1,'kph':1,'mph':1.609344},
 }
 for k in FACETS:
  if k in factors:continue
  u=FACETS[k]['unit'];factors[k]={'mm':1,'cm':10,'m':1000,'in':25.4,'in.':25.4,'ft':304.8} if u=='mm' else {'kg':1,'t':1000,'lb':0.45359237,'lbs':0.45359237} if u=='kg' else {'kn':1,'n':0.001,'lbf':0.004448221615}
 if unit not in factors[key]:return None
 vals=numeric_range(f.get('value'))
 if not vals:return None
 vals=[round(v*factors[key][unit],6) for v in vals]
 if vals[1]<=0:return None
 return key,{'min':vals[0],'max':vals[1],'fact_id':f.get('fact_id'),'power_type':power_type}

def category(meta, raw):
 sources=raw.get('sources') or []
 label=text(raw.get('category') or raw.get('equipment_category') or raw.get('equipment_type'))
 if not label:label=next((text(s.get('category')) for s in sources if isinstance(s,dict) and s.get('category')),'')
 hints=' '.join([label]+[text(s.get(k)) for s in sources if isinstance(s,dict) for k in ['title','source_page','source_url','official_page','source_pages']]).lower().replace('_',' ').replace('-',' ')
 name=meta['model_name'].lower()
 assembly=bool(re.search(r'undercarriage|frontless|screed plate',name))
 if assembly:return '구성품·어셈블리',label or 'Assembly / component',True
 rules=[('백호 로더',r'backhoe'),('스키드·컴팩트 트랙 로더',r'skid steer|compact track loader|compact utility loader'),('휠 로더',r'wheel loader'),('트랙 로더',r'track loader'),('모터 그레이더',r'grader'),('스크레이퍼',r'scraper'),('다짐 장비',r'compactor|roller'),('아스팔트 포장·절삭 장비',r'paver|planer|reclaimer|screed|asphalt finisher'),('텔레핸들러',r'telehandler'),('파이프레이어',r'pipelayer'),('머티리얼 핸들러·임업 장비',r'material handl|forest machine'),('광산·지하 장비',r'underground|load haul dump|drill'),('덤프·운반 장비',r'truck|hauler'),('도저',r'dozer|bulldozer'),('굴착기',r'excavator|shovel|dragline'),('파쇄 장비',r'crusher')]
 for title,regex in rules:
  if re.search(regex,hints):return title,label or title,False
 return '기타·분류 확인 중',label or 'Unspecified',False

def sources(raw):
 out=[]
 for i,s in enumerate(raw.get('sources') or []):
  if not isinstance(s,dict):continue
  z={k:v for k,v in s.items() if k not in {'filename','file_cache','local_path','path','size','content_type','purpose','status'}}
  z['source_id']=s.get('source_id') or s.get('id') or s.get('document_id') or 'S'+str(i+1)
  z['url']=next((safe_url(s.get(k)) for k in ['verified_download_url','download_url','verified_final_url','source_url','source_page','official_page','url'] if safe_url(s.get(k))),None)
  z['product_url']=next((safe_url(s.get(k)) for k in ['source_url','source_page','official_page','verified_final_url','url'] if safe_url(s.get(k))),None)
  z['region']=s.get('market') or s.get('region') or s.get('source_language') or s.get('language') or raw.get('language') or '원문 참조'
  out.append(z)
 return out

def fragments(record):
 # Preserve complete structured text. Individual output fragments are bounded.
 s=json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)
 return [s[i:i+12000] for i in range(0,len(s),12000)] or ['']

def build(src,out):
 src=src.resolve();out=out.resolve()
 manifest_path=src/'SNAPSHOT_MANIFEST.json'; manifest=json.load(open(manifest_path));mh=digest(manifest_path)
 files={x['path']:x for x in manifest['files']}
 idx_path=safe_path(src,'model_index.json');index=json.load(open(idx_path))
 # Verify every file that feeds this import before any publication; aggregate-only
 # manifest is insufficient because category/source metadata lives per model.
 needed={'model_index.json','facts_canonical.jsonl','structured_records.jsonl','EXPORT_MANIFEST.json','SCHEMA.md'}|{m['data_path'] for m in index['models']}
 for rel in sorted(needed):
  p=safe_path(src,rel);expected=files.get(rel)
  if not expected or p.stat().st_size!=expected['bytes'] or digest(p)!=expected['sha256']:raise ValueError('Snapshot hash mismatch: '+rel)
 if len(index['models'])!=manifest['model_records']:raise ValueError('Snapshot record count mismatch')
 if out.exists():raise ValueError('Output already exists; use a new snapshot directory')
 out.parent.mkdir(parents=True,exist_ok=True)
 temp=Path(tempfile.mkdtemp(prefix='.specifications-',dir=out.parent));parts=temp/'parts';parts.mkdir();models={};summaries=[]
 try:
  for m in index['models']:
   rid=hashlib.sha256((m['manufacturer']+'\0'+m['markdown_path']).encode()).hexdigest()[:24]
   key=(m['manufacturer'],m['markdown_path'])
   if key in models:raise ValueError('Duplicate model identity')
   raw=json.load(open(src/m['data_path']));cat,raw_cat,assembly=category(m,raw)
   summary={k:m.get(k) for k in ['manufacturer','model_name','record_kind','base_model','quality_stage','semantic_completeness','updated_at','fact_count','equipment_count','table_count','source_count']}
   summary.update({'id':rid,'category':cat,'original_category':raw_cat,'is_assembly':assembly,'facets':{},'warning_count':sum(len(raw.get(k) or []) for k in ['warnings','uncertainties','conflicts'])})
   meta={**summary,'sources':sources(raw),'scope':raw.get('scope_note') or raw.get('scope') or '', 'inventory_note':raw.get('inventory_record_note') or '', 'source_metadata':{k:v for k,v in raw.items() if k in ['catalog_enrichment_status','semantic_completeness','validation','qa','model_identity','variant','market','region','emissions','revision','pending_conditions','catalog_links']}}
   models[key]={'summary':summary,'meta':meta,'sections':collections.Counter()};summaries.append(summary)
  handles={}
  def append(m,kind,obj):
   rid=m['summary']['id'];fn=rid+'.'+kind
   if fn not in handles:handles[fn]=open(parts/fn,'a',encoding='utf8')
   handles[fn].write(dumps(obj)+'\n')
  excluded=0;fact_count=0
  for line in open(src/'facts_canonical.jsonl'):
   f=json.loads(line);m=models[(f['manufacturer'],f['model_markdown'])]
   f={k:v for k,v in f.items() if k not in ['manufacturer','model_name','model_markdown','record_kind','quality_stage','semantic_completeness']}
   if f.get('applicable_to_record_model') is False:excluded+=1
   candidate=numeric_facet(f,m['summary']['is_assembly'])
   if candidate:
    key,value=candidate;m['summary']['facets'].setdefault(key,[]).append(value)
   append(m,'facts',f);fact_count+=1
  for line in open(src/'structured_records.jsonl'):
   r=json.loads(line);m=models[(r['manufacturer'],r['model_markdown'])];section=r['record_type']
   chunks=fragments(r['record'])
   for i,chunk in enumerate(chunks):append(m,'records',{'section':section,'record_id':r.get('record_id'),'record_index':r.get('record_index'),'part':i+1,'parts':len(chunks),'text':chunk})
   m['sections'][section]+=len(chunks)
  for f in handles.values():f.close()
  (temp/'models').mkdir();output_files=[]
  for m in models.values():
   rid=m['summary']['id'];detail={**m['meta'],'sections':dict(m['sections'])}
   for kind in ['facts','records']:
    p=parts/(rid+'.'+kind);detail[kind]=[json.loads(l) for l in open(p)] if p.exists() else []
   if len(detail['facts'])!=m['summary']['fact_count']:raise ValueError('Fact count mismatch: '+rid)
   # Deduplicate normalized alternatives only when fact identity is also equal.
   for key,values in m['summary']['facets'].items():
    seen=set();m['summary']['facets'][key]=[v for v in values if not (dumps(v) in seen or seen.add(dumps(v)))]
   p=temp/'models'/(rid+'.json.gz')
   with open(p,'wb') as f:
    with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as z:z.write(dumps(detail).encode())
   output_files.append({'path':'models/'+p.name,'bytes':p.stat().st_size,'sha256':digest(p)})
  summaries.sort(key=lambda x:(x['manufacturer'],x['model_name'].casefold(),x['id']))
  # Facet index stores only unique ranges/types, not every supporting fact ID.
  for m in summaries:
   for key,values in m['facets'].items():
    unique={dumps({k:v for k,v in x.items() if k!='fact_id'}) for x in values};m['facets'][key]=[json.loads(s) for s in sorted(unique)]
  payload={'schema_version':VERSION,'snapshot_id':manifest['snapshot_id'],'snapshot_sha256':mh,'built_from_updated_at':index['updated_at'],'scope':index.get('scope'),'model_count':len(summaries),'individual_model_count':index.get('individual_model_count'),'application_variant_count':index.get('application_variant_count'),'fact_count':fact_count,'excluded_reference_fact_count':excluded,'facets':FACETS,'models':summaries}
  p=temp/'index.json';p.write_text(dumps(payload));output_files.append({'path':'index.json','bytes':p.stat().st_size,'sha256':digest(p)})
  (temp/'manifest.json').write_text(dumps({'schema_version':VERSION,'snapshot_id':manifest['snapshot_id'],'snapshot_sha256':mh,'files':output_files}))
  if digest(manifest_path)!=mh:raise ValueError('Snapshot manifest changed during import')
  shutil.rmtree(parts);os.replace(temp,out)
  print(dumps({'output':str(out),'snapshot_id':manifest['snapshot_id'],'models':len(summaries),'facts':fact_count,'reference_facts_excluded':excluded,'index_bytes':p.stat().st_size if p.exists() else (out/'index.json').stat().st_size,'bytes':sum(f['bytes'] for f in output_files),'facets':{k:sum(bool(m['facets'].get(k)) for m in summaries) for k in FACETS}}))
 except BaseException:
  for f in locals().get('handles',{}).values():f.close()
  shutil.rmtree(temp,ignore_errors=True);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.snapshot,a.output)
