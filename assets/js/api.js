/* ==========================================================================
   api — fetch wrapper, number formatting, and the offline read-snapshot engine.

   The site talks to a live FastAPI backend when one sits behind the same
   origin. On a static host (GitHub Pages) there is none, so every read falls
   back to assets/data/snapshot.json — a capture of those same endpoints
   produced by backend/tools/export_snapshot.py.

   The fallback is not a mock: it holds the payloads the live API returned, and
   it reproduces two server-side behaviours exactly rather than approximating,
     * filtered collections — the server filters, sorts by seq descending, then
       limits, so the client does the same to the captured superset;
     * the LCA renewable-share slider — the model is strictly linear in the
       share, so the captured 0 % and 100 % endpoints rebuild every
       intermediate value to the backend's own rounding.
   Writes need the backend and fail with a clear message instead of pretending.
   ========================================================================== */
(function () {
  var BASE = (typeof window.NF_API_BASE === "string" && window.NF_API_BASE) || "/api/v1";
  var USER = "erik";
  var SNAPSHOT_URL = "assets/data/snapshot.json";

  var state = { mode: "live", snapshot: null, loading: null, misses: [] };

  /* --------------------------------------------------------------- helpers */
  function apiUrl(path) {
    if (path.indexOf("http") === 0) return path;
    if (path.indexOf(BASE) === 0 || path.indexOf("/healthz") === 0) return path;
    return BASE + path;
  }

  function parse(raw) {
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return raw; }
  }

  function offlineError(msg) {
    var e = new Error(msg || "live API unreachable");
    e.offline = true;
    return e;
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function r3(v) { return Math.round(v * 1000) / 1000; }
  function r1(v) { return Math.round(v * 10) / 10; }

  /* ------------------------------------------------------------ live calls */
  function live(method, path, body) {
    var opt = { method: method, headers: { "Content-Type": "application/json", "X-Napell-User": USER } };
    if (body !== undefined && body !== null) opt.body = JSON.stringify(body);
    return fetch(apiUrl(path), opt).then(function (r) {
      return r.text().then(function (raw) {
        var data = parse(raw);
        if (!r.ok) {
          var detail = data && data.detail ? data.detail : ("HTTP " + r.status);
          var err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
          // 404 / 405 / 5xx on the API surface means no backend is deployed
          // here — that is the static-host signal, not a bad request.
          if (r.status === 404 || r.status === 405 || r.status >= 500) err.offline = true;
          throw err;
        }
        return data;
      });
    }, function () { throw offlineError(); });
  }

  /* ------------------------------------------------------- snapshot loading */
  function useSnapshot() {
    if (state.loading) return state.loading;
    state.loading = fetch(SNAPSHOT_URL, { cache: "force-cache" })
      .then(function (r) {
        if (!r.ok) throw offlineError("no snapshot on this host");
        return r.json();
      })
      .then(function (snap) {
        state.snapshot = snap;
        state.mode = "snapshot";
        announce();
        return snap;
      })
      .catch(function (e) { state.loading = null; throw e; });
    return state.loading;
  }

  function announce() {
    try {
      document.dispatchEvent(new CustomEvent("nf-mode", { detail: { mode: state.mode } }));
    } catch (e) { /* very old browser: the LED just keeps reporting live */ }
  }

  /* ---------------------------------------------- snapshot query emulation */
  function norm(path) {
    var s = String(path).replace(/^https?:\/\/[^/]+/, "");
    if (s.indexOf(BASE) === 0) s = s.slice(BASE.length);
    return s || "/";
  }

  function collection(bare, params) {
    var src = state.snapshot.endpoints[bare];
    if (!src) return null;
    var items = src.items || [];
    var limit = Number(params.get("limit") || 0);

    if (bare === "/batches") {
      var status = params.get("status");
      if (status) items = items.filter(function (b) { return b.status === status; });
    } else if (bare === "/ledger") {
      var type = params.get("entity_type"), entity = params.get("entity_id");
      if (type) items = items.filter(function (e) { return e.entity_type === type; });
      if (entity) items = items.filter(function (e) { return e.entity_id === entity; });
      items = items.slice().sort(function (a, b) { return b.seq - a.seq; });
    } else {
      return null;
    }

    if (limit > 0) items = items.slice(0, limit);
    var out = clone(src);
    out.items = items;
    if ("count" in out) out.count = items.length;
    return out;
  }

  function lcaPreview(key, share) {
    var pair = state.snapshot.lca_preview && state.snapshot.lca_preview[key];
    if (!pair) throw offlineError("No captured LCA for " + key);
    var rs = Math.max(0, Math.min(1, Number(share) || 0));
    var legOf = function (o) {
      return (o.legs || []).filter(function (l) { return l.key === "co2e"; })[0];
    };
    var out = clone(pair.rs0);
    var e0 = out.co2e_breakdown.electricity;
    var e1 = pair.rs1.co2e_breakdown.electricity;
    out.renewable_share = r3(rs);
    out.co2e_breakdown.electricity = r3(e0 + (e1 - e0) * rs);
    var leg = legOf(out), far = legOf(pair.rs1);
    var aero = r3(leg.aeroponic + (far.aeroponic - leg.aeroponic) * rs);
    leg.aeroponic = aero;
    leg.delta_pct = leg.conventional ? r1((aero - leg.conventional) / leg.conventional * 100) : null;
    leg.better = aero < leg.conventional;
    leg.note = "at " + Math.round(rs * 100) + "% renewable electricity, cradle-to-gate";
    return out;
  }

  function fromSnapshot(method, path, body) {
    var snap = state.snapshot;
    if (!snap) return Promise.reject(offlineError("offline snapshot not loaded"));
    var p = norm(path);
    var parts = p.split("?");
    var bare = parts[0];
    var params = new URLSearchParams(parts[1] || "");

    if (method === "GET") {
      if (snap.endpoints[p]) return Promise.resolve(snap.endpoints[p]);
      var coll = collection(bare, params);
      if (coll) return Promise.resolve(coll);
      state.misses.push(p);
      return Promise.reject(offlineError("Not captured in the offline snapshot: " + p));
    }

    var m = bare.match(/^\/batches\/([^/]+)\/compliance\/lca\/preview$/);
    if (m) {
      try {
        return Promise.resolve(lcaPreview(decodeURIComponent(m[1]), body && body.renewable_share));
      } catch (e) { return Promise.reject(e); }
    }
    return Promise.reject(offlineError(
      "Read-only snapshot — this build has no backend, so nothing can be written."));
  }

  /* ------------------------------------------------------------- dispatcher */
  function request(method, path, body) {
    if (state.mode === "snapshot") return fromSnapshot(method, path, body);
    return live(method, path, body).catch(function (err) {
      if (!err.offline) throw err;
      return useSnapshot().then(function () {
        return fromSnapshot(method, path, body);
      });
    });
  }

  /* ------------------------------------------------------------ formatting */
  function num(v, dp) {
    if (v === null || v === undefined || v === "") return "—";
    var n = Number(v);
    if (!isFinite(n)) return "—";
    return n.toLocaleString("en-US", {
      minimumFractionDigits: dp === undefined ? 0 : dp,
      maximumFractionDigits: dp === undefined ? (Math.abs(n) < 10 ? 2 : 0) : dp
    });
  }

  function compact(v) {
    var n = Number(v || 0);
    var a = Math.abs(n);
    if (a >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return num(n, a < 10 ? 2 : 0);
  }

  function pct(v, dp) {
    if (v === null || v === undefined) return "—";
    var n = Number(v);
    return (n > 0 ? "+" : "") + n.toFixed(dp === undefined ? 1 : dp) + "%";
  }

  function usd(v) {
    return "$" + num(v, 0);
  }

  function shortHash(h, n) {
    if (!h) return "—";
    n = n || 10;
    return h.slice(0, n) + "…" + h.slice(-4);
  }

  function dateStr(ts, withTime) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (isNaN(d)) return ts;
    var o = { year: "numeric", month: "short", day: "2-digit" };
    if (withTime !== false) { o.hour = "2-digit"; o.minute = "2-digit"; o.hour12 = false; }
    return d.toLocaleString("en-GB", o).replace(",", "");
  }

  function dayStr(ts) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (isNaN(d)) return ts;
    return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "2-digit" });
  }

  function ago(ts) {
    if (!ts) return "—";
    var s = (Date.now() - new Date(ts).getTime()) / 1000;
    if (isNaN(s)) return "—";
    if (s < 0) s = 0;
    if (s < 60) return Math.floor(s) + "s ago";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    if (s < 2592000) return Math.floor(s / 86400) + "d ago";
    return Math.floor(s / 2592000) + "mo ago";
  }

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function qs(name, fallback) {
    var v = new URLSearchParams(location.search).get(name);
    return v === null ? fallback : v;
  }

  /* t() passthrough so pages can localise JS-rendered strings */
  function t(key, fb) { return window.NAPI18N ? NAPI18N.t(key, fb) : (fb || key); }

  /* QR image source: a captured .svg file on a static host, the API otherwise */
  function qr(token) {
    if (state.mode === "snapshot") {
      var map = state.snapshot && state.snapshot.qr;
      if (map && map[token]) return map[token];
      return "assets/data/qr/" + encodeURIComponent(token) + ".svg";
    }
    return BASE + "/qr/" + encodeURIComponent(token);
  }

  window.NFApi = {
    get: function (p) { return request("GET", p); },
    post: function (p, b) { return request("POST", p, b); },
    base: BASE,
    mode: function () { return state.mode; },
    readOnly: function () { return state.mode === "snapshot"; },
    snapshot: function () { return state.snapshot; },
    misses: function () { return state.misses.slice(); },
    qr: qr,
    /* let a page react the moment the mode is known (e.g. disable writes) */
    onMode: function (cb) {
      if (state.mode !== "live") cb(state.mode);
      document.addEventListener("nf-mode", function (e) { cb(e.detail.mode); });
    }
  };
  window.Fmt = {
    num: num, compact: compact, pct: pct, usd: usd, shortHash: shortHash,
    dateStr: dateStr, dayStr: dayStr, ago: ago, esc: esc, qs: qs, t: t
  };
})();
