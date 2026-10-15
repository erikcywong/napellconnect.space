"""Napell Farmer Connect — FastAPI application.

Aeroponic coffee supply-chain identity, traceability, compliance and consumer
engagement. Same architecture as the JEBI stack: FastAPI + SQLite, static
frontend served same-origin, demo-safe by default.
"""
from __future__ import annotations

import json
import hashlib
import math
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import segno
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ledger, services
from .config import (
    API_PREFIX,
    APP_NAME,
    APP_VERSION,
    BATCH_STAGES,
    CONVENTIONAL_BASELINE,
    DEFAULT_ACTOR,
    EUDR_CUTOFF_DATE,
    EUDR_REGULATION,
    OFFLINE,
    STAGE_LABEL,
    STAGE_ORDER,
    WEB_DIR,
)
from .db import connect, init_db, insert, load_json, new_id, now_iso
from .domain import build_eudr_report, check_thresholds, compute_lca, simulate_sample
from .seed import ANCHOR, qr_token, seed as run_seed, stable_int

UTC = timezone.utc


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conn = connect()
    try:
        if conn.execute("SELECT COUNT(*) FROM grower").fetchone()[0] == 0:
            run_seed(force=False)
    finally:
        conn.close()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan,
              description="Aeroponic coffee identity, traceability and compliance network.")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def actor_of(x_napell_user: str | None = Header(default=None)) -> str:
    return f"user:{x_napell_user}" if x_napell_user else DEFAULT_ACTOR


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_module(conn, key: str) -> dict:
    r = conn.execute("SELECT * FROM grow_module WHERE code = ? OR id = ?", (key, key)).fetchone()
    if not r:
        raise HTTPException(404, f"grow module '{key}' not found")
    return dict(r)


def resolve_facility(conn, key: str) -> dict:
    r = conn.execute("SELECT * FROM facility WHERE code = ? OR id = ?", (key, key)).fetchone()
    if not r:
        raise HTTPException(404, f"facility '{key}' not found")
    return dict(r)


def resolve_batch(conn, key: str) -> dict:
    r = services.find_batch(conn, key)
    if not r:
        raise HTTPException(404, f"batch '{key}' not found")
    return r


def batch_context(conn, batch: dict) -> tuple[dict, dict, dict, dict]:
    module = dict(conn.execute("SELECT * FROM grow_module WHERE id = ?", (batch["module_id"],)).fetchone())
    facility = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (module["facility_id"],)).fetchone())
    grower = dict(conn.execute("SELECT * FROM grower WHERE id = ?", (facility["grower_id"],)).fetchone())
    return module, facility, grower, {}


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------
@app.get(f"{API_PREFIX}/meta")
def meta():
    return {
        "app": APP_NAME, "version": APP_VERSION, "offline": OFFLINE,
        "grain": "aeroponic_controlled_environment",
        "stages": [{"key": k, "label": STAGE_LABEL[k]} for k in STAGE_ORDER],
        "baseline": CONVENTIONAL_BASELINE,
        "eudr": {"regulation": EUDR_REGULATION, "cutoff_date": EUDR_CUTOFF_DATE},
        "features": ["identity", "iot_telemetry", "traceability_ledger", "compliance", "consumer"],
        "auth": "send X-Napell-User to attribute writes; omitted writes are attributed to system",
    }


@app.get(f"{API_PREFIX}/overview")
def overview(conn=Depends(get_conn)):
    return services.overview(conn)


@app.get(f"{API_PREFIX}/network")
def network(conn=Depends(get_conn)):
    return services.network(conn)


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------
class GrowerIn(BaseModel):
    display_name: str
    org: str | None = None
    country: str | None = None
    region: str | None = None
    kyc_level: int = Field(default=1, ge=0, le=3)
    wallet: str | None = None


class FacilityIn(BaseModel):
    grower: str
    name: str
    city: str | None = None
    country: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    system_type: str = "aeroponic_vertical"
    footprint_m2: float = 0
    racks: int = 0
    cycles_per_year: float = 2.5
    export_distance_km: float = 0
    renewable_share: float = 0.6


class ModuleIn(BaseModel):
    facility: str
    code: str | None = None
    name: str | None = None
    cultivar: str | None = None
    plant_count: int = 0
    ec_target: float | None = None
    ph_target: float | None = None
    vpd_target: float | None = None
    ppfd_target: float | None = None
    temp_target: float | None = None


@app.get(f"{API_PREFIX}/growers")
def list_growers(conn=Depends(get_conn)):
    out = []
    for r in conn.execute("SELECT * FROM grower ORDER BY code").fetchall():
        g = services.grower_public(dict(r))
        g["facility_count"] = conn.execute(
            "SELECT COUNT(*) FROM facility WHERE grower_id = ?", (g["id"],)).fetchone()[0]
        out.append(g)
    return {"items": out, "count": len(out)}


@app.get(f"{API_PREFIX}/growers/{{key}}")
def get_grower(key: str, conn=Depends(get_conn)):
    g = services.grower_detail(conn, key)
    if not g:
        raise HTTPException(404, f"grower '{key}' not found")
    return g


@app.post(f"{API_PREFIX}/growers", status_code=201)
def create_grower(body: GrowerIn, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    n = conn.execute("SELECT COUNT(*) FROM grower").fetchone()[0] + 1
    code = f"NPF-{n:04d}"
    gid = new_id()
    did = f"did:napell:{code.lower()}"
    insert(conn, "grower", {
        "id": gid, "code": code, "display_name": body.display_name, "org": body.org,
        "country": body.country, "region": body.region, "did": did, "wallet": body.wallet,
        "kyc_level": body.kyc_level, "created_at": now_iso(),
        "meta_json": json.dumps({"role": "registrant"}, ensure_ascii=False),
    })
    ev = ledger.append(conn, "grower", gid, "GROWER_REGISTERED", {
        "code": code, "legal_name": body.display_name, "org": body.org,
        "country": body.country, "kyc_level": body.kyc_level, "did": did,
    }, actor=actor)
    services.refresh_grower_scores(conn)
    conn.commit()
    return {"grower": services.grower_public(
        dict(conn.execute("SELECT * FROM grower WHERE id = ?", (gid,)).fetchone())),
        "ledger_event": ev}


@app.get(f"{API_PREFIX}/facilities")
def list_facilities(conn=Depends(get_conn)):
    return services.network(conn)["facilities"]


@app.post(f"{API_PREFIX}/facilities", status_code=201)
def create_facility(body: FacilityIn, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    g = conn.execute("SELECT * FROM grower WHERE code = ? OR id = ?",
                     (body.grower, body.grower)).fetchone()
    if not g:
        raise HTTPException(404, f"grower '{body.grower}' not found")
    n = conn.execute("SELECT COUNT(*) FROM facility").fetchone()[0] + 1
    code = f"FAC-{body.country[:2].upper() if body.country else 'XX'}-{n:02d}"
    fid = new_id()
    insert(conn, "facility", {
        "id": fid, "grower_id": g["id"], "code": code, "name": body.name,
        "country": body.country, "region": body.region, "city": body.city,
        "lat": body.lat, "lon": body.lon, "system_type": body.system_type,
        "footprint_m2": body.footprint_m2, "racks": body.racks,
        "cycles_per_year": body.cycles_per_year, "export_distance_km": body.export_distance_km,
        "renewable_share": body.renewable_share, "commissioned_at": now_iso()[:10],
        "created_at": now_iso(),
    })
    ev = ledger.append(conn, "facility", fid, "FACILITY_COMMISSIONED", {
        "code": code, "name": body.name, "city": body.city, "country": body.country,
        "lat": body.lat, "lon": body.lon, "system_type": body.system_type,
        "footprint_m2": body.footprint_m2, "racks": body.racks,
        "renewable_share": body.renewable_share,
        "land_use_note": "controlled-environment structure, no agricultural plot",
    }, actor=actor)
    services.refresh_grower_scores(conn)
    conn.commit()
    return {"facility": services.facility_public(
        dict(conn.execute("SELECT * FROM facility WHERE id = ?", (fid,)).fetchone())),
        "ledger_event": ev}


@app.get(f"{API_PREFIX}/modules")
def list_modules(facility: str | None = None, conn=Depends(get_conn)):
    net = services.network(conn)
    items = net["modules"]
    if facility:
        items = [m for m in items if m["facility_code"] == facility or m["facility_id"] == facility]
    return {"items": items, "count": len(items)}


@app.post(f"{API_PREFIX}/modules", status_code=201)
def create_module(body: ModuleIn, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    f = resolve_facility(conn, body.facility)
    n = conn.execute("SELECT COUNT(*) FROM grow_module WHERE facility_id = ?", (f["id"],)).fetchone()[0] + 1
    code = body.code or f"{f['code'].split('FAC-')[1]}-M{n:02d}"
    mid = new_id()
    insert(conn, "grow_module", {
        "id": mid, "facility_id": f["id"], "code": code,
        "name": body.name or f"{f['name']} · Rack {n}",
        "cultivar": body.cultivar, "plant_count": body.plant_count,
        "ec_target": body.ec_target, "ph_target": body.ph_target, "vpd_target": body.vpd_target,
        "ppfd_target": body.ppfd_target, "temp_target": body.temp_target,
        "status": "idle", "created_at": now_iso(),
    })
    ev = ledger.append(conn, "module", mid, "MODULE_COMMISSIONED", {
        "code": code, "facility_code": f["code"], "cultivar": body.cultivar,
        "plant_count": body.plant_count,
        "setpoints": {"ec": body.ec_target, "ph": body.ph_target, "vpd_kpa": body.vpd_target,
                      "ppfd": body.ppfd_target, "air_temp_c": body.temp_target},
        "sensor_channels": ["ec", "ph", "water_temp_c", "air_temp_c", "rh_pct",
                            "ppfd", "co2_ppm", "vpd_kpa"],
    }, actor=actor)
    services.refresh_grower_scores(conn)
    conn.commit()
    return {"module": services.module_public(
        dict(conn.execute("SELECT * FROM grow_module WHERE id = ?", (mid,)).fetchone())),
        "ledger_event": ev}


# ---------------------------------------------------------------------------
# IoT telemetry
# ---------------------------------------------------------------------------
class TelemetryIn(BaseModel):
    ec: float | None = None
    ph: float | None = None
    water_temp_c: float | None = None
    air_temp_c: float | None = None
    rh_pct: float | None = None
    ppfd: float | None = None
    co2_ppm: float | None = None
    water_l: float | None = None
    energy_kwh: float | None = None
    ts: str | None = None
    attest: bool = False


@app.get(f"{API_PREFIX}/modules/{{key}}")
def get_module(key: str, conn=Depends(get_conn)):
    m = resolve_module(conn, key)
    fac = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (m["facility_id"],)).fetchone())
    out = services.module_public(m)
    out["facility"] = services.facility_public(fac)
    out["grower_code"] = conn.execute(
        "SELECT code FROM grower WHERE id = ?", (fac["grower_id"],)).fetchone()[0]
    out["active_batch"] = None
    b = conn.execute(
        """SELECT * FROM batch WHERE module_id = ? AND status = 'growing'
           ORDER BY sow_date DESC LIMIT 1""", (m["id"],)).fetchone()
    if b:
        out["active_batch"] = services.batch_public(dict(b))
    out["telemetry_summary"] = services.telemetry_summary(conn, m["id"])
    out["open_alerts"] = conn.execute(
        "SELECT COUNT(*) FROM alert WHERE module_id = ? AND acknowledged = 0", (m["id"],)).fetchone()[0]
    return out


@app.get(f"{API_PREFIX}/modules/{{key}}/telemetry")
def module_telemetry(key: str, hours: int = Query(default=72, ge=1, le=720),
                     bucket: int = Query(default=1, ge=1, le=24), conn=Depends(get_conn)):
    m = resolve_module(conn, key)
    since = iso(ANCHOR - timedelta(hours=hours))
    rows = [dict(r) for r in conn.execute(
        """SELECT ts, ec, ph, water_temp_c, air_temp_c, rh_pct, vpd_kpa, ppfd, co2_ppm,
                  water_l, energy_kwh FROM telemetry
           WHERE module_id = ? AND ts >= ? ORDER BY ts ASC""", (m["id"], since)).fetchall()]
    if bucket > 1:
        rows = rows[::bucket]
    metrics = ["ec", "ph", "water_temp_c", "air_temp_c", "rh_pct", "vpd_kpa", "ppfd", "co2_ppm"]
    series = {k: [r[k] for r in rows] for k in metrics}
    return {
        "module": services.module_public(m),
        "hours": hours, "bucket_hours": bucket, "count": len(rows),
        "timestamps": [r["ts"] for r in rows],
        "series": series,
        "water_l": round(sum(r["water_l"] or 0 for r in rows), 1),
        "energy_kwh": round(sum(r["energy_kwh"] or 0 for r in rows), 2),
        "alerts": [dict(r) for r in conn.execute(
            """SELECT * FROM alert WHERE module_id = ? AND acknowledged = 0
               ORDER BY ts DESC LIMIT 20""", (m["id"],)).fetchall()],
    }


@app.post(f"{API_PREFIX}/modules/{{key}}/telemetry", status_code=201)
def ingest_telemetry(key: str, body: TelemetryIn, conn=Depends(get_conn),
                     actor: str = Depends(actor_of)):
    m = resolve_module(conn, key)
    if body.ec is None and body.ph is None and body.air_temp_c is None:
        raise HTTPException(422, "at least one of ec, ph, air_temp_c must be supplied")
    ts = body.ts or now_iso()
    ec = body.ec if body.ec is not None else 1.65
    ph = body.ph if body.ph is not None else 5.75
    at = body.air_temp_c if body.air_temp_c is not None else 26.0
    rh = body.rh_pct if body.rh_pct is not None else 72.0
    vpd = round((0.6108 * math.exp(17.27 * at / (at + 237.3))) * (1 - rh / 100.0), 3)
    conn.execute(
        """INSERT INTO telemetry (module_id, ts, ec, ph, water_temp_c, air_temp_c, rh_pct,
           vpd_kpa, ppfd, co2_ppm, water_l, energy_kwh)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (m["id"], ts, ec, ph, body.water_temp_c, at, rh, vpd, body.ppfd, body.co2_ppm,
         body.water_l or 0, body.energy_kwh or 0),
    )
    sample = {"ec": ec, "ph": ph, "water_temp_c": body.water_temp_c or 21.5,
              "air_temp_c": at, "rh_pct": rh, "vpd_kpa": vpd}
    raised = []
    for a in check_thresholds(sample, m):
        aid = new_id()
        insert(conn, "alert", {"id": aid, "module_id": m["id"], "ts": ts, **{
            k: a[k] for k in ("metric", "value", "threshold", "severity", "note")},
            "acknowledged": 0})
        raised.append({"id": aid, **a})

    ev = None
    if body.attest:
        ev = ledger.append(conn, "module", m["id"], "TELEMETRY_ATTESTED", {
            "window_start": ts, "window_end": ts, "samples": 1,
            "ec": {"mean": ec, "setpoint": m["ec_target"]},
            "ph": {"mean": ph, "setpoint": m["ph_target"]},
            "vpd_kpa": {"mean": vpd, "setpoint": m["vpd_target"]},
            "air_temp_c": {"mean": at, "setpoint": m["temp_target"]},
            "water_l": body.water_l or 0, "energy_kwh": body.energy_kwh or 0,
            "agency": actor,
        }, actor=actor)
    conn.commit()
    return {"accepted": True, "module_code": m["code"], "ts": ts, "vpd_kpa": vpd,
            "alerts_raised": raised, "ledger_event": ev}


class SimulateIn(BaseModel):
    hours: int = Field(default=1, ge=1, le=24)


@app.post(f"{API_PREFIX}/modules/{{key}}/simulate")
def simulate_module(key: str, body: SimulateIn, conn=Depends(get_conn),
                    actor: str = Depends(actor_of)):
    """Pull forward N hours of deterministic sensor readings for a live demo."""
    m = resolve_module(conn, key)
    last = conn.execute("SELECT MAX(ts) FROM telemetry WHERE module_id = ?", (m["id"],)).fetchone()[0]
    cursor = datetime.fromisoformat(last.replace("Z", "+00:00")) if last else ANCHOR
    key_seed = stable_int(m["code"]) % 99991
    total_water = total_energy = 0.0
    raised = 0
    for h in range(body.hours):
        cursor = cursor + timedelta(hours=1)
        s = simulate_sample(key_seed, int(cursor.timestamp() // 3600) % 100000, "BATCH_VEG")
        conn.execute(
            """INSERT INTO telemetry (module_id, ts, ec, ph, water_temp_c, air_temp_c, rh_pct,
               vpd_kpa, ppfd, co2_ppm, water_l, energy_kwh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (m["id"], iso(cursor), s["ec"], s["ph"], s["water_temp_c"], s["air_temp_c"],
             s["rh_pct"], s["vpd_kpa"], s["ppfd"], s["co2_ppm"], s["water_l"], s["energy_kwh"]),
        )
        total_water += s["water_l"]
        total_energy += s["energy_kwh"]
        for a in check_thresholds(s, m):
            insert(conn, "alert", {"id": new_id(), "module_id": m["id"], "ts": iso(cursor),
                                   "metric": a["metric"], "value": a["value"],
                                   "threshold": a["threshold"], "severity": a["severity"],
                                   "acknowledged": 0, "note": a["note"]})
            raised += 1
    conn.commit()
    return {"module_code": m["code"], "hours_added": body.hours, "to": iso(cursor),
            "water_l": round(total_water, 2), "energy_kwh": round(total_energy, 3),
            "alerts_raised": raised}


@app.get(f"{API_PREFIX}/alerts")
def list_alerts(open_only: bool = True, limit: int = 60, conn=Depends(get_conn)):
    clause = "WHERE a.acknowledged = 0" if open_only else ""
    rows = [dict(r) for r in conn.execute(
        f"""SELECT a.*, m.code AS module_code, m.cultivar, f.code AS facility_code
            FROM alert a JOIN grow_module m ON m.id = a.module_id
            JOIN facility f ON f.id = m.facility_id
            {clause} ORDER BY a.ts DESC LIMIT ?""", (limit,)).fetchall()]
    return {"items": rows, "count": len(rows)}


@app.post(f"{API_PREFIX}/alerts/{{alert_id}}/ack")
def ack_alert(alert_id: str, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    conn.execute("UPDATE alert SET acknowledged = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    return {"acknowledged": alert_id, "by": actor}


# ---------------------------------------------------------------------------
# traceability ledger
# ---------------------------------------------------------------------------
@app.get(f"{API_PREFIX}/ledger")
def ledger_tail(limit: int = Query(default=60, ge=1, le=500),
                entity_id: str | None = None, entity_type: str | None = None,
                conn=Depends(get_conn)):
    events = ledger.tail(conn, limit=limit, entity_id=entity_id, entity_type=entity_type)
    return {"items": events, "count": len(events), "head": ledger.head(conn)}


@app.get(f"{API_PREFIX}/ledger/verify")
def ledger_verify(conn=Depends(get_conn)):
    return ledger.verify(conn)


# ---------------------------------------------------------------------------
# batches
# ---------------------------------------------------------------------------
class BatchIn(BaseModel):
    module: str
    cultivar: str | None = None
    sow_date: str | None = None
    projected_green_kg: float | None = None


class AdvanceIn(BaseModel):
    stage: str | None = None
    payload: dict | None = None


@app.get(f"{API_PREFIX}/batches")
def list_batches(status: str | None = None, limit: int = 50, conn=Depends(get_conn)):
    clause, params = "", []
    if status:
        clause, params = "WHERE b.status = ?", [status]
    rows = conn.execute(
        f"""SELECT b.*, m.code AS module_code, f.code AS facility_code, f.country AS facility_country,
                   g.code AS grower_code
            FROM batch b JOIN grow_module m ON m.id = b.module_id
            JOIN facility f ON f.id = m.facility_id JOIN grower g ON g.id = f.grower_id
            {clause} ORDER BY b.sow_date DESC LIMIT ?""", (*params, limit)).fetchall()
    out = []
    for r in rows:
        r = dict(r)
        b = services.batch_public(r)
        b.update({"module_code": r["module_code"], "facility_code": r["facility_code"],
                  "facility_country": r["facility_country"], "grower_code": r["grower_code"]})
        b["event_count"] = ledger.event_count(conn, r["id"])
        b["has_eudr"] = bool(conn.execute(
            "SELECT 1 FROM compliance_report WHERE batch_id = ? AND kind = 'EUDR'", (r["id"],)).fetchone())
        b["has_lca"] = bool(conn.execute(
            "SELECT 1 FROM compliance_report WHERE batch_id = ? AND kind = 'LCA'", (r["id"],)).fetchone())
        out.append(b)
    return {"items": out, "count": len(out)}


def unique_batch_code(conn, sow: datetime) -> str:
    """LOT-YYMMDD-X, deduplicated against both code and qr_token.

    The seed data uses fixed letters; live creation shares the same namespace,
    so we walk the alphabet and then fall back to a two-hex suffix.
    """
    prefix = "LOT-" + sow.strftime("%y%m%d") + "-"
    existing = {r[0] for r in conn.execute(
        "SELECT code FROM batch WHERE code LIKE ?", (prefix + "%",))}
    for i in range(26):
        candidate = prefix + chr(65 + i)
        if candidate not in existing:
            return candidate
    i = 0
    while True:
        candidate = prefix + chr(65 + (i % 26)) + "-" + secrets.token_hex(1).upper()
        if candidate not in existing:
            return candidate
        i += 1


def unique_qr_token(conn, batch_code: str) -> str:
    """sha256-derived, salted if a collision ever appears."""
    token = qr_token(batch_code)
    if not conn.execute("SELECT 1 FROM batch WHERE qr_token = ?", (token,)).fetchone():
        return token
    salt = 0
    while True:
        salt += 1
        token = "npfc-" + hashlib.sha256(f"{batch_code}:{salt}".encode()).hexdigest()[:10]
        if not conn.execute("SELECT 1 FROM batch WHERE qr_token = ?", (token,)).fetchone():
            return token


@app.post(f"{API_PREFIX}/batches", status_code=201)
def create_batch(body: BatchIn, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    m = resolve_module(conn, body.module)
    fac = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (m["facility_id"],)).fetchone())
    sow = datetime.fromisoformat(body.sow_date).replace(tzinfo=UTC) if body.sow_date else datetime.now(UTC)
    module_count = max(conn.execute(
        "SELECT COUNT(*) FROM grow_module WHERE facility_id = ?", (fac["id"],)).fetchone()[0], 1)
    area = float(fac["footprint_m2"]) / module_count
    projected = body.projected_green_kg or round(area * 2.5, 1)
    code = unique_batch_code(conn, sow)
    token = unique_qr_token(conn, code)
    bid = new_id()
    insert(conn, "batch", {
        "id": bid, "code": code, "module_id": m["id"],
        "cultivar": body.cultivar or m["cultivar"], "sow_date": iso(sow),
        "projected_green_kg": projected, "qr_token": token, "status": "growing",
        "area_m2": area,
        "water_l": round(projected * 33.0, 1), "energy_kwh": round(projected * 6.5, 1),
        "created_at": iso(sow),
        "meta_json": json.dumps({"facility_code": fac["code"], "module_code": m["code"]}),
    })
    conn.execute("UPDATE grow_module SET status = 'cropped' WHERE id = ?", (m["id"],))
    ev = ledger.append(conn, "batch", bid, "BATCH_SOWN", {
        "cultivar": body.cultivar or m["cultivar"], "plant_count": m["plant_count"],
        "module_code": m["code"], "facility_code": fac["code"],
        "effective_area_m2": round(area, 1),
        "delivery": "aeroponic misting, 30 s every 5 min, sealed root chamber",
        "projected_green_kg": projected,
    }, actor=actor)
    conn.commit()
    return {"batch": services.batch_public(
        dict(conn.execute("SELECT * FROM batch WHERE id = ?", (bid,)).fetchone())),
        "ledger_event": ev}


@app.get(f"{API_PREFIX}/batches/{{key}}")
def get_batch(key: str, conn=Depends(get_conn)):
    return services.build_journey(conn, resolve_batch(conn, key))


@app.get(f"{API_PREFIX}/batches/{{key}}/journey")
def get_journey(key: str, conn=Depends(get_conn)):
    return services.build_journey(conn, resolve_batch(conn, key))


@app.post(f"{API_PREFIX}/batches/{{key}}/advance")
def advance_batch(key: str, body: AdvanceIn, conn=Depends(get_conn),
                  actor: str = Depends(actor_of)):
    batch = resolve_batch(conn, key)
    events = [e["event_type"] for e in ledger.tail(conn, limit=500, entity_id=batch["id"])]
    done = [s for s in STAGE_ORDER if s in events]
    target = body.stage
    if not target:
        remaining = [s for s in STAGE_ORDER if s not in events]
        if not remaining:
            raise HTTPException(409, "batch has completed every lifecycle stage")
        target = remaining[0]
    if target not in STAGE_ORDER:
        raise HTTPException(422, f"unknown stage '{target}'")
    if target in done:
        raise HTTPException(409, f"stage {target} already recorded for {batch['code']}")
    if done and STAGE_ORDER.index(target) < STAGE_ORDER.index(done[-1]):
        raise HTTPException(409, f"out-of-order: {done[-1]} already recorded, cannot go back to {target}")

    m = dict(conn.execute("SELECT * FROM grow_module WHERE id = ?", (batch["module_id"],)).fetchone())
    fac = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (m["facility_id"],)).fetchone())
    payload = dict(body.payload or {})

    updates: dict = {"status": "growing"}
    if target == "BATCH_HARVESTED":
        green = float(payload.get("green_kg") or batch["projected_green_kg"])
        payload.setdefault("green_kg", green)
        payload.setdefault("water_l_gross", batch["water_l"])
        payload.setdefault("energy_kwh", batch["energy_kwh"])
        payload.setdefault("area_m2", batch["area_m2"])
        payload.setdefault("yield_kg_per_m2", round(green / max(batch["area_m2"], 1), 3))
        payload.setdefault("water_recovery_pct", 94.0)
        updates = {"status": "harvested", "green_kg": green,
                   "harvest_date": payload.get("harvest_date") or now_iso()}
    elif target == "BATCH_ROASTED":
        roasted = float(payload.get("roasted_kg") or round(batch["green_kg"] * 0.85, 1))
        payload.setdefault("roasted_kg", roasted)
        payload.setdefault("green_kg", batch["green_kg"])
        payload.setdefault("weight_loss_pct", round((1 - roasted / max(batch["green_kg"], 0.1)) * 100, 1))
        updates = {"status": "roasted", "roasted_kg": roasted}
    elif target == "BATCH_PACKED":
        payload.setdefault("qr_token", batch["qr_token"])
        payload.setdefault("consumer_url", f"/consume.html?t={batch['qr_token']}")
        payload.setdefault("units_250g", int(max(batch["roasted_kg"], 0) * 4))
        updates = {"status": "packed"}
    elif target == "BATCH_SHIPPED":
        payload.setdefault("distance_km", fac["export_distance_km"])
        payload.setdefault("co2e_transport_kg",
                           round(fac["export_distance_km"] / 1000 * 0.062, 4))
        updates = {"status": "shipped"}
    else:
        updates = {"status": "growing"}

    conn.execute("UPDATE batch SET " + ", ".join(f"{k} = ?" for k in updates)
                 + " WHERE id = ?", (*updates.values(), batch["id"]))
    ev = ledger.append(conn, "batch", batch["id"], target, payload, actor=actor)

    issued = None
    if target == "BATCH_HARVESTED":
        fresh = dict(conn.execute("SELECT * FROM batch WHERE id = ?", (batch["id"],)).fetchone())
        grown = dict(conn.execute("SELECT * FROM grower WHERE id = ?", (fac["grower_id"],)).fetchone())
        evs = sorted(ledger.tail(conn, limit=1000, entity_id=batch["id"]), key=lambda e: e["seq"])
        for kind, maker in (("LCA", lambda: compute_lca(fresh, fac, fac["renewable_share"])),
                            ("EUDR", lambda: build_eudr_report(fresh, fac, grown, m, evs, now_iso()))):
            rep = maker()
            e = ledger.append(conn, "compliance", batch["id"], f"{kind}_ISSUED",
                              {"kind": kind, "report": rep} if kind == "LCA"
                              else {"kind": kind, "report_id": rep["report_id"],
                                    "risk": rep["risk"]["overall"], "checks": rep["total_checks"]},
                              actor="auditor:napell-fc")
            insert(conn, "compliance_report", {
                "id": new_id(), "batch_id": batch["id"], "kind": kind,
                "payload_json": json.dumps(rep, ensure_ascii=False), "issued_at": now_iso(),
                "ledger_seq": e["seq"], "hash": e["hash"],
            })
            issued = (issued or {}) | {kind: {"ledger_seq": e["seq"], "hash": e["hash"]}}

    services.refresh_grower_scores(conn)
    conn.commit()
    return {"batch_code": batch["code"], "advanced_to": target,
            "label": STAGE_LABEL[target], "payload": payload,
            "ledger_event": ev, "auto_issued_reports": issued}


@app.get(f"{API_PREFIX}/batches/{{key}}/compliance/{{kind}}")
def get_compliance(key: str, kind: str, conn=Depends(get_conn)):
    kind = kind.upper()
    if kind not in ("EUDR", "LCA"):
        raise HTTPException(422, "kind must be EUDR or LCA")
    batch = resolve_batch(conn, key)
    row = conn.execute("SELECT * FROM compliance_report WHERE batch_id = ? AND kind = ?",
                       (batch["id"], kind)).fetchone()
    if not row:
        module, facility, grower, _ = batch_context(conn, batch)
        if kind == "LCA":
            return {"batch_code": batch["code"], "kind": kind, "issued": False,
                    "preview": compute_lca(batch, facility, facility["renewable_share"])}
        evs = sorted(ledger.tail(conn, limit=1000, entity_id=batch["id"]), key=lambda e: e["seq"])
        return {"batch_code": batch["code"], "kind": kind, "issued": False,
                "preview": build_eudr_report(batch, facility, grower, module, evs, now_iso())}
    row = dict(row)
    return {"batch_code": batch["code"], "kind": kind, "issued": True,
            "issued_at": row["issued_at"], "hash": row["hash"], "ledger_seq": row["ledger_seq"],
            "report": json.loads(row["payload_json"])}


class LcaPreviewIn(BaseModel):
    renewable_share: float = Field(default=0.6, ge=0, le=1)


@app.post(f"{API_PREFIX}/batches/{{key}}/compliance/lca/preview")
def lca_preview(key: str, body: LcaPreviewIn, conn=Depends(get_conn)):
    batch = resolve_batch(conn, key)
    module, facility, _, _ = batch_context(conn, batch)
    out = compute_lca(batch, facility, body.renewable_share)
    out["provisional"] = batch["green_kg"] == 0
    return out


@app.post(f"{API_PREFIX}/batches/{{key}}/compliance/{{kind}}", status_code=201)
def issue_compliance(key: str, kind: str, conn=Depends(get_conn), actor: str = Depends(actor_of)):
    kind = kind.upper()
    if kind not in ("EUDR", "LCA"):
        raise HTTPException(422, "kind must be EUDR or LCA")
    batch = resolve_batch(conn, key)
    module, facility, grower, _ = batch_context(conn, batch)
    evs = sorted(ledger.tail(conn, limit=1000, entity_id=batch["id"]), key=lambda e: e["seq"])
    if kind == "LCA":
        report = compute_lca(batch, facility, facility["renewable_share"])
        summary = {"kind": kind, "report": report}
    else:
        report = build_eudr_report(batch, facility, grower, module, evs, now_iso())
        summary = {"kind": kind, "report_id": report["report_id"],
                   "risk": report["risk"]["overall"], "checks": report["total_checks"]}
    ev = ledger.append(conn, "compliance", batch["id"], f"{kind}_ISSUED", summary, actor=actor)
    rid = new_id()
    conn.execute("DELETE FROM compliance_report WHERE batch_id = ? AND kind = ?", (batch["id"], kind))
    insert(conn, "compliance_report", {
        "id": rid, "batch_id": batch["id"], "kind": kind,
        "payload_json": json.dumps(report, ensure_ascii=False), "issued_at": now_iso(),
        "ledger_seq": ev["seq"], "hash": ev["hash"],
    })
    conn.commit()
    return {"batch_code": batch["code"], "kind": kind, "issued_at": now_iso(),
            "hash": ev["hash"], "ledger_seq": ev["seq"], "report": report}


# ---------------------------------------------------------------------------
# consumer (Thank My Farm)
# ---------------------------------------------------------------------------
@app.get(f"{API_PREFIX}/consumer/{{token}}")
def consumer_view(token: str, conn=Depends(get_conn)):
    batch = resolve_batch(conn, token)
    module, facility, grower, _ = batch_context(conn, batch)
    events = sorted(ledger.tail(conn, limit=1000, entity_id=batch["id"]), key=lambda e: e["seq"])
    by_type = {e["event_type"]: e for e in events}
    lca = compute_lca(batch, facility, facility["renewable_share"])
    scans = dict(conn.execute(
        """SELECT COUNT(*) total, SUM(CASE WHEN kind='tip' THEN 1 ELSE 0 END) tips,
                  COALESCE(SUM(amount),0) tip_usd FROM scan WHERE batch_id = ?""",
        (batch["id"],)).fetchone())
    by_country = [dict(r) for r in conn.execute(
        """SELECT country, COUNT(*) c FROM scan WHERE batch_id = ? AND country IS NOT NULL
           GROUP BY country ORDER BY c DESC LIMIT 10""", (batch["id"],)).fetchall()]
    return {
        "batch": services.batch_public(batch),
        "grower": {"display_name": grower["display_name"], "org": grower["org"],
                   "country": grower["country"], "code": grower["code"],
                   "did": grower["did"], "kyc_level": grower["kyc_level"]},
        "facility": {"name": facility["name"], "city": facility["city"],
                     "country": facility["country"], "lat": facility["lat"],
                     "lon": facility["lon"], "system_type": facility["system_type"],
                     "footprint_m2": facility["footprint_m2"], "racks": facility["racks"],
                     "renewable_share": facility["renewable_share"]},
        "module": {"code": module["code"], "cultivar": module["cultivar"],
                   "plant_count": module["plant_count"]},
        "journey": [
            {"stage": k, "label": STAGE_LABEL[k], "completed": k in by_type,
             "at": by_type[k]["ts"] if k in by_type else None,
             "hash": by_type[k]["hash"][:24] + "…" if k in by_type else None,
             "seq": by_type[k]["seq"] if k in by_type else None,
             "payload": by_type[k]["payload"] if k in by_type else None}
            for k in STAGE_ORDER
        ],
        "environment": {
            "setpoints": {"ec": module["ec_target"], "ph": module["ph_target"],
                          "vpd_kpa": module["vpd_target"], "ppfd": module["ppfd_target"],
                          "air_temp_c": module["temp_target"]},
            "attestations": len([e for e in events if e["event_type"] == "TELEMETRY_ATTESTED"]),
            "samples": 168 * 7 * max(1, len([e for e in events if e["event_type"] == "TELEMETRY_ATTESTED"])),
        },
        "impact": lca,
        "integrity": {"events": len(events),
                      "head_hash": events[-1]["hash"] if events else None,
                      "head_seq": events[-1]["seq"] if events else None,
                      "chain_ok": ledger.verify(conn)["ok"]},
        "community": {"scans": scans.get("total") or 0, "tips": scans.get("tips") or 0,
                      "tip_usd": round(scans.get("tip_usd") or 0, 2), "by_country": by_country},
        "projects": [dict(r) for r in conn.execute(
            "SELECT * FROM project WHERE status = 'active' ORDER BY raised_usd DESC").fetchall()],
    }


class EngageIn(BaseModel):
    kind: str = "view"
    country: str | None = None
    amount: float = 0.0
    project_id: str | None = None
    device: str | None = "Web"


@app.post(f"{API_PREFIX}/consumer/{{token}}/engage", status_code=201)
def consumer_engage(token: str, body: EngageIn, conn=Depends(get_conn)):
    batch = resolve_batch(conn, token)
    kind = body.kind if body.kind in ("view", "tip") else "view"
    insert(conn, "scan", {
        "id": new_id(), "qr_token": batch["qr_token"], "batch_id": batch["id"],
        "ts": now_iso(), "country": body.country, "device": body.device, "kind": kind,
        "amount": round(body.amount, 2) if kind == "tip" else 0.0,
        "currency": "USD", "project_id": body.project_id,
    })
    ev = None
    if kind == "tip" and body.amount > 0:
        project = None
        if body.project_id:
            row = conn.execute("SELECT * FROM project WHERE id = ? OR name = ?",
                               (body.project_id, body.project_id)).fetchone()
            project = dict(row) if row else None
            if project:
                conn.execute("UPDATE project SET raised_usd = raised_usd + ?, backers = backers + 1 WHERE id = ?",
                             (round(body.amount, 2), project["id"]))
        ev = ledger.append(conn, "fund", batch["id"], "FUND_RECEIVED", {
            "amount_usd": round(body.amount, 2), "purpose": "origin_community_support",
            "project": project["name"] if project else None,
            "project_id": project["id"] if project else None,
            "allocated_to": "grower",
            "grower_code": conn.execute(
                """SELECT g.code FROM grower g JOIN facility f ON f.grower_id = g.id
                   JOIN grow_module m ON m.facility_id = f.id WHERE m.id = ?""",
                (batch["module_id"],)).fetchone()[0],
            "traceable": True,
        }, actor="consumer:qr")
    conn.commit()
    return {"recorded": kind, "amount": body.amount, "batch_code": batch["code"], "ledger_event": ev}


@app.get(f"{API_PREFIX}/projects")
def list_projects(conn=Depends(get_conn)):
    rows = [dict(r) for r in conn.execute("SELECT * FROM project ORDER BY raised_usd DESC").fetchall()]
    for r in rows:
        r["progress_pct"] = round(r["raised_usd"] / r["goal_usd"] * 100, 1) if r["goal_usd"] else 0
        r["funded_by_batch"] = conn.execute(
            "SELECT COUNT(*) FROM scan WHERE project_id = ? AND kind = 'tip'", (r["id"],)).fetchone()[0]
    return {"items": rows, "count": len(rows)}


def qr_svg_markup(data: str, scale: int = 5, border: int = 2,
                  dark: str = "#000000", light: str = "#ffffff") -> str:
    """Render a QR matrix to SVG ourselves.

    segno's svg_inline() has kwarg conflicts in 1.6.x and its output carries no
    xmlns, which makes it unusable as an <img> source. segno still does the
    encoding; we only draw the result.
    """
    import html

    qr = segno.make(data, error="m")
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    total = n + border * 2
    px = total * scale

    path = []
    for y, row in enumerate(matrix):
        x = 0
        while x < n:
            if row[x]:
                start = x
                while x < n and row[x]:
                    x += 1
                path.append(f"M{start + border} {y + border}h{x - start}v1h-{x - start}z")
            else:
                x += 1

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
        f'viewBox="0 0 {total} {total}" shape-rendering="crispEdges" role="img" '
        f'aria-label="QR code for batch token {html.escape(data)}">'
        f'<rect width="{total}" height="{total}" fill="{light}"/>'
        f'<path d="{"".join(path)}" fill="{dark}"/>'
        "</svg>"
    )


@app.get(f"{API_PREFIX}/qr/{{token}}")
def qr_svg(token: str, scale: int = Query(default=5, ge=2, le=20), conn=Depends(get_conn)):
    batch = resolve_batch(conn, token)
    return HTMLResponse(qr_svg_markup(batch["qr_token"], scale=scale),
                        media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=3600"})


# ---------------------------------------------------------------------------
# analytics + admin
# ---------------------------------------------------------------------------
@app.get(f"{API_PREFIX}/analytics/impact")
def analytics_impact(conn=Depends(get_conn)):
    ov = services.overview(conn)
    rows = []
    for r in conn.execute(
            """SELECT b.*, f.renewable_share AS renewable_share,
                      f.export_distance_km AS export_distance_km,
                      f.footprint_m2 AS footprint_m2, f.cycles_per_year AS cycles_per_year
               FROM batch b
               JOIN grow_module m ON m.id = b.module_id
               JOIN facility f ON f.id = m.facility_id""").fetchall():
        r = dict(r)
        lca = compute_lca(r, r, r["renewable_share"])
        rows.append({
            "batch_code": r["code"], "green_kg": r["green_kg"],
            "renewable_share": r["renewable_share"],
            "water_l_per_kg": next(l["aeroponic"] for l in lca["legs"] if l["key"] == "water"),
            "co2e_kg_per_kg": next(l["aeroponic"] for l in lca["legs"] if l["key"] == "co2e"),
            "land_m2_per_kg": next(l["aeroponic"] for l in lca["legs"] if l["key"] == "land"),
        })
    return {"overview": ov, "batches": rows,
            "scenarios": ["renewable_share", "distance_to_port_km", "water_recovery_pct"]}


@app.get(f"{API_PREFIX}/analytics/scenario")
def analytics_scenario(batch: str, renewable_share: float = Query(default=0.6, ge=0, le=1),
                       water_recovery_pct: float | None = None, conn=Depends(get_conn)):
    b = resolve_batch(conn, batch)
    module, facility, _, _ = batch_context(conn, b)
    lca = compute_lca(b, facility, renewable_share)
    if water_recovery_pct is not None:
        from . import domain
        original = domain.WATER_RECOVERY
        domain.WATER_RECOVERY = max(0.0, min(0.999, water_recovery_pct / 100.0))
        try:
            lca = compute_lca(b, facility, renewable_share)
        finally:
            domain.WATER_RECOVERY = original
    lca["provisional"] = b["green_kg"] == 0
    return lca


class SeedIn(BaseModel):
    force: bool = False


@app.post(f"{API_PREFIX}/admin/seed")
def admin_seed(body: SeedIn):
    return run_seed(force=body.force)


@app.get("/healthz")
def healthz(conn=Depends(get_conn)):
    return {"ok": True, "db": conn.execute("SELECT COUNT(*) FROM ledger_event").fetchone()[0],
            "at": now_iso()}


# ---------------------------------------------------------------------------
# static frontend (same-origin mount, must be last)
#
# The site is served from the repository root because GitHub Pages publishes
# that same folder. That means the mount would also expose backend sources,
# the SQLite file and local notes — so a deny-list keeps them out of reach
# even when the dev server is bound to 0.0.0.0 for a demo.
# ---------------------------------------------------------------------------
DENIED_PREFIXES = ("backend", "docs", ".workbuddy", ".git", "tests")


class SiteFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        # Windows trap: Starlette normalises the path with os.path.normpath, so
        # by the time it reaches us "backend/app/main.py" has become
        # "backend\app\main.py". Splitting on "/" alone silently matched nothing
        # and the deny-list never fired. Normalise both separators first.
        head = path.replace("\\", "/").lstrip("/").split("/", 1)[0]
        if head in DENIED_PREFIXES or head.startswith("."):
            return PlainTextResponse("Not found", status_code=404)
        return await super().get_response(path, scope)


if WEB_DIR.exists():
    app.mount("/", SiteFiles(directory=str(WEB_DIR), html=True), name="web")
else:  # pragma: no cover
    @app.get("/")
    def _no_web():
        return JSONResponse({"error": "site directory not found", "expected": str(WEB_DIR)}, status_code=500)
