import React,{useEffect,useState} from 'react';
import './focus-scan.css';
import MailListingSnapshot from './MailListingSnapshot.jsx';

const bounds=(a,b,unit)=>`${a??'제한 없음'} ~ ${b??'제한 없음'}${unit}`;
function safeLink(value){try{const u=new URL(value);return u.protocol==='https:'&&['4396200.com','www.4396200.com'].includes(u.hostname)?u.href:null}catch{return null}}
export default function MailHistory({authFetchOptions}){
  const [data,setData]=useState({rows:[],total:0,limit:50}),[page,setPage]=useState(1),[search,setSearch]=useState(''),[q,setQ]=useState(''),[refresh,setRefresh]=useState(0);
  const [loading,setLoading]=useState(true),[error,setError]=useState('');
  useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');
    fetch(`/api/focus-mail-history?page=${page}&q=${encodeURIComponent(q)}`,{...authFetchOptions,signal:controller.signal})
      .then(async r=>{if(!r.ok)throw Error('발송내역을 불러오지 못했습니다. 새로고침으로 다시 시도하세요.');return r.json()})
      .then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});
    return()=>controller.abort();
  },[authFetchOptions,page,q,refresh]);
  return <section className="focus-scan" aria-label="메일 발송내역">
    <header className="focus-heading"><div><h3>메일 발송내역</h3><p>집중탐색에서 조건에 일치하여 발송한 매물입니다. 알림을 삭제해도 이 기록은 영구 보관합니다.</p></div><button disabled={loading} type="button" onClick={()=>setRefresh(v=>v+1)}>발송내역 새로고침</button></header>
    <p>메일 서버가 발송 요청을 수락한 건만 표시합니다. 수신함 도착·열람 여부를 의미하지 않습니다. 당시의 조건, 수신 이메일, 매물 주요정보 및 확인된 연락처를 함께 보관합니다.</p>
    <form className="focus-form" onSubmit={e=>{e.preventDefault();setPage(1);setQ(search.trim());setRefresh(v=>v+1)}}><label htmlFor="mail-history-search">매물명 또는 수신 이메일 검색<input id="mail-history-search" type="search" maxLength="120" value={search} onChange={e=>setSearch(e.target.value)} placeholder="모델명, 이메일"/></label><div className="focus-actions"><button disabled={loading} type="submit">검색</button>{q&&<button type="button" onClick={()=>{setSearch('');setQ('');setPage(1)}}>검색 초기화</button>}</div></form>
    {error&&<p role="alert" className="focus-error">{error}</p>}
    {loading?<p role="status">발송내역을 불러오는 중입니다…</p>:<><p role="status">발송 {data.total.toLocaleString()}건 · {page}페이지</p>
      {data.rows.length===0?<p>{q?'검색 결과가 없습니다.':'아직 발송한 메일이 없습니다. 조건에 맞는 신규 매물이 발송되면 여기에 표시됩니다.'}</p>:<div className="focus-log-list">{data.rows.map(row=><article className="focus-rule" key={row.id}>
        <h3>{safeLink(row.detail_url)?<a href={safeLink(row.detail_url)} target="_blank" rel="noopener noreferrer">{row.listing_name||'이름 없는 매물'} ↗</a>:row.listing_name||'이름 없는 매물'}</h3>
        <p><strong>{row.price_text||'가격 정보 없음'}</strong> · 연식 {row.manufactured_ym||'정보 없음'}</p>
        <p>발송 {row.sent_at} · 수신 {row.recipient}</p>
        <MailListingSnapshot snapshot={row.listing_snapshot}/>
        <details><summary>매칭된 알림 조건 #{row.rule_id}</summary><p>모델명 포함: {row.condition.model_contains}<br/>가격: {bounds(row.condition.price_min_manwon,row.condition.price_max_manwon,'만원')}<br/>연식: {bounds(row.condition.year_min,row.condition.year_max,'년')}</p></details>
      </article>)}</div>}
      <nav className="focus-actions" aria-label="발송내역 페이지"><button type="button" disabled={page<=1} onClick={()=>setPage(v=>v-1)}>이전</button><button type="button" disabled={page*data.limit>=data.total} onClick={()=>setPage(v=>v+1)}>다음</button></nav>
    </>}
  </section>;
}

