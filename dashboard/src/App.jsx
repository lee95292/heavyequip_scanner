import { useEffect, useMemo, useState } from "react";

const SORT_OPTIONS = [
  { value: "posted_desc", label: "등록일 최신순" },
  { value: "posted_asc", label: "등록일 오래된순" },
  { value: "price_desc", label: "가격 높은순" },
  { value: "price_asc", label: "가격 낮은순" }
];

function formatPrice(item) {
  if (item.priceValue) {
    return item.priceValue.toLocaleString("ko-KR") + "원";
  }
  return item.price || "-";
}

function compactNumber(value) {
  if (!value) {
    return "";
  }
  return String(value).replace(/,/g, "").trim();
}

function App() {
  const [payload, setPayload] = useState({ items: [], total: 0, databaseTotal: 0, pricedTotal: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [postedFrom, setPostedFrom] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [sort, setSort] = useState("posted_desc");

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("q", query.trim());
      }
      if (postedFrom) {
        params.set("posted_from", postedFrom);
      }
      if (compactNumber(priceMin)) {
        params.set("price_min", compactNumber(priceMin));
      }
      if (compactNumber(priceMax)) {
        params.set("price_max", compactNumber(priceMax));
      }
      params.set("sort", sort);

      setLoading(true);
      setError("");
      fetch(`/api/listings?${params.toString()}`, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`API ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          setPayload(data);
          setLoading(false);
        })
        .catch((fetchError) => {
          if (fetchError.name === "AbortError") {
            return;
          }
          setError(fetchError.message);
          setLoading(false);
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, postedFrom, priceMin, priceMax, sort]);

  const metrics = useMemo(() => {
    return {
      databaseTotal: payload.databaseTotal || 0,
      filteredTotal: payload.total || 0,
      priced: payload.pricedTotal || 0,
      latest: payload.latestPostedDate || "-"
    };
  }, [payload]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Heavy equipment scanner</p>
          <h1>중장비 매물 대시보드</h1>
        </div>
        <div className="meta">
          <span>DB {payload.db?.database || "heavyequip_scanner"}</span>
          <span>{payload.db ? `${payload.db.host}:${payload.db.port}` : "MySQL"}</span>
        </div>
      </header>

      <section className="summary-grid" aria-label="수집 현황">
        <div className="metric">
          <span>DB 전체 매물</span>
          <strong>{metrics.databaseTotal.toLocaleString("ko-KR")}</strong>
        </div>
        <div className="metric">
          <span>검색 결과</span>
          <strong>{metrics.filteredTotal.toLocaleString("ko-KR")}</strong>
        </div>
        <div className="metric">
          <span>가격 데이터</span>
          <strong>{metrics.priced.toLocaleString("ko-KR")}</strong>
        </div>
        <div className="metric">
          <span>최근 등록일</span>
          <strong>{metrics.latest}</strong>
        </div>
      </section>

      <section className="toolbar" aria-label="검색 및 정렬">
        <label className="search-box">
          <span>검색</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="예: 볼보 EC480, 두산, 010-"
          />
        </label>
        <label className="filter-box">
          <span>등록일자 이후</span>
          <input type="date" value={postedFrom} onChange={(event) => setPostedFrom(event.target.value)} />
        </label>
        <label className="filter-box">
          <span>최소 가격</span>
          <input
            inputMode="numeric"
            value={priceMin}
            onChange={(event) => setPriceMin(event.target.value)}
            placeholder="원"
          />
        </label>
        <label className="filter-box">
          <span>최대 가격</span>
          <input
            inputMode="numeric"
            value={priceMax}
            onChange={(event) => setPriceMax(event.target.value)}
            placeholder="원"
          />
        </label>
        <label className="select-box">
          <span>정렬</span>
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {loading && <div className="state">DB에서 데이터를 불러오는 중입니다.</div>}
      {error && <div className="state error">API 오류: {error}</div>}

      {!loading && !error && (
        <section className="table-wrap" aria-label="매물 목록">
          <table>
            <thead>
              <tr>
                <th>가격</th>
                <th>표시명</th>
                <th>모델명</th>
                <th>사이트</th>
                <th>등록일자</th>
                <th>연락처</th>
                <th>수집 링크</th>
              </tr>
            </thead>
            <tbody>
              {payload.items.map((item) => (
                <tr key={item.id}>
                  <td data-label="가격" className="price-cell">
                    {formatPrice(item)}
                  </td>
                  <td data-label="표시명">
                    <div className="primary-text">{item.displayName}</div>
                    <div className="sub-text">{[item.categoryName, item.location].filter(Boolean).join(" · ")}</div>
                  </td>
                  <td data-label="모델명">{item.modelName || "-"}</td>
                  <td data-label="사이트">
                    <span className="site-badge" title={item.sourceSite}>
                      {item.siteShort}
                    </span>
                  </td>
                  <td data-label="등록일자">{item.postedDate || "-"}</td>
                  <td data-label="연락처">{item.contact || "-"}</td>
                  <td data-label="수집 링크">
                    {item.link ? (
                      <a href={item.link} target="_blank" rel="noreferrer">
                        열기
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!payload.items.length && <div className="state">조건에 맞는 매물이 없습니다.</div>}
        </section>
      )}
    </main>
  );
}

export default App;
