"""Deterministic demo network for Napell Farmer Connect.

Everything is generated from fixed seeds, so the numbers on the site are stable
across restarts. Re-running with force=True rebuilds the ledger from scratch.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import datetime, timedelta, timezone

from . import ledger
from .config import DB_PATH, STAGE_ORDER
from .db import connect, init_db, insert, new_id, now_iso
from .domain import check_thresholds, simulate_sample

UTC = timezone.utc
ANCHOR = datetime(2026, 10, 15, 4, 0, tzinfo=UTC)      # network "now"
YIELD_PER_CYCLE = 2.5                                  # kg green / m2 floor / cycle
WATER_PER_KG = 33.0                                    # L gross recirculated / kg green
ENERGY_PER_KG = 6.5                                    # kWh / kg green
ROAST_YIELD = 0.85

GROWERS = [
    dict(code="NPF-0001", display_name="Napell Aeroponic HK Ltd.", org="Napell BIO",
         country="Hong Kong, China", region="Hong Kong, China", kyc_level=3,
         wallet="0x7a3f...c21e", meta={"role": "operator", "since": "2023-08-01"}),
    dict(code="NPF-0002", display_name="Kansai Vertical Coffee KK", org="Kansai Vertical",
         country="Japan", region="Kansai", kyc_level=2,
         wallet="0x51bd...9f04", meta={"role": "licensed_partner", "since": "2024-06-10"}),
    dict(code="NPF-0003", display_name="Rhine Green Cultivation BV", org="Rhine Green",
         country="Netherlands", region="Zuid-Holland", kyc_level=2,
         wallet="0x0e72...44ab", meta={"role": "licensed_partner", "since": "2025-01-20"}),
]

FACILITIES = [
    dict(grower="NPF-0001", code="FAC-HK-01", name="Napell Yuen Long Grow Hub",
         country="Hong Kong, China", region="New Territories", city="Yuen Long",
         lat=22.4445, lon=114.0225, system_type="aeroponic_vertical",
         footprint_m2=480.0, racks=8, cycles_per_year=2.6, export_distance_km=28.0,
         renewable_share=0.62, commissioned_at="2024-03-18", modules=5),
    dict(grower="NPF-0001", code="FAC-HK-02", name="Napell Tsuen Wan Nursery",
         country="Hong Kong, China", region="New Territories", city="Tsuen Wan",
         lat=22.3707, lon=114.1140, system_type="aeroponic_container",
         footprint_m2=200.0, racks=4, cycles_per_year=3.1, export_distance_km=22.0,
         renewable_share=0.45, commissioned_at="2023-11-02", modules=2),
    dict(grower="NPF-0002", code="FAC-JP-01", name="Kansai Grow Facility",
         country="Japan", region="Osaka", city="Osaka",
         lat=34.6937, lon=135.5023, system_type="aeroponic_vertical",
         footprint_m2=320.0, racks=6, cycles_per_year=2.4, export_distance_km=14.0,
         renewable_share=0.38, commissioned_at="2024-06-10", modules=3),
    dict(grower="NPF-0003", code="FAC-NL-01", name="Rhine Aeroponic Works",
         country="Netherlands", region="Zuid-Holland", city="Rotterdam",
         lat=51.9244, lon=4.4777, system_type="aeroponic_vertical",
         footprint_m2=400.0, racks=6, cycles_per_year=2.2, export_distance_km=6.0,
         renewable_share=0.81, commissioned_at="2025-01-20", modules=2),
]

CULTIVARS = [
    ("Napell Catimor-A", 1.62, 5.78, 0.92, 430.0, 26.0),
    ("Napell Caturra-Nano", 1.58, 5.72, 0.88, 400.0, 25.5),
    ("Arabica Geisha (aeroponic)", 1.74, 5.85, 1.02, 470.0, 24.5),
    ("Napell SL28 Comp", 1.70, 5.80, 0.96, 455.0, 25.0),
    ("Fine-Aroma Robusta (aeroponic)", 1.95, 5.95, 1.15, 510.0, 27.5),
]

BATCHES = [
    dict(sow="2026-02-18", stage="BATCH_SHIPPED", ymult=1.04, grade="Specialty 87.5",
         fac="FAC-HK-01", cult=0, buyer="Segafredo Zanetti S.p.A. (demo)"),
    dict(sow="2026-04-06", stage="BATCH_ROASTED", ymult=0.97, grade="Specialty 86.0",
         fac="FAC-HK-01", cult=2, buyer="UCC Ueshima Coffee (demo)"),
    dict(sow="2026-05-22", stage="BATCH_PACKED", ymult=1.01, grade="Specialty 85.5",
         fac="FAC-NL-01", cult=3, buyer="Rotterdam Green Roasters (demo)"),
    dict(sow="2026-06-30", stage="BATCH_HARVESTED", ymult=0.94, grade="Premium 83.5",
         fac="FAC-JP-01", cult=1, buyer=None),
    dict(sow="2026-08-14", stage="BATCH_FRUITING", ymult=1.00, grade=None,
         fac="FAC-HK-02", cult=4, buyer=None),
    dict(sow="2026-09-02", stage="BATCH_VEG", ymult=1.00, grade=None,
         fac="FAC-JP-01", cult=0, buyer=None),
    dict(sow="2026-09-19", stage="BATCH_FLOWERING", ymult=1.00, grade=None,
         fac="FAC-NL-01", cult=2, buyer=None),
    dict(sow="2026-10-02", stage="BATCH_GERMINATED", ymult=1.00, grade=None,
         fac="FAC-HK-01", cult=0, buyer=None),
]

PROJECTS = [
    dict(name="Yuen Long Water Circularity Upgrade", region="Hong Kong, China",
         summary="Condensate capture and UV sterilisation retrofit across 8 racks — lifts "
                 "closed-loop water recovery from 94% to 98% and cuts net withdrawal below 1 L/kg.",
         goal_usd=48000, raised_usd=31240, backers=418),
    dict(name="Kansai Renewable PPA", region="Japan",
         summary="Three-year solar PPA covering the full Osaka grow-facility load, taking "
                 "cradle-to-gate carbon down by roughly 43% against conventional baseline.",
         goal_usd=96000, raised_usd=28700, backers=266),
    dict(name="Aeroponic Cultivar Library", region="Global",
         summary="Open-access genotype screen for dwarf arabica lines suited to closed-loop "
                 "aeroponic cycles. Every result is published back to the ledger.",
         goal_usd=150000, raised_usd=61250, backers=905),
]

STAGE_OFFSETS = {
    "BATCH_SOWN": 0, "BATCH_GERMINATED": 12, "BATCH_VEG": 38, "BATCH_FLOWERING": 96,
    "BATCH_FRUITING": 148, "BATCH_HARVESTED": 206, "BATCH_PROCESSED": 211,
    "BATCH_MILLED": 226, "BATCH_ROASTED": 243, "BATCH_PACKED": 246, "BATCH_SHIPPED": 252,
}

STAGE_STATUS = {
    "BATCH_SOWN": "growing", "BATCH_GERMINATED": "growing", "BATCH_VEG": "growing",
    "BATCH_FLOWERING": "growing", "BATCH_FRUITING": "growing", "BATCH_HARVESTED": "harvested",
    "BATCH_PROCESSED": "processed", "BATCH_MILLED": "milled", "BATCH_ROASTED": "roasted",
    "BATCH_PACKED": "packed", "BATCH_SHIPPED": "shipped",
}


def qr_token(batch_code: str) -> str:
    return "npfc-" + hashlib.sha256(batch_code.encode()).hexdigest()[:10]


def stable_int(value: str) -> int:
    """Deterministic across processes — builtin hash() is salted per run."""
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def reset_database() -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(str(DB_PATH) + suffix)
        except OSError:
            pass


def _stage_payload(stage: str, ctx: dict, rng: random.Random) -> dict:
    c = ctx
    if stage == "BATCH_SOWN":
        return {"cultivar": c["cultivar"], "plant_count": c["plant_count"],
                "module_code": c["module_code"], "facility_code": c["facility_code"],
                "effective_area_m2": round(c["area"], 1),
                "delivery": "aeroponic misting, 30 s every 5 min, sealed root chamber"}
    if stage == "BATCH_GERMINATED":
        return {"germination_rate_pct": round(rng.uniform(93, 99.5), 1),
                "days_to_germination": 12, "viability_note": "uniform emergence across all trays"}
    if stage == "BATCH_VEG":
        return {"avg_ec": round(c["ec"] + rng.uniform(-0.05, 0.05), 3),
                "avg_ph": round(c["ph"] + rng.uniform(-0.05, 0.05), 3),
                "avg_vpd_kpa": round(c["vpd"] + rng.uniform(-0.05, 0.05), 3),
                "canopy_cover_pct": round(rng.uniform(78, 92), 1),
                "note": "closed-loop EC/pH held inside +-0.05 across the whole window"}
    if stage == "BATCH_FLOWERING":
        return {"photoperiod_h": 11.5, "avg_vpd_kpa": round(c["vpd"], 3),
                "flower_sites": int(c["plant_count"] * rng.uniform(38, 52)),
                "note": "climate window locked; no open-pollinator or pesticide exposure"}
    if stage == "BATCH_FRUITING":
        return {"cherry_set_pct": round(rng.uniform(88, 96), 1),
                "avg_brix": round(rng.uniform(18.4, 22.6), 1),
                "days_to_harvest_estimate": 58}
    if stage == "BATCH_HARVESTED":
        return {"green_kg": c["green_kg"], "cherry_kg": round(c["green_kg"] * 5.6, 1),
                "moisture_pct": round(rng.uniform(10.4, 11.6), 2),
                "water_l_gross": c["water_l"], "water_recovery_pct": 94.0,
                "energy_kwh": c["energy_kwh"], "area_m2": round(c["area"], 1),
                "yield_kg_per_m2": round(c["green_kg"] / c["area"], 3)}
    if stage == "BATCH_PROCESSED":
        return {"process": "washed", "fermentation_h": 36,
                "moisture_pct": round(rng.uniform(10.6, 11.4), 2),
                "defect_pct": round(rng.uniform(0.4, 1.6), 2),
                "note": "onsite processing — no third-party custody gap"}
    if stage == "BATCH_MILLED":
        return {"green_kg": c["green_kg"], "screen_size": "15/16",
                "grade": c["grade"] or "Specialty", "milling_loss_pct": 0.8}
    if stage == "BATCH_ROASTED":
        return {"green_kg": c["green_kg"], "roasted_kg": c["roasted_kg"],
                "weight_loss_pct": round((1 - ROAST_YIELD) * 100, 1),
                "roast_profile": "medium-light, 11:20 total, first crack 8:45",
                "buyer": c["buyer"]}
    if stage == "BATCH_PACKED":
        return {"qr_token": c["qr_token"], "units_250g": int(c["roasted_kg"] * 4),
                "packaging": "mono-material recyclable, PPWR-aligned",
                "consumer_url": f"/consume.html?t={c['qr_token']}"}
    if stage == "BATCH_SHIPPED":
        return {"carrier": "Ocean freight, reefer-free ambient",
                "destination": c["buyer"], "container_id": f"MSKU{rng.randint(1000000, 9999999)}",
                "distance_km": c["distance_km"], "co2e_transport_kg": round(c["distance_km"] / 1000 * 0.062, 4)}
    return {}


def seed(force: bool = False) -> dict:
    if force:
        reset_database()
    init_db()
    conn = connect()
    try:
        if not force:
            existing = conn.execute("SELECT COUNT(*) FROM grower").fetchone()[0]
            if existing:
                return {"seeded": False, "reason": "database already populated", "growers": existing}

        ts0 = iso(ANCHOR - timedelta(days=420))

        # ---------------- growers ----------------
        grower_ids: dict[str, str] = {}
        for g in GROWERS:
            gid = new_id()
            grower_ids[g["code"]] = gid
            did = f"did:napell:{g['code'].lower()}"
            insert(conn, "grower", {
                "id": gid, "code": g["code"], "display_name": g["display_name"],
                "org": g["org"], "country": g["country"], "region": g["region"],
                "did": did, "wallet": g["wallet"], "kyc_level": g["kyc_level"],
                "created_at": ts0, "meta_json": json.dumps(g["meta"], ensure_ascii=False),
            })
            ledger.append(conn, "grower", gid, "GROWER_REGISTERED", {
                "code": g["code"], "legal_name": g["display_name"], "org": g["org"],
                "country": g["country"], "kyc_level": g["kyc_level"], "did": did,
                "wallet": g["wallet"],
            }, actor=f"operator:{g['code']}", ts=ts0)

        # ---------------- facilities + modules ----------------
        facility_ids: dict[str, str] = {}
        fac_rows: dict[str, dict] = {}
        modules: list[dict] = []
        for f in FACILITIES:
            fid = new_id()
            facility_ids[f["code"]] = fid
            fac_rows[f["code"]] = dict(f, id=fid)
            insert(conn, "facility", {
                "id": fid, "grower_id": grower_ids[f["grower"]], "code": f["code"],
                "name": f["name"], "country": f["country"], "region": f["region"],
                "city": f["city"], "lat": f["lat"], "lon": f["lon"],
                "system_type": f["system_type"], "footprint_m2": f["footprint_m2"],
                "racks": f["racks"], "cycles_per_year": f["cycles_per_year"],
                "export_distance_km": f["export_distance_km"],
                "renewable_share": f["renewable_share"],
                "commissioned_at": f["commissioned_at"], "created_at": ts0,
            })
            ledger.append(conn, "facility", fid, "FACILITY_COMMISSIONED", {
                "code": f["code"], "name": f["name"], "city": f["city"], "country": f["country"],
                "lat": f["lat"], "lon": f["lon"], "system_type": f["system_type"],
                "footprint_m2": f["footprint_m2"], "racks": f["racks"],
                "commissioned_at": f["commissioned_at"], "renewable_share": f["renewable_share"],
                "land_use_note": "controlled-environment structure, no agricultural plot",
            }, actor=f"operator:{f['grower']}", ts=ts0)

            per = f["footprint_m2"] / f["modules"]
            for i in range(f["modules"]):
                cult = CULTIVARS[(stable_int(f["code"]) + i) % len(CULTIVARS)]
                mid = new_id()
                mcode = f"{f['code'].split('FAC-')[1]}-M{i + 1:02d}"
                modules.append({"id": mid, "code": mcode, "facility": f["code"],
                                "facility_id": fid, "area_m2": per, "cultivar": cult[0],
                                "plant_count": int(per * 4)})
                insert(conn, "grow_module", {
                    "id": mid, "facility_id": fid, "code": mcode,
                    "name": f"{f['name']} · Rack {i + 1}", "cultivar": cult[0],
                    "plant_count": int(per * 4), "ec_target": cult[1], "ph_target": cult[2],
                    "vpd_target": cult[3], "ppfd_target": cult[4], "temp_target": cult[5],
                    "status": "idle", "created_at": ts0,
                })
                ledger.append(conn, "module", mid, "MODULE_COMMISSIONED", {
                    "code": mcode, "facility_code": f["code"], "cultivar": cult[0],
                    "effective_area_m2": round(per, 1), "plant_count": int(per * 4),
                    "rack_index": i + 1,
                    "setpoints": {"ec": cult[1], "ph": cult[2], "vpd_kpa": cult[3],
                                  "ppfd": cult[4], "air_temp_c": cult[5]},
                    "sensor_channels": ["ec", "ph", "water_temp_c", "air_temp_c",
                                        "rh_pct", "ppfd", "co2_ppm", "vpd_kpa"],
                }, actor=f"operator:{f['grower']}", ts=ts0)

        # ---------------- batches ----------------
        rng = random.Random(20261015)
        batch_meta: list[dict] = []
        for idx, b in enumerate(BATCHES, start=1):
            fac = fac_rows[b["fac"]]
            candidates = [m for m in modules if m["facility"] == b["fac"] and m["cultivar"] == CULTIVARS[b["cult"]][0]]
            mod = candidates[0] if candidates else next(m for m in modules if m["facility"] == b["fac"])
            sow = datetime.fromisoformat(b["sow"]).replace(tzinfo=UTC)
            area = mod["area_m2"]
            projected = round(area * YIELD_PER_CYCLE * b["ymult"], 1)
            harvested = STAGE_ORDER.index(b["stage"]) >= STAGE_ORDER.index("BATCH_HARVESTED")
            green_kg = projected if harvested else 0.0
            roasted_kg = round(green_kg * ROAST_YIELD, 1) if STAGE_ORDER.index(b["stage"]) >= STAGE_ORDER.index("BATCH_ROASTED") else 0.0
            water_l = round(projected * WATER_PER_KG, 1)
            energy_kwh = round(projected * ENERGY_PER_KG, 1)
            bid = new_id()
            code = f"LOT-{sow.strftime('%y%m%d')}-{chr(64 + idx)}"
            token = qr_token(code)
            insert(conn, "batch", {
                "id": bid, "code": code, "module_id": mod["id"], "cultivar": mod["cultivar"],
                "sow_date": iso(sow), "harvest_date": iso(sow + timedelta(days=206)) if harvested else None,
                "green_kg": green_kg, "roasted_kg": roasted_kg, "projected_green_kg": projected,
                "grade": b["grade"], "buyer": b["buyer"], "water_l": water_l,
                "energy_kwh": energy_kwh, "area_m2": round(area, 1), "qr_token": token,
                "status": STAGE_STATUS[b["stage"]], "created_at": iso(sow),
                "meta_json": json.dumps({"facility_code": b["fac"], "module_code": mod["code"]}),
            })

            ctx = {
                "cultivar": mod["cultivar"], "plant_count": mod["plant_count"],
                "module_code": mod["code"], "facility_code": b["fac"], "area": area,
                "green_kg": green_kg, "roasted_kg": roasted_kg, "grade": b["grade"],
                "buyer": b["buyer"], "qr_token": token, "water_l": water_l,
                "energy_kwh": energy_kwh, "distance_km": fac["export_distance_km"],
                "ec": 0.0, "ph": 0.0, "vpd": 0.0,
            }
            cult_row = next(c for c in CULTIVARS if c[0] == mod["cultivar"])
            ctx.update(ec=cult_row[1], ph=cult_row[2], vpd=cult_row[3])

            upto = STAGE_ORDER.index(b["stage"])
            for si, stage in enumerate(STAGE_ORDER[: upto + 1]):
                if not harvested and stage in ("BATCH_HARVESTED", "BATCH_PROCESSED", "BATCH_MILLED",
                                               "BATCH_ROASTED", "BATCH_PACKED", "BATCH_SHIPPED"):
                    continue
                at = sow + timedelta(days=STAGE_OFFSETS[stage])
                ledger.append(conn, "batch", bid, stage, _stage_payload(stage, ctx, rng),
                              actor=f"facility:{b['fac']}", ts=iso(at))

            # weekly telemetry attestation written into the chain
            weeks = max(1, int(((ANCHOR - sow).days) / 7))
            for w in range(weeks):
                at = sow + timedelta(days=7 * w)
                snap = simulate_sample(stable_int(code) % 99991, (at.hour + w) % 24, b["stage"])
                ledger.append(conn, "batch", bid, "TELEMETRY_ATTESTED", {
                    "window_start": iso(at), "window_end": iso(at + timedelta(days=7)),
                    "samples": 168 * 7,
                    "ec": {"mean": round(snap["ec"], 3), "setpoint": cult_row[1]},
                    "ph": {"mean": round(snap["ph"], 3), "setpoint": cult_row[2]},
                    "vpd_kpa": {"mean": round(snap["vpd_kpa"], 3), "setpoint": cult_row[3]},
                    "air_temp_c": {"mean": round(snap["air_temp_c"], 2), "setpoint": cult_row[5]},
                    "water_l": round(water_l / max(weeks, 1), 1),
                    "energy_kwh": round(energy_kwh / max(weeks, 1), 2),
                    "agency": "Napell closed-loop controller, signed by facility gateway",
                }, actor=f"facility:{b['fac']}@gateway", ts=iso(at))

            conn.execute("UPDATE grow_module SET status = ? WHERE id = ?",
                         ("cropped" if b["stage"] != "BATCH_SHIPPED" else "idle", mod["id"]))
            batch_meta.append({"id": bid, "code": code, "token": token, "stage": b["stage"],
                               "module_id": mod["id"], "facility_code": b["fac"],
                               "green_kg": green_kg, "projected": projected})

        # ---------------- telemetry ----------------
        tel_rows = 0
        for m in modules:
            active = next((bm for bm in batch_meta if bm["module_id"] == m["id"]), None)
            phase = active["stage"] if active else "BATCH_VEG"
            seed_key = stable_int(m["code"]) % 99991
            for h in range(168):
                at = ANCHOR - timedelta(hours=168 - h)
                s = simulate_sample(seed_key, h, phase)
                conn.execute(
                    """INSERT INTO telemetry (module_id, ts, ec, ph, water_temp_c, air_temp_c,
                       rh_pct, vpd_kpa, ppfd, co2_ppm, water_l, energy_kwh)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (m["id"], iso(at), s["ec"], s["ph"], s["water_temp_c"], s["air_temp_c"],
                     s["rh_pct"], s["vpd_kpa"], s["ppfd"], s["co2_ppm"], s["water_l"], s["energy_kwh"]),
                )
                tel_rows += 1
                for a in check_thresholds(s, {"ec_target": 1.65, "ph_target": 5.75,
                                              "vpd_target": 0.95, "temp_target": 26.0}):
                    if random.Random(seed_key + h + stable_int(a["metric"])).random() < 0.06:
                        insert(conn, "alert", {
                            "id": new_id(), "module_id": m["id"], "ts": iso(at),
                            "metric": a["metric"], "value": a["value"],
                            "threshold": a["threshold"], "severity": a["severity"],
                            "acknowledged": 1 if h > 96 else 0, "note": a["note"],
                        })

        # ---------------- compliance reports ----------------
        from .domain import build_eudr_report, compute_lca
        from .services import refresh_grower_scores
        reports = 0
        for bm in batch_meta:
            if STAGE_ORDER.index(bm["stage"]) < STAGE_ORDER.index("BATCH_HARVESTED"):
                continue
            batch = dict(conn.execute("SELECT * FROM batch WHERE id = ?", (bm["id"],)).fetchone())
            module = dict(conn.execute("SELECT * FROM grow_module WHERE id = ?", (batch["module_id"],)).fetchone())
            fac = dict(conn.execute("SELECT * FROM facility WHERE id = ?", (module["facility_id"],)).fetchone())
            grower = dict(conn.execute("SELECT * FROM grower WHERE id = ?", (fac["grower_id"],)).fetchone())
            evs = ledger.tail(conn, limit=500, entity_id=bm["id"])
            evs = sorted(evs, key=lambda e: e["seq"])

            lca = compute_lca(batch, fac, fac.get("renewable_share"))
            at = iso(datetime.fromisoformat(batch["harvest_date"].replace("Z", "+00:00")) + timedelta(days=30))
            ev = ledger.append(conn, "compliance", bm["id"], "LCA_ISSUED",
                               {"kind": "LCA", "report": lca}, actor="auditor:napell-fc", ts=at)
            insert(conn, "compliance_report", {
                "id": new_id(), "batch_id": bm["id"], "kind": "LCA",
                "payload_json": json.dumps(lca, ensure_ascii=False), "issued_at": at,
                "ledger_seq": ev["seq"], "hash": ev["hash"],
            })
            reports += 1

            eudr = build_eudr_report(batch, fac, grower, module, evs, at)
            ev2 = ledger.append(conn, "compliance", bm["id"], "EUDR_ISSUED",
                                {"kind": "EUDR", "report_id": eudr["report_id"],
                                 "risk": eudr["risk"]["overall"], "checks": eudr["total_checks"]},
                                actor="auditor:napell-fc", ts=at)
            insert(conn, "compliance_report", {
                "id": new_id(), "batch_id": bm["id"], "kind": "EUDR",
                "payload_json": json.dumps(eudr, ensure_ascii=False), "issued_at": at,
                "ledger_seq": ev2["seq"], "hash": ev2["hash"],
            })
            reports += 1

        # ---------------- projects + consumer engagement ----------------
        for p in PROJECTS:
            insert(conn, "project", {"id": new_id(), **p, "status": "active"})

        packed = [bm for bm in batch_meta if STAGE_ORDER.index(bm["stage"]) >= STAGE_ORDER.index("BATCH_PACKED")]
        consumers = [("Hong Kong, China", 62), ("Japan", 48), ("Germany", 41), ("Netherlands", 37),
                     ("United States", 29), ("United Kingdom", 24), ("Australia", 18), ("Singapore", 16)]
        srng = random.Random(4242)
        for bm in packed:
            for country, volume in consumers:
                for _ in range(max(1, volume // 9)):
                    kind = "tip" if srng.random() < 0.31 else "view"
                    insert(conn, "scan", {
                        "id": new_id(), "qr_token": bm["token"], "batch_id": bm["id"],
                        "ts": iso(ANCHOR - timedelta(hours=srng.randint(1, 1400))),
                        "country": country, "device": srng.choice(["iOS", "Android", "Web"]),
                        "kind": kind,
                        "amount": round(srng.uniform(1.0, 25.0), 2) if kind == "tip" else 0.0,
                        "currency": "USD",
                        "project_id": None,
                    })

        refresh_grower_scores(conn)
        conn.commit()
        return {
            "seeded": True, "growers": len(GROWERS), "facilities": len(FACILITIES),
            "modules": len(modules), "batches": len(BATCHES), "telemetry_rows": tel_rows,
            "compliance_reports": reports,
            "ledger_events": conn.execute("SELECT COUNT(*) FROM ledger_event").fetchone()[0],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    print(json.dumps(seed(force=a.force), indent=2, ensure_ascii=False))
