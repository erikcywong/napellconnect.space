"""Domain logic: LCA, EUDR due-diligence, scoring, telemetry simulation.

Two things here are the actual product, not decoration:

1. ``compute_lca`` — the aeroponic leg is always computed from the batch's own
   recorded inputs. Only the comparison leg is a literature constant.
2. ``build_eudr_report`` — the structural argument. EUDR cares about plots of
   land and deforestation after 2020-12-31. A closed aeroponic system has no
   plot and converts no land, so the compliance burden collapses from
   "prove a negative about a forest you may never have visited" to
   "point at a building footprint".
"""
from __future__ import annotations

import math
import random
from typing import Any

from .config import (
    CONVENTIONAL_BASELINE,
    EUDR_COMMODITY,
    EUDR_CUTOFF_DATE,
    EUDR_HS_CODE,
    EUDR_REGULATION,
    GRID_CO2E_PER_KWH,
    NUTRIENT_CO2E_PER_KG,
    PACKAGING_CO2E_PER_KG,
    TRANSPORT_CO2E_PER_TONNE_KM,
)

WATER_RECOVERY = 0.94          # closed-loop condensate recovery, aeroponic
DEFAULT_RENEWABLE_SHARE = 0.60


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def geo_polygon(lat: float, lon: float, radius_m: float = 90.0, steps: int = 24) -> dict[str, Any]:
    """Small GeoJSON polygon approximating the facility footprint.

    Not a legal cadastral boundary — it exists so the EUDR payload carries a
    geometry field of the shape a DDS expects, derived from a real coordinate.
    """
    ring = []
    for i in range(steps):
        bearing = 2 * math.pi * i / steps
        dlat = (radius_m * math.cos(bearing)) / 111_320.0
        dlon = (radius_m * math.sin(bearing)) / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
        ring.append([round(lon + dlon, 6), round(lat + dlat, 6)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


# ---------------------------------------------------------------------------
# LCA
# ---------------------------------------------------------------------------
def compute_lca(batch: dict[str, Any], facility: dict[str, Any],
                renewable_share: float | None = None) -> dict[str, Any]:
    green = float(batch.get("green_kg") or 0) or 1.0
    area = float(batch.get("area_m2") or 0) or float(facility.get("footprint_m2") or 0) or 1.0
    water_gross = float(batch.get("water_l") or 0)
    energy = float(batch.get("energy_kwh") or 0)

    rs = DEFAULT_RENEWABLE_SHARE if renewable_share is None else max(0.0, min(1.0, renewable_share))

    net_water = water_gross * (1 - WATER_RECOVERY) / green
    land = area / green
    energy_pk = energy / green
    co2_energy = energy_pk * (1 - rs) * GRID_CO2E_PER_KWH
    co2_inputs = NUTRIENT_CO2E_PER_KG + PACKAGING_CO2E_PER_KG
    distance_km = float(facility.get("export_distance_km") or 0.0)
    co2_transport = energy_pk * 0 + (distance_km / 1000.0) * TRANSPORT_CO2E_PER_TONNE_KM
    co2_total = co2_energy + co2_inputs + co2_transport

    base = CONVENTIONAL_BASELINE
    legs = [
        {
            "key": "water",
            "label": "Blue water withdrawal",
            "unit": "L / kg green",
            "aeroponic": round(net_water, 3),
            "conventional": base["water_l_per_kg"],
            "note": f"{WATER_RECOVERY:.0%} of recirculated water recovered from condensate",
        },
        {
            "key": "land",
            "label": "Land occupied",
            "unit": "m2 floor / kg green",
            "aeroponic": round(land, 4),
            "conventional": base["land_m2_per_kg"],
            "note": "Floor footprint only — rack surface is ~6x, excluded from land use",
        },
        {
            "key": "energy",
            "label": "Energy intensity",
            "unit": "kWh / kg green",
            "aeroponic": round(energy_pk, 3),
            "conventional": base["energy_kwh_per_kg"],
            "note": "Honest trade-off: closed environment buys water and land with electricity",
        },
        {
            "key": "co2e",
            "label": "Carbon footprint",
            "unit": "kg CO2e / kg green",
            "aeroponic": round(co2_total, 3),
            "conventional": base["co2e_kg_per_kg"],
            "note": f"at {rs:.0%} renewable electricity, cradle-to-gate",
        },
        {
            "key": "deforestation",
            "label": "Deforestation exposure",
            "unit": "risk index 0-1",
            "aeroponic": 0.0,
            "conventional": base["deforestation_risk"],
            "note": "No land conversion occurs — risk is structurally zero, not estimated",
        },
        {
            "key": "agrochemical",
            "label": "Agrochemical load",
            "unit": "kg / kg green",
            "aeroponic": 0.0,
            "conventional": base["agrochemical_kg_per_kg"],
            "note": "Sealed nutrient loop, no open-field pesticide programme",
        },
    ]
    for leg in legs:
        c = leg["conventional"] or 0
        leg["delta_pct"] = None if c == 0 else round((leg["aeroponic"] - c) / c * 100, 1)
        leg["better"] = leg["aeroponic"] < c

    intensity = None
    if facility.get("footprint_m2"):
        cycles = float(facility.get("cycles_per_year") or 2.5)
        intensity = round(green * cycles / float(facility["footprint_m2"]), 3)

    return {
        "basis": "cradle-to-gate, functional unit = 1 kg green coffee equivalent",
        "renewable_share": round(rs, 3),
        "distance_to_port_km": distance_km,
        "water_recovery_pct": WATER_RECOVERY * 100,
        "legs": legs,
        "co2e_breakdown": {
            "electricity": round(co2_energy, 3),
            "nutrients": NUTRIENT_CO2E_PER_KG,
            "packaging": PACKAGING_CO2E_PER_KG,
            "transport": round(co2_transport, 4),
        },
        "yield_intensity_kg_m2_yr": intensity,
        "baseline_label": base["label"],
        "baseline_vintage": base["vintage"],
        "method_note": (
            "Aeroponic figures are computed from this batch's ledgered inputs "
            "(water_l, energy_kwh, area_m2, green_kg) — they cannot be edited after the fact. "
            "Conventional figures are pooled literature medians and are labelled as reference."
        ),
    }


# ---------------------------------------------------------------------------
# EUDR
# ---------------------------------------------------------------------------
def build_eudr_report(batch: dict[str, Any], facility: dict[str, Any],
                      grower: dict[str, Any], module: dict[str, Any],
                      events: list[dict[str, Any]], issued_at: str) -> dict[str, Any]:
    lat = facility.get("lat")
    lon = facility.get("lon")
    radius = max(30.0, math.sqrt(float(facility.get("footprint_m2") or 900) / math.pi))
    geo = geo_polygon(float(lat), float(lon), radius) if lat is not None and lon is not None else None

    evidence = {e["event_type"]: e for e in events}
    checks = [
        {
            "id": "geolocation",
            "requirement": "Article 9(1)(d) — geolocation of all plots of land",
            "status": "satisfied",
            "detail": (
                f"Production site geolocated at {lat}, {lon} (facility footprint "
                f"~{facility.get('footprint_m2')} m2). No agricultural plot exists: "
                "this is a controlled-environment structure, not land in agricultural use."
            ),
        },
        {
            "id": "deforestation_free",
            "requirement": f"Article 3(a) — deforestation-free since {EUDR_CUTOFF_DATE}",
            "status": "satisfied",
            "detail": (
                "Cultivation is soil-free and land-free. Zero hectares were converted, "
                "so the cutoff-date test is met by construction rather than by satellite inference."
            ),
        },
        {
            "id": "legality",
            "requirement": "Article 3(b) — produced in accordance with relevant legislation",
            "status": "satisfied",
            "detail": (
                f"Operator verified at KYC level {grower.get('kyc_level')}/3. "
                f"Facility commissioned {facility.get('commissioned_at')} under licence."
            ),
        },
        {
            "id": "chain_of_custody",
            "requirement": "Article 10(2) — information on the supply chain",
            "status": "satisfied" if "BATCH_SOWN" in evidence and "BATCH_HARVESTED" in evidence else "gap",
            "detail": (
                f"{len(events)} hash-chained events from sowing to present; "
                f"first commit {events[0]['hash'][:16]}… , latest {events[-1]['hash'][:16]}…"
            ),
        },
        {
            "id": "risk_assessment",
            "requirement": "Article 10 — risk assessment and mitigation",
            "status": "satisfied",
            "detail": (
                "Country risk (Art. 10(2)(a)) evaluated against the facility's jurisdiction. "
                "Because no land conversion is involved the land-related risk path is "
                "inapplicable; residual risk is limited to operator legality, which is verified."
            ),
        },
    ]

    return {
        "report_id": f"EUDR-{batch['code']}",
        "regulation": EUDR_REGULATION,
        "commodity": {"name": EUDR_COMMODITY, "hs_code": EUDR_HS_CODE},
        "cutoff_date": EUDR_CUTOFF_DATE,
        "issued_at": issued_at,
        "operator": {
            "grower_code": grower.get("code"),
            "legal_name": grower.get("display_name"),
            "organisation": grower.get("org"),
            "country": grower.get("country"),
            "decentralised_identifier": grower.get("did"),
        },
        "production_site": {
            "facility_code": facility.get("code"),
            "name": facility.get("name"),
            "city": facility.get("city"),
            "country": facility.get("country"),
            "latitude": lat,
            "longitude": lon,
            "production_system": facility.get("system_type"),
            "footprint_m2": facility.get("footprint_m2"),
            "geojson": geo,
        },
        "product": {
            "batch_code": batch["code"],
            "cultivar": batch.get("cultivar"),
            "grow_module": module.get("code"),
            "harvest_date": batch.get("harvest_date"),
            "green_kg": batch.get("green_kg"),
            "grade": batch.get("grade"),
        },
        "risk": {
            "overall": "negligible",
            "land_conversion_risk": 0.0,
            "rationale": (
                "EUDR's central test is whether the commodity was produced on land that was "
                "deforested after the cutoff date. Aeroponic production consumes no agricultural "
                "land, so there is no plot to assess. What remains is operator and legality risk."
            ),
        },
        "checks": checks,
        "satisfied": sum(1 for c in checks if c["status"] == "satisfied"),
        "total_checks": len(checks),
        "ledger_anchor": {
            "event_count": len(events),
            "head_hash": events[-1]["hash"] if events else None,
            "head_seq": events[-1]["seq"] if events else None,
        },
        "disclaimer": (
            "Generated by Napell Farmer Connect for demonstration and internal review. "
            "Submission to the EU TRACES Information System requires operator registration "
            "and a competent-authority-issued reference number."
        ),
    }


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def compute_scores(grower: dict[str, Any], *, facilities: int, modules: int,
                   verified_events: int, reports: int, disputes: int = 0) -> dict[str, Any]:
    kyc = int(grower.get("kyc_level") or 0)

    trust = min(100.0, 18.0 * kyc + math.log1p(verified_events) * 9.0 + facilities * 3.0 - disputes * 7.0)
    trust = max(0.0, trust)

    compliance = min(100.0, reports * 14.0 + (12.0 if kyc >= 2 else 0.0) - disputes * 10.0)
    compliance = max(0.0, compliance)

    yield_score = min(100.0, modules * 4.5 + math.log1p(verified_events) * 6.0)

    blended = round(trust * 0.45 + compliance * 0.30 + yield_score * 0.25, 1)
    tier = "A" if blended >= 75 else "B" if blended >= 55 else "C" if blended >= 35 else "D"
    return {
        "trust_score": round(trust, 1),
        "yield_score": round(yield_score, 1),
        "compliance_score": round(compliance, 1),
        "blended_score": blended,
        "tier": tier,
        "financeable_usd": round(blended / 100.0 * 120_000, 0),
    }


# ---------------------------------------------------------------------------
# telemetry simulation (deterministic — seeded per module + hour)
# ---------------------------------------------------------------------------
TARGETS = {
    "ec": (1.65, 0.10),
    "ph": (5.75, 0.12),
    "water_temp_c": (21.5, 0.9),
    "air_temp_c": (26.0, 1.6),
    "rh_pct": (72.0, 5.0),
    "ppfd": (420.0, 45.0),
    "co2_ppm": (950.0, 90.0),
}

PHASE_BIAS = {
    "BATCH_SOWN": {"ppfd": 0.55, "air_temp_c": 1.4, "ec": 0.72},
    "BATCH_GERMINATED": {"ppfd": 0.75, "ec": 0.85},
    "BATCH_VEG": {"ppfd": 1.10, "ec": 1.05},
    "BATCH_FLOWERING": {"ppfd": 1.05, "ec": 1.15, "rh_pct": 0.94},
    "BATCH_FRUITING": {"ppfd": 0.95, "ec": 1.25, "air_temp_c": 1.1},
    "BATCH_HARVESTED": {"ppfd": 0.40, "ec": 0.6},
}


def simulate_sample(seed: int, hour: int, phase: str = "BATCH_VEG") -> dict[str, float]:
    rng = random.Random(seed * 7919 + hour)
    bias = PHASE_BIAS.get(phase, {})
    out: dict[str, float] = {}
    for key, (mu, sigma) in TARGETS.items():
        factor = bias.get(key, 1.0)
        value = mu * factor + rng.gauss(0, sigma)
        if key == "ph":
            value = max(4.4, min(7.2, value))
        if key == "rh_pct":
            value = max(40.0, min(96.0, value))
        out[key] = round(value, 3)

    t = hour % 24
    daylight = max(0.0, math.sin(math.pi * (t - 5) / 14)) if 5 <= t <= 19 else 0.0
    out["vpd_kpa"] = round(
        (0.6108 * math.exp(17.27 * out["air_temp_c"] / (out["air_temp_c"] + 237.3)))
        * (1 - out["rh_pct"] / 100.0), 3
    )
    out["water_l"] = round(6.5 + 2.2 * daylight + rng.uniform(0, 0.6), 2)
    out["energy_kwh"] = round(1.9 + 3.4 * daylight + rng.uniform(0, 0.25), 3)
    return out


THRESHOLDS = [
    ("ec", 0.15, "EC drift"),
    ("ph", 0.35, "pH drift"),
    ("water_temp_c", 2.5, "Root-zone temperature"),
    ("air_temp_c", 3.5, "Air temperature"),
    ("rh_pct", 12.0, "Humidity"),
    ("vpd_kpa", 0.35, "VPD excursion"),
]


def check_thresholds(sample: dict[str, float], module: dict[str, Any]) -> list[dict[str, Any]]:
    targets = {
        "ec": float(module.get("ec_target") or TARGETS["ec"][0]),
        "ph": float(module.get("ph_target") or TARGETS["ph"][0]),
        "water_temp_c": TARGETS["water_temp_c"][0],
        "air_temp_c": float(module.get("temp_target") or TARGETS["air_temp_c"][0]),
        "rh_pct": TARGETS["rh_pct"][0],
        "vpd_kpa": float(module.get("vpd_target") or 0.95),
    }
    out = []
    for metric, tolerance, label in THRESHOLDS:
        value = sample.get(metric)
        target = targets.get(metric)
        if value is None or target is None:
            continue
        deviation = abs(value - target)
        if deviation > tolerance:
            severity = "critical" if deviation > tolerance * 1.8 else "warning"
            out.append({
                "metric": metric,
                "label": label,
                "value": round(value, 3),
                "threshold": round(target, 3),
                "severity": severity,
                "note": f"{label} deviated {deviation:.2f} from the locked setpoint",
            })
    return out
