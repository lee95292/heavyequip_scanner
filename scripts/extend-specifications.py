#!/usr/bin/env python3
"""Derive a new immutable catalog, recomputing facets and adding reviewed official facts."""
import argparse,collections,gzip,hashlib,importlib.util,json,shutil,tempfile,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('builder',Path(__file__).with_name('build-specifications.py'));b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
def extend(root,snapshot,additions):
 pointer=json.loads((root/'current.json').read_text());old=root/pointer['snapshot_id'];mb=(old/'manifest.json').read_bytes();assert hashlib.sha256(mb).hexdigest()==pointer['manifest_sha256'];manifest=json.loads(mb)
 for f in manifest['files']:
  p=b.safe_path(old,f['path']);assert p.stat().st_size==f['bytes'] and b.digest(p)==f['sha256'],f['path']
 idx=json.loads((old/'index.json').read_text());out=root/snapshot
 if out.exists():raise ValueError('Snapshot exists')
 tmp=Path(tempfile.mkdtemp(prefix='.extend-',dir=root));(tmp/'models').mkdir();models=[];files=[]
 def emit(d):
  facets={}
  for f in d['facts']:
   v=b.numeric_facet(f,d['is_assembly'])
   if v:facets.setdefault(v[0],[]).append(v[1])
  d['facets']=facets;p=tmp/'models'/(d['id']+'.json.gz')
  with p.open('wb') as f:
   with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as z:z.write(b.dumps(d).encode())
  files.append(dict(path='models/'+p.name,bytes=p.stat().st_size,sha256=b.digest(p)))
  keys=['id','manufacturer','model_name','record_kind','base_model','quality_stage','semantic_completeness','updated_at','fact_count','equipment_count','table_count','source_count','category','original_category','is_assembly','warning_count']
  summary={k:d.get(k) for k in keys};summary['facets']={k:[json.loads(x) for x in sorted({b.dumps({a:c for a,c in v.items() if a!='fact_id'}) for v in vs})] for k,vs in facets.items()};models.append(summary)
 try:
  identities=set()
  for m in idx['models']:
   d=json.load(gzip.open(old/'models'/(m['id']+'.json.gz')));identities.add((d['manufacturer'],d['model_name'],d['category']));emit(d)
  for a in json.loads(additions.read_text()):
   identity=(a['manufacturer'],a['model_name'],a['category']);assert identity not in identities,identity;identities.add(identity)
   rid=hashlib.sha256(('official-web\0'+'\0'.join(identity)+'\0'+a['region']).encode()).hexdigest()[:24]
   facts=[{**f,'fact_id':'WEB'+str(i+1),'category':'Technical specifications','configuration':f.get('configuration',a['region']),'verification':f.get('verification','reviewed_web_factual_partial'),'source_id':'S1','source_url':a['url'],'applicable_to_record_model':True,'original_fact':{**f,'source_url':a['url'],'retrieved_at':a['reviewed_at']}} for i,f in enumerate(a['facts'])]
   emit(dict(id=rid,manufacturer=a['manufacturer'],model_name=a['model_name'],category=a['category'],original_category=a.get('original_category',a['category']),record_kind='individual_model',base_model=None,quality_stage='reviewed_web_factual_partial',semantic_completeness='not_verified',updated_at=a['reviewed_at'],fact_count=len(facts),equipment_count=0,table_count=0,source_count=1,is_assembly=False,warning_count=sum(bool(f.get('conflict_ids')) for f in facts),scope=a.get('scope','공식 제품 페이지·비교표에서 확인한 주요 수치만 수록했습니다. 전체 카탈로그 검토는 미완료입니다.'),inventory_note='판매 지역과 개정에 따라 다른 사양을 하나로 합치지 않습니다.',sources=[dict(source_id='S1',title=a.get('source_title',a['model_name']+' official specifications'),sha256=a.get('source_sha256'),url=a['url'],product_url=a['url'],region=a['region'],retrieved_at=a['reviewed_at'])],source_metadata={'review_scope':('공식 핸드북 표 추출·부분 대조' if a.get('source_sha256') else '주요 제원만 수동 확인'),'semantic_completeness':'not_verified'},sections={},facts=facts,records=[]))
  models.sort(key=lambda m:(m['manufacturer'],m['model_name'],m['id']));idx.update(snapshot_id=snapshot,built_from_updated_at='2026-10-18',model_count=len(models),individual_model_count=sum(m['record_kind']=='individual_model' for m in models),application_variant_count=sum(m['record_kind']=='application_variant' for m in models),fact_count=sum(m['fact_count'] for m in models),facets=b.FACETS,models=models,parent_snapshot_id=pointer['snapshot_id'],additions_sha256=b.digest(additions))
  p=tmp/'index.json';p.write_text(b.dumps(idx));files.append(dict(path=p.name,bytes=p.stat().st_size,sha256=b.digest(p)));(tmp/'manifest.json').write_text(b.dumps(dict(schema_version=1,snapshot_id=snapshot,parent_manifest_sha256=pointer['manifest_sha256'],files=files)))
  os.replace(tmp,out);print(b.dumps({'snapshot':snapshot,'models':len(models),'facts':idx['fact_count'],'manufacturers':dict(collections.Counter(m['manufacturer'] for m in models)),'facets':{k:sum(bool(m['facets'].get(k)) for m in models) for k in b.FACETS}}))
 except BaseException:shutil.rmtree(tmp,ignore_errors=True);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('snapshot');p.add_argument('additions',type=Path);a=p.parse_args();assert __import__('re').fullmatch('[A-Za-z0-9_-]{1,80}',a.snapshot);extend(a.root,a.snapshot,a.additions)
