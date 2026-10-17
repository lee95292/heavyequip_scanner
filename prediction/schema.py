from __future__ import annotations

import pymysql

from prediction.config import PredictionSettings
from prediction.db import mysql_connect, quote_identifier


RAW_TABLE = "products_raw"
CLEANED_TABLE = "products_cleaned"
MODEL_CATALOG_TABLE = "model_dictionary"
CLEANING_RUNS_TABLE = "cleaning_runs"
TRAINING_RUNS_TABLE = "training_runs"


def initialize_warehouse(settings: PredictionSettings) -> None:
    database = quote_identifier(settings.warehouse_mysql.database)
    with mysql_connect(settings.warehouse_mysql, database="") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {database} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

    with mysql_connect(settings.warehouse_mysql) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(RAW_TABLE)} (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    source_listing_id BIGINT UNSIGNED NOT NULL,
                    content_hash CHAR(64) NULL,
                    source_revision_hash CHAR(64) NOT NULL,
                    origin VARCHAR(255) NULL,
                    source_site VARCHAR(100) NULL,
                    crawl_url TEXT NULL,
                    detail_url TEXT NULL,
                    pid VARCHAR(64) NULL,
                    category_code VARCHAR(32) NULL,
                    category_name VARCHAR(255) NULL,
                    listing_name VARCHAR(500) NULL,
                    model_name VARCHAR(255) NULL,
                    model_norm VARCHAR(255) NULL,
                    description MEDIUMTEXT NULL,
                    price VARCHAR(100) NULL,
                    price_krw BIGINT NULL,
                    contact VARCHAR(255) NULL,
                    posted_date DATE NULL,
                    posted_at DATETIME NULL,
                    crawled_at DATETIME NULL,
                    manufacturer VARCHAR(255) NULL,
                    manufactured_ym VARCHAR(50) NULL,
                    location VARCHAR(255) NULL,
                    seller VARCHAR(255) NULL,
                    status VARCHAR(100) NULL,
                    view_count INT NULL,
                    raw_json JSON NULL,
                    payload_json JSON NULL,
                    source_created_at DATETIME NULL,
                    source_updated_at DATETIME NULL,
                    checked TINYINT(1) NOT NULL DEFAULT 0,
                    check_status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    check_message VARCHAR(1000) NULL,
                    checked_at DATETIME NULL,
                    ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_products_raw_source (source_listing_id),
                    KEY idx_products_raw_checked (checked, check_status, source_listing_id),
                    KEY idx_products_raw_model (model_norm, model_name),
                    KEY idx_products_raw_price (price_krw)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS column_count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='source_revision_hash'
                """,
                (settings.warehouse_mysql.database, RAW_TABLE),
            )
            revision_column = cursor.fetchone() or {}
            if int(revision_column.get("column_count") or 0) == 0:
                cursor.execute(
                    f"""
                    ALTER TABLE {quote_identifier(RAW_TABLE)}
                    ADD COLUMN source_revision_hash CHAR(64) NULL AFTER content_hash
                    """
                )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(CLEANED_TABLE)} (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    source_listing_id BIGINT UNSIGNED NOT NULL,
                    pid VARCHAR(64) NULL,
                    detail_url TEXT NULL,
                    manufactured_year SMALLINT UNSIGNED NOT NULL,
                    manufactured_month TINYINT UNSIGNED NULL,
                    model_name_raw VARCHAR(255) NULL,
                    model_norm VARCHAR(255) NULL,
                    model_name_clean VARCHAR(255) NOT NULL,
                    model_confidence DECIMAL(7,6) NOT NULL DEFAULT 1.0,
                    cleaning_method VARCHAR(32) NOT NULL,
                    price_krw BIGINT UNSIGNED NOT NULL,
                    operating_hours DECIMAL(12,2) NULL,
                    manufacturer VARCHAR(255) NULL,
                    category_code VARCHAR(32) NULL,
                    category_name VARCHAR(255) NULL,
                    equipment_status VARCHAR(100) NULL,
                    source_site VARCHAR(100) NULL,
                    location VARCHAR(255) NULL,
                    seller VARCHAR(255) NULL,
                    contact VARCHAR(255) NULL,
                    seller_dedupe_hash CHAR(64) NULL,
                    contact_dedupe_hash CHAR(64) NULL,
                    owner_group_hash CHAR(64) NULL,
                    entity_group_hash CHAR(64) NOT NULL,
                    listing_name VARCHAR(500) NULL,
                    posted_at DATETIME NULL,
                    crawled_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_products_cleaned_source (source_listing_id),
                    UNIQUE KEY uq_products_cleaned_seller (seller_dedupe_hash),
                    UNIQUE KEY uq_products_cleaned_contact (contact_dedupe_hash),
                    KEY idx_products_cleaned_norm_year (model_norm, manufactured_year),
                    KEY idx_products_cleaned_price (price_krw),
                    KEY idx_products_cleaned_posted (posted_at),
                    KEY idx_products_cleaned_owner_group (owner_group_hash),
                    KEY idx_products_cleaned_entity_group (entity_group_hash)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS column_count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='model_norm'
                """,
                (settings.warehouse_mysql.database, CLEANED_TABLE),
            )
            cleaned_model_norm_column = cursor.fetchone() or {}
            if int(cleaned_model_norm_column.get("column_count") or 0) == 0:
                cursor.execute(
                    f"""
                    ALTER TABLE {quote_identifier(CLEANED_TABLE)}
                    ADD COLUMN model_norm VARCHAR(255) NULL AFTER model_name_raw
                    """
                )
                cursor.execute(
                    f"""
                    UPDATE {quote_identifier(CLEANED_TABLE)}
                    SET model_norm=model_name_clean
                    WHERE cleaning_method='seed_norm'
                    """
                )
            cursor.execute(
                """
                SELECT COUNT(*) AS index_count
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                  AND INDEX_NAME='idx_products_cleaned_norm_year'
                """,
                (settings.warehouse_mysql.database, CLEANED_TABLE),
            )
            cleaned_model_norm_index = cursor.fetchone() or {}
            if int(cleaned_model_norm_index.get("index_count") or 0) == 0:
                cursor.execute(
                    f"""
                    ALTER TABLE {quote_identifier(CLEANED_TABLE)}
                    ADD KEY idx_products_cleaned_norm_year (model_norm, manufactured_year)
                    """
                )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(MODEL_CATALOG_TABLE)} (
                    model_name_clean VARCHAR(255) NOT NULL,
                    observation_count INT UNSIGNED NOT NULL,
                    seed_source VARCHAR(32) NOT NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (model_name_clean),
                    KEY idx_model_dictionary_count (observation_count)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(CLEANING_RUNS_TABLE)} (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME NULL,
                    status VARCHAR(20) NOT NULL,
                    seed_model_count INT UNSIGNED NOT NULL DEFAULT 0,
                    processed_count INT UNSIGNED NOT NULL DEFAULT 0,
                    inserted_count INT UNSIGNED NOT NULL DEFAULT 0,
                    duplicate_count INT UNSIGNED NOT NULL DEFAULT 0,
                    review_count INT UNSIGNED NOT NULL DEFAULT 0,
                    rejected_count INT UNSIGNED NOT NULL DEFAULT 0,
                    metrics_json JSON NULL,
                    PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_identifier(TRAINING_RUNS_TABLE)} (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    trained_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    artifact_path VARCHAR(1000) NOT NULL,
                    best_model VARCHAR(50) NOT NULL,
                    train_rows INT UNSIGNED NOT NULL,
                    validation_rows INT UNSIGNED NOT NULL,
                    metrics_json JSON NOT NULL,
                    PRIMARY KEY (id),
                    KEY idx_training_runs_trained (trained_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )


def assert_warehouse_available(settings: PredictionSettings) -> None:
    try:
        with mysql_connect(settings.warehouse_mysql) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM {quote_identifier(RAW_TABLE)} LIMIT 1")
    except pymysql.MySQLError as error:
        raise RuntimeError("prediction warehouse is not initialized; run `python -m prediction init`") from error
