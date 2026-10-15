"""End-to-end smoke test. Run with the API listening on BASE.

    python tests/smoke.py [base_url]

Exercises the full write path: telemetry ingest, guided simulation, batch
creation, lifecycle advance (which auto-issues EUDR + LCA), consumer tip, and
a full hash-chain re-verification afterwards.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8780"
PASS, FAIL = [], []


def call(method: str, path: str, body: dict | None = None, user: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if user:
        req.add_header("X-Napell-User", user)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            ctype = r.headers.get("content-type", "")
            return r.status, (json.loads(raw) if "json" in ctype else raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def check(label: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(label)
    print(("  PASS  " if ok else "  FAIL  ") + label + (f"   {detail}" if detail else ""))


print(f"Napell Farmer Connect — smoke test against {BASE}\n")

# ---------------------------------------------------------------- read paths
print("read paths")
st, meta = call("GET", "/api/v1/meta")
check("GET /meta", st == 200 and meta["grain"] == "aeroponic_controlled_environment")

st, ov = call("GET", "/api/v1/overview")
check("GET /overview", st == 200 and ov["counts"]["growers"] > 0,
      f"{ov['counts']['ledger_events']} ledger events" if st == 200 else str(ov)[:120])
check("overview > chain integrity", ov.get("integrity", {}).get("ok") is True,
      str(ov.get("integrity", {}).get("broken_at", "")))
check("overview reports water saving",
      ov["impact"]["water_saved_l"] > 0, f"{ov['impact']['water_saved_l']:,.0f} L")

st, net = call("GET", "/api/v1/network")
check("GET /network", st == 200 and len(net["modules"]) > 0,
      f"{len(net['growers'])} growers / {len(net['facilities'])} facilities / {len(net['modules'])} modules")

st, verify = call("GET", "/api/v1/ledger/verify")
check("GET /ledger/verify", st == 200 and verify["ok"] is True, f"{verify.get('checked')} events")

st, batches = call("GET", "/api/v1/batches")
check("GET /batches", st == 200 and batches["count"] > 0, f"{batches['count']} batches")

shipped = next((b for b in batches["items"] if b["status"] == "shipped"), batches["items"][0])

st, j = call("GET", f"/api/v1/batches/{shipped['code']}/journey")
check("GET /batches/{code}/journey", st == 200 and j["event_count"] > 0,
      f"{j['event_count']} events, {len(j['attestations'])} attestations")

legs = {l["key"]: l for l in j["lca"]["legs"]}
check("LCA water delta < -90%", legs["water"]["delta_pct"] < -90, f"{legs['water']['delta_pct']}%")
check("LCA land delta < -90%", legs["land"]["delta_pct"] < -90, f"{legs['land']['delta_pct']}%")
check("LCA deforestation exposure = 0", legs["deforestation"]["aeroponic"] == 0.0)
check("LCA energy trade-off is disclosed (positive delta)",
      legs["energy"]["delta_pct"] > 0, f"{legs['energy']['delta_pct']}%")

if j["eudr"]:
    checks = j["eudr"]["checks"]
    check("EUDR report present", j["eudr"]["risk"]["overall"] == "negligible",
          f"{len(checks)} checks, {j['eudr']['satisfied']} satisfied")
    check("EUDR geolocation check satisfied",
          any(c["id"] == "geolocation" and c["status"] == "satisfied" for c in checks))
    check("EUDR carries GeoJSON geometry",
          j["eudr"]["production_site"]["geojson"]["type"] == "Polygon")

st, svg = call("GET", f"/api/v1/qr/{j['batch']['qr_token']}")
check("GET /qr/{token} returns SVG", st == 200 and "<svg" in str(svg)[:200])

# --------------------------------------------------------------- write paths
print("\nwrite paths")
target = net["modules"][0]["code"]

st, r = call("POST", f"/api/v1/modules/{target}/telemetry",
             {"ec": 2.42, "ph": 6.31, "air_temp_c": 31.2, "rh_pct": 44,
              "ppfd": 560, "co2_ppm": 1180, "water_l": 9.1, "energy_kwh": 4.2, "attest": True},
             user="smoke")
check("POST telemetry ingest", st == 201 and r.get("accepted") is True,
      f"vpd={r.get('vpd_kpa')} alerts={len(r.get('alerts_raised', []))}")
check("out-of-range reading raises alerts", len(r.get("alerts_raised", [])) > 0,
      ", ".join(a["metric"] for a in r.get("alerts_raised", [])))
check("attested reading anchors to ledger", bool(r.get("ledger_event")))

st, r = call("POST", "/api/v1/modules/JP-01-M02/simulate", {"hours": 6})
check("POST simulate", st == 200 and r["hours_added"] == 6,
      f"{r['water_l']} L, {r['energy_kwh']} kWh")

st, r = call("GET", f"/api/v1/modules/{target}/telemetry?hours=48")
check("GET telemetry series", st == 200 and r["count"] > 0,
      f"{r['count']} samples × {len(r['series'])} channels")

st, nb = call("POST", "/api/v1/batches", {"module": "JP-01-M02"}, user="smoke")
check("POST /batches", st == 201, nb.get("batch", {}).get("code") if st == 201 else str(nb)[:120])
new_code = nb["batch"]["code"] if st == 201 else None

if new_code:
    order = ["BATCH_GERMINATED", "BATCH_VEG", "BATCH_FLOWERING", "BATCH_FRUITING"]
    ok = True
    for stage in order:
        st, r = call("POST", f"/api/v1/batches/{new_code}/advance", {"stage": stage}, user="smoke")
        ok = ok and st == 200 and r.get("advanced_to") == stage
    check("POST advance through lifecycle", ok)

    st, r = call("POST", f"/api/v1/batches/{new_code}/advance", {"stage": "BATCH_VEG"}, user="smoke")
    check("out-of-order advance is rejected", st == 409, f"HTTP {st}")

    st, r = call("POST", f"/api/v1/batches/{new_code}/advance",
                 {"stage": "BATCH_HARVESTED", "payload": {"green_kg": 251.4}}, user="smoke")
    check("POST advance to harvest", st == 200 and r["advanced_to"] == "BATCH_HARVESTED",
          f"green_kg={r['payload'].get('green_kg')}")
    check("harvest auto-issues EUDR + LCA",
          bool(r["auto_issued_reports"]) and set(r["auto_issued_reports"]) == {"EUDR", "LCA"},
          str(list(r.get("auto_issued_reports") or [])))

    st, r = call("GET", f"/api/v1/batches/{new_code}/compliance/EUDR")
    check("GET issued EUDR report", st == 200 and r["issued"] is True,
          f"hash {str(r.get('hash'))[:16]}…")

    st, r = call("POST", f"/api/v1/batches/{new_code}/compliance/lca/preview",
                 {"renewable_share": 1.0})
    co2 = next(l for l in r["legs"] if l["key"] == "co2e")
    check("LCA scenario at 100% renewable beats baseline", co2["delta_pct"] < 0,
          f"{co2['aeroponic']} kg CO2e/kg ({co2['delta_pct']}%)")

    st, r = call("POST", f"/api/v1/batches/{new_code}/compliance/lca/preview",
                 {"renewable_share": 0.0})
    co2 = next(l for l in r["legs"] if l["key"] == "co2e")
    check("LCA scenario at 0% renewable is worse than baseline", co2["delta_pct"] > 0,
          f"{co2['aeroponic']} kg CO2e/kg (+{co2['delta_pct']}%)")

# consumer
token = j["batch"]["qr_token"]
st, r = call("POST", f"/api/v1/consumer/{token}/engage",
             {"kind": "tip", "amount": 12.5, "country": "Germany", "device": "iOS"})
check("POST consumer tip", st == 201 and r["recorded"] == "tip", f"${r.get('amount')}")

st, r = call("POST", f"/api/v1/consumer/{token}/engage", {"kind": "view", "country": "Japan"})
check("POST consumer view", st == 201 and r["ledger_event"] is None)

st, cv = call("GET", f"/api/v1/consumer/{token}")
check("GET /consumer/{token}", st == 200 and cv["integrity"]["chain_ok"] is True,
      f"{cv['community']['scans']} scans, {cv['community']['tips']} tips")
check("consumer journey exposes only completed stages",
      all(s["hash"] for s in cv["journey"] if s["completed"]))

# tamper detection
print("\ntamper detection")
import sqlite3
from pathlib import Path
db = Path(__file__).resolve().parents[1] / "data" / "napell_fc.sqlite3"
if db.exists():
    con = sqlite3.connect(db)
    row = con.execute("SELECT seq, payload_json FROM ledger_event ORDER BY seq LIMIT 1 OFFSET 3").fetchone()
    original = row[1]
    con.execute("UPDATE ledger_event SET payload_json = ? WHERE seq = ?",
                (original.replace("{", "{\"tampered\":true,", 1), row[0]))
    con.commit()
    con.close()
    st, v = call("GET", "/api/v1/ledger/verify")
    check("modified payload breaks verification", st == 200 and v["ok"] is False,
          f"broken at seq {v.get('broken_at')} — {v.get('reason')}")
    con = sqlite3.connect(db)
    con.execute("UPDATE ledger_event SET payload_json = ? WHERE seq = ?", (original, row[0]))
    con.commit()
    con.close()
    st, v = call("GET", "/api/v1/ledger/verify")
    check("chain verifies again after restore", v["ok"] is True, f"{v.get('length')} events")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("failed: " + "; ".join(FAIL))
    sys.exit(1)
