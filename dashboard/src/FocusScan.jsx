import React, {useCallback,useEffect,useRef,useState} from 'react';
import './focus-scan.css';
import MailHistory from './MailHistory';
import FocusResponseRows from './FocusResponseRows';

const empty=()=>({model_contains:'',email:'',price_min_manwon:'',price_max_manwon:'',year_min:'',year_max:'',enabled:false});
const labels={model_contains:'모델명 포함 조건',email:'수신 이메일',price_min_manwon:'최소 가격 (만원)',price_max_manwon:'최대 가격 (만원)',year_min:'최소 연식 (년)',year_max:'최대 연식 (년)'};
const statuses={paused:'중지',waiting:'실행 대기',running:'스캔 중',complete:'확인 완료',baseline:'최초 기준점',partial:'일부 미확인',failed:'실패',mail_missing:'메일 설정 필요',cancelled:'중지됨',response:'HTTP 응답',parsed:'목록 응답',network_error:'연결 실패',sent:'메일 발송',uncertain:'발송 확인 필요'};
export default function FocusScan({authFetchOptions}) {
  const [data,setData]=useState({rules:[],categories:[],logs:[],service:null});
  const [section,setSection]=useState('settings'),[form,setForm]=useState(empty),[edit,setEdit]=useState(null);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[errors,setErrors]=useState({}),[notice,setNotice]=useState('');
  const [scanDraft,setScanDraft]=useState(null);
  const [search,setSearch]=useState(''),[showAll,setShowAll]=useState(false); const errorRef=useRef(null), controller=useRef(null);
  const load=useCallback(async()=>{
    controller.current?.abort(); const abort=new AbortController();controller.current=abort;
    try {const r=await fetch('/api/focus-scan',{...authFetchOptions,signal:abort.signal});if(!r.ok)throw new Error('설정을 불러오지 못했습니다. 새로고침으로 다시 시도하세요.');setData(await r.json())}
    catch(e){if(e.name!=='AbortError')setError(e.message)}finally{if(!abort.signal.aborted)setLoading(false)}
  },[authFetchOptions]);
  useEffect(()=>{load();const id=setInterval(()=>{if(!document.hidden)load()},30000);return()=>{clearInterval(id);controller.current?.abort()}},[load]);
  async function write(url,method,body) {
    setBusy(true);setError('');setErrors({});setNotice('');
    try{const r=await fetch(url,{...authFetchOptions,method,headers:{...authFetchOptions.headers,'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await r.json();if(!r.ok){setErrors(result.errors||{});throw new Error(result.error||'저장 실패');}await load();return true}
    catch(e){setError(e.message);setTimeout(()=>errorRef.current?.focus(),0);return false}finally{setBusy(false)}
  }
  function change(key,value){setForm(f=>({...f,[key]:value}))}
  const scan=scanDraft||data.scan||{categories:[],interval_minutes:10,request_delay_seconds:2,enabled:false};
  const changeScan=(key,value)=>setScanDraft({...scan,[key]:value});
  const service=data.service, online=service && service.heartbeat_age<240;
  return <section className="focus-scan" aria-label="집중탐색">
    <header className="focus-heading"><div><h2>집중탐색</h2><p>공통 크롤링 1회 → 여러 알림 조건 비교 → 조건별 메일 발송</p></div><button type="button" onClick={load} disabled={loading||busy}>새로고침</button></header>
    <div className="focus-notes"><strong>{online?'스캐너 연결됨':'스캐너 연결 확인 필요'}{service && !service.mail_ready?' · 메일 설정 필요':''}</strong><p>기존 매물 수집과 별개로 동작합니다. 응답 원문은 저장하지 않습니다. 실제 조회한 목록의 모델명·연식·가격과 요청·응답 요약은 최근 7일만 보관합니다. 성공한 메일의 매물·수신자·조건·발송 시각은 ‘메일 발송내역’ 하위 탭에 영구 보관합니다.</p><p>공통 크롤링을 처음 시작·재시작하거나 카테고리를 바꾸면 기준점을 등록합니다. 알림 조건 추가·수정은 공통 기준점과 주기를 바꾸지 않습니다. 알림 조건이 늘어도 사이트 요청은 늘어나지 않습니다. 다음 주기부터 새 번호를 탐색합니다. 등록 시·분이 없는 매물은 최초 발견 기준이며, 정확한 등록 시각으로 단정하지 않습니다.</p></div>
    <nav className="focus-sections" aria-label="집중탐색 화면"><button type="button" aria-pressed={section==='settings'} onClick={()=>setSection('settings')}>탐색·알림 설정</button><button type="button" aria-pressed={section==='history'} onClick={()=>setSection('history')}>최근 1주일 기록</button><button type="button" aria-pressed={section==='mailHistory'} onClick={()=>setSection('mailHistory')}>메일 발송내역</button></nav>
    {error&&<div className="focus-error" role="alert" ref={errorRef} tabIndex={-1}>{error}{Object.entries(errors).map(([key,value])=><p key={key}><a href={`#focus-${key}`}>{labels[key]||{interval_minutes:'스캔 주기',request_delay_seconds:'요청 간격',categories:'카테고리',enabled:'활성화'}[key]||key}: {value}</a></p>)}</div>}
    {notice&&<p role="status">{notice}</p>}
    {loading?<p role="status">집중탐색 설정을 불러오는 중입니다…</p>:section==='settings'?<>

      <form className="focus-form" aria-label="공통 크롤링 설정" onSubmit={async e=>{e.preventDefault();if(await write('/api/focus-scan/config','PUT',{...scan,enabled:Boolean(scan.enabled)})){setScanDraft(null);setNotice('공통 크롤링 설정을 저장했습니다.')}}}>
        <h3>1. 공통 크롤링 설정</h3>
        <p>{data.scan?.enabled?'활성':'중지'} · {statuses[data.scan?.last_status]||'실행 전'} · 최근 {data.scan?.last_started_at||'—'} · 다음 {data.scan?.enabled?(data.scan?.next_run_at||'곧 실행'):'중지'}</p>
        <p>{data.scan?.last_summary}</p>
        <fieldset id="focus-categories" tabIndex={-1}><legend>탐색 카테고리 (필수 · 최대 15개)</legend><label>카테고리 검색<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="굴삭기, 지게차 등"/></label><div className="focus-categories">{data.categories.filter(c=>c.name.includes(search)).slice(0,search||showAll?undefined:12).map(c=><button type="button" key={c.code} aria-pressed={scan.categories.includes(c.code)} disabled={!scan.categories.includes(c.code)&&scan.categories.length>=15} onClick={()=>changeScan('categories',scan.categories.includes(c.code)?scan.categories.filter(x=>x!==c.code):[...scan.categories,c.code])}>{c.name}</button>)}</div>{!search&&data.categories.length>12&&<button type="button" onClick={()=>setShowAll(v=>!v)}>{showAll?'카테고리 접기':`전체 ${data.categories.length}개 카테고리 보기`}</button>}<p>{scan.categories.length}개 선택 · {scan.categories.map(c=>data.categories.find(x=>x.code===c)?.name||c).join(', ')}</p>{errors.categories&&<p className="focus-error">{errors.categories}</p>}</fieldset>
        <label htmlFor="focus-interval_minutes">스캔 주기 (분)<input id="focus-interval_minutes" type="number" min="1" max="1440" step="1" required value={scan.interval_minutes} onChange={e=>changeScan('interval_minutes',e.target.value)}/></label>
        <label htmlFor="focus-request_delay_seconds">요청 간격 (초)<input id="focus-request_delay_seconds" type="number" min="1" max="30" step="1" required value={scan.request_delay_seconds??2} onChange={e=>changeScan('request_delay_seconds',e.target.value)} aria-invalid={!!errors.request_delay_seconds} aria-describedby="focus-delay-help"/></label>
        <p id="focus-delay-help">1~30초 · 기본 2초. 서로 다른 카테고리의 요청 사이에도 적용합니다. 변경한 간격은 다음 회차부터 적용합니다.</p>
        <div className="focus-presets" aria-label="주기 빠른 선택">{[5,10,30,60].map(n=><button key={n} type="button" aria-pressed={Number(scan.interval_minutes)===n} onClick={()=>changeScan('interval_minutes',n)}>{n}분</button>)}</div>
        <p>설정한 요청 간격 적용 · 카테고리당 최대 3페이지 · 한 회차 최대 40요청/150초. 실행은 겹치지 않습니다. 선택 수·요청 간격에 따라 회차 한도에 도달하면 일부 미확인으로 표시합니다. 알림이 없어도 공통 크롤링은 실행됩니다. 활성 알림이 있는데 메일 설정이 없으면 누락 방지를 위해 대기합니다.</p>
        <label className="focus-enable"><input id="focus-enabled" type="checkbox" checked={Boolean(scan.enabled)} onChange={e=>changeScan('enabled',e.target.checked)}/>공통 크롤링 활성화</label>
        <div className="focus-actions"><button type="submit" disabled={busy}>{busy?'저장 중…':'공통 크롤링 저장'}</button>{scanDraft&&<button type="button" disabled={busy} onClick={()=>setScanDraft(null)}>변경 취소</button>}</div>
      </form>
      <h3>2. 알림 조건</h3><p>같은 새 매물을 모든 활성 조건과 비교합니다. 여러 조건에 일치하면 조건별로 메일을 보냅니다. 알림을 꺼도 공통 크롤링은 중지되지 않습니다.</p>
      <div className="focus-rules" aria-label="알림 조건 목록">{data.rules.length===0?<p>등록된 알림 조건이 없습니다.</p>:data.rules.map(r=><article className="focus-rule" key={r.id}><div><h3>{r.model_contains}</h3><span className="focus-badge">알림 {r.enabled?'활성':'중지'} · #{r.id}</span></div><p>{r.email} · 가격 {r.price_min_manwon??'제한 없음'} ~ {r.price_max_manwon??'제한 없음'}만원 · 연식 {r.year_min??'제한 없음'} ~ {r.year_max??'제한 없음'}년</p><div className="focus-actions"><button disabled={busy} type="button" onClick={()=>{setEdit(r.id);setForm({...empty(),...r,enabled:Boolean(r.enabled),...Object.fromEntries(Object.keys(labels).map(k=>[k,r[k]??'']))});setErrors({});setError('');document.getElementById('focus-model_contains')?.focus()}}>수정</button><button disabled={busy} type="button" onClick={async()=>{if(await write(`/api/focus-scan/${r.id}`,'PATCH',{enabled:!r.enabled}))setNotice(r.enabled?'이 알림을 중지했습니다.':'다음 공통 크롤링부터 이 조건을 적용합니다.')}}>{r.enabled?'알림 중지':'알림 활성화'}</button><button type="button" disabled={busy} onClick={async()=>{if(!window.confirm(`“${r.model_contains}” 알림 조건을 삭제할까요? 이미 발송한 내역은 보존됩니다.`))return;if(await write(`/api/focus-scan/${r.id}`,'DELETE',{})){if(edit===r.id){setEdit(null);setForm(empty())}setNotice('알림 조건을 삭제했습니다. 발송내역은 보존됩니다.')}}}>삭제</button></div></article>)}</div>
      <form className="focus-form" aria-label="알림 조건 설정" onSubmit={async e=>{e.preventDefault();if(await write(edit?`/api/focus-scan/${edit}`:'/api/focus-scan',edit?'PUT':'POST',form)){setForm(empty());setEdit(null);setNotice('알림 조건을 저장했습니다. 공통 크롤링 주기와 기준점은 유지됩니다.')}}}>
        <h3>{edit?'알림 조건 수정':'새 알림 조건'}</h3>
        <div className="focus-fields">{Object.entries(labels).map(([key,label])=><label key={key} htmlFor={`focus-${key}`}>{label}{['model_contains','email'].includes(key)?' (필수)':''}<input id={`focus-${key}`} type={key==='email'?'email':key==='model_contains'?'text':'number'} required={['model_contains','email'].includes(key)} step={1} min={key==='interval_minutes'?1:key.startsWith('year')?1900:0} max={key==='interval_minutes'?1440:key.startsWith('year')?new Date().getFullYear()+1:undefined} value={form[key]} onChange={e=>change(key,e.target.value)} aria-invalid={!!errors[key]} aria-describedby={errors[key]?`focus-error-${key}`:key==='model_contains'?'focus-model-help':undefined}/>{errors[key]&&<span className="focus-error" id={`focus-error-${key}`}>{errors[key]}</span>}</label>)}</div>
        <p id="focus-model-help">모델명은 자유롭게 입력합니다. 입력한 글자가 포함된 모델을 찾습니다. 여러 모델은 조건을 각각 등록하세요. 가격·연식의 빈 칸은 제한 없음입니다.</p>
        <label className="focus-enable"><input type="checkbox" checked={form.enabled} onChange={e=>change('enabled',e.target.checked)}/>이 알림 조건 활성화</label>
        <div className="focus-actions"><button type="submit" disabled={busy}>{busy?'저장 중…':edit?'알림 변경 저장':'알림 조건 저장'}</button>{edit&&<button type="button" disabled={busy} onClick={()=>{setEdit(null);setForm(empty());setErrors({})}}>수정 취소</button>}</div>
      </form>
    </>:section==='mailHistory'?<MailHistory authFetchOptions={authFetchOptions}/>:<section aria-label="최근 1주일 스캔 기록"><h3>공통 크롤링 / 조건별 알림 기록</h3><p>조회한 목록은 모델명·연식·가격만 보관합니다. 연식·가격은 원문 표기이며 빈 값은 —로 표시합니다. 응답 원문·쿠키·인증정보는 저장하지 않습니다. 기록은 7일 이후 시간별 정리 작업에서 삭제됩니다. 메일 발송 확인 불명확 시에는 중복 방지를 위해 자동 재발송하지 않습니다.</p>{data.logs.length===0?<p>아직 기록이 없습니다. 설정을 활성화하면 첫 스캔부터 표시됩니다.</p>:<div className="focus-log-list">{data.logs.map(log=><article className="focus-log" key={log.id}><strong>{statuses[log.status]||log.status}{log.http_status?` · HTTP ${log.http_status}`:''}</strong><span>{log.created_at} · {log.rule_id==null?'공통 크롤링':`알림 #${log.rule_id}`} {log.category_code?`· ${data.categories.find(c=>c.code===log.category_code)?.name||log.category_code}`:''}</span>{log.request_path&&<code>{log.method} {log.request_path}</code>}<p>{log.summary}{log.duration_ms!=null?` · ${log.duration_ms}ms · ${log.response_bytes??0} bytes`:''}</p><FocusResponseRows rows={log.response_rows} legacyNames={log.sample_names}/></article>)}</div>}</section>}
  </section>;
}
