"""Napell Farmer Connect — runtime config and modelled baselines."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The static site lives at the repository root so that GitHub Pages can publish
# it with a legacy main/root build (Pages only accepts "/" or "/docs" as source).
WEB_DIR = ROOT
DATA_DIR = ROOT / "backend" / "data"
DB_PATH = Path(os.environ.get("NAPELL_DB", DATA_DIR / "napell_fc.sqlite3"))

APP_NAME = "Napell Farmer Connect"
APP_VERSION = "0.1.0"
API_PREFIX = "/api/v1"

# Aeroponic coffee supply chain, closed-loop. Demo mode is offline by default:
# no external calls, all telemetry/ledger data is generated locally and deterministic.
OFFLINE = os.environ.get("NAPELL_OFFLINE", "1") not in ("0", "false", "False")

GENESIS_HASH = "0" * 64

# ---------------------------------------------------------------------------
# Lifecycle of an aeroponic coffee batch. Ordered — the ledger enforces order.
# ---------------------------------------------------------------------------
BATCH_STAGES = [
    ("BATCH_SOWN", "播种 / Sown", "种苗植入气雾培舱，记录品种与株数"),
    ("BATCH_GERMINATED", "发芽 / Germinated", "发芽率与初始冠层面积记录"),
    ("BATCH_VEG", "营养生长 / Vegetative", "EC / pH / VPD 稳定期，冠层扩展"),
    ("BATCH_FLOWERING", "开花 / Flowering", "光周期与温湿度窗口锁定"),
    ("BATCH_FRUITING", "结果 / Fruiting", "果实膨大，糖度累积监测"),
    ("BATCH_HARVESTED", "采收 / Harvested", "鲜果重量、水分、等级入库"),
    ("BATCH_PROCESSED", "处理 / Processed", "水洗 / 日晒，含水率与瑕疵率"),
    ("BATCH_MILLED", "脱壳 / Milled", "生豆出率与分级"),
    ("BATCH_ROASTED", "烘焙 / Roasted", "烘焙曲线与失重率"),
    ("BATCH_PACKED", "包装 / Packed", "生成唯一 QR 溯源令牌"),
    ("BATCH_SHIPPED", "出运 / Shipped", "承运方与目的地写入账本"),
]
STAGE_ORDER = [s[0] for s in BATCH_STAGES]
STAGE_LABEL = {s[0]: s[1] for s in BATCH_STAGES}
STAGE_DESC = {s[0]: s[2] for s in BATCH_STAGES}

# Minimum evidence required before a batch can be considered retail-ready.
RETAIL_READY_REQUIRED = [
    "BATCH_SOWN",
    "BATCH_VEG",
    "BATCH_FLOWERING",
    "BATCH_HARVESTED",
    "BATCH_PROCESSED",
    "BATCH_ROASTED",
    "BATCH_PACKED",
]

# ---------------------------------------------------------------------------
# LCA reference baselines for CONVENTIONAL (soil, open-field) arabica.
# Modelled constants, literature median. Used only as the comparison leg —
# the aeroponic leg is always computed from the batch's own recorded data.
# ---------------------------------------------------------------------------
CONVENTIONAL_BASELINE = {
    "label": "Conventional open-field arabica (reference baseline)",
    "water_l_per_kg": 250.0,        # blue water, irrigation + processing
    "land_m2_per_kg": 10.0,         # ~1.0 t green bean / ha
    "energy_kwh_per_kg": 1.8,       # field + dry mill
    "co2e_kg_per_kg": 2.40,         # cultivation + primary processing, cradle-to-gate
    "agrochemical_kg_per_kg": 0.012,
    "deforestation_risk": 0.32,     # share of new planting on recently cleared land
    "vintage": "ICO / peer-reviewed median, 2015-2024",
}

# Grid emission factor used to convert aeroponic electricity into CO2e.
GRID_CO2E_PER_KWH = 0.55         # blended Asia-Pacific grid, kg CO2e / kWh
NUTRIENT_CO2E_PER_KG = 0.40      # closed-loop nutrient concentrate, cradle-to-gate
PACKAGING_CO2E_PER_KG = 0.25
TRANSPORT_CO2E_PER_TONNE_KM = 0.062

# EUDR
EUDR_REGULATION = "Regulation (EU) 2023/1115 (EUDR)"
EUDR_CUTOFF_DATE = "2020-12-31"
EUDR_HS_CODE = "0901"
EUDR_COMMODITY = "Coffee"

DEFAULT_ACTOR = "system:napell-fc"
