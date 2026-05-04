import { useEffect, useMemo, useState } from "react";

const SORT_OPTIONS = [
  { value: "posted_desc", label: "등록일 최신순" },
  { value: "posted_asc", label: "등록일 오래된순" },
  { value: "price_desc", label: "가격 높은순" },
  { value: "price_asc", label: "가격 낮은순" }
];

const TASK_STATUS_OPTIONS = [
  { value: "", label: "전체 상태" },
  { value: "running", label: "실행중" },
  { value: "pending", label: "대기" },
  { value: "done", label: "완료" }
];

const AUTH_STORAGE_KEY = "heavyequip_dashboard_auth";
const AUTH_TTL_MS = 24 * 60 * 60 * 1000;

function ownerPhoneFromLocation() {
  if (typeof window === "undefined") {
    return "";
  }
  return new URLSearchParams(window.location.search).get("owner_phone") || "";
}

function readStoredAuth() {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(AUTH_STORAGE_KEY) || "null");
    if (!parsed?.password || !parsed?.expiresAt || Number(parsed.expiresAt) <= Date.now()) {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

function writeStoredAuth(password) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      password,
      expiresAt: Date.now() + AUTH_TTL_MS
    })
  );
}

function clearStoredAuth() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

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

function formatHours(value) {
  if (!value) {
    return "-";
  }
  return Number(value).toLocaleString("ko-KR") + "시간";
}

function statusLabel(status) {
  const labels = {
    running: "실행중",
    pending: "대기",
    done: "완료"
  };
  return labels[status] || status || "-";
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  return String(value).replace("T", " ").slice(0, 19);
}

function App() {
  const initialOwnerPhone = ownerPhoneFromLocation();
  const [activeTab, setActiveTab] = useState(initialOwnerPhone ? "ownerDetail" : "listings");
  const [authStatus, setAuthStatus] = useState("checking");
  const [authPassword, setAuthPassword] = useState("");
  const [authInput, setAuthInput] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [payload, setPayload] = useState({ items: [], total: 0, databaseTotal: 0, pricedTotal: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ownerPayload, setOwnerPayload] = useState({ items: [], total: 0, listingWithPhoneCount: 0 });
  const [ownerLoading, setOwnerLoading] = useState(false);
  const [ownerError, setOwnerError] = useState("");
  const [ownerQuery, setOwnerQuery] = useState("");
  const [ownerPhone, setOwnerPhone] = useState(initialOwnerPhone);
  const [ownerDetailPayload, setOwnerDetailPayload] = useState({ items: [], total: 0, displayPhone: "" });
  const [ownerDetailLoading, setOwnerDetailLoading] = useState(false);
  const [ownerDetailError, setOwnerDetailError] = useState("");
  const [taskPayload, setTaskPayload] = useState({ items: [], total: 0, statusCounts: [], siteCounts: [] });
  const [taskLoading, setTaskLoading] = useState(false);
  const [taskError, setTaskError] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [taskStatus, setTaskStatus] = useState("");
  const [query, setQuery] = useState("");
  const [postedFrom, setPostedFrom] = useState("");
  const [postedTo, setPostedTo] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [manufacturedFrom, setManufacturedFrom] = useState("");
  const [manufacturedTo, setManufacturedTo] = useState("");
  const [hoursMin, setHoursMin] = useState("");
  const [hoursMax, setHoursMax] = useState("");
  const [sort, setSort] = useState("posted_desc");

  const verifyPassword = (password) => {
    return fetch("/api/auth/verify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password })
    }).then((response) => {
      if (!response.ok) {
        throw new Error("비밀번호가 올바르지 않습니다.");
      }
      return response.json();
    });
  };

  useEffect(() => {
    const stored = readStoredAuth();
    if (!stored) {
      setAuthStatus("anonymous");
      return;
    }
    verifyPassword(stored.password)
      .then(() => {
        setAuthPassword(stored.password);
        setAuthStatus("authenticated");
      })
      .catch(() => {
        clearStoredAuth();
        setAuthPassword("");
        setAuthStatus("anonymous");
      });
  }, []);

  const authFetchOptions = useMemo(() => {
    return {
      headers: {
        "x-dashboard-password": authPassword
      }
    };
  }, [authPassword]);

  const handleLogin = (event) => {
    event.preventDefault();
    const password = authInput.trim();
    if (!password) {
      setAuthError("비밀번호를 입력해주세요.");
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    verifyPassword(password)
      .then(() => {
        writeStoredAuth(password);
        setAuthPassword(password);
        setAuthInput("");
        setAuthStatus("authenticated");
        setAuthLoading(false);
      })
      .catch((loginError) => {
        clearStoredAuth();
        setAuthError(loginError.message);
        setAuthLoading(false);
      });
  };

  const handleLogout = () => {
    clearStoredAuth();
    setAuthPassword("");
    setAuthStatus("anonymous");
  };

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "listings") {
      return undefined;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("q", query.trim());
      }
      if (postedFrom) {
        params.set("posted_from", postedFrom);
      }
      if (postedTo) {
        params.set("posted_to", postedTo);
      }
      if (compactNumber(priceMin)) {
        params.set("price_min", compactNumber(priceMin));
      }
      if (compactNumber(priceMax)) {
        params.set("price_max", compactNumber(priceMax));
      }
      if (manufacturedFrom) {
        params.set("manufactured_from", manufacturedFrom);
      }
      if (manufacturedTo) {
        params.set("manufactured_to", manufacturedTo);
      }
      if (compactNumber(hoursMin)) {
        params.set("hours_min", compactNumber(hoursMin));
      }
      if (compactNumber(hoursMax)) {
        params.set("hours_max", compactNumber(hoursMax));
      }
      params.set("sort", sort);

      setLoading(true);
      setError("");
      fetch(`/api/listings?${params.toString()}`, { ...authFetchOptions, signal: controller.signal })
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
  }, [
    activeTab,
    authFetchOptions,
    authStatus,
    query,
    postedFrom,
    postedTo,
    priceMin,
    priceMax,
    manufacturedFrom,
    manufacturedTo,
    hoursMin,
    hoursMax,
    sort
  ]);

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "owners") {
      return undefined;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (ownerQuery.trim()) {
        params.set("q", ownerQuery.trim());
      }
      params.set("limit", "1000");

      setOwnerLoading(true);
      setOwnerError("");
      fetch(`/api/owners?${params.toString()}`, { ...authFetchOptions, signal: controller.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`API ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          setOwnerPayload(data);
          setOwnerLoading(false);
        })
        .catch((fetchError) => {
          if (fetchError.name === "AbortError") {
            return;
          }
          setOwnerError(fetchError.message);
          setOwnerLoading(false);
        });
    }, 200);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [activeTab, authFetchOptions, authStatus, ownerQuery]);

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "ownerDetail" || !ownerPhone) {
      return undefined;
    }
    const controller = new AbortController();
    setOwnerDetailLoading(true);
    setOwnerDetailError("");
    fetch(`/api/owners/${encodeURIComponent(ownerPhone)}/listings`, { ...authFetchOptions, signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`API ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        setOwnerDetailPayload(data);
        setOwnerDetailLoading(false);
      })
      .catch((fetchError) => {
        if (fetchError.name === "AbortError") {
          return;
        }
        setOwnerDetailError(fetchError.message);
        setOwnerDetailLoading(false);
      });

    return () => controller.abort();
  }, [activeTab, authFetchOptions, authStatus, ownerPhone]);

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "tasks") {
      return undefined;
    }
    const controller = new AbortController();
    const loadTasks = () => {
      const params = new URLSearchParams();
      if (taskQuery.trim()) {
        params.set("q", taskQuery.trim());
      }
      if (taskStatus) {
        params.set("status", taskStatus);
      }
      params.set("limit", "800");

      setTaskLoading(true);
      setTaskError("");
      fetch(`/api/crawl-tasks?${params.toString()}`, { ...authFetchOptions, signal: controller.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`API ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          setTaskPayload(data);
          setTaskLoading(false);
        })
        .catch((fetchError) => {
          if (fetchError.name === "AbortError") {
            return;
          }
          setTaskError(fetchError.message);
          setTaskLoading(false);
        });
    };
    const timer = window.setTimeout(loadTasks, 150);
    const interval = window.setInterval(loadTasks, 30000);

    return () => {
      window.clearTimeout(timer);
      window.clearInterval(interval);
      controller.abort();
    };
  }, [activeTab, authFetchOptions, authStatus, taskQuery, taskStatus]);

  const metrics = useMemo(() => {
    return {
      databaseTotal: payload.databaseTotal || 0,
      filteredTotal: payload.total || 0,
      priced: payload.pricedTotal || 0,
      latest: payload.latestPostedDate || "-"
    };
  }, [payload]);

  const activeFilterCount = useMemo(() => {
    return [postedFrom, postedTo, priceMin, priceMax, manufacturedFrom, manufacturedTo, hoursMin, hoursMax].filter(
      (value) => String(value || "").trim()
    ).length;
  }, [postedFrom, postedTo, priceMin, priceMax, manufacturedFrom, manufacturedTo, hoursMin, hoursMax]);

  const clearFilters = () => {
    setPostedFrom("");
    setPostedTo("");
    setPriceMin("");
    setPriceMax("");
    setManufacturedFrom("");
    setManufacturedTo("");
    setHoursMin("");
    setHoursMax("");
  };

  const ownerMetrics = useMemo(() => {
    return {
      total: ownerPayload.total || 0,
      listingWithPhoneCount: ownerPayload.listingWithPhoneCount || 0,
      maxListingCount: ownerPayload.maxListingCount || 0,
      visible: ownerPayload.items?.length || 0
    };
  }, [ownerPayload]);

  const openOwnerWindow = (phone) => {
    window.open(`/?owner_phone=${encodeURIComponent(phone)}`, "_blank", "noopener,noreferrer");
  };

  const closeOwnerDetail = () => {
    setOwnerPhone("");
    setActiveTab("owners");
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", window.location.pathname);
    }
  };

  const taskMetrics = useMemo(() => {
    const byStatus = Object.fromEntries((taskPayload.statusCounts || []).map((item) => [item.status, item.count]));
    return {
      total: taskPayload.total || 0,
      running: byStatus.running || 0,
      pending: byStatus.pending || 0,
      done: byStatus.done || 0,
      latest: formatDateTime(taskPayload.latestTaskAt)
    };
  }, [taskPayload]);

  if (authStatus === "checking") {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <p className="eyebrow">Heavy equipment scanner</p>
          <h1>대시보드 확인 중</h1>
          <div className="state">저장된 로그인 정보를 확인하고 있습니다.</div>
        </section>
      </main>
    );
  }

  if (authStatus !== "authenticated") {
    return (
      <main className="auth-shell">
        <form className="auth-panel" onSubmit={handleLogin}>
          <p className="eyebrow">Heavy equipment scanner</p>
          <h1>대시보드 로그인</h1>
          <label className="search-box">
            <span>비밀번호</span>
            <input
              autoFocus
              type="password"
              value={authInput}
              onChange={(event) => setAuthInput(event.target.value)}
              placeholder="비밀번호 입력"
            />
          </label>
          {authError && <div className="auth-error">{authError}</div>}
          <button className="auth-button" type="submit" disabled={authLoading}>
            {authLoading ? "확인 중" : "로그인"}
          </button>
        </form>
      </main>
    );
  }

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
          <button type="button" onClick={handleLogout}>
            로그아웃
          </button>
        </div>
      </header>

      <nav className="tabbar" aria-label="대시보드 탭">
        <button
          className={activeTab === "listings" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("listings")}
        >
          매물 목록
        </button>
        <button
          className={activeTab === "owners" || activeTab === "ownerDetail" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("owners")}
        >
          차주별 매물
        </button>
        <button
          className={activeTab === "tasks" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("tasks")}
        >
          크롤링 작업
        </button>
      </nav>

      {activeTab === "listings" && (
        <>
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

          <details className="filter-panel">
            <summary>
              <span>필터</span>
              <strong>{activeFilterCount}</strong>
            </summary>
            <div className="filter-grid">
              <fieldset className="range-field">
                <legend>등록일자</legend>
                <input type="date" value={postedFrom} onChange={(event) => setPostedFrom(event.target.value)} />
                <span>~</span>
                <input type="date" value={postedTo} onChange={(event) => setPostedTo(event.target.value)} />
              </fieldset>
              <fieldset className="range-field">
                <legend>가격</legend>
                <input
                  inputMode="numeric"
                  value={priceMin}
                  onChange={(event) => setPriceMin(event.target.value)}
                  placeholder="최소"
                />
                <span>~</span>
                <input
                  inputMode="numeric"
                  value={priceMax}
                  onChange={(event) => setPriceMax(event.target.value)}
                  placeholder="최대"
                />
              </fieldset>
              <fieldset className="range-field">
                <legend>연식</legend>
                <input
                  type="month"
                  value={manufacturedFrom}
                  onChange={(event) => setManufacturedFrom(event.target.value)}
                />
                <span>~</span>
                <input
                  type="month"
                  value={manufacturedTo}
                  onChange={(event) => setManufacturedTo(event.target.value)}
                />
              </fieldset>
              <fieldset className="range-field">
                <legend>가동시간</legend>
                <input
                  inputMode="numeric"
                  value={hoursMin}
                  onChange={(event) => setHoursMin(event.target.value)}
                  placeholder="최소"
                />
                <span>~</span>
                <input
                  inputMode="numeric"
                  value={hoursMax}
                  onChange={(event) => setHoursMax(event.target.value)}
                  placeholder="최대"
                />
              </fieldset>
              <button className="clear-button" type="button" onClick={clearFilters}>
                초기화
              </button>
            </div>
          </details>

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
                    <th>연식</th>
                    <th>가동시간</th>
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
                        <div className="sub-text">
                          {[item.categoryName, item.location].filter(Boolean).join(" · ")}
                        </div>
                      </td>
                      <td data-label="모델명">{item.modelName || "-"}</td>
                      <td data-label="연식">{item.manufacturedYm || "-"}</td>
                      <td data-label="가동시간">{formatHours(item.operatingHoursValue)}</td>
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
        </>
      )}

      {activeTab === "owners" && (
        <>
          <section className="summary-grid" aria-label="차주별 매물 현황">
            <div className="metric">
              <span>전화번호 수</span>
              <strong>{ownerMetrics.total.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>전화번호 매칭 매물</span>
              <strong>{ownerMetrics.listingWithPhoneCount.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>최대 보유 매물</span>
              <strong>{ownerMetrics.maxListingCount.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>표시 중</span>
              <strong>{ownerMetrics.visible.toLocaleString("ko-KR")}</strong>
            </div>
          </section>

          <section className="toolbar owner-toolbar" aria-label="차주 검색">
            <label className="search-box">
              <span>차주 검색</span>
              <input
                value={ownerQuery}
                onChange={(event) => setOwnerQuery(event.target.value)}
                placeholder="전화번호, 상호, 사이트"
              />
            </label>
          </section>

          {ownerLoading && <div className="state">차주별 매물 수를 불러오는 중입니다.</div>}
          {ownerError && <div className="state error">API 오류: {ownerError}</div>}

          {!ownerLoading && !ownerError && (
            <section className="table-wrap" aria-label="차주별 매물 목록">
              <table className="owner-table">
                <thead>
                  <tr>
                    <th>전화번호</th>
                    <th>보유 매물 수</th>
                    <th>차주/상호</th>
                    <th>수집사이트</th>
                    <th>최근 등록</th>
                    <th>매물 목록</th>
                  </tr>
                </thead>
                <tbody>
                  {ownerPayload.items.map((owner) => (
                    <tr key={owner.phone}>
                      <td data-label="전화번호">
                        <button className="link-button" type="button" onClick={() => openOwnerWindow(owner.phone)}>
                          {owner.displayPhone}
                        </button>
                      </td>
                      <td data-label="보유 매물 수" className="price-cell">
                        {owner.listingCount.toLocaleString("ko-KR")}
                      </td>
                      <td data-label="차주/상호">
                        <div className="primary-text">{owner.sellerNames?.join(", ") || "-"}</div>
                      </td>
                      <td data-label="수집사이트">{owner.sourceSites?.join(", ") || "-"}</td>
                      <td data-label="최근 등록">{formatDateTime(owner.latestPostedAt)}</td>
                      <td data-label="매물 목록">
                        <button className="open-button" type="button" onClick={() => openOwnerWindow(owner.phone)}>
                          보기
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!ownerPayload.items.length && <div className="state">표시할 차주 매물이 없습니다.</div>}
            </section>
          )}
        </>
      )}

      {activeTab === "ownerDetail" && (
        <>
          <section className="detail-heading" aria-label="차주 매물 상세">
            <div>
              <p className="eyebrow">Owner listings</p>
              <h2>{ownerDetailPayload.displayPhone || ownerPhone}</h2>
            </div>
            <div className="detail-actions">
              <span>{(ownerDetailPayload.total || 0).toLocaleString("ko-KR")}건</span>
              <button type="button" onClick={closeOwnerDetail}>
                차주 목록
              </button>
            </div>
          </section>

          {ownerDetailLoading && <div className="state">차주 매물 목록을 불러오는 중입니다.</div>}
          {ownerDetailError && <div className="state error">API 오류: {ownerDetailError}</div>}

          {!ownerDetailLoading && !ownerDetailError && (
            <section className="table-wrap" aria-label="차주 업로드 매물 목록">
              <table>
                <thead>
                  <tr>
                    <th>가격</th>
                    <th>표시명</th>
                    <th>모델명</th>
                    <th>연식</th>
                    <th>사이트</th>
                    <th>등록일자</th>
                    <th>연락처</th>
                    <th>수집 링크</th>
                  </tr>
                </thead>
                <tbody>
                  {ownerDetailPayload.items.map((item) => (
                    <tr key={item.id}>
                      <td data-label="가격" className="price-cell">
                        {formatPrice(item)}
                      </td>
                      <td data-label="표시명">
                        <div className="primary-text">{item.displayName}</div>
                        <div className="sub-text">{[item.categoryName, item.location].filter(Boolean).join(" · ")}</div>
                      </td>
                      <td data-label="모델명">{item.modelName || "-"}</td>
                      <td data-label="연식">{item.manufacturedYm || "-"}</td>
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
              {!ownerDetailPayload.items.length && <div className="state">해당 전화번호의 매물이 없습니다.</div>}
            </section>
          )}
        </>
      )}

      {activeTab === "tasks" && (
        <>
          <section className="summary-grid" aria-label="크롤링 작업 현황">
            <div className="metric">
              <span>전체 작업</span>
              <strong>{taskMetrics.total.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>실행중</span>
              <strong>{taskMetrics.running.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>대기</span>
              <strong>{taskMetrics.pending.toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>마지막 크롤링</span>
              <strong>{taskMetrics.latest}</strong>
            </div>
          </section>

          <section className="toolbar task-toolbar" aria-label="작업 검색">
            <label className="search-box">
              <span>작업 검색</span>
              <input
                value={taskQuery}
                onChange={(event) => setTaskQuery(event.target.value)}
                placeholder="사이트, 카테고리, URL"
              />
            </label>
            <label className="select-box">
              <span>상태</span>
              <select value={taskStatus} onChange={(event) => setTaskStatus(event.target.value)}>
                {TASK_STATUS_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </section>

          {!!taskPayload.siteCounts?.length && (
            <section className="site-strip" aria-label="사이트별 작업">
              {taskPayload.siteCounts.map((site) => (
                <div className="site-chip" key={site.siteSlug || site.siteName}>
                  <span>{site.siteName}</span>
                  <strong>{site.count.toLocaleString("ko-KR")}</strong>
                  <small>{formatDateTime(site.latestTaskAt)}</small>
                </div>
              ))}
            </section>
          )}

          {taskLoading && <div className="state">크롤링 작업을 불러오는 중입니다.</div>}
          {taskError && <div className="state error">API 오류: {taskError}</div>}

          {!taskLoading && !taskError && (
            <section className="table-wrap" aria-label="크롤링 작업 목록">
              <table className="task-table">
                <thead>
                  <tr>
                    <th>상태</th>
                    <th>사이트</th>
                    <th>작업</th>
                    <th>카테고리</th>
                    <th>마지막 크롤링</th>
                    <th>다음 실행</th>
                    <th>시도</th>
                    <th>대상 링크</th>
                  </tr>
                </thead>
                <tbody>
                  {taskPayload.items.map((task) => (
                    <tr key={task.id}>
                      <td data-label="상태">
                        <span className={`status-pill ${task.status}`}>{statusLabel(task.status)}</span>
                      </td>
                      <td data-label="사이트">
                        <div className="primary-text">{task.siteName}</div>
                        <div className="sub-text">{task.origin || task.siteSlug}</div>
                      </td>
                      <td data-label="작업">
                        <div className="primary-text">{task.taskType}</div>
                        <div className="sub-text">ID {task.id}</div>
                      </td>
                      <td data-label="카테고리">
                        <div className="primary-text">{task.categoryName || "-"}</div>
                        <div className="sub-text">
                          {[task.categoryCode, task.page && `page ${task.page}`].filter(Boolean).join(" · ")}
                        </div>
                      </td>
                      <td data-label="마지막 크롤링">{formatDateTime(task.lastCrawledAt)}</td>
                      <td data-label="다음 실행">{formatDateTime(task.nextRunAt)}</td>
                      <td data-label="시도">
                        <div className="primary-text">{task.attempts}</div>
                        <div className="sub-text">{task.lastStatusCode ? `HTTP ${task.lastStatusCode}` : ""}</div>
                      </td>
                      <td data-label="대상 링크">
                        {task.link ? (
                          <a href={task.link} target="_blank" rel="noreferrer" title={task.link}>
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
              {!taskPayload.items.length && <div className="state">표시할 크롤링 작업이 없습니다.</div>}
            </section>
          )}
        </>
      )}
    </main>
  );
}

export default App;
