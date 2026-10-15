# Napell Farmer Connect — Technical Specification

Version 0.1.0 · demo build

---

## 1. Object model

Five entity types, in strict containment order. Creation of each writes a ledger event.

```
Grower (GrowerID, did:napell:npf-xxxx)
  └── Facility (FAC-CC-NN)          production site, geolocated, land-free
        └── GrowModule (CC-NN-Mxx)   a chamber: cultivar + climate setpoints + 8 sensors
              └── Batch (LOT-YYMMDD-X)  one closed lifecycle, carries the QR token
                    └── ComplianceReport (EUDR | LCA)
```

### 1.1 grower

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT UNIQUE | `NPF-0001`, assigned |
| `did` | TEXT UNIQUE | `did:napell:npf-0001` |
| `kyc_level` | INT 0–3 | feeds the trust score |
| `trust_score`, `yield_score`, `compliance_score` | REAL | **derived, never hand-entered** |
| `meta_json` | TEXT | role, since |

### 1.2 facility

The single most important row for EUDR. It carries `lat`/`lon`, `footprint_m2`,
`system_type`, `cycles_per_year`, `export_distance_km`, `renewable_share`. There is no
plot geometry column because there is no plot; the EUDR dossier derives a footprint
polygon from the coordinate at report time.

### 1.3 grow_module

Holds the climate setpoints (`ec_target`, `ph_target`, `vpd_target`, `ppfd_target`,
`temp_target`). Threshold alerts are evaluated against these, and the attestation digests
record the setpoint alongside the mean so a reader can judge drift without a second lookup.

### 1.4 batch

| Column | Notes |
|---|---|
| `qr_token` | UNIQUE, `npfc-<10 hex>` — the public consumer handle |
| `green_kg` | 0 until harvest; never back-filled |
| `projected_green_kg` | used for LCA on unharvested batches, flagged provisional |
| `water_l`, `energy_kwh` | full-cycle totals, ledgered at harvest |
| `area_m2` | allocated floor footprint — the denominator for land intensity |

### 1.5 batch lifecycle

```
BATCH_SOWN → BATCH_GERMINATED → BATCH_VEG → BATCH_FLOWERING → BATCH_FRUITING
           → BATCH_HARVESTED → BATCH_PROCESSED → BATCH_MILLED → BATCH_ROASTED
           → BATCH_PACKED → BATCH_SHIPPED
```

Ordering is enforced server-side (HTTP 409 on any violation). `RETAIL_READY_REQUIRED`
lists the seven stages a batch needs before it is sellable; `journey.missing_evidence`
names the gaps.

Advancing to `BATCH_HARVESTED` atomically issues the LCA and the EUDR dossier and anchors
both. That single decision is what makes the compliance story credible: the operator cannot
produce a harvest and file its paperwork a quarter later, after the facts have softened.

---

## 2. Ledger

```
hash_n = sha256(seq | ts | entity_type | entity_id | event_type | actor | payload | hash_{n-1})
```

* `payload_json` is canonical JSON — sorted keys, no whitespace — so hashes reproduce byte-for-byte.
* Genesis `prev_hash` is 64 zeros.
* `verify()` rewalks the chain, recomputes every hash and reports the first sequence where
  either the payload hash or the linkage fails.

**Event types**

| Type | Written by |
|---|---|
| `GROWER_REGISTERED`, `FACILITY_COMMISSIONED`, `MODULE_COMMISSIONED` | identity |
| `BATCH_SOWN` … `BATCH_SHIPPED` | lifecycle |
| `TELEMETRY_ATTESTED` | weekly digest, signed by the facility gateway |
| `LCA_ISSUED`, `EUDR_ISSUED` | compliance engine |
| `FUND_RECEIVED` | consumer contribution |

Raw telemetry stays out of the ledger. The chain holds periodic digests: window, sample
count, mean, setpoint. High-volume streams in the ledger would make it unreviewable without
adding evidentiary value.

---

## 3. LCA model

`domain.compute_lca(batch, facility, renewable_share)` → six legs.

Aeroponic legs are computed from the batch record:

```
net_water_l_per_kg = water_l × (1 − WATER_RECOVERY) / green_kg      # 94% condensate recovery
land_m2_per_kg     = area_m2 / green_kg                             # floor footprint only
energy_kwh_per_kg  = energy_kwh / green_kg
co2e               = energy × (1 − renewable_share) × GRID_CO2E_PER_KWH
                   + NUTRIENT + PACKAGING + (distance_km / 1000) × TRANSPORT
```

Conventional legs are constants in `config.CONVENTIONAL_BASELINE`, labelled with a vintage
and surfaced in every response as `baseline_label` / `baseline_vintage`. The comparison leg
is never presented as measured.

`POST /batches/{key}/compliance/lca/preview` accepts a `renewable_share` override so the
front end can render the grid-mix scenario live. Water, land and deforestation are
unaffected by it, and the API returns them unchanged — the scenario is only about
electricity.

---

## 4. EUDR dossier

`domain.build_eudr_report(...)` produces five checks, all derived rather than asserted:

| Check | Regulation | Basis |
|---|---|---|
| `geolocation` | Art. 9(1)(d) | facility coordinate + derived footprint polygon |
| `deforestation_free` | Art. 3(a) | no land conversion, so the cutoff test is met by construction |
| `legality` | Art. 3(b) | operator KYC level + commissioning date |
| `chain_of_custody` | Art. 10(2) | count and head hash of the batch's ledger events |
| `risk_assessment` | Art. 10 | land-related path inapplicable; residual risk is operator legality |

The payload carries a GeoJSON polygon for the shape a DDS expects, and a
`ledger_anchor` block so a filed report can be traced back to the exact event.

`disclaimer` states plainly that submission to EU TRACES needs operator registration and a
competent-authority reference number.

---

## 5. Scoring

`domain.compute_scores(...)` → `trust`, `yield`, `compliance`, blended, tier A–D and a
`financeable_usd` indication.

```
trust       = 18·kyc + 9·ln(1 + verified_events) + 3·facilities − 7·disputes
compliance  = 14·reports + 12·[kyc ≥ 2] − 10·disputes
yield       = 4.5·modules + 6·ln(1 + verified_events)
blended     = 0.45·trust + 0.30·compliance + 0.25·yield
```

All inputs are ledger-derived. A grower cannot raise its own score, which is the whole point
of offering credit signals to a finance partner.

---

## 6. Telemetry

Eight channels: `ec`, `ph`, `water_temp_c`, `air_temp_c`, `rh_pct`, `vpd_kpa`, `ppfd`,
`co2_ppm`, plus the derived `water_l` and `energy_kwh` per interval.

VPD is derived, not reported: `0.6108·e^(17.27·T/(T+237.3))·(1 − RH/100)`. Deriving it
server-side from temperature and humidity means the two series cannot disagree.

`domain.check_thresholds(sample, module)` raises on |value − setpoint| beyond tolerance per
channel, escalating to `critical` at 1.8× tolerance. Alerts are deliberately **not**
ledgered — they are an operations signal, and the ledger is for evidence.

---

## 7. API surface

40 endpoints under `/api/v1`. Full machine-readable contract at `/openapi.json`,
browsable at `/docs`. Grouped reference with per-endpoint semantics on `api.html`.

Writes are attributed via `X-Napell-User`; the value becomes the `actor` field, which is
hashed into the event. The demo is unauthenticated, so attribution is a convention rather
than a guarantee — in production it is replaced by a JWT carrying the GrowerID.

---

## 8. Front end

Multi-page static HTML served same-origin by FastAPI. No build step. The site lives at the
repository root so GitHub Pages can publish the same folder with a `main / root` build.

| File | Responsibility |
|---|---|
| `assets/css/style.css` | design tokens, components, responsive rules |
| `assets/js/i18n.js` | EN authored inline, ZH dictionary; single source per string |
| `assets/js/api.js` | fetch wrapper, number formatting, offline read-snapshot engine |
| `assets/js/ui.js` | echarts wrappers, journey timeline, impact bars, world map |
| `assets/js/chrome.js` | floating nav, hover dropdowns, chain status LED, footer |
| `assets/data/snapshot.json` | captured read API for hosts with no backend (generated) |

Design tokens follow the x.com dark register: `#000` ground, `#16181c` panels, `#2f3336`
rules, `#1d9bf0` accent, `#00ba7c` verified/positive, `#f4212e` negative. Anything
cryptographic renders in monospace.

### 8.1 Two data modes

`NFApi` resolves the data source per request and reports which one is in play through
`NFApi.mode()` (`live` | `snapshot`).

| | live | snapshot |
|---|---|---|
| Trigger | API answers on the same origin | 404 / 405 / 5xx, or the network fails |
| Source | FastAPI + SQLite | `assets/data/snapshot.json`, produced by `backend/tools/export_snapshot.py` |
| Reads | all | all captured endpoints, plus emulated filters |
| LCA slider | server-side `compute_lca` | linear reconstruction from the captured 0 % and 100 % endpoints |
| Writes | all | rejected with an explanatory message |
| Nav LED | green, `N events · chain ok` | amber, `snapshot · N events · chain ok` |

The fallback engages once and is latched for the session. Set `window.NF_API_BASE` before
`api.js` loads to point the site at a different origin (e.g. a hosted API).

Two behaviours are reproduced exactly rather than approximated:

* **filtered collections** — the server filters, orders by `seq` descending, then limits
  (`ledger.tail`). The client applies the same three steps to the captured superset, so
  `/ledger?entity_type=…&limit=…` and `/batches?status=…` agree with the API.
* **the renewable-share slider** — `co2_electricity = energy_pk · (1 − share) · grid_factor` is
  strictly linear in the share, so two captured endpoints span the whole range. The endpoints
  match the API exactly; an intermediate share can differ by up to 0.001 kg CO₂e/kg because the
  API rounds each endpoint it returns to three decimals. Displayed deltas can therefore move by
  0.1 pp. Everything else on the page — including the default LCA of a batch — comes from a
  captured payload and is exact.

---

## 9. Known gaps

1. Sensor honesty rests on the gateway, not on signed hardware.
2. Conventional comparison legs are literature medians, not measured competitors.
3. EU TRACES submission requires operator registration first.
4. Carbon accounting is cradle-to-gate; use phase and end of life are excluded.
5. The ledger is single-writer. Consortium write consensus is future work.
6. The published snapshot is a point-in-time capture and does not age — regenerate it with
   `tools/export_snapshot.py` whenever the seed or the API changes.
