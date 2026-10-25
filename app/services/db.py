"""SQLite 持久层。单文件库，零外部依赖，适合单机部署。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings

DB_PATH: Path = settings.base_dir / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT UNIQUE NOT NULL,
    pwd_hash    TEXT NOT NULL,
    pwd_salt    TEXT NOT NULL,
    nickname    TEXT,
    city_id     TEXT,
    city_name   TEXT,
    created_at  TEXT NOT NULL,
    last_login  TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS verify_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL,
    code        TEXT NOT NULL,
    purpose     TEXT NOT NULL DEFAULT 'register',
    expires_at  TEXT NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_codes_email ON verify_codes(email, created_at);

CREATE TABLE IF NOT EXISTS plans (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    title       TEXT,
    city        TEXT,
    days        INTEGER,
    summary     TEXT,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS orders (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    type        TEXT NOT NULL,
    title       TEXT NOT NULL,
    city        TEXT,
    detail      TEXT,
    amount      REAL NOT NULL DEFAULT 0,
    quantity    INTEGER NOT NULL DEFAULT 1,
    travel_date TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    plan_id     TEXT,
    note        TEXT,
    channel     TEXT NOT NULL DEFAULT 'manual',
    external_order_id TEXT,
    pay_url     TEXT,
    commission  REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at DESC);
"""


def conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        _migrate(c)


def _migrate(c: sqlite3.Connection) -> None:
    """轻量迁移：给老库补字段，避免删库重建。"""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(plans)").fetchall()}
    if cols:
        if "share_token" not in cols:
            c.execute("ALTER TABLE plans ADD COLUMN share_token TEXT")
        if "is_public" not in cols:
            c.execute("ALTER TABLE plans ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0")
    ucols = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
    if ucols and "origin_city" not in ucols:
        c.execute("ALTER TABLE users ADD COLUMN origin_city TEXT")
    ocols = {r["name"] for r in c.execute("PRAGMA table_info(orders)").fetchall()}
    if ocols:
        for col, ddl in (("channel", "TEXT NOT NULL DEFAULT 'manual'"),
                         ("external_order_id", "TEXT"),
                         ("pay_url", "TEXT"),
                         ("commission", "REAL NOT NULL DEFAULT 0")):
            if col not in ocols:
                c.execute(f"ALTER TABLE orders ADD COLUMN {col} {ddl}")
    c.commit()


def query_one(sql: str, args: tuple = ()) -> dict[str, Any] | None:
    with conn() as c:
        row = c.execute(sql, args).fetchone()
        return dict(row) if row else None


def query_all(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def execute(sql: str, args: tuple = ()) -> int:
    with conn() as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid or 0
