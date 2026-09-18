CREATE DATABASE IF NOT EXISTS `heavyequip_scanner`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `heavyequip_scanner`;

CREATE TABLE IF NOT EXISTS `listings` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `content_hash` CHAR(64) NULL,
  `origin` VARCHAR(255) NULL,
  `source_site` VARCHAR(100) NULL,
  `crawl_url` TEXT NULL,
  `detail_url` TEXT NULL,
  `pid` VARCHAR(64) NULL,
  `category_code` VARCHAR(32) NULL,
  `category_name` VARCHAR(255) NULL,
  `listing_name` VARCHAR(500) NULL,
  `model_name` VARCHAR(255) NULL,
  `model_norm` VARCHAR(255) NULL,
  `description` MEDIUMTEXT NULL,
  `price` VARCHAR(100) NULL,
  `price_krw` BIGINT NULL,
  `contact` VARCHAR(255) NULL,
  `posted_date` DATE NULL,
  `posted_at` DATETIME NULL,
  `crawled_at` DATETIME NULL,
  `manufacturer` VARCHAR(255) NULL,
  `manufactured_ym` VARCHAR(50) NULL,
  `location` VARCHAR(255) NULL,
  `seller` VARCHAR(255) NULL,
  `status` VARCHAR(100) NULL,
  `view_count` INT NULL,
  `raw_json` JSON NULL,
  `payload_json` JSON NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_listings_content_hash` (`content_hash`),
  KEY `idx_listings_origin` (`origin`),
  KEY `idx_listings_posted_date` (`posted_date`),
  KEY `idx_listings_posted_at` (`posted_at`),
  KEY `idx_listings_crawled_at` (`crawled_at`),
  KEY `idx_listings_price_krw` (`price_krw`),
  KEY `idx_listings_model_norm` (`model_norm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `crawl_tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `site_slug` VARCHAR(100) NOT NULL,
  `origin` VARCHAR(255) NULL,
  `task_type` VARCHAR(50) NOT NULL,
  `url_hash` CHAR(64) NOT NULL,
  `url` TEXT NOT NULL,
  `category_code` VARCHAR(32) NULL,
  `category_name` VARCHAR(255) NULL,
  `page` INT NULL,
  `priority` INT NOT NULL DEFAULT 100,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `attempts` INT NOT NULL DEFAULT 0,
  `last_status_code` INT NULL,
  `last_error` TEXT NULL,
  `next_run_at` DATETIME NULL,
  `success_at` DATETIME NULL,
  `metadata_json` JSON NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_crawl_tasks_site_url` (`site_slug`, `url_hash`),
  KEY `idx_crawl_tasks_pick` (`site_slug`, `status`, `next_run_at`, `priority`, `id`),
  KEY `idx_crawl_tasks_type` (`site_slug`, `task_type`),
  KEY `idx_crawl_tasks_category` (`site_slug`, `category_code`, `page`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `source_sync_state` (
  `site_slug` VARCHAR(100) NOT NULL,
  `stream_key` VARCHAR(191) NOT NULL DEFAULT 'all',
  `direction` VARCHAR(20) NOT NULL DEFAULT 'backward',
  `status` VARCHAR(20) NOT NULL DEFAULT 'idle',
  `next_cursor` VARCHAR(500) NULL,
  `last_success_cursor` VARCHAR(500) NULL,
  `newest_seen_at` DATETIME NULL,
  `oldest_seen_at` DATETIME NULL,
  `last_request_fingerprint` CHAR(64) NULL,
  `last_error` TEXT NULL,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`site_slug`, `stream_key`),
  KEY `idx_source_sync_status` (`status`, `updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `source_request_log` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `site_slug` VARCHAR(100) NOT NULL,
  `request_fingerprint` CHAR(64) NOT NULL,
  `method` VARCHAR(10) NOT NULL,
  `url` TEXT NOT NULL,
  `cursor_value` VARCHAR(500) NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'planned',
  `response_status` INT NULL,
  `item_count` INT NULL,
  `requested_at` DATETIME NULL,
  `completed_at` DATETIME NULL,
  `last_error` TEXT NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_source_request_fingerprint` (`site_slug`, `request_fingerprint`),
  KEY `idx_source_request_resume` (`site_slug`, `status`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
