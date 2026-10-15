"""Read-side services: journeys, roll-ups, grower scoring, analytics."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import ledger
from .config import (
    BATCH_STAGES,
    CONVENTIONAL_BASELINE,
    RETAIL_READY_REQUIRED,
    STAGE_DESC,
    STAGE_LABEL,
    STAGE_ORDER,
)
from .db import load_json
from .domain import compute_lca, compute_scores


# ---------------------------------------------------------------------------
# serialisers
# ---------------------------------------------------------------------------
def batch_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "code": row["code"], "cultivar": row["cultivar"],
        "sow_date": row["sow_date"], "harvest_date": row["harvest_date"],
        "green_kg": row["green_kg"], "roasted_kg": row["roasted_kg"],
        "projected_green_kg": row["projected_green_kg"],
        "grade": row["grade"], "buyer": row["buyer"], "status": row["status"],
        "area_m2": row["area_m2"], "water_l": row["water_l"], "energy_kwh": row["energy_kwh"],
        "qr_token": row["qr_token"],
        "consumer_url": f"/consume.html?t={row['qr_token']}",
        "meta": load_json(row.get("meta_json"), {}),
    }


def module_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "code": row["code"], "name": row["name"],
        "cultivar": row["cultivar"], "plant_count": row["plant_count"],
        "status": row["status"], "facility_id": row["facility_id"],
        "setpoints": {
            "ec": row["ec_target"], "ph": row["ph_target"], "vpd_kpa": row["vpd_target"],
            "ppfd": row["ppfd_target"], "air_temp_c": row["temp_target"],
        },
    }


def facility_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "code": row["code"], "name": row["name"], "grower_id": row["grower_id"],
        "country": row["country"], "region": row["region"], "city": row["city"],
        "lat": row["lat"], "lon": row["lon"], "system_type": row["system_type"],
        "footprint_m2": row["footprint_m2"], "racks": row["racks"],
        "cycles_per_year": row["cycles_per_year"], "export_distance_km": row["export_distance_km"],
        "renewable_share": row["renewable_share"], "commissioned_at": row["commissioned_at"],
        "status": row["status"],
    }


def grower_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "code": row["code"], "display_name": row["display_name"],
        "org": row["org"], "country": row["country"], "region": row["region"],
        "did": row["did"], "wallet": row["wallet"], "kyc_level": row["kyc_level"],
        "trust_score": row["trust_score"], "yield_score": row["yield_score"],
        "compliance_score": row["compliance_score"],
        "meta": load_json(row.get("meta_json"), {}),
    }


# ---------------------------------------------------------------------------
# grower scoring
# ---------------------------------------------------------------------------
def refresh_grower_scores(conn: sqlite3.Connection) -> None:
    for g in conn.execute("SELECT * FROM grower").fetchall():
        g = dict(g)
        facs = conn.execute("SELECT COUNT(*) FROM facility WHERE grower_id = ?", (g["id"],)).fetchone()[0]
        mods = conn.execute(
            """SELECT COUNT(*) FROM grow_module m JOIN facility f ON f.id = m.facility_id
               WHERE f.grower_id = ?""", (g["id"],)).fetchone()[0]
        verified = conn.execute(
            """SELECT COUNT(*) FROM ledger_event e JOIN batch b ON b.id = e.entity_id
               JOIN grow_module m ON m.id = b.module_id JOIN facility f ON f.id = m.facility_id
               WHERE f.grower_id = ?""", (g["id"],)).fetchone()[0]
        reports = conn.execute(
            """SELECT COUNT(*) FROM compliance_report c JOIN batch b ON b.id = c.batch_id
               JOIN grow_module m ON m.id = b.module_id JOIN facility f ON f.id = m.facility_id
               WHERE f.grower_id = ?""", (g["id"],)).fetchone()[0]
        s = compute_scores(g, facilities=facs, modules=mods, verified_events=verified, reports=reports)
        conn.execute(
            """UPDATE grower SET trust_score = ?, yield_score = ?, compliance_score = ?
               WHERE id = ?""",
            (s["trust_score"], s["yield_score"], s["compliance_score"], g["id"]),
        )


def grower_detail(conn: sqlite3.Connection, grower_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM grower WHERE id = ? OR code = ?", (grower_id, grower_id)).fetchone()
    if not row:
        return None
    g = grower_public(dict(row))
    facs = conn.execute("SELECT * FROM facility WHERE grower_id = ?", (g["id"],)).fetchall()
    mods = conn.execute(
        """SELECT m.* FROM grow_module m JOIN facility f ON f.id = m.facility_id
           WHERE f.grower_id = ?""", (g["id"],)).fetchall()
    reports = conn.execute(
        """SELECT COUNT(*) FROM compliance_report c JOIN batch b ON b.id = c.batch_id
           JOIN grow_module m ON m.id = b.module_id JOIN facility f ON f.id = m.facility_id
           WHERE f.grower_id = ?""", (g["id"],)).fetchone()[0]
    verified = conn.execute(
        """SELECT COUNT(*) FROM ledger_event e JOIN batch b ON b.id = e.entity_id
           JOIN grow_module m ON m.id = b.module_id JOIN facility f ON f.id = m.facility_id
           WHERE f.grower_id = ?""", (g["id"],)).fetchone()[0]
    score = compute_scores(dict(row), facilities=len(facs), modules=len(mods),
                           verified_events=verified, reports=reports)
    g["facilities"] = [facility_public(dict(f)) for f in facs]
    g["module_count"] = len(mods)
    g["verified_ledger_events"] = verified
    g["compliance_reports"] = reports
    g["score"] = score
    return g


# ---------------------------------------------------------------------------
# journey
# ---------------------------------------------------------------------------
def telemetry_summary(conn: sqlite3.Connection, module_id: str) -> dict[str, Any]:
    row = conn.execute(
        """SELECT COUNT(*) n, AVG(ec) ec, AVG(ph) ph, AVG(vpd_kpa) vpd,
                  AVG(air_temp_c) temp, AVG(rh_pct) rh, AVG(ppfd) ppfd, AVG(co2_ppm) co2,
                  SUM(water_l) water, SUM(energy_kwh) energy,
                  MIN(ec) ec_min, MAX(ec) ec_max, MIN(ph) ph_min, MAX(ph) ph_max
           FROM telemetry WHERE module_id = ?""", (module_id,)).fetchone()
    d = dict(row) if row else {}
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def build_journey(conn: sqlite3.Connection, batch_row: dict[str, Any]) -> dict[str, Any]:
    batch = batch_public(batch_row)
    module = dict(conn.execute("SELECT * FROM grow_module WHERE id = ?", (batch_row["module_id"],)).fetchone())
    facility = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (module["facility_id"],)).fetchone())
    grower = dict(conn.execute("SELECT * FROM grower WHERE id = ?", (facility["grower_id"],)).fetchone())

    events = sorted(ledger.tail(conn, limit=1000, entity_id=batch_row["id"]), key=lambda e: e["seq"])
    by_type: dict[str, dict] = {}
    for e in events:
        by_type.setdefault(e["event_type"], e)

    stages = []
    for key in STAGE_ORDER:
        ev = by_type.get(key)
        stages.append({
            "stage": key,
            "label": STAGE_LABEL[key],
            "description": STAGE_DESC[key],
            "completed": ev is not None,
            "at": ev["ts"] if ev else None,
            "seq": ev["seq"] if ev else None,
            "hash": ev["hash"] if ev else None,
            "prev_hash": ev["prev_hash"] if ev else None,
            "actor": ev["actor"] if ev else None,
            "payload": ev["payload"] if ev else None,
        })

    reports = {}
    for r in conn.execute("SELECT * FROM compliance_report WHERE batch_id = ?", (batch_row["id"],)).fetchall():
        r = dict(r)
        reports[r["kind"]] = {
            "kind": r["kind"], "issued_at": r["issued_at"], "hash": r["hash"],
            "ledger_seq": r["ledger_seq"], "report": json.loads(r["payload_json"]),
        }

    lca = reports.get("LCA", {}).get("report") or compute_lca(batch_row, facility,
                                                              facility.get("renewable_share"))
    lca = dict(lca)
    lca["provisional"] = batch_row["green_kg"] == 0

    scans = dict(conn.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN kind = 'tip' THEN 1 ELSE 0 END) tips,
                  COALESCE(SUM(amount), 0) tip_usd
           FROM scan WHERE batch_id = ?""", (batch_row["id"],)).fetchone())
    by_country = [dict(r) for r in conn.execute(
        """SELECT country, COUNT(*) c FROM scan WHERE batch_id = ? GROUP BY country
           ORDER BY c DESC LIMIT 8""", (batch_row["id"],)).fetchall()]

    verified = ledger.verify(conn)
    completed = [s for s in stages if s["completed"]]
    missing = [k for k in RETAIL_READY_REQUIRED if k not in by_type]

    return {
        "batch": batch,
        "grower": grower_public(grower),
        "facility": facility_public(facility),
        "module": module_public(module),
        "stages": stages,
        "attestations": [e for e in events if e["event_type"] == "TELEMETRY_ATTESTED"],
        "event_count": len(events),
        "progress_pct": round(len(completed) / len(STAGE_ORDER) * 100, 1),
        "current_stage": completed[-1]["stage"] if completed else None,
        "current_stage_label": completed[-1]["label"] if completed else None,
        "retail_ready": not missing,
        "missing_evidence": [STAGE_LABEL.get(k, k) for k in missing],
        "telemetry_summary": telemetry_summary(conn, batch_row["module_id"]),
        "lca": lca,
        "eudr": reports.get("EUDR", {}).get("report"),
        "reports": {k: {"issued_at": v["issued_at"], "hash": v["hash"]} for k, v in reports.items()},
        "consumer": {"scans": scans.get("total") or 0, "tips": scans.get("tips") or 0,
                     "tip_usd": round(scans.get("tip_usd") or 0, 2), "by_country": by_country},
        "integrity": verified,
    }


def find_batch(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM batch WHERE code = ? OR id = ? OR qr_token = ?",
                       (key, key, key)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------
def overview(conn: sqlite3.Connection) -> dict[str, Any]:
    q = lambda sql, p=(): conn.execute(sql, p).fetchone()[0]
    harvested = [dict(r) for r in conn.execute(
        """SELECT b.*, f.renewable_share AS renewable_share, f.export_distance_km AS export_distance_km,
                  f.footprint_m2 AS footprint_m2, f.cycles_per_year AS cycles_per_year
           FROM batch b JOIN grow_module m ON m.id = b.module_id
           JOIN facility f ON f.id = m.facility_id
           WHERE b.green_kg > 0""").fetchall()]

    green_total = sum(b["green_kg"] for b in harvested)
    water_saved = land_saved = co2_saved = 0.0
    co2e_weighted = 0.0
    for b in harvested:
        lca = compute_lca(b, b, b.get("renewable_share"))
        w = next(l for l in lca["legs"] if l["key"] == "water")
        ld = next(l for l in lca["legs"] if l["key"] == "land")
        co2 = next(l for l in lca["legs"] if l["key"] == "co2e")
        water_saved += (w["conventional"] - w["aeroponic"]) * b["green_kg"]
        land_saved += (ld["conventional"] - ld["aeroponic"]) * b["green_kg"]
        co2_saved += (co2["conventional"] - co2["aeroponic"]) * b["green_kg"]
        co2e_weighted += co2["aeroponic"] * b["green_kg"]

    floor = q("SELECT COALESCE(SUM(footprint_m2),0) FROM facility") or 1.0
    cycles = q("SELECT COALESCE(AVG(cycles_per_year),2.5) FROM facility") or 2.5

    stage_mix = [dict(r) for r in conn.execute(
        "SELECT status, COUNT(*) c FROM batch GROUP BY status ORDER BY c DESC").fetchall()]
    alerts = [dict(r) for r in conn.execute(
        """SELECT severity, COUNT(*) c FROM alert WHERE acknowledged = 0
           GROUP BY severity""").fetchall()]
    scans = dict(conn.execute(
        """SELECT COUNT(*) total, SUM(CASE WHEN kind='tip' THEN 1 ELSE 0 END) tips,
                  COALESCE(SUM(amount),0) tip_usd FROM scan""").fetchone())

    return {
        "counts": {
            "growers": q("SELECT COUNT(*) FROM grower"),
            "facilities": q("SELECT COUNT(*) FROM facility"),
            "modules": q("SELECT COUNT(*) FROM grow_module"),
            "batches": q("SELECT COUNT(*) FROM batch"),
            "harvested_batches": len(harvested),
            "ledger_events": q("SELECT COUNT(*) FROM ledger_event"),
            "compliance_reports": q("SELECT COUNT(*) FROM compliance_report"),
            "open_alerts": q("SELECT COUNT(*) FROM alert WHERE acknowledged = 0"),
        },
        "production": {
            "green_kg": round(green_total, 1),
            "roasted_kg": round(sum(b["roasted_kg"] for b in harvested), 1),
            "floor_m2": round(floor, 1),
            "kg_per_m2_per_year": round(green_total / floor * cycles, 2),
        },
        "impact": {
            "water_saved_l": round(water_saved, 0),
            "land_saved_m2": round(land_saved, 1),
            "co2_saved_kg": round(co2_saved, 1),
            "co2e_per_kg_weighted": round(co2e_weighted / green_total, 3) if green_total else None,
            "deforestation_exposure": 0.0,
            "baseline_water_l_per_kg": CONVENTIONAL_BASELINE["water_l_per_kg"],
            "baseline_land_m2_per_kg": CONVENTIONAL_BASELINE["land_m2_per_kg"],
            "baseline_co2e_kg_per_kg": CONVENTIONAL_BASELINE["co2e_kg_per_kg"],
            "note": "Deltas vs the conventional baseline in config, applied to actual ledgered yields.",
        },
        "stage_mix": stage_mix,
        "open_alerts": alerts,
        "consumer": {"scans": scans.get("total") or 0, "tips": scans.get("tips") or 0,
                     "tip_usd": round(scans.get("tip_usd") or 0, 2)},
        "integrity": ledger.verify(conn),
    }


def network(conn: sqlite3.Connection) -> dict[str, Any]:
    growers = [grower_public(dict(r)) for r in conn.execute("SELECT * FROM grower ORDER BY code").fetchall()]
    facilities = []
    for r in conn.execute("SELECT * FROM facility ORDER BY code").fetchall():
        f = facility_public(dict(r))
        f["module_count"] = conn.execute(
            "SELECT COUNT(*) FROM grow_module WHERE facility_id = ?", (f["id"],)).fetchone()[0]
        f["batch_count"] = conn.execute(
            """SELECT COUNT(*) FROM batch b JOIN grow_module m ON m.id = b.module_id
               WHERE m.facility_id = ?""", (f["id"],)).fetchone()[0]
        f["green_kg"] = conn.execute(
            """SELECT COALESCE(SUM(b.green_kg),0) FROM batch b JOIN grow_module m ON m.id = b.module_id
               WHERE m.facility_id = ?""", (f["id"],)).fetchone()[0]
        f["grower_code"] = conn.execute(
            "SELECT code FROM grower WHERE id = ?", (f["grower_id"],)).fetchone()[0]
        facilities.append(f)
    modules = []
    for r in conn.execute("SELECT * FROM grow_module ORDER BY code").fetchall():
        m = module_public(dict(r))
        m["facility_code"] = conn.execute(
            "SELECT code FROM facility WHERE id = ?", (m["facility_id"],)).fetchone()[0]
        last = conn.execute(
            "SELECT ts FROM telemetry WHERE module_id = ? ORDER BY ts DESC LIMIT 1", (m["id"],)).fetchone()
        m["last_telemetry"] = last[0] if last else None
        modules.append(m)
    return {"growers": growers, "facilities": facilities, "modules": modules}
