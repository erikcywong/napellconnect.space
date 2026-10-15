"""Append-only hash-chained ledger.

Every state change in the network — a module commissioned, telemetry aggregated,
a batch advanced, a compliance report issued, a fund flowing back to a grower —
is written as one event. Each event commits to the previous event's hash, so
tampering with any historical row invalidates every row after it.

This is the property farmerconnect.com buys from IBM Food Trust. For a closed
aeroponic system we get it cheaper and stronger, because the inputs are sensor
readings rather than self-reported spreadsheets.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from .config import GENESIS_HASH
from .db import one, rows, now_iso


def canonical(payload: Any) -> str:
    """Deterministic JSON — key order and separators fixed so hashes reproduce."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(
    seq: int,
    ts: str,
    entity_type: str,
    entity_id: str,
    event_type: str,
    actor: str,
    payload_json: str,
    prev_hash: str,
) -> str:
    body = "|".join([str(seq), ts, entity_type, entity_id, event_type, actor, payload_json, prev_hash])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def head(conn: sqlite3.Connection) -> tuple[int, str]:
    cur = conn.execute("SELECT seq, hash FROM ledger_event ORDER BY seq DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return 0, GENESIS_HASH
    return int(row["seq"]), str(row["hash"])


def append(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    event_type: str,
    payload: Any = None,
    actor: str = "system:napell-fc",
    ts: str | None = None,
) -> dict[str, Any]:
    """Write one event and return it. Caller owns the transaction."""
    ts = ts or now_iso()
    payload_json = canonical(payload or {})
    prev_seq, prev_hash = head(conn)
    seq = prev_seq + 1
    digest = compute_hash(seq, ts, entity_type, entity_id, event_type, actor, payload_json, prev_hash)
    conn.execute(
        """INSERT INTO ledger_event
           (seq, ts, entity_type, entity_id, event_type, actor, payload_json, prev_hash, hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (seq, ts, entity_type, entity_id, event_type, actor, payload_json, prev_hash, digest),
    )
    return {
        "seq": seq,
        "ts": ts,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "event_type": event_type,
        "actor": actor,
        "payload": json.loads(payload_json),
        "prev_hash": prev_hash,
        "hash": digest,
    }


def tail(conn: sqlite3.Connection, limit: int = 50, entity_id: str | None = None,
         entity_type: str | None = None) -> list[dict[str, Any]]:
    where, params = [], []
    if entity_id:
        where.append("entity_id = ?")
        params.append(entity_id)
    if entity_type:
        where.append("entity_type = ?")
        params.append(entity_type)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    cur = conn.execute(
        f"SELECT * FROM ledger_event {clause} ORDER BY seq DESC LIMIT ?", (*params, limit)
    )
    out = rows(cur)
    for r in out:
        r["payload"] = json.loads(r.pop("payload_json") or "{}")
    return out


def verify(conn: sqlite3.Connection) -> dict[str, Any]:
    """Recompute the whole chain. Returns integrity verdict."""
    cur = conn.execute("SELECT * FROM ledger_event ORDER BY seq ASC")
    expected_prev = GENESIS_HASH
    count = 0
    for r in cur.fetchall():
        count += 1
        recomputed = compute_hash(
            int(r["seq"]), r["ts"], r["entity_type"], r["entity_id"],
            r["event_type"], r["actor"], r["payload_json"], r["prev_hash"],
        )
        if r["prev_hash"] != expected_prev:
            return {"ok": False, "checked": count, "broken_at": r["seq"],
                    "reason": "prev_hash does not match the previous event hash"}
        if recomputed != r["hash"]:
            return {"ok": False, "checked": count, "broken_at": r["seq"],
                    "reason": "recomputed hash differs — payload was modified"}
        expected_prev = r["hash"]

    head_seq, head_hash = head(conn)
    return {
        "ok": True,
        "checked": count,
        "length": head_seq,
        "head_hash": head_hash,
        "algo": "sha256(seq|ts|entity_type|entity_id|event_type|actor|payload|prev_hash)",
    }


def event_count(conn: sqlite3.Connection, entity_id: str, event_type: str | None = None) -> int:
    if event_type:
        row = conn.execute(
            "SELECT COUNT(*) FROM ledger_event WHERE entity_id = ? AND event_type = ?",
            (entity_id, event_type),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM ledger_event WHERE entity_id = ?", (entity_id,)).fetchone()
    return int(row[0]) if row else 0


def latest_by_entity(conn: sqlite3.Connection, entity_id: str) -> dict[str, Any] | None:
    return one(conn.execute(
        "SELECT * FROM ledger_event WHERE entity_id = ? ORDER BY seq DESC LIMIT 1", (entity_id,)
    ))
