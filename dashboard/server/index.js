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

function parseTime(value) {
  const text = String(value || "");
  if (!text) {
    return null;
  }
  const time = Date.parse(text);
  return Number.isFinite(time) ? time : null;
}

function normalizeRecord(record) {
  const postedValue = record.posted_at || record.posted_date;
  const crawledValue = record.crawled_at;
  const link = record.detail_url || record.crawl_url || "";
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
    seller: record.seller || "",
    location: record.location || "",
    crawledAt: crawledValue || "",
    crawledAtMs: parseTime(crawledValue)
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

function orderSql(sort) {
  const orders = {
    posted_desc: "posted_at DESC, posted_date DESC, crawled_at DESC, id DESC",
    posted_asc: "posted_at ASC, posted_date ASC, crawled_at DESC, id DESC",
    price_desc: "price_krw IS NULL ASC, price_krw DESC, posted_at DESC, id DESC",
    price_asc: "price_krw IS NULL ASC, price_krw ASC, posted_at DESC, id DESC"
  };
  return orders[sort] || orders.posted_desc;
}

async function queryListings(filters) {
  const db = getPool();
  const { whereSql, params } = buildFilters(filters);
  const limit = Math.min(Math.max(Number(filters.limit || 1000), 1), 5000);
  const sort = orderSql(filters.sort);

  const [statsRows] = await db.execute(
    "SELECT COUNT(*) AS databaseTotal, COUNT(price_krw) AS pricedTotal, MAX(posted_date) AS latestPostedDate FROM listings"
  );
  const [countRows] = await db.execute(`SELECT COUNT(*) AS filteredTotal FROM listings ${whereSql}`, params);
  const [rows] = await db.execute(
    `
      SELECT
        id, content_hash, origin, source_site, crawl_url, detail_url, pid,
        category_code, category_name, listing_name, model_name, model_norm,
        price, price_krw, contact, posted_date, posted_at, crawled_at,
        manufacturer, manufactured_ym, location, seller, status, view_count
      FROM listings
      ${whereSql}
      ORDER BY ${sort}
      LIMIT ${limit}
    `,
    params
  );

  const stats = statsRows[0] || {};
  return {
    generatedAt: new Date().toISOString(),
    db: publicDbInfo(activeDbConfig),
    limit,
    total: Number(countRows[0]?.filteredTotal || 0),
    databaseTotal: Number(stats.databaseTotal || 0),
    pricedTotal: Number(stats.pricedTotal || 0),
    latestPostedDate: stats.latestPostedDate || "",
    items: rows.map(normalizeRecord)
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
