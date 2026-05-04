const fs = require("fs");
const path = require("path");
const express = require("express");
const cors = require("cors");
const mysql = require("mysql2/promise");

const app = express();
const port = Number(process.env.PORT || 5050);
const repoRoot = path.resolve(__dirname, "..", "..");
const configPath = process.env.CRAWL_CONFIG_PATH || path.join(repoRoot, "crawl", "config.json");

app.use(cors());

let pool;
let activeDbConfig;

function readMysqlConfig() {
  const raw = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const source = raw.mysql || raw;
  const connectTimeoutSeconds = Number(source.connect_timeout || 10);
  return {
    host: String(source.host || "127.0.0.1"),
    port: Number(source.port || 3306),
    user: String(source.user || "root"),
    password: String(source.password || ""),
    database: String(source.database || "heavyequip_scanner"),
    charset: String(source.charset || "utf8mb4"),
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0,
    dateStrings: true,
    connectTimeout: Math.max(1, connectTimeoutSeconds) * 1000
  };
}

function publicDbInfo(config) {
  return {
    database: config.database,
    host: config.host,
    port: config.port
  };
}

function getPool() {
  if (!pool) {
    activeDbConfig = readMysqlConfig();
    pool = mysql.createPool(activeDbConfig);
  }
  return pool;
}

function siteShortName(record) {
  const source = record.source_site || record.origin || "";
  if (source.includes("그린")) {
    return "그린";
  }
  if (source.includes("Mascus")) {
    return "Mascus";
  }
  if (source.includes("중기114")) {
    return "중기114";
  }
  try {
    const host = new URL(record.origin || record.detail_url || record.crawl_url).hostname;
    return host.replace(/^www\./, "").split(".")[0];
  } catch {
    return String(source || "-").slice(0, 12);
  }
}

function taskSiteName(record) {
  if (record.site_slug === "green_heavy") {
    return "그린중기";
  }
  if (record.site_slug === "mascus_korea") {
    return "Mascus";
  }
  if (record.site_slug === "junggi114") {
    return "중기114";
  }
  return record.site_slug || record.origin || "-";
}

function parseTime(value) {
  const text = String(value || "");
  if (!text) {
    return null;
  }
  const time = Date.parse(text);
  return Number.isFinite(time) ? time : null;
}

function parseYearMonth(value) {
  const text = String(value || "");
  const yearMatch = text.match(/(19|20)\d{2}/);
  if (!yearMatch) {
    return null;
  }
  const year = Number(yearMatch[0]);
  const afterYear = text.slice(yearMatch.index + yearMatch[0].length);
  const monthMatch = afterYear.match(/\D?(\d{1,2})/);
  const month = monthMatch ? Number(monthMatch[1]) : 1;
  if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
    return null;
  }
  return year * 100 + month;
}

function parseMonthParam(value, fallbackMonth) {
  const match = String(value || "").match(/^((?:19|20)\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2] || fallbackMonth);
  if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
    return null;
  }
  return year * 100 + month;
}

function parseHoursFromText(value) {
  const text = String(value || "");
  if (!text) {
    return null;
  }
  const pattern = /(\d{1,3}(?:[, ]?\d{3})+|\d{3,6})\s*(?:시간|hr|hrs|hour|hours|h\b)/gi;
  let match;
  while ((match = pattern.exec(text))) {
    const number = Number(match[1].replace(/[, ]/g, ""));
    if (!Number.isFinite(number) || number < 100) {
      continue;
    }
    const context = text.slice(Math.max(0, match.index - 12), match.index + match[0].length + 16);
    if (number <= 24 && /상담|문의|친절/.test(context)) {
      continue;
    }
    return number;
  }
  return null;
}

function extractOperatingHours(record) {
  const raw = record.raw_json;
  if (raw) {
    try {
      const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
      const detail = parsed?.detail || {};
      const detailEntries = Object.entries(detail);
      const priority = detailEntries.filter(([key]) => /가동|운행|사용|시간/.test(key));
      for (const [_key, value] of [...priority, ...detailEntries]) {
        const hours = parseHoursFromText(value);
        if (hours !== null) {
          return hours;
        }
      }
    } catch {
      const hours = parseHoursFromText(raw);
      if (hours !== null) {
        return hours;
      }
    }
  }

  return (
    parseHoursFromText(record.description) ??
    parseHoursFromText(record.listing_name) ??
    parseHoursFromText(record.model_name)
  );
}

function normalizeRecord(record) {
  const postedValue = record.posted_at || record.posted_date;
  const crawledValue = record.crawled_at;
  const link = record.detail_url || record.crawl_url || "";
  const manufacturedYearMonthValue = parseYearMonth(record.manufactured_ym);
  const operatingHoursValue = extractOperatingHours(record);
  return {
    id: record.id,
    contentHash: record.content_hash || "",
    price: record.price || "",
    priceValue: record.price_krw == null ? null : Number(record.price_krw),
    displayName: record.listing_name || "-",
    modelName: record.model_norm || record.model_name || "",
    sourceSite: record.source_site || record.origin || "-",
    siteShort: siteShortName(record),
    postedDate: record.posted_date || (postedValue ? String(postedValue).slice(0, 10) : ""),
    postedAt: postedValue || "",
    postedAtMs: parseTime(postedValue),
    contact: record.contact || "",
    link,
    crawlUrl: record.crawl_url || "",
    categoryName: record.category_name || "",
    manufacturer: record.manufacturer || "",
    manufacturedYm: record.manufactured_ym || "",
    manufacturedYearMonthValue,
    operatingHoursValue,
    seller: record.seller || "",
    location: record.location || "",
    crawledAt: crawledValue || "",
    crawledAtMs: parseTime(crawledValue)
  };
}

function normalizeTask(record) {
  const lastCrawledAt = record.success_at || record.updated_at || record.created_at || "";
  return {
    id: record.id,
    siteSlug: record.site_slug || "",
    siteName: taskSiteName(record),
    origin: record.origin || "",
    taskType: record.task_type || "",
    status: record.status || "",
    attempts: Number(record.attempts || 0),
    lastStatusCode: record.last_status_code == null ? null : Number(record.last_status_code),
    lastError: record.last_error || "",
    nextRunAt: record.next_run_at || "",
    successAt: record.success_at || "",
    updatedAt: record.updated_at || "",
    createdAt: record.created_at || "",
    lastCrawledAt,
    categoryCode: record.category_code || "",
    categoryName: record.category_name || "",
    page: record.page == null ? "" : String(record.page),
    link: record.url || ""
  };
}

function parseNumberParam(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const number = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(number) ? number : null;
}

function buildFilters(query) {
  const where = [];
  const params = [];
  const search = String(query.q || "").trim();
  const postedFrom = String(query.posted_from || "").trim();
  const postedTo = String(query.posted_to || "").trim();
  const priceMin = parseNumberParam(query.price_min);
  const priceMax = parseNumberParam(query.price_max);

  if (search) {
    const like = `%${search}%`;
    const fields = [
      "listing_name",
      "model_name",
      "model_norm",
      "description",
      "price",
      "contact",
      "source_site",
      "origin",
      "category_name",
      "manufacturer",
      "seller",
      "location"
    ];
    where.push(`(${fields.map((field) => `COALESCE(${field}, '') LIKE ?`).join(" OR ")})`);
    params.push(...fields.map(() => like));
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(postedFrom)) {
    where.push("posted_date IS NOT NULL AND posted_date >= ?");
    params.push(postedFrom);
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(postedTo)) {
    where.push("posted_date IS NOT NULL AND posted_date <= ?");
    params.push(postedTo);
  }

  if (priceMin !== null) {
    where.push("price_krw IS NOT NULL AND price_krw >= ?");
    params.push(priceMin);
  }

  if (priceMax !== null) {
    where.push("price_krw IS NOT NULL AND price_krw <= ?");
    params.push(priceMax);
  }

  return {
    whereSql: where.length ? `WHERE ${where.join(" AND ")}` : "",
    params
  };
}

function buildRangeFilters(query) {
  return {
    manufacturedFrom: parseMonthParam(query.manufactured_from, 1),
    manufacturedTo: parseMonthParam(query.manufactured_to, 12),
    hoursMin: parseNumberParam(query.hours_min),
    hoursMax: parseNumberParam(query.hours_max)
  };
}

function matchesRangeFilters(item, filters) {
  if (filters.manufacturedFrom !== null) {
    if (item.manufacturedYearMonthValue === null || item.manufacturedYearMonthValue < filters.manufacturedFrom) {
      return false;
    }
  }
  if (filters.manufacturedTo !== null) {
    if (item.manufacturedYearMonthValue === null || item.manufacturedYearMonthValue > filters.manufacturedTo) {
      return false;
    }
  }
  if (filters.hoursMin !== null) {
    if (item.operatingHoursValue === null || item.operatingHoursValue < filters.hoursMin) {
      return false;
    }
  }
  if (filters.hoursMax !== null) {
    if (item.operatingHoursValue === null || item.operatingHoursValue > filters.hoursMax) {
      return false;
    }
  }
  return true;
}

function orderSql(sort) {
  const orders = {
    posted_desc: "posted_at IS NULL ASC, posted_at DESC, posted_date DESC, crawled_at DESC, id DESC",
    posted_asc: "posted_at IS NULL ASC, posted_at ASC, posted_date ASC, crawled_at DESC, id DESC",
    price_desc: "price_krw IS NULL ASC, price_krw DESC, posted_at DESC, id DESC",
    price_asc: "price_krw IS NULL ASC, price_krw ASC, posted_at DESC, id DESC"
  };
  return orders[sort] || orders.posted_desc;
}

function sortListings(items, sort) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (sort === "price_desc") {
      return (b.priceValue || -1) - (a.priceValue || -1) || (b.postedAtMs || 0) - (a.postedAtMs || 0);
    }
    if (sort === "price_asc") {
      return (
        (a.priceValue ?? Number.MAX_SAFE_INTEGER) - (b.priceValue ?? Number.MAX_SAFE_INTEGER) ||
        (b.postedAtMs || 0) - (a.postedAtMs || 0)
      );
    }
    if (sort === "posted_asc") {
      return (a.postedAtMs || 0) - (b.postedAtMs || 0) || (b.crawledAtMs || 0) - (a.crawledAtMs || 0);
    }
    return (b.postedAtMs || 0) - (a.postedAtMs || 0) || (b.crawledAtMs || 0) - (a.crawledAtMs || 0);
  });
  return sorted;
}

async function queryListings(filters) {
  const db = getPool();
  const { whereSql, params } = buildFilters(filters);
  const limit = Math.min(Math.max(Number(filters.limit || 1000), 1), 5000);
  const sort = orderSql(filters.sort);
  const rangeFilters = buildRangeFilters(filters);
  const baseFetchLimit = 50000;

  const [statsRows] = await db.execute(
    "SELECT COUNT(*) AS databaseTotal, COUNT(price_krw) AS pricedTotal, MAX(posted_date) AS latestPostedDate FROM listings"
  );
  const [rows] = await db.execute(
    `
      SELECT
        id, content_hash, origin, source_site, crawl_url, detail_url, pid,
        category_code, category_name, listing_name, model_name, model_norm,
        description, price, price_krw, contact, posted_date, posted_at, crawled_at,
        manufacturer, manufactured_ym, location, seller, status, view_count, raw_json
      FROM listings
      ${whereSql}
      ORDER BY ${sort}
      LIMIT ${baseFetchLimit}
    `,
    params
  );

  const stats = statsRows[0] || {};
  const filteredItems = sortListings(
    rows.map(normalizeRecord).filter((item) => matchesRangeFilters(item, rangeFilters)),
    filters.sort
  );
  return {
    generatedAt: new Date().toISOString(),
    db: publicDbInfo(activeDbConfig),
    limit,
    total: filteredItems.length,
    databaseTotal: Number(stats.databaseTotal || 0),
    pricedTotal: Number(stats.pricedTotal || 0),
    latestPostedDate: stats.latestPostedDate || "",
    items: filteredItems.slice(0, limit)
  };
}

async function tableExists(tableName) {
  const db = getPool();
  const [rows] = await db.execute(
    `
      SELECT COUNT(*) AS cnt
      FROM information_schema.TABLES
      WHERE TABLE_SCHEMA = ?
        AND TABLE_NAME = ?
    `,
    [activeDbConfig.database, tableName]
  );
  return Number(rows?.[0]?.cnt || 0) > 0;
}

async function queryCrawlTasks(filters) {
  const db = getPool();
  const limit = Math.min(Math.max(Number(filters.limit || 500), 1), 2000);
  const status = String(filters.status || "").trim();
  const site = String(filters.site || "").trim();
  const search = String(filters.q || "").trim();
  const where = [];
  const params = [];

  if (!(await tableExists("crawl_tasks"))) {
    return {
      generatedAt: new Date().toISOString(),
      db: publicDbInfo(activeDbConfig),
      total: 0,
      statusCounts: [],
      siteCounts: [],
      latestTaskAt: "",
      items: []
    };
  }

  if (status) {
    where.push("status = ?");
    params.push(status);
  }

  if (site) {
    where.push("site_slug = ?");
    params.push(site);
  }

  if (search) {
    const like = `%${search}%`;
    where.push(
      "(COALESCE(site_slug, '') LIKE ? OR COALESCE(origin, '') LIKE ? OR COALESCE(category_name, '') LIKE ? OR COALESCE(url, '') LIKE ?)"
    );
    params.push(like, like, like, like);
  }

  const whereSql = where.length ? `WHERE ${where.join(" AND ")}` : "";
  const [summaryRows] = await db.execute(
    `
      SELECT
        COUNT(*) AS total,
        MAX(COALESCE(success_at, updated_at, created_at)) AS latestTaskAt
      FROM crawl_tasks
      ${whereSql}
    `,
    params
  );
  const [statusRows] = await db.execute(
    `
      SELECT status, COUNT(*) AS count
      FROM crawl_tasks
      ${whereSql}
      GROUP BY status
      ORDER BY count DESC, status ASC
    `,
    params
  );
  const [siteRows] = await db.execute(
    `
      SELECT site_slug, COUNT(*) AS count, MAX(COALESCE(success_at, updated_at, created_at)) AS latestTaskAt
      FROM crawl_tasks
      ${whereSql}
      GROUP BY site_slug
      ORDER BY count DESC, site_slug ASC
    `,
    params
  );
  const [rows] = await db.execute(
    `
      SELECT
        id, site_slug, origin, task_type, url, category_code, category_name, page,
        status, attempts, last_status_code, last_error, next_run_at, success_at,
        created_at, updated_at
      FROM crawl_tasks
      ${whereSql}
      ORDER BY
        FIELD(status, 'running', 'pending', 'done') ASC,
        COALESCE(next_run_at, success_at, updated_at, created_at) DESC,
        id DESC
      LIMIT ${limit}
    `,
    params
  );

  const summary = summaryRows[0] || {};
  return {
    generatedAt: new Date().toISOString(),
    db: publicDbInfo(activeDbConfig),
    total: Number(summary.total || 0),
    latestTaskAt: summary.latestTaskAt || "",
    statusCounts: statusRows.map((row) => ({
      status: row.status || "-",
      count: Number(row.count || 0)
    })),
    siteCounts: siteRows.map((row) => ({
      siteSlug: row.site_slug || "",
      siteName: taskSiteName(row),
      count: Number(row.count || 0),
      latestTaskAt: row.latestTaskAt || ""
    })),
    items: rows.map(normalizeTask)
  };
}

app.get("/api/listings", async (req, res) => {
  try {
    res.json(await queryListings(req.query));
  } catch (error) {
    console.error(`[dashboard] listings query failed: ${error.message}`);
    res.status(500).json({ error: "DB 조회에 실패했습니다.", detail: error.message });
  }
});

app.get("/api/crawl-tasks", async (req, res) => {
  try {
    res.json(await queryCrawlTasks(req.query));
  } catch (error) {
    console.error(`[dashboard] crawl task query failed: ${error.message}`);
    res.status(500).json({ error: "크롤링 작업 조회에 실패했습니다.", detail: error.message });
  }
});

if (process.env.NODE_ENV === "production") {
  const distDir = path.join(__dirname, "..", "dist");
  app.use(express.static(distDir));
  app.get(/.*/, (_req, res) => {
    res.sendFile(path.join(distDir, "index.html"));
  });
}

app.listen(port, () => {
  const dbInfo = publicDbInfo(readMysqlConfig());
  console.log(`[dashboard] API server listening on http://localhost:${port}`);
  console.log(`[dashboard] reading MySQL ${dbInfo.database} at ${dbInfo.host}:${dbInfo.port}`);
});
