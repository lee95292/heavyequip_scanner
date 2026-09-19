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
  { value: "failed", label: "실패" },
  { value: "done", label: "완료" }
];

const AUTH_STORAGE_KEY = "heavyequip_dashboard_auth";
const AUTH_TTL_MS = 24 * 60 * 60 * 1000;
const LISTING_PAGE_SIZE = 50;

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
  if (item.priceCurrency && item.nativePriceAmount !== null) {
    const native = item.priceCurrency === "KRW"
      ? `${Number(item.nativePriceAmount).toLocaleString("ko-KR")}원`
      : `${item.priceCurrency} ${Number(item.nativePriceAmount).toLocaleString("ko-KR")}`;
    if (item.priceCurrency !== "KRW" && item.priceValue) {
      return `${native} · 약 ${item.priceValue.toLocaleString("ko-KR")}원`;
    }
    return native;
  }
  if (item.priceValue) {
    return item.priceValue.toLocaleString("ko-KR") + "원";
  }
  return item.price || "-";
}

function formatFxRate(item) {
  if (
    item.nativePriceAmount === null
    || !item.priceFxRateKrw
    || !item.priceCurrency
    || item.priceCurrency === "KRW"
  ) {
    return "";
  }
  return `1 ${item.priceCurrency} = ${Number(item.priceFxRateKrw).toLocaleString("ko-KR", {
    maximumFractionDigits: 4
  })}원 · ${item.priceFxRateDate || "기준일 미상"}`;
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

function formatKrw(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR", {
    style: "currency",
    currency: "KRW",
    maximumFractionDigits: 0
  }).format(Math.round(amount));
}

async function readApiResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || data.detail || `API ${response.status}`);
  }
  return data;
}

function statusLabel(status) {
  const labels = {
    running: "실행중",
    pending: "대기",
    failed: "실패",
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

function readinessLabel(value) {
  const labels = {
    response_capture_required: "응답 캡처 필요",
    research_pending: "추가 조사 필요",
    ready: "연동 준비 완료",
    collection_enabled: "수집 활성",
    blocked_by_waf: "자동 접근 차단"
  };
  return labels[value] || value || "미확인";
}

function filenameFromDisposition(disposition, fallback) {
  const header = String(disposition || "");
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ""));
    } catch {
      return fallback;
    }
  }
  const quotedMatch = header.match(/filename="([^"]+)"/i);
  return quotedMatch?.[1] || fallback;
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function isCsvResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/html")) {
    return false;
  }
  return contentType.includes("text/csv") || response.headers.has("x-listing-link-count");
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
  const [ownerCsvLoading, setOwnerCsvLoading] = useState(false);
  const [ownerCsvError, setOwnerCsvError] = useState("");
  const [ownerCsvMessage, setOwnerCsvMessage] = useState("");
  const [taskPayload, setTaskPayload] = useState({ items: [], total: 0, statusCounts: [], siteCounts: [] });
  const [taskLoading, setTaskLoading] = useState(false);
  const [taskError, setTaskError] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [taskStatus, setTaskStatus] = useState("");
  const [selectedTaskIds, setSelectedTaskIds] = useState([]);
  const [taskStartQueuedIds, setTaskStartQueuedIds] = useState([]);
  const [taskStartLoading, setTaskStartLoading] = useState(false);
  const [taskStartError, setTaskStartError] = useState("");
  const [taskStartMessage, setTaskStartMessage] = useState("");
  const [taskRefreshKey, setTaskRefreshKey] = useState(0);
  const [internationalPayload, setInternationalPayload] = useState({
    sources: [],
    summary: {},
    requestPolicy: {}
  });
  const [internationalLoading, setInternationalLoading] = useState(false);
  const [internationalError, setInternationalError] = useState("");
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
  const [sourceScope, setSourceScope] = useState("all");
  const [sourceSite, setSourceSite] = useState("");
  const [sourceSiteOptions, setSourceSiteOptions] = useState([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [predictionQuery, setPredictionQuery] = useState("");
  const [predictionYear, setPredictionYear] = useState("");
  const [predictionSuggestions, setPredictionSuggestions] = useState([]);
  const [predictionSelected, setPredictionSelected] = useState(null);
  const [predictionInputFocused, setPredictionInputFocused] = useState(false);
  const [predictionSuggestionsOpen, setPredictionSuggestionsOpen] = useState(false);
  const [predictionSuggestionsLoading, setPredictionSuggestionsLoading] = useState(false);
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [predictionError, setPredictionError] = useState("");
  const [predictionResult, setPredictionResult] = useState(null);

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

  useEffect(() => {
    if (authStatus !== "authenticated") {
      return undefined;
    }
    const controller = new AbortController();
    fetch("/api/listing-sources", { ...authFetchOptions, signal: controller.signal })
      .then(readApiResponse)
      .then((data) => setSourceSiteOptions(data.items || []))
      .catch((fetchError) => {
        if (fetchError.name !== "AbortError") setSourceSiteOptions([]);
      });
    return () => controller.abort();
  }, [authFetchOptions, authStatus]);

  const listingQueryBase = useMemo(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (postedFrom) params.set("posted_from", postedFrom);
    if (postedTo) params.set("posted_to", postedTo);
    if (compactNumber(priceMin)) params.set("price_min", compactNumber(priceMin));
    if (compactNumber(priceMax)) params.set("price_max", compactNumber(priceMax));
    if (manufacturedFrom) params.set("manufactured_from", manufacturedFrom);
    if (manufacturedTo) params.set("manufactured_to", manufacturedTo);
    if (compactNumber(hoursMin)) params.set("hours_min", compactNumber(hoursMin));
    if (compactNumber(hoursMax)) params.set("hours_max", compactNumber(hoursMax));
    params.set("sort", sort);
    params.set("source_scope", sourceScope);
    if (sourceSite) params.set("source_site", sourceSite);
    params.set("limit", String(LISTING_PAGE_SIZE));
    return params.toString();
  }, [query, postedFrom, postedTo, priceMin, priceMax, manufacturedFrom, manufacturedTo, hoursMin, hoursMax, sort, sourceScope, sourceSite]);

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
      const params = new URLSearchParams(listingQueryBase);
      params.set("offset", "0");

      setLoading(true);
      setLoadingMore(false);
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
    listingQueryBase
  ]);

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "listings" || loading || !payload.hasMore) {
      return undefined;
    }
    const controller = new AbortController();
    let requesting = false;
    const handleScroll = () => {
      const documentHeight = document.documentElement.scrollHeight;
      const viewportBottom = window.scrollY + window.innerHeight;
      if (requesting || documentHeight <= 0 || viewportBottom < documentHeight * 0.9) return;
      requesting = true;
      setLoadingMore(true);
      const params = new URLSearchParams(listingQueryBase);
      params.set("offset", String(payload.nextOffset || payload.items.length));
      fetch(`/api/listings?${params.toString()}`, { ...authFetchOptions, signal: controller.signal })
        .then(readApiResponse)
        .then((data) => {
          setPayload((current) => ({ ...data, items: [...current.items, ...data.items] }));
          setLoadingMore(false);
          requesting = false;
        })
        .catch((fetchError) => {
          if (fetchError.name !== "AbortError") setError(fetchError.message);
          setLoadingMore(false);
          requesting = false;
        });
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => {
      controller.abort();
      window.removeEventListener("scroll", handleScroll);
    };
  }, [activeTab, authFetchOptions, authStatus, listingQueryBase, loading, payload.hasMore, payload.items.length, payload.nextOffset]);

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
    setOwnerCsvError("");
    setOwnerCsvMessage("");
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
  }, [activeTab, authFetchOptions, authStatus, taskQuery, taskRefreshKey, taskStatus]);

  useEffect(() => {
    if (authStatus !== "authenticated" || activeTab !== "international") {
      return undefined;
    }
    const controller = new AbortController();
    setInternationalLoading(true);
    setInternationalError("");
    fetch("/api/international-sources", { ...authFetchOptions, signal: controller.signal })
      .then(readApiResponse)
      .then((data) => {
        setInternationalPayload(data);
        setInternationalLoading(false);
      })
      .catch((fetchError) => {
        if (fetchError.name === "AbortError") {
          return;
        }
        setInternationalError(fetchError.message);
        setInternationalLoading(false);
      });
    return () => controller.abort();
  }, [activeTab, authFetchOptions, authStatus]);

  useEffect(() => {
    const queryText = predictionQuery.trim();
    const hasSelectedModel = predictionSelected?.modelName === queryText;
    if (
      authStatus !== "authenticated" ||
      activeTab !== "prediction" ||
      !predictionInputFocused ||
      !queryText ||
      hasSelectedModel
    ) {
      setPredictionSuggestionsOpen(false);
      if (!queryText) {
        setPredictionSuggestions([]);
        setPredictionSuggestionsLoading(false);
      }
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ q: queryText, limit: "12" });
      setPredictionSuggestionsLoading(true);
      setPredictionError("");
      fetch(`/api/prediction/models?${params.toString()}`, {
        ...authFetchOptions,
        signal: controller.signal
      })
        .then(readApiResponse)
        .then((data) => {
          const items = Array.isArray(data.items)
            ? data.items.map((item) => ({ ...item, modelVersion: data.modelVersion }))
            : [];
          setPredictionSuggestions(items);
          setPredictionSuggestionsOpen(true);
          setPredictionSuggestionsLoading(false);
        })
        .catch((fetchError) => {
          if (fetchError.name === "AbortError") {
            return;
          }
          setPredictionSuggestions([]);
          setPredictionSuggestionsOpen(false);
          setPredictionError(fetchError.message);
          setPredictionSuggestionsLoading(false);
        });
    }, 200);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    activeTab,
    authFetchOptions,
    authStatus,
    predictionInputFocused,
    predictionQuery,
    predictionSelected
  ]);

  const metrics = useMemo(() => {
    return {
      databaseTotal: payload.databaseTotal || 0,
      filteredTotal: payload.total || 0,
      priced: payload.pricedTotal || 0,
      latest: payload.latestPostedDate || "-"
    };
  }, [payload]);

  const activeFilterCount = useMemo(() => {
    return [postedFrom, postedTo, priceMin, priceMax, manufacturedFrom, manufacturedTo, hoursMin, hoursMax, sourceScope === "all" ? "" : sourceScope, sourceSite].filter(
      (value) => String(value || "").trim()
    ).length;
  }, [postedFrom, postedTo, priceMin, priceMax, manufacturedFrom, manufacturedTo, hoursMin, hoursMax, sourceScope, sourceSite]);

  const clearFilters = () => {
    setPostedFrom("");
    setPostedTo("");
    setPriceMin("");
    setPriceMax("");
    setManufacturedFrom("");
    setManufacturedTo("");
    setHoursMin("");
    setHoursMax("");
    setSourceScope("all");
    setSourceSite("");
  };

  const handlePredictionQueryChange = (event) => {
    const value = event.target.value;
    setPredictionQuery(value);
    if (predictionSelected?.modelName !== value.trim()) {
      setPredictionSelected(null);
    }
    setPredictionResult(null);
    setPredictionError("");
    setPredictionSuggestions([]);
    setPredictionSuggestionsLoading(Boolean(value.trim()));
    setPredictionSuggestionsOpen(Boolean(value.trim()));
  };

  const selectPredictionModel = (suggestion) => {
    setPredictionSelected(suggestion);
    setPredictionQuery(suggestion.modelName);
    setPredictionSuggestions([]);
    setPredictionSuggestionsLoading(false);
    setPredictionSuggestionsOpen(false);
    setPredictionResult(null);
    setPredictionError("");
  };

  const handlePredictionSubmit = (event) => {
    event.preventDefault();
    const manufacturedYear = Number(predictionYear);
    const maximumYear = new Date().getFullYear() + 1;
    if (!predictionSelected || predictionSelected.modelName !== predictionQuery.trim()) {
      setPredictionError("검색 결과에서 모델을 선택해주세요.");
      return;
    }
    if (!Number.isInteger(manufacturedYear) || manufacturedYear < 1970 || manufacturedYear > maximumYear) {
      setPredictionError(`연식은 1970년부터 ${maximumYear}년 사이로 입력해주세요.`);
      return;
    }

    setPredictionLoading(true);
    setPredictionError("");
    setPredictionResult(null);
    fetch("/api/prediction/price", {
      method: "POST",
      headers: {
        ...authFetchOptions.headers,
        "content-type": "application/json"
      },
      body: JSON.stringify({
        suggestionId: predictionSelected.id,
        modelVersion: predictionSelected.modelVersion,
        manufacturedYear
      })
    })
      .then(readApiResponse)
      .then((data) => {
        setPredictionResult(data);
        setPredictionLoading(false);
      })
      .catch((predictionRequestError) => {
        setPredictionError(predictionRequestError.message);
        setPredictionLoading(false);
      });
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

  const handleDownloadOwnerLinksCsv = () => {
    if (!ownerPhone || ownerCsvLoading) {
      return;
    }
    setOwnerCsvLoading(true);
    setOwnerCsvError("");
    setOwnerCsvMessage("");
    fetch(`/api/owners/${encodeURIComponent(ownerPhone)}/listing-links.csv`, authFetchOptions)
      .then(async (response) => {
        if (!response.ok) {
          let message = `API ${response.status}`;
          try {
            const data = await response.json();
            message = data.detail || data.error || message;
          } catch {
            // Keep the status-only message when the response is not JSON.
          }
          throw new Error(message);
        }

        if (!isCsvResponse(response)) {
          const text = await response.text();
          const preview = text.replace(/\s+/g, " ").slice(0, 80);
          throw new Error(`CSV 응답이 아닙니다. 서버가 HTML/다른 응답을 반환했습니다: ${preview}`);
        }

        const blob = await response.blob();
        const filename = filenameFromDisposition(
          response.headers.get("content-disposition"),
          `owner-listing-links-${ownerPhone}.csv`
        );
        const exportedCount = Number(response.headers.get("x-listing-link-count") || 0);
        const skippedDeleted = Number(response.headers.get("x-skipped-deleted-count") || 0);
        const failedChecks = Number(response.headers.get("x-failed-check-count") || 0);
        const summary = [`${exportedCount.toLocaleString("ko-KR")}건`];
        if (skippedDeleted) {
          summary.push(`삭제 의심 ${skippedDeleted.toLocaleString("ko-KR")}건 제외`);
        }
        if (failedChecks) {
          summary.push(`확인 실패 ${failedChecks.toLocaleString("ko-KR")}건은 포함`);
        }

        downloadBlob(blob, filename);
        setOwnerCsvMessage(`CSV 다운로드 완료 (${summary.join(", ")})`);
      })
      .catch((downloadError) => {
        setOwnerCsvError(downloadError.message);
      })
      .finally(() => {
        setOwnerCsvLoading(false);
      });
  };

  const taskMetrics = useMemo(() => {
    const byStatus = Object.fromEntries((taskPayload.statusCounts || []).map((item) => [item.status, item.count]));
    return {
      total: taskPayload.total || 0,
      running: byStatus.running || 0,
      pending: byStatus.pending || 0,
      failed: byStatus.failed || 0,
      done: byStatus.done || 0,
      latest: formatDateTime(taskPayload.latestTaskAt)
    };
  }, [taskPayload]);

  const taskStartQueuedIdSet = useMemo(() => new Set(taskStartQueuedIds), [taskStartQueuedIds]);
  const selectedTaskIdSet = useMemo(() => new Set(selectedTaskIds), [selectedTaskIds]);
  const isTaskStartQueued = (task) => {
    return task.status === "pending" && (task.manualStartRequestedAt || taskStartQueuedIdSet.has(task.id));
  };
  const visibleStartableTaskIds = useMemo(() => {
    return (taskPayload.items || [])
      .filter((task) => task.status === "pending" && !task.manualStartRequestedAt && !taskStartQueuedIdSet.has(task.id))
      .map((task) => task.id);
  }, [taskPayload, taskStartQueuedIdSet]);
  const allVisiblePendingSelected =
    visibleStartableTaskIds.length > 0 && visibleStartableTaskIds.every((id) => selectedTaskIdSet.has(id));

  useEffect(() => {
    const startableIds = new Set(visibleStartableTaskIds);
    setSelectedTaskIds((current) => {
      const next = current.filter((id) => startableIds.has(id));
      return next.length === current.length ? current : next;
    });
  }, [visibleStartableTaskIds]);

  useEffect(() => {
    const visibleTasks = new Map((taskPayload.items || []).map((task) => [task.id, task]));
    setTaskStartQueuedIds((current) => {
      const next = current.filter((id) => {
        const task = visibleTasks.get(id);
        return !task || (task.status === "pending" && Boolean(task.manualStartRequestedAt));
      });
      return next.length === current.length ? current : next;
    });
  }, [taskPayload]);

  const toggleVisiblePendingTasks = (checked) => {
    setTaskStartError("");
    setTaskStartMessage("");
    if (checked) {
      setSelectedTaskIds((current) => [...new Set([...current, ...visibleStartableTaskIds])]);
      return;
    }
    const visibleIds = new Set(visibleStartableTaskIds);
    setSelectedTaskIds((current) => current.filter((id) => !visibleIds.has(id)));
  };

  const toggleTaskSelection = (taskId, checked) => {
    setTaskStartError("");
    setTaskStartMessage("");
    setSelectedTaskIds((current) => {
      if (checked) {
        return current.includes(taskId) ? current : [...current, taskId];
      }
      return current.filter((id) => id !== taskId);
    });
  };

  const handleStartSelectedTasks = () => {
    if (!selectedTaskIds.length || taskStartLoading) {
      return;
    }
    setTaskStartLoading(true);
    setTaskStartError("");
    setTaskStartMessage("");
    fetch("/api/crawl-tasks/start", {
      method: "POST",
      headers: {
        ...authFetchOptions.headers,
        "content-type": "application/json"
      },
      body: JSON.stringify({ taskIds: selectedTaskIds })
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || data.error || `API ${response.status}`);
        }
        return data;
      })
      .then((data) => {
        const startedCount = Number(data.startedTaskCount || 0);
        const alreadyRequestedCount = Number(data.alreadyRequestedTaskCount || 0);
        const startedTaskIds = (data.startedTaskIds || []).map(Number).filter((id) => Number.isSafeInteger(id) && id > 0);
        const sites = (data.runs || []).map((run) => run.siteSlug).filter(Boolean).join(", ");
        const messageParts = [];
        if (startedCount) {
          messageParts.push(`${startedCount.toLocaleString("ko-KR")}개 작업을 시작 대기로 등록했습니다`);
        }
        if (alreadyRequestedCount) {
          messageParts.push(`${alreadyRequestedCount.toLocaleString("ko-KR")}개는 이미 시작 대기 중입니다`);
        }
        const message = messageParts.length
          ? `${messageParts.join(", ")}${sites ? ` (${sites})` : ""}.`
          : "시작 가능한 대기 작업이 없습니다.";
        if (startedTaskIds.length) {
          setTaskStartQueuedIds((current) => [...new Set([...current, ...startedTaskIds])]);
        }
        setSelectedTaskIds([]);
        setTaskStartMessage(message);
        setTaskRefreshKey((value) => value + 1);
      })
      .catch((startError) => {
        setTaskStartError(startError.message);
      })
      .finally(() => {
        setTaskStartLoading(false);
      });
  };

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
        <button
          className={activeTab === "international" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("international")}
        >
          국제 사이트 분석
        </button>
        <button
          className={activeTab === "prediction" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("prediction")}
        >
          가격 예측
        </button>
      </nav>

      {activeTab === "international" && (
        <section className="international-page" aria-labelledby="international-title">
          <header className="international-heading">
            <div>
              <p className="eyebrow">International sources</p>
              <h2 id="international-title">국제 중고중장비 수집 분석</h2>
            </div>
            <p>공식 공개 목록을 기준으로 수집 표면, 역순 동기화 방식, 파싱 필드를 비교합니다.</p>
            <button
              className="clear-button"
              type="button"
              onClick={() => {
                setSourceScope("international");
                setSourceSite("");
                setActiveTab("listings");
              }}
            >
              수집된 국제 매물 보기
            </button>
          </header>

          <section className="summary-grid" aria-label="국제 사이트 분석 현황">
            <div className="metric">
              <span>조사 사이트</span>
              <strong>{Number(internationalPayload.summary?.sourceCount || 0).toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>파서 준비</span>
              <strong>{Number(internationalPayload.summary?.parserReadyCount || 0).toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>요청 활성화</span>
              <strong>{Number(internationalPayload.summary?.enabledCount || 0).toLocaleString("ko-KR")}</strong>
            </div>
            <div className="metric">
              <span>수집 매물</span>
              <strong>{Number(internationalPayload.summary?.listingCount || 0).toLocaleString("ko-KR")}</strong>
            </div>
          </section>

          <div className="request-policy" role="note">
            <strong>현재 단계: 공개 목록 수집 활성</strong>
            <span>{internationalPayload.requestPolicy?.message || "분석 정보를 불러오고 있습니다."}</span>
            <small>{internationalPayload.requestPolicy?.resumeRule || ""}</small>
          </div>

          {internationalLoading && <div className="state">국제 사이트 분석 정보를 불러오는 중입니다.</div>}
          {internationalError && <div className="state error">API 오류: {internationalError}</div>}

          {!internationalLoading && !internationalError && (
            <div className="source-grid">
              {(internationalPayload.sources || []).map((source) => (
                <article className="source-card" key={source.slug}>
                  <header>
                    <div>
                      <span className={`readiness-pill ${source.readiness}`}>
                        {readinessLabel(source.readiness)}
                      </span>
                      <h3>{source.name}</h3>
                      <p>{source.region}</p>
                    </div>
                    <a href={source.listingUrl} target="_blank" rel="noreferrer">
                      공식 목록
                    </a>
                  </header>

                  <dl className="source-facts">
                    <div><dt>수집 표면</dt><dd>{source.surface}</dd></div>
                    <div><dt>API 상태</dt><dd>{source.apiStatus}</dd></div>
                    <div><dt>응답</dt><dd>{source.method} · {source.responseFormat}</dd></div>
                    <div><dt>정렬</dt><dd>{source.ordering}</dd></div>
                    <div><dt>페이지</dt><dd>{source.pagination}</dd></div>
                    <div><dt>프록시 검증</dt><dd>{source.proxyProbe || "미확인"}</dd></div>
                    <div><dt>범위</dt><dd>{source.categoryScope}</dd></div>
                  </dl>

                  <div className="field-map">
                    <strong>확인·정규화 대상 필드</strong>
                    <div>
                      {(source.fields || []).map((field) => <span key={field}>{field}</span>)}
                    </div>
                  </div>

                  <p className="source-note">{source.notes}</p>

                  <footer>
                    <span>DB 매물 <strong>{Number(source.stats?.listingCount || 0).toLocaleString("ko-KR")}</strong></span>
                    <span>작업 <strong>{Number(source.stats?.tasks?.total || 0).toLocaleString("ko-KR")}</strong></span>
                    <span>체크포인트 <strong>{source.stats?.syncStreams?.length || 0}</strong></span>
                  </footer>
                  {(source.stats?.syncStreams || []).slice(0, 2).map((stream) => (
                    <p className={`sync-state ${stream.status === "failed" ? "error" : ""}`} key={stream.streamKey}>
                      {stream.streamKey} · {stream.status} · {Number(stream.itemCount || 0).toLocaleString("ko-KR")}건
                      {stream.stopReason ? ` · ${stream.stopReason}` : ""}
                      {stream.lastError ? ` · ${stream.lastError}` : ""}
                    </p>
                  ))}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {activeTab === "prediction" && (
        <section className="prediction-page" aria-labelledby="prediction-title">
          <header className="prediction-heading">
            <div>
              <p className="eyebrow">Price prediction</p>
              <h2 id="prediction-title">중장비 가격 예측</h2>
            </div>
            <p>학습된 매물 데이터의 모델명·카테고리·연식을 바탕으로 가격을 계산합니다.</p>
          </header>

          <form className="prediction-form" onSubmit={handlePredictionSubmit}>
            <div
              className="prediction-autocomplete"
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) {
                  setPredictionInputFocused(false);
                  setPredictionSuggestionsOpen(false);
                }
              }}
            >
              <label htmlFor="prediction-model">모델명</label>
              <input
                id="prediction-model"
                role="combobox"
                aria-autocomplete="list"
                aria-controls="prediction-model-suggestions"
                aria-expanded={predictionSuggestionsOpen}
                autoComplete="off"
                disabled={predictionLoading}
                value={predictionQuery}
                onChange={handlePredictionQueryChange}
                onFocus={() => {
                  setPredictionInputFocused(true);
                  if (predictionQuery.trim() && !predictionSelected) {
                    setPredictionSuggestionsOpen(true);
                  }
                }}
                placeholder="예: EC480, DX380LC"
              />
              {predictionSuggestionsOpen && (
                <ul id="prediction-model-suggestions" className="prediction-suggestions" role="listbox">
                  {predictionSuggestionsLoading && <li className="prediction-suggestion-state">검색 중...</li>}
                  {!predictionSuggestionsLoading && !predictionSuggestions.length && (
                    <li className="prediction-suggestion-state">일치하는 학습 모델이 없습니다.</li>
                  )}
                  {!predictionSuggestionsLoading &&
                    predictionSuggestions.map((suggestion) => (
                      <li key={suggestion.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={predictionSelected?.id === suggestion.id}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectPredictionModel(suggestion)}
                        >
                          <span>{suggestion.modelName}</span>
                          <small>
                            {[suggestion.manufacturer, suggestion.categoryName].filter(Boolean).join(" · ") ||
                              "분류 정보 없음"}
                          </small>
                          <strong>{Number(suggestion.sampleCount || 0).toLocaleString("ko-KR")}건 학습</strong>
                        </button>
                      </li>
                    ))}
                </ul>
              )}
            </div>

            <label className="prediction-year" htmlFor="prediction-year">
              <span>연식</span>
              <input
                id="prediction-year"
                type="number"
                inputMode="numeric"
                min="1970"
                max={new Date().getFullYear() + 1}
                step="1"
                required
                disabled={predictionLoading}
                value={predictionYear}
                onChange={(event) => {
                  setPredictionYear(event.target.value);
                  setPredictionResult(null);
                  setPredictionError("");
                }}
                placeholder="예: 2020"
              />
            </label>

            <button
              className="prediction-submit"
              type="submit"
              disabled={predictionLoading || !predictionSelected || !predictionYear}
            >
              {predictionLoading ? "예측 중" : "가격 예측"}
            </button>

            {predictionSelected && (
              <div className="prediction-selected" aria-live="polite">
                <strong>{predictionSelected.modelName}</strong>
                <span>
                  {[predictionSelected.manufacturer, predictionSelected.categoryName]
                    .filter(Boolean)
                    .join(" · ") || "분류 정보 없음"}
                </span>
                <small>
                  학습 표본 {Number(predictionSelected.sampleCount || 0).toLocaleString("ko-KR")}건
                  {predictionSelected.yearMin && predictionSelected.yearMax
                    ? ` · ${predictionSelected.yearMin}~${predictionSelected.yearMax}년 데이터`
                    : ""}
                </small>
              </div>
            )}
          </form>

          {predictionError && <div className="prediction-feedback error">{predictionError}</div>}

          {predictionResult && (
            <section className="prediction-result" aria-live="polite" aria-label="가격 예측 결과">
              <div className="prediction-result-main">
                <span>예측 가격</span>
                <strong>{formatKrw(predictionResult.predictedPriceKrw)}</strong>
                <small>
                  {predictionResult.input?.manufacturedYear}년식 {predictionResult.input?.modelName}
                </small>
              </div>
              <div className="prediction-range">
                <span>웹 입력 기준 MAE 참고 범위</span>
                <strong>
                  {formatKrw(predictionResult.expectedLowKrw)} ~ {formatKrw(predictionResult.expectedHighKrw)}
                </strong>
                <small>{predictionResult.rangeNotice || "통계적 신뢰구간이 아닌 참고 범위입니다."}</small>
              </div>
              <dl className="prediction-meta">
                <div>
                  <dt>분류</dt>
                  <dd>{predictionResult.input?.categoryName || "-"}</dd>
                </div>
                <div>
                  <dt>제조사</dt>
                  <dd>{predictionResult.input?.manufacturer || "-"}</dd>
                </div>
                <div>
                  <dt>모델</dt>
                  <dd>{predictionResult.algorithm || "-"}</dd>
                </div>
                <div>
                  <dt>모델 버전</dt>
                  <dd>{predictionResult.modelVersion || "-"}</dd>
                </div>
              </dl>
            </section>
          )}
        </section>
      )}

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
                placeholder="표시명, 모델명, 제조사, 카테고리, 사이트, 판매자, 지역, 연락처"
              />
            </label>
            <label className="select-box">
              <span>출처</span>
              <select
                value={sourceScope}
                onChange={(event) => {
                  setSourceScope(event.target.value);
                  setSourceSite("");
                }}
              >
                <option value="all">전체 매물</option>
                <option value="international">국제 매물</option>
                <option value="domestic">국내 매물</option>
              </select>
            </label>
            <label className="select-box">
              <span>수집 사이트</span>
              <select value={sourceSite} onChange={(event) => setSourceSite(event.target.value)}>
                <option value="">전체 사이트</option>
                {sourceSiteOptions.map((option) => (
                  <option key={option.sourceSite} value={option.sourceSite}>
                    {option.sourceSite} ({Number(option.listingCount || 0).toLocaleString("ko-KR")})
                  </option>
                ))}
              </select>
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
                        <div className="primary-text">{formatPrice(item)}</div>
                        {formatFxRate(item) && <div className="sub-text">{formatFxRate(item)}</div>}
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
              {loadingMore && <div className="state">다음 50건을 불러오는 중입니다.</div>}
              {!payload.hasMore && payload.items.length > 0 && (
                <div className="state">전체 {Number(payload.total || 0).toLocaleString("ko-KR")}건을 모두 표시했습니다.</div>
              )}
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
              <button
                className="download-button"
                type="button"
                onClick={handleDownloadOwnerLinksCsv}
                disabled={ownerCsvLoading || ownerDetailLoading || !ownerDetailPayload.items.length}
              >
                {ownerCsvLoading ? "CSV 생성 중" : "링크 CSV 다운로드"}
              </button>
              <button type="button" onClick={closeOwnerDetail}>
                차주 목록
              </button>
            </div>
          </section>

          {ownerCsvMessage && <div className="export-feedback">{ownerCsvMessage}</div>}
          {ownerCsvError && <div className="export-feedback error">CSV 오류: {ownerCsvError}</div>}

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
          <section className="summary-grid task-summary-grid" aria-label="크롤링 작업 현황">
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
              <span>3회 실패</span>
              <strong>{taskMetrics.failed.toLocaleString("ko-KR")}</strong>
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
            <div className="task-actions">
              <button
                className="start-button"
                type="button"
                onClick={handleStartSelectedTasks}
                disabled={!selectedTaskIds.length || taskStartLoading}
              >
                {taskStartLoading ? "시작 중" : `선택 시작 (${selectedTaskIds.length})`}
              </button>
            </div>
          </section>

          {taskStartMessage && <div className="export-feedback">{taskStartMessage}</div>}
          {taskStartError && <div className="export-feedback error">시작 오류: {taskStartError}</div>}

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
                    <th className="task-select-cell">
                      <input
                        type="checkbox"
                        aria-label="대기 작업 전체 선택"
                        checked={allVisiblePendingSelected}
                        disabled={!visibleStartableTaskIds.length}
                        onChange={(event) => toggleVisiblePendingTasks(event.target.checked)}
                      />
                    </th>
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
                  {taskPayload.items.map((task) => {
                    const startQueued = isTaskStartQueued(task);
                    return (
                      <tr key={task.id}>
                        <td data-label="선택" className="task-select-cell">
                          <input
                            type="checkbox"
                            aria-label={`작업 ${task.id} 선택`}
                            checked={!startQueued && selectedTaskIdSet.has(task.id)}
                            disabled={task.status !== "pending" || startQueued}
                            onChange={(event) => toggleTaskSelection(task.id, event.target.checked)}
                          />
                        </td>
                        <td data-label="상태">
                          <span className={`status-pill ${startQueued ? "queued" : task.status}`}>
                            {startQueued ? "시작 대기" : statusLabel(task.status)}
                          </span>
                        </td>
                        <td data-label="사이트">
                          <div className="primary-text">{task.siteName}</div>
                          <div className="sub-text">{task.origin || task.siteSlug}</div>
                        </td>
                        <td data-label="작업">
                          <div className="primary-text">{task.taskType}</div>
                          <div className="sub-text">ID {task.id}{startQueued ? " · 예약됨" : ""}</div>
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
                          <div className="sub-text" title={task.lastError || ""}>
                            {task.lastStatusCode ? `HTTP ${task.lastStatusCode}` : task.lastError || ""}
                          </div>
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
                    );
                  })}
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
