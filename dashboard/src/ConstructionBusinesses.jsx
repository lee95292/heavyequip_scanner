import {useEffect,useState} from 'react';
import './construction-businesses.css';
const columns = [['name','사업장명'],['business_type','사업종류'],['registration_type','등록종구분'],['road_address','도로명주소'],['lot_address','지번주소'],['phone','대표전화'],['registration_number','등록번호'],['registered_date','등록일'],['agency','관리기관'],['agency_phone','관리기관 전화'],['reference_date','데이터 기준일'],['provider','제공기관'],['provider_code','기관코드'],['latitude','위도'],['longitude','경도']];
const statuses = {not_started:'수집 전',running:'수집 중',failed:'수집 실패',complete:'수집 완료'};
export default function ConstructionBusinesses({authFetchOptions}) {
  const [draft,setDraft] = useState('');
  const [query,setQuery] = useState({q:'',region:'',business_type:'',registration_type:'',page:1});
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(true);
  const [refresh,setRefresh] = useState(0);
  const [syncing,setSyncing] = useState(false);
  useEffect(()=>{
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch('/api/construction-businesses?'+new URLSearchParams(query), {...authFetchOptions,signal:controller.signal})
      .then(async response=>{const body=await response.json();if(!response.ok)throw new Error(body.error||'조회 실패');return body;})
      .then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[query,refresh,authFetchOptions]);
  useEffect(()=>{
    if(data?.sync?.status!=='running')return;
    const timer=setInterval(()=>setRefresh(x=>x+1),3000);
    return ()=>clearInterval(timer);
  },[data?.sync?.status]);
  async function collect() {
    setSyncing(true);setError('');
    try {
      const response=await fetch('/api/construction-businesses/sync',{
        ...authFetchOptions,method:'POST',headers:{...authFetchOptions.headers,'Content-Type':'application/json'},
        body:JSON.stringify({restart:data?.sync?.status==='complete'})});
      const body=await response.json();if(!response.ok)throw new Error(body.error);
      setData(current=>({...current,sync:{...current?.sync,status:'running'}}));setRefresh(x=>x+1);
    }catch(e){setError(e.message);}finally{setSyncing(false);}
  }
  return <section className="business-registry" aria-labelledby="business-title">
    <header><div><h2 id="business-title">건설기계 사업자</h2><p>공공데이터포털 등록 사업자 · 매물 및 판매자 정보와 별도로 관리합니다.</p></div>
      <button type="button" onClick={collect} disabled={!data?.serviceKeyConfigured||syncing||data?.sync?.status==='running'}>
        {data?.sync?.status==='running'?'API 수집 중':data?.sync?.status==='failed'?'이어서 수집':data?.sync?.status==='complete'?'API 새로 수집':'API 수집 시작'}</button></header>
    <div className="business-notice">
      <a href="https://www.data.go.kr/data/15155695/standard.do" target="_blank" rel="noreferrer">전국건설기계사업자표준데이터 · 공공데이터포털 / 행별 제공기관</a>
      <p>기관별 데이터 기준일이 다르며 현재 영업 여부를 보장하지 않습니다. 기존 행을 폐업으로 추정하여 자동 삭제하지 않습니다.</p>
      {data&&!data.serviceKeyConfigured&&<p>새 수집에는 서버의 DATA_GO_KR_SERVICE_KEY 설정이 필요합니다. 저장된 자료는 계속 조회할 수 있습니다.</p>}
      <p role="status">{statuses[data?.sync?.status]||'상태 확인 중'} · 원본 처리 {data?.sync?.processed?.toLocaleString()||0} / {data?.sync?.total?.toLocaleString()??'미확인'}건
        {data?.sync?.completed_at&&` · 최근 완료 ${data.sync.completed_at}`}</p>
      {data?.sync?.error&&<p role="alert">수집 오류: {data.sync.error}</p>}
      {data?.schedule&&<p>자동 갱신: {data.schedule.label} · {data.schedule.healthy?'서버 실행 중':'서버 실행 상태 확인 필요'}<br/>다음 실행: {new Date(data.schedule.nextRunAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})}{data.schedule.error&&` · 최근 오류: ${data.schedule.error}`}</p>}
    </div>
    <form className="business-filters" onSubmit={event=>{event.preventDefault();setQuery(q=>({...q,q:draft,page:1}));}}>
      <label>사업장명·주소·등록번호<input value={draft} onChange={e=>setDraft(e.target.value)} maxLength={100}/></label>
      {[['region','지역'],['business_type','사업종류'],['registration_type','등록종구분']].map(([key,label])=><label key={key}>{label}
        <select value={query[key]} onChange={e=>setQuery(q=>({...q,[key]:e.target.value,page:1}))}>
          <option value="">전체</option>{(data?.options?.[key]||[]).map(value=><option key={value}>{value}</option>)}
        </select></label>)}
      <button type="submit">검색</button><button type="button" onClick={()=>{setDraft('');setQuery({q:'',region:'',business_type:'',registration_type:'',page:1});}}>초기화</button>
    </form>
    {error&&<p role="alert">{error} <button onClick={()=>setRefresh(x=>x+1)}>다시 시도</button></p>}
    <p aria-live="polite">{loading?'조회 중…':error?'조회 결과를 표시할 수 없습니다.':`검색 결과 ${(data?.total||0).toLocaleString()}건 · 페이지당 50건`}</p>
    {!loading&&!error&&<><div className="business-table" tabIndex={0} role="region" aria-label="사업자 정보 표, 가로 스크롤 가능">
      <table><caption>건설기계 사업자 등록 정보</caption><thead><tr>{columns.map(([key,label])=><th scope="col" key={key}>{label}</th>)}</tr></thead>
        <tbody>{data?.items.map(row=><tr key={row.id}>{columns.map(([key])=><td key={key}>{row[key]||'—'}</td>)}</tr>)}</tbody></table>
      {!data?.items.length&&<p>{data?.sync?.status==='not_started'?'아직 수집된 사업자 정보가 없습니다.':'검색 조건에 맞는 사업자가 없습니다.'}</p>}
    </div><nav aria-label="사업자 목록 페이지" className="business-pagination">
      <button disabled={query.page<=1} onClick={()=>setQuery(q=>({...q,page:q.page-1}))}>이전</button>
      <span>{query.page} / {Math.max(1,Math.ceil((data?.total||0)/50))}</span>
      <button disabled={query.page*50>=(data?.total||0)} onClick={()=>setQuery(q=>({...q,page:q.page+1}))}>다음</button>
    </nav></>}
  </section>;
}
