#!/usr/bin/env python3
"""Extract bounded factual columns from CAT PHB50 Former Models, retaining each row's context.
Requires pdfplumber. Input PDF SHA is recorded; no network or active-catalog mutation.
Only explicitly supported table layouts are imported; numeric cells fail closed.
"""
import argparse,collections,hashlib,json,re
from pathlib import Path
import pdfplumber
URL='https://wheelercat.com/wp-content/uploads/2025/03/Cat-Performance-Handbook-Edition-50-June-2022.pdf'
P=('Net engine power (flywheel)','hp'); PK=(P[0],'kW'); W=('Approximate machine weight','kg'); OW=('Operating weight','kg'); SW=('Shipping weight','kg')
def profile(n):
 if 362<=n<=388:return '도저','Track-Type Tractors',{3:P,4:W,5:('Track gauge','m'),6:('Tractor length','m')}
 if 398<=n<=401:return '모터 그레이더','Motor Graders',{3:('Rated engine power','hp'),4:SW,5:('Wheelbase','m'),6:('Overall length','m'),7:('Overall width','m'),8:('Blade length','m')}
 if 402<=n<=405:return '스키드·컴팩트 트랙 로더',('Skid Steer Loaders' if n<=403 else 'Compact Track Loaders'),{3:W,4:('Net engine power','kW'),5:('Length to coupler','mm'),6:('Overall width','mm'),7:('Overall height','mm'),10:('Rated operating capacity','kg')}
 if 406<=n<=425:return '굴착기','Hydraulic Excavators (Track)',{3:P,4:OW,5:('Track gauge','m'),6:('Transport height','m'),7:('Transport length','m'),8:('Transport width','m'),9:('Maximum reach','m')}
 if 426<=n<=427:return '굴착기','Hydraulic Excavators (Wheel)',{3:P,4:OW,5:('Transport height','m'),6:('Transport length','m'),7:('Transport width','m'),8:('Maximum reach','m')}
 if 430<=n<=431:return '머티리얼 핸들러·임업 장비','Material Handlers',{3:PK,4:OW,5:('Maximum reach','m')}
 if 432<=n<=433:return '머티리얼 핸들러·임업 장비','Logging and Forest Product Machines',{3:PK,6:('Overall width','m'),7:OW}
 if 441<=n<=447:return '스크레이퍼','Wheel Tractor-Scrapers',{5:SW,6:('Overall length','m'),7:('Overall width','m'),8:('Overall height','m')}
 if n==448:return '스크레이퍼','Tractor-Towed Scrapers',{4:W,5:('Overall width','m'),6:('Overall length','m'),7:('Overall height','m')}
 if 436<=n<=438:return '백호 로더','Backhoe Loaders',{3:PK,4:OW,5:('Maximum digging depth','mm'),6:('Bucket capacity (GP)','m3')}
 if 439<=n<=440:return '파이프레이어','Pipelayers',{3:P,4:('Tractor weight','kg')}
 if 449<=n<=450 or 452<=n<=454:return '덤프·운반 장비','Articulated Trucks' if n>=452 else 'Mining & Off-Highway Trucks',{3:PK,4:('Rated payload','t'),5:W,6:('Overall width','m'),7:('Overall length','m'),8:('Overall height','m')}
 if n==455:return '도저','Wheel Dozers',{3:PK,4:OW,5:('Overall length','m'),8:('Ground clearance','mm')}
 if n==456:return '다짐 장비','Compactors',{3:PK,4:OW}
 if 457<=n<=461 or n==465:return '휠 로더','Wheel Loaders' if n!=465 else 'Integrated Toolcarriers',{3:P,4:SW,5:('Bucket capacity','m3'),7:('Overall width','m'),8:('Ground clearance','mm')}
 if 462<=n<=464:return '트랙 로더','Track Loaders',{3:P,4:OW,5:('Bucket capacity','m3'),6:('Tractor length','m'),7:('Overall width','m'),8:('Overall height','m')}
 if n==466:return '텔레핸들러','Telehandlers',{3:PK,4:OW,6:('Maximum lift height','m'),7:('Maximum reach','m'),8:('Maximum lift capacity','kg')}
 if n==467 or 471<=n<=473:return '아스팔트 포장·절삭 장비','Paving Products',{3:PK,4:OW}
 if 474<=n<=479:return '다짐 장비','Vibratory Compactors',{3:PK,4:OW,6:('Drum width','mm')}
 return None

def check_secondary(f,raw):
 # Cross-check printed dual units. Conflicts remain visible but cannot drive filters.
 if not raw.startswith('('):return
 raw=raw.strip('()');converted=None
 if f['unit']=='kg' and re.fullmatch(r'[\d, ]+(?:\.\d+)?',raw):
  f['secondary_value']=raw.replace(',','').replace(' ','');f['secondary_unit']='lb';converted=float(f['secondary_value'])*.45359237
 elif f['unit']=='m':
  mt=re.fullmatch(r"(\d+)'(\d+(?:\.\d+)?)\"",raw)
  if mt:f['secondary_value']=raw;f['secondary_unit']='ft/in';converted=int(mt[1])*.3048+float(mt[2])*.0254
 if converted:
  f['secondary_role']='원문 병기 단위'
  if abs(float(f['value'])-converted)>max(.03*converted,.03):
   f['verification']='source_unit_conflict';f['conflict_ids']=['PHB50_DUAL_UNIT_MISMATCH']

def extract(pdf,index):
 existing={(re.sub(r'\s+','',m['model_name']).upper(),m['category']) for m in index['models'] if m['manufacturer']=='Caterpillar'}
 models={};audit={'source_url':URL,'source_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':[],'existing_skipped':set(),'held':[]}
 with pdfplumber.open(pdf) as doc:
  for n in range(362,480):
   pr=profile(n)
   if not pr:continue
   category,original,fields=pr;page=doc.pages[n-1];words=page.extract_words();heads=[x for x in words if x['text']=='Model' and x['x0']<90]
   if not heads: audit['held'].append({'page':n,'reason':'missing model header'});continue
   head=heads[0];gs=[]
   for w in sorted([w for w in words if abs(w['top']-head['top'])<1],key=lambda x:x['x0']):
    if gs and w['x0']-gs[-1][-1]['x1']<3.5:gs[-1].append(w)
    else:gs.append([w])
   centers=[(g[0]['x0']+g[-1]['x1'])/2 for g in gs];bounds=[34]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[488]
   labels=[' '.join(x['text'] for x in g) for g in gs]
   if len(labels)<max(fields)+1 or 'Built' not in labels[2]:audit['held'].append({'page':n,'reason':'unexpected columns','headers':labels});continue
   rows=[]
   for w in sorted([w for w in words if head['bottom']+1<w['top']<page.height-30 and 34<=w['x0']<488],key=lambda x:(round(x['top']),x['x0'])):
    if rows and abs(w['top']-rows[-1][0]['top'])<2:rows[-1].append(w)
    else:rows.append([w])
   count=0
   def cells_of(ws):return [' '.join(w['text'] for w in sorted(ws,key=lambda x:x['x0']) if a<=(w['x0']+w['x1'])/2<b) for a,b in zip(bounds,bounds[1:])]
   for ri,ws in enumerate(rows):
    ws=sorted(ws,key=lambda x:x['x0']);cells=[' '.join(w['text'] for w in ws if a<=(w['x0']+w['x1'])/2<b) for a,b in zip(bounds,bounds[1:])]
    name=(cells[0].split() or [''])[0].rstrip('*†')
    if not re.fullmatch(r'(?:[A-Z]{1,3}-?)?\d{1,4}(?:\.\d)?[A-Z0-9]*',name):continue
    # No first-column serial-prefix or blank continuation may create a model.
    if not any(re.search(r'\d',cells[c]) for c in fields):continue
    if (re.sub(r'\s+','',name).upper(),category) in existing:audit['existing_skipped'].add(name);continue
    context=' '.join(cells[:3]); facts=[]
    for c,(attribute,unit) in fields.items():
     raw=cells[c];v=raw
     if 'power' in attribute and re.fullmatch(r'[\d .]+ kW',raw):v=raw.removesuffix(' kW');unit='kW'
     if n<=388 and c==3:v=raw.split('/')[0]
     v=re.sub(r'\s+','',v)
     if not re.fullmatch(r'\d+(?:\.\d+)?',v):continue
     value=float(v)
     if value<=0:continue
     if 'power' in attribute and not 5<=value<=5000:continue
     if unit=='kg' and not 100<=value<=2000000:continue
     if unit=='m' and not .1<=value<=100:continue
     facts.append({'attribute':attribute,'value':v,'unit':unit,'configuration':context,'source_pdf_page':n,'source_printed_page':f'23-{n-361}','source_cell':raw})
    if ri+1<len(rows):
     secondary=cells_of(rows[ri+1])
     for f in facts:
      ci=next((c for c,pair in fields.items() if pair[0]==f['attribute']),None)
      if ci is not None:check_secondary(f,secondary[ci])
    continuation=[]
    for fi,following in enumerate(rows[ri+1:],ri+1):
     cs=[' '.join(w['text'] for w in sorted(following,key=lambda x:x['x0']) if a<=(w['x0']+w['x1'])/2<b) for a,b in zip(bounds,bounds[1:])]
     if re.match(r'^(?:[A-Z]{1,3}-?)?\d',cs[0]) or any('NOTE:' in x or '*D' in x for x in cs):break
     if any(cs[:3]):continuation.append(' '.join(cs[:3]).strip())
     if n<=388 and len(cs)>6 and all(re.fullmatch(r'\d+(?:\.\d+)?',cs[c]) for c in (5,6)):
      for c,attribute in [(5,'Overall width'),(6,'Overall height')]:
       if .5<=float(cs[c])<=15:facts.append({'attribute':attribute,'value':cs[c],'unit':'m','configuration':context,'source_pdf_page':n,'source_printed_page':f'23-{n-361}','source_cell':cs[c]})
      if fi+1<len(rows):
       second=cells_of(rows[fi+1])
       for f,c in zip(facts[-2:],[5,6]):check_secondary(f,second[c])
      break
    context+=' / '+' / '.join(continuation)
    if len(facts)<2:audit['held'].append({'page':n,'model':name,'reason':'fewer than two safe numeric columns','cells':cells});continue
    if cells[2]:facts.insert(0,{'attribute':'Years built (source notation)','value':cells[2],'unit':'','configuration':context,'source_pdf_page':n})
    # Preserve the table's per-row model suffixes, serial prefix and notes as evidence.
    key=(name,category);m=models.setdefault(key,{'manufacturer':'Caterpillar','model_name':name,'category':category,'original_category':original,'region':'Historical models · PHB50 / PHB49 inventory','url':URL,'reviewed_at':'2026-10-18','facts':[],'source_sha256':audit['source_sha256'],'source_title':'Caterpillar Performance Handbook, Edition 50, June 2022 — Former Models','scope':'캐터필러 성능 핸드북의 구형 모델 주요 제원. 구성·일련번호별 값을 보존하며 최신 판매 모델과 동일 사양을 뜻하지 않습니다. 기계 중량·출하 중량은 운전 중량과 구별합니다. 이 구형 목록은 PHB49 이후 갱신이 중단되었습니다.'})
    for f in facts:
     f['configuration']=f'구형 / {original} / 원문 모델·일련번호·연도: {context}'
     # Include source notes; never silently interpret inconsistent original units.
     f['source_row']=' | '.join(cells);f['source_continuation']=continuation
    m['facts'].extend(facts);count+=1
   audit['pages'].append({'page':n,'headers':labels,'rows_added':count})
  # The foreign-built dozer table has a separate layout; collect missing base names.
  for n in range(389,393):
   for line in doc.pages[n-1].extract_text().splitlines():
    mt=re.search(r'\b(D\d+[A-Z]*)\b.*?([A-Z0-9]{2,3})\*?\s+(\d{2}-\d{2})\s+(\d+)(?:/[—\d]+)?\s+(PS|DD|HYS)(?:\s+(\d+\.\d+))?',line)
    if not mt:continue
    name,prefix,years,power,trans,gauge=mt.groups()
    if name.endswith(('XL','LGP')) or (name,'도저') in existing or (name,'도저') in models:continue
    fs=[{'attribute':'Net engine power (flywheel)','value':power,'unit':'hp'},{'attribute':'Years built (source notation)','value':years,'unit':''},{'attribute':'Transmission','value':trans,'unit':''}]
    if gauge:fs.append({'attribute':'Track gauge','value':gauge,'unit':'m'})
    for f in fs:f.update(configuration='구형 / 해외 생산 / '+line,source_pdf_page=n,source_printed_page=f'23-{n-361}',source_row=line)
    models[(name,'도저')]={'manufacturer':'Caterpillar','model_name':name,'category':'도저','original_category':'Track-Type Tractors','region':'Historical models · foreign-built table','url':URL,'reviewed_at':'2026-10-18','facts':fs,'source_sha256':audit['source_sha256'],'source_title':'Caterpillar Performance Handbook 50 — Former Models','scope':'해외 생산 구형 모델 표에서 확인한 주요 제원. 세부 구성별 전체 제원은 미확인입니다.'}
 audit['existing_skipped']=sorted(audit['existing_skipped']);audit['source_scope']='PHB50 Former Models, supported numeric table layouts; model base names grouped with source configurations retained; other tables and unresolved cells held, not inferred';audit['unprocessed_pages']=[n for n in range(362,482) if not profile(n)];audit['added_models']=len(models);audit['categories']=dict(collections.Counter(m['category'] for m in models.values()))
 return sorted(models.values(),key=lambda x:(x['category'],x['model_name'])),audit
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('pdf',type=Path);p.add_argument('index',type=Path);p.add_argument('output',type=Path);a=p.parse_args();models,audit=extract(a.pdf,json.loads(a.index.read_text()));a.output.write_text(json.dumps(models,ensure_ascii=False,indent=2)+'\n');a.output.with_suffix('.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');print(audit['added_models'],audit['categories'], 'held',len(audit['held']))
