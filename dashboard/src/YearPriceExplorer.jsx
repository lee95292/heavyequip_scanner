import {useEffect, useRef, useState} from 'react';
import './year-price.css';

const colors=['#16786b','#387bb8','#b27423','#a4517a','#7661ad','#467b39','#a45636','#58717d'];
const num=v=>Number(v||0).toLocaleString('ko-KR');
const money=v=>v==null?'—':`${num(Math.round(v/10000))}만`;
const getYears=countries=>[...new Set(countries.flatMap(c=>c.cells.map(p=>p.year)))].sort((a,b)=>a-b);
export function yearTicks(years, width) {
  if (!years.length) return [];
  const min=years[0],max=years.at(-1),count=Math.min(width<450?3:6,max-min+1);
  return count===1?[min]:Array.from({length:count},(_,i)=>Math.round(min+(max-min)*i/(count-1)));
}
function bestYear(countries, minimum) {
  return getYears(countries).sort((a,b)=>{
    const score=y=>countries.reduce((n,c)=>n+(c.cells.some(p=>p.year===y&&p.count>=minimum)?1:0),0);
    const count=y=>countries.reduce((n,c)=>n+(c.cells.find(p=>p.year===y)?.count||0),0);
    return score(b)-score(a)||count(b)-count(a)||b-a;
  })[0];
}

function YearChart({countries, selectedYear, minimum, onYear}) {
  const container=useRef(null);
  const [width,setWidth]=useState(720);
  useEffect(()=>{
    const observer=new ResizeObserver(([entry])=>setWidth(Math.max(250,entry.contentRect.width)));
    observer.observe(container.current);
    return ()=>observer.disconnect();
  },[countries.length > 0]);
  const years=getYears(countries), points=countries.flatMap(c=>c.cells);
  if (!points.length) return <div ref={container} className="yp-empty">비교할 국가를 선택하세요. 확인된 연식이 없는 모델은 그래프를 표시하지 않습니다.</div>;
  const height=330,left=66,right=18,top=25,bottom=55;
  const yearMin=years[0],yearMax=years.at(-1),span=Math.max(yearMax-yearMin,1);
  const plotRight=width-right,plotBottom=height-bottom;
  const minPrice=Math.min(...points.map(p=>p.q1)),maxPrice=Math.max(...points.map(p=>p.q3));
  const pricePad=Math.max((maxPrice-minPrice)*.12,maxPrice*.06,1000000);
  const lo=Math.max(0,minPrice-pricePad),hi=maxPrice+pricePad;
  const x=year=>yearMax===yearMin?(left+plotRight)/2:left+9+(year-yearMin)/span*(plotRight-left-18);
  const y=price=>plotBottom-(price-lo)/(hi-lo)*(plotBottom-top);
  const tickYears=yearTicks(years,width);
  function pickYear(event) {
    const rect=event.currentTarget.getBoundingClientRect();
    const px=(event.clientX-rect.left)*width/rect.width;
    onYear(years.reduce((a,b)=>Math.abs(x(a)-px)<Math.abs(x(b)-px)?a:b));
  }
  return <div ref={container} className="yp-chart">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="선택 모델의 국가별 제조연식과 가격 중앙값 비교. 하단 연식 선택과 표에서 같은 값을 확인할 수 있습니다.">
      {[0,.25,.5,.75,1].map(t=>{const value=lo+(hi-lo)*t;return <g key={t}><line x1={left} x2={plotRight} y1={y(value)} y2={y(value)} stroke="#e5ece8"/><text x={left-9} y={y(value)+4} textAnchor="end">{num(Math.round(value/10000))}</text></g>;})}
      <text x={left} y={13} className="yp-axis-label">가격 (만원)</text>
      {tickYears.map(year=><text key={year} x={x(year)} y={plotBottom+23} textAnchor="middle">{year}</text>)}
      <text x={(left+plotRight)/2} y={height-7} textAnchor="middle" className="yp-axis-label">제조연식 (년) · 등록연도 아님</text>
      {selectedYear!=null&&<line x1={x(selectedYear)} x2={x(selectedYear)} y1={top} y2={plotBottom} stroke="#7d9086" strokeDasharray="4 4"/>}
      {countries.map(country=><g key={country.country}>
        {country.cells.map((p,i)=>{
          const prev=country.cells[i-1];
          return <g key={p.year}>
            {prev&&prev.year===p.year-1&&prev.count>=minimum&&p.count>=minimum&&<line x1={x(prev.year)} x2={x(p.year)} y1={y(prev.median)} y2={y(p.median)} stroke={country.color} strokeWidth="2"/>}
            {p.count>=minimum&&<g stroke={country.color} opacity=".35" strokeWidth="2"><line x1={x(p.year)} x2={x(p.year)} y1={y(p.q1)} y2={y(p.q3)}/><line x1={x(p.year)-4} x2={x(p.year)+4} y1={y(p.q1)} y2={y(p.q1)}/><line x1={x(p.year)-4} x2={x(p.year)+4} y1={y(p.q3)} y2={y(p.q3)}/></g>}
            <circle cx={x(p.year)} cy={y(p.median)} r={p.year===selectedYear?6:4} fill={p.count>=minimum?country.color:'#fff'} stroke={country.color} strokeWidth="2" opacity={p.count>=minimum?1:.55}><title>{`${country.country} · ${p.year}년 · 중앙값 ${money(p.median)}원 · ${p.count}건${p.count<minimum?' · 표본 부족':''}`}</title></circle>
          </g>;
        })}
      </g>)}
      <rect x={left} y={top} width={plotRight-left} height={plotBottom-top} fill="transparent" onClick={pickYear} style={{cursor:'crosshair'}}><title>연도를 클릭하면 아래 국가 비교가 바뀝니다.</title></rect>
    </svg>
  </div>;
}

export default function YearPriceExplorer({data, loading, error}) {
  const models=data?.models||[];
  const [modelName,setModelName]=useState('');
  const [countrySelection,setCountrySelection]=useState(null);
  const [pickedYear,setPickedYear]=useState(null);
  const [minimum,setMinimum]=useState(3);
  const model=models.find(m=>m.model===modelName)||models[0];
  const allCountries=(model?.countries||[]).map((c,i)=>({...c,color:colors[i]}));
  const chosen=countrySelection && countrySelection.model===model?.model?countrySelection.names:allCountries.slice(0,5).map(c=>c.country);
  const countries=allCountries.filter(c=>chosen.includes(c.country));
  const years=getYears(countries);
  const selectedYear=years.includes(pickedYear)?pickedYear:bestYear(countries,minimum);
  const comparisons=countries.map(c=>({...c,point:c.cells.find(p=>p.year===selectedYear)})).sort((a,b)=>(b.point?.median||0)-(a.point?.median||0));
  const enough=comparisons.filter(c=>c.point?.count>=minimum);
  const reference=enough.length>=2?Math.min(...enough.map(c=>c.point.median)):null;
  const changeModel=value=>{setModelName(value);setCountrySelection(null);setPickedYear(null);};
  const toggleCountry=country=>{setCountrySelection({model:model.model,names:chosen.includes(country)?chosen.filter(c=>c!==country):[...chosen,country]});};
  return <section className="year-price" aria-labelledby="year-price-title" aria-busy={loading}>
    <header className="yp-header"><div><span className="yp-kicker">TOP 30 · PRICE EXPLORER</span><h3 id="year-price-title">같은 모델, 같은 연식. 어느 나라가 비쌀까?</h3><p>모델을 고르고 국가별 가격 곡선을 비교하세요. 연식을 클릭하면 같은 조건의 가격 차이가 보입니다.</p></div><span className="yp-scope">전체 수집 매물 기준<br/>정규화 모델 · 1,000만원 이상</span></header>
    {!data ? <div className="yp-empty" role={error?'alert':'status'}>{error||'국가·모델·연식 가격을 분석하고 있습니다…'}</div> : !models.length ? <div className="yp-empty">국가와 정규화 모델이 확인된 매물이 없습니다.</div> : <>
      <div className="yp-controls"><label>매물 수 상위 {models.length}개 모델<select aria-label="가격 비교 모델" value={model.model} onChange={e=>changeModel(e.target.value)}>{models.map(m=><option key={m.model} value={m.model}>{m.rank}. {m.model} · {num(m.count)}건</option>)}</select></label>
        <label>국가·연식별 비교선 기준<select aria-label="연식별 최소 표본" value={minimum} onChange={e=>setMinimum(Number(e.target.value))}>{[3,5,10].map(n=><option key={n} value={n}>{n}건 이상</option>)}</select></label>
        <div className="yp-model-summary"><strong>{model.model}</strong><span>{num(model.count)}건 · 연식 확인 {num(model.usableCount)}건 · {model.countryCount}개 국가</span></div>
      </div>
      <div className="yp-country-heading"><strong>비교 국가 <small>최대 5개 · 연식 확인 매물 수 상위 {Math.min(model.countryCount,8)}개 후보</small></strong><button type="button" onClick={()=>{setCountrySelection(null);setPickedYear(null);}}>국가 선택 초기화</button></div>
      <div className="yp-countries" role="group" aria-label="가격 비교 국가">{allCountries.map(c=><label key={c.country} className={chosen.includes(c.country)?'selected':''}><input type="checkbox" checked={chosen.includes(c.country)} disabled={!chosen.includes(c.country)&&chosen.length>=5} onChange={()=>toggleCountry(c.country)}/><i style={{background:c.color}}/><span>{c.country}</span><small>{num(c.count)}건</small></label>)}</div>
      {model.countryCount===1&&<p className="yp-caution">이 모델은 연식이 확인된 국가가 1개뿐입니다. 국가 간 비교는 아직 할 수 없습니다.</p>}
      <YearChart countries={countries} selectedYear={selectedYear} minimum={minimum} onYear={setPickedYear}/>
      <p className="yp-chart-key">● 가격 중앙값 · 세로 막대: 중간 50% 가격 범위 · ○ {minimum}건 미만(비교선 제외) · 연속된 연식만 연결</p>
      <div className="yp-detail-heading"><div><h4>{selectedYear?`${model.model} · ${selectedYear}년식 국가 비교`:'같은 연식의 국가 비교'}</h4><span>그래프의 연도를 클릭하거나 선택하세요.</span></div><label>비교 연식<select aria-label="비교 연식" value={selectedYear||''} disabled={!years.length} onChange={e=>setPickedYear(Number(e.target.value))}>{!years.length&&<option value="">연식 없음</option>}{years.map(year=><option key={year} value={year}>{year}년</option>)}</select></label></div>
      <div className="yp-table-scroll"><table className="yp-comparison"><caption className="yp-sr-only">{model.model} {selectedYear}년식 국가별 가격 중앙값과 표본 수</caption><thead><tr><th>국가</th><th>가격 중앙값</th><th>중간 50% 가격</th><th>매물 / 출처</th><th>최저 국가 대비</th></tr></thead><tbody>{comparisons.map(c=><tr key={c.country}><th><i style={{background:c.color}}/>{c.country}</th><td><strong>{money(c.point?.median)}{c.point?'원':''}</strong>{c.point&&c.point.count<minimum&&<small>표본 부족 · 참고값</small>}</td><td>{c.point?`${money(c.point.q1)} ~ ${money(c.point.q3)}원`:'해당 연식 없음'}</td><td>{c.point?`${c.point.count}건 / ${c.point.sourceCount}개 사이트`:'—'}</td><td>{reference&&c.point?.count>=minimum?`${c.point.median===reference?'기준':`+${Math.round((c.point.median/reference-1)*100)}%`}`:'비교 불가'}</td></tr>)}</tbody></table></div>
      <p className="yp-footnote">{num(model.missingYearCount)}건은 연식 미상·비정상으로 그래프에서 제외했습니다.{model.countryCount>8?` 국가 후보는 ${model.countryCount}개 중 상위 8개(${num(model.displayedCount)}건)입니다.`:''} 상위 30개 순위는 국가·모델이 확인된 전체 매물 수 기준이며, 아래 탐색 필터와 독립적입니다.</p>
      <p className="yp-footnote">월별 보정 환율을 적용한 판매 희망가격입니다. 연식별 곡선은 과거 가격 추이나 감가상각률이 아닙니다. 세부 사양·가동시간·상태·세금·운송비는 보정하지 않았으며, 최저가 비교는 동일 연식에서 표본 기준을 충족한 선택 국가끼리만 계산합니다.</p>
    </>}
  </section>;
}
