"""Export a static snapshot of the read API so the site works on GitHub Pages.

GitHub Pages can only serve files — there is no FastAPI process behind it. This
tool walks the same HTTP surface the frontend uses, captures every response into
``assets/data/snapshot.json`` and writes the batch QR codes as real ``.svg``
files. The frontend (``assets/js/api.js``) falls back to that snapshot whenever
the live API is unreachable, so the published site stays fully browsable.

Two kinds of endpoints need care:

* **Varying query strings** (``/ledger``, ``/batches?status=``, telemetry ranges)
  — export the *superset* the UI can request and let the client slice it. For
  collections that are filtered then limited server-side, the client reproduces
  exactly that order (filter -> newest first -> slice).
* **The LCA preview** takes a free-running 0-100 % renewable slider. The model is
  strictly linear in that share (``co2 = energy_pk * (1 - share) * grid_factor``),
  so capturing the 0 % and 100 % endpoints is enough for the client to rebuild
  every intermediate value exactly rather than approximating it.

Usage::

    python tools/export_snapshot.py                  # against http://127.0.0.1:8780
    python tools/export_snapshot.py --base http://host:port
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "assets" / "data" / "snapshot.json"
OUT_QR_DIR = ROOT / "assets" / "data" / "qr"

# Telemetry ranges offered by the module monitor.
TELEMETRY_HOURS = [24, 72, 168]
LEDGER_LIMITS = [7, 40, 60, 500]


class Client:
    def __init__(self, base: str, prefix: str = "/api/v1") -> None:
        self.base = base.rstrip("/")
        self.prefix = prefix
        self.gets = 0

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if path.startswith(self.prefix) or path.startswith("/healthz"):
            return self.base + path
        return self.base + self.prefix + path

    def get(self, path: str, raw: bool = False):
        url = self.url(path)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"GET {url} -> HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise SystemExit(
                f"GET {url} failed: {e.reason}. Is the API running?"
            ) from e
        self.gets += 1
        return body.decode() if raw else json.loads(body)


def trim(obj):
    """Round floats to 4 significant digits.

    The telemetry series carry full double precision, which roughly doubles the
    snapshot size and makes every re-export produce a spurious diff. Four
    significant digits is well below the resolution the UI displays.
    """
    if isinstance(obj, float):
        return float(f"{obj:.4g}") if obj else 0.0
    if isinstance(obj, dict):
        return {k: trim(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [trim(v) for v in obj]
    return obj


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8780")
    args = ap.parse_args()
    c = Client(args.base)

    print(f"exporting from {args.base} …")
    snapshot: dict = {}
    endpoints: dict[str, object] = {}

    # ---------------------------------------------------------------- singles
    singles = ["/meta", "/overview", "/network", "/projects", "/analytics/impact",
               "/ledger/verify", "/batches", "/modules", "/growers", "/facilities"]
    for path in singles:
        endpoints[path] = c.get(path)
        print(f"  GET {path}")

    batches = endpoints["/batches"]["items"]
    modules = endpoints["/modules"]["items"] if isinstance(endpoints["/modules"], dict) else endpoints["/modules"]
    growers = endpoints["/growers"]["items"] if isinstance(endpoints["/growers"], dict) else endpoints["/growers"]

    # --------------------------------------------------------- ledger superset
    # One dump large enough to satisfy any filter the trace page can build.
    endpoints["/ledger"] = c.get(f"/ledger?limit={max(LEDGER_LIMITS)}")
    print(f"  GET /ledger?limit={max(LEDGER_LIMITS)}  ({endpoints['/ledger']['count']} events)")

    # ------------------------------------------------------------ per batch
    previews: dict[str, dict] = {}
    qr_map: dict[str, str] = {}
    # start from a clean slate so tokens from a previous seed don't linger
    if OUT_QR_DIR.exists():
        for stale in OUT_QR_DIR.glob("*.svg"):
            stale.unlink()
    OUT_QR_DIR.mkdir(parents=True, exist_ok=True)

    for b in batches:
        code, key = b["code"], b["code"]
        endpoints[f"/batches/{key}"] = c.get(f"/batches/{key}")
        endpoints[f"/batches/{key}/journey"] = c.get(f"/batches/{key}/journey")
        for kind in ("EUDR", "LCA"):
            try:
                endpoints[f"/batches/{key}/compliance/{kind}"] = c.get(
                    f"/batches/{key}/compliance/{kind}")
            except SystemExit:
                pass  # not yet filed — the frontend previews it instead
        # slider endpoints: 0 % and 1.0 give the client an exact linear model
        for tag, share in (("rs0", 0.0), ("rs1", 1.0)):
            previews.setdefault(key, {})[tag] = post(c, f"/batches/{key}/compliance/lca/preview",
                                                     {"renewable_share": share})
        # QR as a real file
        token = b.get("qr_token")
        if token:
            svg = c.get(f"/qr/{token}", raw=True)
            (OUT_QR_DIR / f"{token}.svg").write_text(svg, encoding="utf-8")
            qr_map[token] = f"assets/data/qr/{token}.svg"
        print(f"  batch {code}: journey + compliance + LCA endpoints + QR")

    # ----------------------------------------------------------- per module
    for m in modules:
        code = m["code"]
        endpoints[f"/modules/{code}"] = c.get(f"/modules/{code}")
        for hours in TELEMETRY_HOURS:
            bucket = 2 if hours > 100 else 1
            endpoints[f"/modules/{code}/telemetry?hours={hours}&bucket={bucket}"] = c.get(
                f"/modules/{code}/telemetry?hours={hours}&bucket={bucket}")
        print(f"  module {code}: meta + {len(TELEMETRY_HOURS)} telemetry ranges")

    # ------------------------------------------------------------ per grower
    for g in growers:
        code = g.get("code") or g.get("id")
        if code:
            endpoints[f"/growers/{code}"] = c.get(f"/growers/{code}")

    # -------------------------------------------------------- consumer tokens
    for b in batches:
        token = b.get("qr_token")
        if not token:
            continue
        try:
            endpoints[f"/consumer/{token}"] = c.get(f"/consumer/{token}")
        except SystemExit:
            pass

    snapshot = {
        "kind": "napell-farmer-connect-read-snapshot",
        "note": "Static capture of the read API. Regenerate with backend/tools/export_snapshot.py",
        "generated_from": args.base,
        "base": "/api/v1",
        "counts": endpoints["/overview"]["counts"],
        "ledger_head": endpoints["/ledger"].get("head"),
        "endpoints": trim(endpoints),
        "lca_preview": trim(previews),
        "qr": qr_map,
        "hints": {
            "telemetry_hours": TELEMETRY_HOURS,
            "ledger_limits": LEDGER_LIMITS,
            "write_paths_disabled": True,
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    size = OUT_JSON.stat().st_size / 1024
    print(f"\nwrote {OUT_JSON.relative_to(ROOT)}  ({len(endpoints)} endpoints, {size:.0f} KB)")
    print(f"wrote {len(qr_map)} QR files into {OUT_QR_DIR.relative_to(ROOT)}")
    print(f"total upstream GETs: {c.gets}")
    return 0


def post(c: Client, path: str, body: dict):
    url = c.url(path)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            c.gets += 1
            return json.loads(r.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise SystemExit(f"POST {url} failed: {e}") from e


if __name__ == "__main__":
    sys.exit(main())
