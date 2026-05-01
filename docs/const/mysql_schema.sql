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
