"""SQLite storage layer — schema, connection, and small helpers."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import DB_PATH

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS grower (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  org TEXT,
  country TEXT,
  region TEXT,
  did TEXT UNIQUE,
  wallet TEXT,
  kyc_level INTEGER NOT NULL DEFAULT 0,
  trust_score REAL NOT NULL DEFAULT 0,
  yield_score REAL NOT NULL DEFAULT 0,
  compliance_score REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  meta_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS facility (
  id TEXT PRIMARY KEY,
  grower_id TEXT NOT NULL REFERENCES grower(id),
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  country TEXT,
  region TEXT,
  city TEXT,
  lat REAL,
  lon REAL,
  system_type TEXT NOT NULL DEFAULT 'aeroponic_vertical',
  footprint_m2 REAL NOT NULL DEFAULT 0,
  racks INTEGER NOT NULL DEFAULT 0,
  cycles_per_year REAL NOT NULL DEFAULT 2.5,
  export_distance_km REAL NOT NULL DEFAULT 0,
  renewable_share REAL NOT NULL DEFAULT 0.6,
  commissioned_at TEXT,
  status TEXT NOT NULL DEFAULT 'operational',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grow_module (
  id TEXT PRIMARY KEY,
  facility_id TEXT NOT NULL REFERENCES facility(id),
  code TEXT UNIQUE NOT NULL,
  name TEXT,
  cultivar TEXT,
  plant_count INTEGER NOT NULL DEFAULT 0,
  ec_target REAL, ph_target REAL, vpd_target REAL, ppfd_target REAL, temp_target REAL,
  status TEXT NOT NULL DEFAULT 'idle',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batch (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  module_id TEXT NOT NULL REFERENCES grow_module(id),
  cultivar TEXT,
  sow_date TEXT,
  harvest_date TEXT,
  green_kg REAL NOT NULL DEFAULT 0,
  roasted_kg REAL NOT NULL DEFAULT 0,
  projected_green_kg REAL NOT NULL DEFAULT 0,
  grade TEXT,
  buyer TEXT,
  water_l REAL NOT NULL DEFAULT 0,
  energy_kwh REAL NOT NULL DEFAULT 0,
  area_m2 REAL NOT NULL DEFAULT 0,
  qr_token TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'growing',
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  ec REAL, ph REAL, water_temp_c REAL, air_temp_c REAL, rh_pct REAL,
  vpd_kpa REAL, ppfd REAL, co2_ppm REAL, water_l REAL, energy_kwh REAL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_module_ts ON telemetry(module_id, ts);

CREATE TABLE IF NOT EXISTS alert (
  id TEXT PRIMARY KEY,
  module_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL,
  threshold REAL,
  severity TEXT NOT NULL DEFAULT 'warning',
  acknowledged INTEGER NOT NULL DEFAULT 0,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_module ON alert(module_id, acknowledged);

CREATE TABLE IF NOT EXISTS ledger_event (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_entity ON ledger_event(entity_type, entity_id);

CREATE TABLE IF NOT EXISTS compliance_report (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES batch(id),
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  ledger_seq INTEGER,
  hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_compliance_batch ON compliance_report(batch_id, kind);

CREATE TABLE IF NOT EXISTS project (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT,
  summary TEXT,
  goal_usd REAL NOT NULL DEFAULT 0,
  raised_usd REAL NOT NULL DEFAULT 0,
  backers INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS scan (
  id TEXT PRIMARY KEY,
  qr_token TEXT NOT NULL,
  batch_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  country TEXT,
  device TEXT,
  kind TEXT NOT NULL DEFAULT 'view',
  amount REAL NOT NULL DEFAULT 0,
  currency TEXT DEFAULT 'USD',
  project_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_scan_batch ON scan(batch_id, kind);
"""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def one(cur: sqlite3.Cursor) -> dict[str, Any] | None:
    r = cur.fetchone()
    return dict(r) if r else None


def load_json(value: Any, fallback: Any = None) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def insert(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> None:
    keys = list(data.keys())
    placeholders = ", ".join("?" for _ in keys)
    sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
    conn.execute(sql, [data[k] for k in keys])


def update(conn: sqlite3.Connection, table: str, row_id: str, data: dict[str, Any]) -> None:
    keys = list(data.keys())
    sets = ", ".join(f"{k} = ?" for k in keys)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [data[k] for k in keys] + [row_id])


def scalar(cur: sqlite3.Cursor, sql: str, params: Iterable[Any] = ()) -> Any:
    row = cur.execute(sql, tuple(params)).fetchone()
    return row[0] if row else None
