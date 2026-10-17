from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.json"
DEFAULT_EXAMPLE_CONFIG_PATH = PROJECT_DIR / "config.example.json"
DEFAULT_ENV_PATH = PROJECT_DIR / ".env"


@dataclass(frozen=True)
class MySQLSettings:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    read_timeout: int = 120
    write_timeout: int = 120
    ssl_ca: Optional[str] = None


@dataclass(frozen=True)
class PredictionSettings:
    source_mysql: MySQLSettings
    warehouse_mysql: MySQLSettings
    source_table: str = "listings"
    min_model_frequency: int = 10
    model_confidence_threshold: float = 0.75
    minimum_training_rows: int = 100
    price_min_krw: int = 1_000_000
    price_max_krw: int = 10_000_000_000
    random_seed: int = 42
    data_dir: Path = PROJECT_DIR / "data"
    artifact_dir: Path = PROJECT_DIR / "artifacts"


def _env(name: str, fallback: Any) -> Any:
    value = os.environ.get(name)
    return fallback if value is None else value


def _mysql_settings(data: dict[str, Any], prefix: str) -> MySQLSettings:
    ssl_ca = str(_env(f"{prefix}_SSL_CA", data.get("ssl_ca") or "")).strip() or None
    return MySQLSettings(
        host=str(_env(f"{prefix}_HOST", data.get("host", "127.0.0.1"))),
        port=int(_env(f"{prefix}_PORT", data.get("port", 3306))),
        user=str(_env(f"{prefix}_USER", data.get("user", "root"))),
        password=str(_env(f"{prefix}_PASSWORD", data.get("password", ""))),
        database=str(_env(f"{prefix}_DATABASE", data.get("database", ""))),
        charset=str(data.get("charset", "utf8mb4")),
        connect_timeout=int(data.get("connect_timeout", 10)),
        read_timeout=int(data.get("read_timeout", 120)),
        write_timeout=int(data.get("write_timeout", data.get("read_timeout", 120))),
        ssl_ca=ssl_ca,
    )


def _resolve_directory(value: Any, config_path: Path, default_name: str) -> Path:
    path = Path(str(value or default_name)).expanduser()
    if not path.is_absolute():
        path = config_path.parent / path
    return path.resolve()


def load_settings(path: Optional[Path] = None) -> PredictionSettings:
    load_dotenv(DEFAULT_ENV_PATH, override=False)
    configured_path = path or os.environ.get("PREDICTION_CONFIG_PATH")
    config_path = Path(
        configured_path or DEFAULT_CONFIG_PATH
    ).expanduser().resolve()
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    elif configured_path and config_path != DEFAULT_CONFIG_PATH.resolve():
        raise FileNotFoundError(
            f"prediction config not found: {config_path}. "
            f"Use {DEFAULT_ENV_PATH.name} or copy {DEFAULT_EXAMPLE_CONFIG_PATH.name}."
        )
    else:
        payload = {}
    source = _mysql_settings(payload.get("source_mysql") or {}, "PREDICTION_SOURCE")
    warehouse = _mysql_settings(payload.get("warehouse_mysql") or {}, "PREDICTION_WAREHOUSE")
    if not source.database:
        raise ValueError("source_mysql.database is required")
    if not warehouse.database:
        raise ValueError("warehouse_mysql.database is required")
    confidence = float(payload.get("model_confidence_threshold", 0.75))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("model_confidence_threshold must be between 0 and 1")
    settings = PredictionSettings(
        source_mysql=source,
        warehouse_mysql=warehouse,
        source_table=str(payload.get("source_table", "listings")),
        min_model_frequency=max(2, int(payload.get("min_model_frequency", 10))),
        model_confidence_threshold=confidence,
        minimum_training_rows=max(10, int(payload.get("minimum_training_rows", 100))),
        price_min_krw=max(1, int(payload.get("price_min_krw", 1_000_000))),
        price_max_krw=max(1, int(payload.get("price_max_krw", 10_000_000_000))),
        random_seed=int(payload.get("random_seed", 42)),
        data_dir=_resolve_directory(payload.get("data_dir"), config_path, "data"),
        artifact_dir=_resolve_directory(payload.get("artifact_dir"), config_path, "artifacts"),
    )
    source_identity = (
        settings.source_mysql.host.lower(),
        settings.source_mysql.port,
        settings.source_mysql.database.lower(),
    )
    warehouse_identity = (
        settings.warehouse_mysql.host.lower(),
        settings.warehouse_mysql.port,
        settings.warehouse_mysql.database.lower(),
    )
    if source_identity == warehouse_identity:
        raise ValueError("source and warehouse must use separate MySQL databases")
    return settings
