import {useEffect, useMemo, useState} from 'react';
import './market-analytics.css';

const number = value => Number(value || 0).toLocaleString('ko-KR');
const money = value => value == null ? '—' : `${number(Math.round(value / 10000))}만원`;
const percent = value => value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
const tone = value => value < 0 ? 'is-cheap' : value > 0 ? 'is-costly' : 'is-neutral';
const pairKey = pair => JSON.stringify([pair.country, pair.model]);
const defaults = {source: '', category: '', minSample: '3', minYears: '1', yearFrom: '', yearTo: ''};

function Empty({children}) {return <div className="pa-empty">{children || '같은 모델·연식으로 비교할 표본이 부족합니다. 조건을 완화하거나 수집 데이터가 더 쌓인 뒤 확인하세요.'}</div>;}
function Panel({number: index, title, description, children, className = ''}) {
  return <section className={`pa-panel ${className}`}><header className="pa-panel-heading"><div><span className="pa-section-number">{index}</span><h3>{title}</h3></div><p>{description}</p></header>{children}</section>;
}
function CountryRanking({countries, focus, onFocus}) {
  const broad = countries.filter(country => country.broadEnough);
  const narrow = countries.filter(country => !country.broadEnough);
  const maximum = Math.max(20, ...countries.map(country => Math.abs(country.gapPercent)));
  const rows = items => items.map(country => <button type="button" key={country.country} className={`pa-country-row ${focus === country.country ? 'selected' : ''}`} onClick={() => onFocus(focus === country.country ? '' : country.country)} aria-pressed={focus === country.country}>
    <span className="pa-country-name"><strong>{country.country}</strong><small>{country.modelCount}개 모델 · {number(country.count)}건</small></span>
    <span className="pa-diverging" aria-hidden="true"><i/><b className={tone(country.gapPercent)} style={{left: country.gapPercent < 0 ? `${50 - Math.abs(country.gapPercent) / maximum * 48}%` : '50%', width: `${Math.max(.5, Math.abs(country.gapPercent) / maximum * 48)}%`}}/></span>
    <span className={`pa-country-value ${tone(country.gapPercent)}`}><strong>{percent(country.gapPercent)}</strong><small>저렴한 모델 {country.cheapModelCount}/{country.modelCount}</small></span>
  </button>);
  return <><div className="pa-bar-legend"><span>← 타국 대비 저렴</span><span>비쌈 →</span></div>
    {broad.length ? rows(broad) : <Empty>3개 이상의 모델을 비교할 수 있는 국가가 없습니다. 아래 소수 모델의 결과만 참고하세요.</Empty>}
    {narrow.length > 0 && <details className="pa-limited" open={!broad.length}><summary>소수 모델만 비교 가능한 국가 {narrow.length}개 · 종합 판단 제외</summary>{rows(narrow)}</details>}
    <p className="pa-note">모델별 가격 차이를 동일 가중치로 종합했습니다. 국가는 서로 다른 모델·연식·비교국을 포함할 수 있어, 같은 장비 묶음의 확정 순위는 아닙니다.</p>
  </>;
}
function Opportunities({pairs, onPair, selected}) {
  const [page, setPage] = useState(0);
  const cheap = pairs.filter(pair => pair.gapPercent < 0);
  const safePage = Math.min(page, Math.max(0, Math.ceil(cheap.length / 6) - 1));
  if (!cheap.length) return <Empty>현재 조건에서는 타국 대비 저렴한 국가·모델 조합이 없습니다.</Empty>;
  return <><div className="pa-opportunities">{cheap.slice(safePage * 6, safePage * 6 + 6).map(pair => <button type="button" className={`pa-opportunity ${selected === pairKey(pair) ? 'selected' : ''}`} key={pairKey(pair)} onClick={() => onPair(pair)}>
    <span><strong>{pair.model}</strong><small>{pair.country} · {pair.yearCount}개 연식 · {number(pair.count)}건</small></span>
    <span className="pa-opportunity-value is-cheap"><strong>{percent(pair.gapPercent)}</strong><small>저렴한 연식 {pair.cheapYearPercent}%</small></span><span aria-hidden="true">↗</span>
  </button>)}</div><div className="pa-pagination"><span>저렴한 조합 {cheap.length}개 · {safePage + 1}/{Math.max(1, Math.ceil(cheap.length / 6))}</span><div><button disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>이전</button><button disabled={(safePage + 1) * 6 >= cheap.length} onClick={() => setPage(safePage + 1)}>다음</button></div></div>
    <p className="pa-note">음수일수록 타국보다 저렴합니다. 매물 수로 가중하지 않은 연식별 가격비의 중앙값이며, 한 연식만 비교된 조합도 포함합니다.</p></>;
}
function Heatmap({data, focus, onPair, selected}) {
  const [page, setPage] = useState(0);
  const [onlyComparable, setOnlyComparable] = useState(true);
  const visibleModels = data.models.filter(model => !onlyComparable || data.pairs.some(pair => pair.model === model.model && (!focus || pair.country === focus)));
  const safePage = Math.min(page, Math.max(0, Math.ceil(visibleModels.length / 10) - 1));
  const models = visibleModels.slice(safePage * 10, safePage * 10 + 10);
  const countries = data.countries.filter(country => !focus || country.country === focus);
  const lookup = useMemo(() => new Map(data.pairs.map(pair => [pairKey(pair), pair])), [data]);
  if (!models.length || !countries.length) return <Empty/>;
  return <><div className="pa-heat-legend"><span><i className="is-cheap"/>저렴</span><span><i className="is-costly"/>비쌈</span><span>— 비교 불가 · 국가 열을 가로로 스크롤할 수 있습니다</span><label><input type="checkbox" checked={onlyComparable} onChange={event => {setOnlyComparable(event.target.checked); setPage(0);}}/>비교 가능한 모델만</label></div>
    <div className="pa-table-scroll" tabIndex="0" role="region" aria-label="국가별 모델 가격차 표"><table className="pa-table pa-heatmap"><caption className="pa-sr-only">상위 30개 모델의 타국 대비 가격 차이. 비교 가능한 동일 연식만 집계합니다.</caption><thead><tr><th>모델 / 국가</th>{countries.map(country => <th key={country.country}>{country.country}</th>)}</tr></thead><tbody>{models.map(model => <tr key={model.model}><th>{model.model}<small>전체 {number(model.count)}건</small></th>{countries.map(({country}) => {
      const pair = lookup.get(JSON.stringify([country, model.model]));
      return <td key={country}>{pair ? <button type="button" className={`${tone(pair.gapPercent)} ${selected === pairKey(pair) ? 'selected' : ''}`} style={{backgroundColor: pair.gapPercent < 0 ? `rgba(18,126,104,${.08 + Math.min(.3, Math.abs(pair.gapPercent) / 150)})` : `rgba(193,111,40,${.08 + Math.min(.3, pair.gapPercent / 150)})`}} onClick={() => onPair(pair)} title={`${country} / ${model.model}: ${percent(pair.gapPercent)}, ${pair.yearCount}개 연식, ${pair.count}건. 상세 가격 보기`}><strong>{percent(pair.gapPercent)}</strong><small>{pair.yearCount}개 연식 · {number(pair.count)}건</small></button> : <span className="pa-no-cell" title="표본 기준을 충족하는 같은 연식의 타국 매물이 부족합니다">—</span>}</td>;
    })}</tr>)}</tbody></table></div><div className="pa-pagination"><span>상위 {data.models.length}개 중 {visibleModels.length}개 표시 · {safePage + 1}/{Math.max(1, Math.ceil(visibleModels.length / 10))}</span><div><button disabled={!safePage} onClick={() => setPage(safePage - 1)}>이전 모델</button><button disabled={(safePage + 1) * 10 >= visibleModels.length} onClick={() => setPage(safePage + 1)}>다음 모델</button></div></div></>;
}
function MatchedChart({pair}) {
  const years = pair.years;
  const width = 840, height = 280, left = 78, right = 34, top = 22, bottom = 48;
  const low = years[0].year, high = years.at(-1).year;
  const x = year => low === high ? (width + left - right) / 2 : left + (year - low) / (high - low) * (width - left - right);
  const maximum = Math.max(...years.flatMap(year => [year.q3, year.referenceMedian])) * 1.12;
  const y = price => height - bottom - price / maximum * (height - bottom - top);
  const tickCount = Math.min(5, high - low + 1);
  const ticks = [...new Set(Array.from({length: tickCount}, (_, i) => Math.round(low + (high - low) * i / Math.max(1, tickCount - 1))))];
  return <div className="pa-chart-scroll"><svg className="pa-price-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${pair.country} ${pair.model}의 같은 연식별 가격 중앙값과 타국 기준가격. 아래 표에서 정확한 값을 확인할 수 있습니다.`}>
    {[0, .25, .5, .75, 1].map(t => <g key={t}><line x1={left} x2={width - right} y1={y(maximum * t)} y2={y(maximum * t)} stroke="#e4e9ed"/><text x={left - 10} y={y(maximum * t) + 4} textAnchor="end">{number(Math.round(maximum * t / 10000))}</text></g>)}
    <text x={left} y={13}>가격 (만원)</text>{ticks.map(year => <text key={year} x={x(year)} y={height - 24} textAnchor="middle">{year}</text>)}<text x={(left + width - right) / 2} y={height - 3} textAnchor="middle">제조연식</text>
    {years.map((year, i) => {const prev = years[i - 1]; return <g key={year.year}>
      {prev && prev.year === year.year - 1 && <><line x1={x(prev.year)} x2={x(year.year)} y1={y(prev.median)} y2={y(year.median)} stroke="#137e68" strokeWidth="3"/><line x1={x(prev.year)} x2={x(year.year)} y1={y(prev.referenceMedian)} y2={y(year.referenceMedian)} stroke="#526883" strokeWidth="2" strokeDasharray="5 4"/></>}
      <line x1={x(year.year)} x2={x(year.year)} y1={y(year.q1)} y2={y(year.q3)} stroke="#137e68" strokeWidth="8" opacity=".22"/>
      <circle cx={x(year.year)} cy={y(year.median)} r="5" fill="#137e68"><title>{`${year.year}년 ${pair.country}: ${money(year.median)}, ${year.count}건`}</title></circle>
      <rect x={x(year.year) - 4} y={y(year.referenceMedian) - 4} width="8" height="8" fill="#526883"><title>{`${year.year}년 타국 기준: ${money(year.referenceMedian)}, ${year.referenceCountries.length}개국`}</title></rect>
    </g>;})}
  </svg></div>;
}
export function PriceDetail({pair, pairs, onPair}) {
  if (!pair) return <Empty/>;
  const modelNames = [...new Set(pairs.map(item => item.model))].sort();
  const countries = pairs.filter(item => item.model === pair.model);
  return <><div className="pa-detail-controls"><label>비교 모델<select value={pair.model} onChange={event => onPair(pairs.find(item => item.model === event.target.value))}>{modelNames.map(model => <option key={model}>{model}</option>)}</select></label><label>기준 국가<select value={pair.country} onChange={event => onPair(countries.find(item => item.country === event.target.value))}>{countries.map(item => <option key={item.country}>{item.country}</option>)}</select></label><div className="pa-detail-result"><strong className={tone(pair.gapPercent)}>{percent(pair.gapPercent)}</strong><span>타국 대비 · {pair.yearCount}개 연식 비교<br/>{number(pair.count)}건 / 타국 {number(pair.referenceCount)}건</span></div></div>
    <div className="pa-chart-legend"><span><i className="pa-local"/>{pair.country} 중앙값</span><span><i className="pa-reference"/>타국 기준가격</span><span>세로 띠: 해당 국가의 중간 50% 가격</span></div>
    <MatchedChart pair={pair}/>
    <div className="pa-table-scroll" tabIndex="0" role="region" aria-label="연식별 가격 비교 상세"><table className="pa-table pa-detail-table"><thead><tr><th>제조연식</th><th>{pair.country} 중앙값</th><th>중간 50% 가격</th><th>타국 기준가격</th><th>가격 차이</th><th>비교 표본</th></tr></thead><tbody>{pair.years.map(year => <tr key={year.year}><th>{year.year}년</th><td><strong>{money(year.median)}</strong></td><td>{money(year.q1)} ~ {money(year.q3)}</td><td>{money(year.referenceMedian)}<small>{year.referenceCountries.map(country => `${country.country} ${money(country.median)} (${country.count}건)`).join(' · ')}</small></td><td className={tone(year.gapPercent)}><strong>{percent(year.gapPercent)}</strong></td><td>{year.count}건 / 타국 {year.referenceCount}건<small>{year.sourceCount}개 사이트 / 타국 {year.referenceCountries.length}개국</small></td></tr>)}</tbody></table></div>
    <p className="pa-note">각 연식의 타국 기준가격은 해당 국가를 제외한 국가별 중앙값의 중앙값입니다. 연식마다 비교 국가가 달라질 수 있습니다. 선은 연속된 제조연식만 연결하며, 과거 가격 추이나 감가상각률이 아닙니다.</p>
  </>;
}
export function PriceAnalysisContent({data, focus, onFocus, selection, onSelect}) {
  const pairs = data.pairs.filter(pair => !focus || pair.country === focus);
  const selected = pairs.find(pair => pairKey(pair) === selection) || pairs[0];
  const broad = data.countries.filter(country => country.broadEnough);
  const best = broad[0];
  const cheap = pairs.find(pair => pair.gapPercent < 0);
  const coverage = data.coverage;
  function choosePair(pair, scroll = false) {
    onSelect(pairKey(pair));
    if (scroll) document.getElementById('price-comparison-detail')?.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  return <><div className="pa-metrics">
    <div><span>비교 모델 기준 최저 상대가격 국가</span><strong>{best?.country || '종합 판단 보류'} {best && <b className={tone(best.gapPercent)}>{percent(best.gapPercent)}</b>}</strong><p>{best ? `${best.modelCount}개 모델 중 ${best.cheapModelCount}개가 타국보다 저렴` : '비교 모델 3개 이상인 국가가 필요합니다'}</p></div>
    <div><span>{focus || '전체 국가'}에서 가장 저렴한 모델 조합</span><strong>{cheap?.model || '비교 후보 없음'} {cheap && <b className="is-cheap">{percent(cheap.gapPercent)}</b>}</strong><p>{cheap ? `${cheap.country} · ${cheap.yearCount}개 연식 · ${number(cheap.count)}건` : '표본 기준을 충족한 저가 조합이 없습니다'}</p></div>
    <div><span>동일 모델·연식으로 비교 가능한 범위</span><strong>{coverage.comparedModelCount}<small> / {data.models.length}개 모델</small></strong><p>{coverage.comparedCountryCount}개국 · {number(coverage.comparedCount)}건 · {number(coverage.pairCount)}개 국가·모델 조합</p></div>
  </div><div className="pa-two-columns">
    <Panel number="01" title="어느 국가가 전반적으로 저렴할까?" description="같은 모델·연식끼리 비교한 가격 차이 · 0% = 타국과 동일"><CountryRanking countries={data.countries} focus={focus} onFocus={onFocus}/></Panel>
    <Panel number="02" title={`${focus || '국가별'} 특히 저렴한 모델`} description="타국 대비 가격이 낮은 조합부터 · 선택하면 비교 근거로 이동"><Opportunities key={focus} pairs={pairs} selected={selected && pairKey(selected)} onPair={pair => choosePair(pair, true)}/></Panel>
  </div>
  <Panel number="03" title="국가 × 모델 가격차 지도" description="같은 연식끼리 비교한 상대가격 · 음수는 저렴, 양수는 비쌈 · 칸을 선택해 상세 확인"><Heatmap data={data} focus={focus} selected={selected && pairKey(selected)} onPair={pair => choosePair(pair, true)}/></Panel>
  <div id="price-comparison-detail"><Panel number="04" title={selected ? `${selected.country} · ${selected.model}, 실제 가격 차이는?` : '모델별 가격 차이 확인'} description="같은 제조연식의 원화 가격과 표본을 직접 대조합니다"><PriceDetail pair={selected} pairs={pairs} onPair={choosePair}/></Panel></div>
  <details className="pa-method"><summary>계산 방식과 해석 범위</summary><ol><li>현재 필터에서 국가·정규화 모델이 확인된 매물 수 상위 30개 모델을 분석합니다. 제조연식이 미상·비정상인 매물은 가격 비교에서 제외합니다.</li><li>각 국가·모델·연식에 최소 {data.filters.minSample}건이 있고, 같은 모델·연식의 타국에도 국가당 최소 {data.filters.minSample}건이 있어야 비교합니다. 국가·모델 조합은 비교 연식이 {data.filters.minYears}개 이상이어야 표시합니다.</li><li>연식별 가격비 = 해당 국가 중앙값 ÷ 타국 국가별 중앙값의 중앙값. 모델별 가격차 = (연식별 가격비의 중앙값 − 1) × 100. 국가별 가격차 = (모델별 가격비의 중앙값 − 1) × 100. 연식·모델은 각각 동일 가중치입니다.</li><li>국가 종합 비교는 모델이 3개 이상인 경우에만 제시합니다. 소수 모델 결과나 일부 연식의 낮은 가격을 전체 시장의 저가로 일반화하지 마세요. 표본 기준은 통계적 유의성을 보장하지 않습니다.</li><li>월별 보정 환율을 적용한 판매 희망가격이며 실거래가가 아닙니다. 가동시간·상태·세부 사양·세금·운송비는 보정하지 않았습니다. 사이트·판매자 편향과 사이트 간 중복 게시가 있을 수 있어 예상 수익으로 해석할 수 없습니다.</li></ol><p>필터 내 가격 유효 매물 {number(coverage.scopedCount)}건 → 국가·모델 확인 {number(coverage.knownCount)}건 → 상위 모델 중 연식 확인 {number(coverage.validTopModelCount)}건 → 비교 기준 충족 {number(coverage.comparedCount)}건. 모델 미확인 {number(coverage.missingModelCount)}건, 국가 미상 {number(coverage.missingCountryCount)}건, 국가·모델 확인 매물 중 연식 미확인 {number(coverage.missingYearCount)}건. 등록일 미상은 가격 분석에 포함합니다.</p></details>
  <footer className="pa-footer">판매 희망가격 · 원화 기준 · 1,000만원 이상 건설기계 <span>집계 {new Date(data.generatedAt).toLocaleString('ko-KR')}</span></footer></>;
}

export default function MarketAnalytics({authFetchOptions, readApiResponse}) {
  const [filters, setFilters] = useState(defaults);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [focus, setFocus] = useState('');
  const [selection, setSelection] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetch(`/api/international-price-statistics?${new URLSearchParams(filters)}`, {...authFetchOptions, signal: controller.signal})
      .then(readApiResponse).then(data => {
        if (!controller.signal.aborted) {setPayload(data); setLoading(false);}
      }).catch(reason => {if (!controller.signal.aborted) {setError(reason.message); setLoading(false);}});
    return () => controller.abort();
  }, [filters, refresh, authFetchOptions, readApiResponse]);
  const update = (key, value) => {setFilters(current => ({...current, [key]: value})); setSelection('');};
  const options = payload?.filters || {};
  const activeFocus = payload?.countries.some(country => country.country === focus) ? focus : '';
  const years = Array.from({length: new Date().getFullYear() - 1949}, (_, i) => new Date().getFullYear() - i);
  return <section className="price-analysis" aria-labelledby="price-analysis-title" aria-busy={loading}>
    <header className="pa-header"><div><p>COUNTRY × MODEL / PRICE ANALYSIS</p><h2 id="price-analysis-title">어디서, 어떤 모델이 더 저렴할까?</h2><span>매물 수 상위 30개 모델 · 같은 모델·같은 연식의 가격만 비교합니다.</span></div><button type="button" onClick={() => setRefresh(value => value + 1)} disabled={loading}>{loading ? '분석 중…' : '↻ 데이터 새로고침'}</button></header>
    <div className="pa-filters" role="group" aria-label="가격 통계 필터">
      <label>수집 사이트<select value={filters.source} onChange={event => update('source', event.target.value)}><option value="">전체 사이트</option>{options.sources?.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>장비 종류<select value={filters.category} onChange={event => update('category', event.target.value)}><option value="">전체 건설기계</option>{options.categories?.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>국가·모델·연식당 표본<select value={filters.minSample} onChange={event => update('minSample', event.target.value)}>{[3, 5, 10].map(value => <option key={value} value={value}>{value}건 이상</option>)}</select></label>
      <label>모델별 비교 연식<select value={filters.minYears} onChange={event => update('minYears', event.target.value)}>{[1, 2, 3].map(value => <option key={value} value={value}>{value}개 이상</option>)}</select></label>
      <label>제조연식부터<select value={filters.yearFrom} onChange={event => update('yearFrom', event.target.value)}><option value="">제한 없음</option>{years.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>제조연식까지<select value={filters.yearTo} onChange={event => update('yearTo', event.target.value)}><option value="">제한 없음</option>{years.map(value => <option key={value}>{value}</option>)}</select></label>
      <button type="button" onClick={() => {setFilters(defaults); setFocus(''); setSelection('');}}>초기화</button>
    </div>
    {filters.yearFrom && filters.yearTo && Number(filters.yearFrom) > Number(filters.yearTo) && <p className="pa-error" role="alert">시작 연식이 종료 연식보다 큽니다. 연식 범위를 다시 선택하세요.</p>}
    <div className="pa-focus"><label>국가별 모델 살펴보기 <select value={activeFocus} onChange={event => {setFocus(event.target.value); setSelection('');}}><option value="">전체 국가</option>{payload?.countries.map(country => <option key={country.country}>{country.country}</option>)}</select></label>{activeFocus ? <button type="button" onClick={() => setFocus('')}>{activeFocus} 선택 해제 ×</button> : <span>국가를 선택해도 비교 기준은 타국 전체로 유지됩니다.</span>}</div>
    {loading ? <div className="pa-state" role="status">동일 모델·연식의 국가별 가격 차이를 계산하고 있습니다…</div> : error ? <div className="pa-state pa-error" role="alert">가격 통계를 불러오지 못했습니다. {error}<button type="button" onClick={() => setRefresh(value => value + 1)}>다시 시도</button></div> : payload && <PriceAnalysisContent data={payload} focus={activeFocus} onFocus={setFocus} selection={selection} onSelect={setSelection}/>}
  </section>;
}
