"""SQLite access helpers. Plain sqlite3 keeps the MVP dependency-free.

Migration path: the schema is standard SQL; moving to PostgreSQL means swapping
this module for SQLAlchemy/psycopg and converting the JSON TEXT columns to JSONB.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL") if str(path) != ":memory:" else None
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def insert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))
    return int(cur.lastrowid)


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, tuple(params)).fetchall()


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, tuple(params)).fetchone()


# ---------------------------------------------------------------- clients --

def client_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return one(conn, "SELECT * FROM clients WHERE slug = ?", (slug,))


def client_by_id(conn: sqlite3.Connection, client_id: int) -> sqlite3.Row | None:
    return one(conn, "SELECT * FROM clients WHERE id = ?", (client_id,))


def client_config(conn: sqlite3.Connection, client_id: int) -> dict[str, Any]:
    """Client row + competitors as plain dicts with JSON columns decoded."""
    row = client_by_id(conn, client_id)
    if row is None:
        raise LookupError(f"client {client_id} not found")
    cfg = dict(row)
    for key in ("brand_aliases", "extra_domains", "services", "geographies"):
        cfg[key] = loads(cfg[key], [])
    cfg["competitors"] = [
        {**dict(c), "aliases": loads(c["aliases"], [])}
        for c in rows(conn, "SELECT * FROM competitors WHERE client_id = ? ORDER BY name", (client_id,))
    ]
    return cfg


def owned(conn: sqlite3.Connection, table: str, row_id: int, client_id: int) -> sqlite3.Row | None:
    """Fetch a row only if it belongs to client_id (client-separation guard)."""
    allowed = {"site_audits", "visibility_batches", "visibility_responses", "audit_findings",
               "recommendations", "prompts", "competitors", "page_checks"}
    if table not in allowed:
        raise ValueError(f"table {table} is not client-scoped")
    return one(conn, f"SELECT * FROM {table} WHERE id = ? AND client_id = ?", (row_id, client_id))
