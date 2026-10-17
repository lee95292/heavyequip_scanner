from __future__ import annotations

import re
from typing import Optional

import pymysql

from prediction.config import MySQLSettings


def quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z_]+", str(value or "")):
        raise ValueError(f"unsupported SQL identifier: {value!r}")
    return f"`{value}`"


def mysql_connect(
    settings: MySQLSettings,
    *,
    database: Optional[str] = None,
    streaming: bool = False,
    autocommit: bool = True,
):
    cursor_class = pymysql.cursors.SSDictCursor if streaming else pymysql.cursors.DictCursor
    kwargs = {
        "host": settings.host,
        "port": settings.port,
        "user": settings.user,
        "password": settings.password,
        "database": settings.database if database is None else database,
        "charset": settings.charset,
        "connect_timeout": settings.connect_timeout,
        "read_timeout": settings.read_timeout,
        "write_timeout": settings.write_timeout,
        "autocommit": autocommit,
        "cursorclass": cursor_class,
    }
    if settings.ssl_ca:
        kwargs["ssl"] = {"ca": settings.ssl_ca, "check_hostname": True}
    if not kwargs["database"]:
        kwargs.pop("database")
    return pymysql.connect(**kwargs)
