CREATE TABLE IF NOT EXISTS focus_rules (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 legacy_id BIGINT UNSIGNED NULL UNIQUE,
 model_contains VARCHAR(120) NOT NULL,
 email VARCHAR(254) NOT NULL,
 price_min_manwon BIGINT NULL, price_max_manwon BIGINT NULL,
 year_min INT NULL, year_max INT NULL,
 categories_json JSON NOT NULL,
 interval_minutes INT NOT NULL DEFAULT 10,
 enabled BOOLEAN NOT NULL DEFAULT FALSE,
 revision INT NOT NULL DEFAULT 1,
 next_run_at DATETIME NULL, last_started_at DATETIME NULL,
 last_finished_at DATETIME NULL, last_status VARCHAR(32) NOT NULL DEFAULT 'paused',
 last_summary VARCHAR(240) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 KEY focus_due(enabled,next_run_at)
);
CREATE TABLE IF NOT EXISTS focus_cursors (
 rule_id BIGINT UNSIGNED NOT NULL, revision INT NOT NULL,
 category_code VARCHAR(16) NOT NULL, last_success_at DATETIME NOT NULL,
 boundary_json JSON NOT NULL,
 PRIMARY KEY(rule_id,revision,category_code)
);
CREATE TABLE IF NOT EXISTS focus_seen (
 rule_id BIGINT UNSIGNED NOT NULL, identity_hash CHAR(64) NOT NULL,
 status VARCHAR(24) NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(rule_id,identity_hash), KEY focus_seen_age(created_at)
);
CREATE TABLE IF NOT EXISTS focus_logs (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 rule_id BIGINT UNSIGNED NULL, category_code VARCHAR(16) NULL,
 kind VARCHAR(16) NOT NULL, status VARCHAR(32) NOT NULL,
 method VARCHAR(8) NULL, request_path VARCHAR(180) NULL,
 http_status INT NULL, response_bytes INT NULL, duration_ms INT NULL,
 summary VARCHAR(240) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY focus_log_age(created_at), KEY focus_log_rule(rule_id,id)
);
CREATE TABLE IF NOT EXISTS focus_service_state (
 id INT PRIMARY KEY, heartbeat_at DATETIME NOT NULL,
 mail_ready BOOLEAN NOT NULL, status VARCHAR(32) NOT NULL
);
CREATE TABLE IF NOT EXISTS focus_scan_config (
 id INT PRIMARY KEY,
 categories_json JSON NOT NULL,
 interval_minutes INT NOT NULL DEFAULT 10,
 request_delay_seconds INT NOT NULL DEFAULT 2,
 enabled BOOLEAN NOT NULL DEFAULT FALSE, revision INT NOT NULL DEFAULT 1,
 next_run_at DATETIME NULL, last_started_at DATETIME NULL, last_finished_at DATETIME NULL,
 last_status VARCHAR(32) NOT NULL DEFAULT 'paused', last_summary VARCHAR(240) NULL,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS focus_shared_cursors (
 scan_id INT NOT NULL, revision INT NOT NULL, category_code VARCHAR(16) NOT NULL,
 last_success_at DATETIME NOT NULL, boundary_json JSON NOT NULL,
 PRIMARY KEY(scan_id,revision,category_code)
);
INSERT IGNORE INTO focus_scan_config(id,categories_json) VALUES(1,JSON_ARRAY());
CREATE TABLE IF NOT EXISTS focus_log_samples (
 log_id BIGINT UNSIGNED PRIMARY KEY,
 names_json JSON NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY focus_samples_age(created_at)
);
CREATE TABLE IF NOT EXISTS focus_mail_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 rule_id BIGINT UNSIGNED NOT NULL, identity_hash CHAR(64) NOT NULL,
 recipient VARCHAR(254) NOT NULL, listing_name VARCHAR(240) NOT NULL,
 price_text VARCHAR(120) NULL, manufactured_ym VARCHAR(40) NULL,
 detail_url VARCHAR(500) NULL, category_code VARCHAR(16) NULL,
 condition_json JSON NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'sending',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at DATETIME NULL,
 UNIQUE KEY focus_mail_once(rule_id,identity_hash), KEY focus_mail_sent(status,sent_at,id)
);
CREATE TABLE IF NOT EXISTS focus_migrations (
 name VARCHAR(80) PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
