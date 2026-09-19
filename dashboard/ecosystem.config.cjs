const path = require("path");

const repoRoot = path.resolve(__dirname, "..");

module.exports = {
  apps: [
    {
      name: "heavyequip-dashboard",
      script: "server/index.js",
      cwd: __dirname,
      instances: 1,
      exec_mode: "fork",
      watch: false,
      autorestart: true,
      max_memory_restart: "300M",
      env: {
        NODE_ENV: "production",
        PORT: "5050",
        DASHBOARD_MANUAL_CRAWL_SLEEP: "1.5"
      }
    },
    {
      name: "heavyequip-international-daily",
      script: "crawl/international/daily.py",
      cwd: repoRoot,
      interpreter: process.env.CRAWL_PYTHON_BIN || "python3",
      instances: 1,
      exec_mode: "fork",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      kill_timeout: 60000,
      max_memory_restart: "300M",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: repoRoot,
        CRAWL_CONFIG_PATH: process.env.CRAWL_CONFIG_PATH || path.join(repoRoot, "crawl", "config.json"),
        INTERNATIONAL_DAILY_AT: process.env.INTERNATIONAL_DAILY_AT || "05:00",
        INTERNATIONAL_CRAWL_SLEEP: process.env.INTERNATIONAL_CRAWL_SLEEP || "1.5",
        INTERNATIONAL_DAILY_STATE_PATH:
          process.env.INTERNATIONAL_DAILY_STATE_PATH || path.join(repoRoot, "crawl", "data", "international_daily_state.json"),
        INTERNATIONAL_DAILY_LOCK_PATH:
          process.env.INTERNATIONAL_DAILY_LOCK_PATH || path.join(repoRoot, "crawl", "data", "international_daily.lock")
      }
    },
    {
      name: "heavyequip-fx-monthly",
      script: "crawl/fx_monthly.py",
      cwd: repoRoot,
      interpreter: process.env.CRAWL_PYTHON_BIN || "python3",
      instances: 1,
      exec_mode: "fork",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      kill_timeout: 60000,
      max_memory_restart: "200M",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: repoRoot,
        CRAWL_CONFIG_PATH: process.env.CRAWL_CONFIG_PATH || path.join(repoRoot, "crawl", "config.json"),
        FX_MONTHLY_DAY: process.env.FX_MONTHLY_DAY || "1",
        FX_MONTHLY_AT: process.env.FX_MONTHLY_AT || "05:30",
        FX_CACHE_PATH: process.env.FX_CACHE_PATH || path.join(repoRoot, "crawl", "data", "fx_rates.json"),
        FX_MONTHLY_STATE_PATH:
          process.env.FX_MONTHLY_STATE_PATH || path.join(repoRoot, "crawl", "data", "fx_monthly_state.json"),
        FX_MONTHLY_LOCK_PATH:
          process.env.FX_MONTHLY_LOCK_PATH || path.join(repoRoot, "crawl", "data", "fx_monthly.lock")
      }
    }
  ]
};
