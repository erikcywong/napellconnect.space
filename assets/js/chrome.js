/* ==========================================================================
   chrome — floating nav with hover dropdowns, language switch, chain status,
   and the footer. Injected so every page carries an identical frame.
   English labels live here so the frame stays self-contained; i18n swaps them.
   ========================================================================== */
(function () {
  var NAV = [
    { key: "nav.platform", en: "Platform", children: [
      { href: "index.html", key: "nav.overview", en: "Overview", d: "nav.overview.d", den: "Network and production metrics" },
      { href: "network.html", key: "nav.network", en: "Network registry", d: "nav.network.d", den: "GrowerID · facilities · modules" },
      { href: "modules.html", key: "nav.modules", en: "Grow modules", d: "nav.modules.d", den: "IoT telemetry and climate envelope" },
      { href: "analytics.html", key: "nav.analytics", en: "Analytics", d: "nav.analytics.d", den: "Yield, energy and scenarios" }
    ]},
    { key: "nav.trace", en: "Traceability", children: [
      { href: "trace.html", key: "nav.ledger", en: "Ledger explorer", d: "nav.ledger.d", den: "Browse and verify the hash chain" },
      { href: "lots.html", key: "nav.lots", en: "Batches", d: "nav.lots.d", den: "Sowing through to shipment" }
    ]},
    { key: "nav.compliance", en: "Compliance", children: [
      { href: "compliance.html", key: "nav.reports", en: "Report centre", d: "nav.reports.d", den: "EUDR and LCA dossiers" },
      { href: "compliance.html#checks", key: "c.verified_chain", en: "Verification checks", d: "nav.reports.d", den: "What each report asserts" }
    ]},
    { key: "nav.consumer", en: "Consumer", children: [
      { href: "consume.html", key: "nav.consume", en: "Thank My Farm", d: "nav.consume.d", den: "Scan-to-journey experience" },
      { href: "consume.html#projects", key: "nav.projects", en: "Community projects", d: "nav.projects.d", den: "Traceable fund flows" }
    ]},
    { key: "nav.docs", en: "Docs", children: [
      { href: "api.html", key: "nav.api", en: "API reference", d: "nav.api.d", den: "Endpoints, auth and examples" },
      { href: "about.html", key: "nav.why", en: "Why aeroponic", d: "nav.why.d", den: "How the traceability argument changes" }
    ]}
  ];

  var FOOTER_HEADS = [
    { key: "f.platform", en: "Platform" },
    { key: "f.compliance", en: "Compliance" },
    { key: "f.docs", en: "Docs" }
  ];
  var FOOTER_COLS = [
    [["index.html", "nav.overview", "Overview"], ["network.html", "nav.network", "Network registry"],
     ["modules.html", "nav.modules", "Grow modules"], ["analytics.html", "nav.analytics", "Analytics"]],
    [["trace.html", "nav.ledger", "Ledger explorer"], ["lots.html", "nav.lots", "Batches"],
     ["compliance.html", "nav.reports", "Report centre"], ["consume.html", "nav.consume", "Thank My Farm"]],
    [["api.html", "nav.api", "API reference"], ["about.html", "nav.why", "Why aeroponic"],
     ["index.html#impact", "home.impact.eyebrow", "Impact accounting"],
     ["index.html#pillars", "home.pillars.eyebrow", "Four modules"]]
  ];

  function t(key, en) { return window.NAPI18N ? NAPI18N.t(key, en) : en; }

  function page() {
    return (location.pathname.split("/").pop() || "index.html").split("#")[0];
  }

  function navHtml() {
    var here = page();
    var items = NAV.map(function (g) {
      var active = g.children.some(function (c) { return c.href.split("#")[0] === here; });
      var kids = g.children.map(function (c) {
        return '<a href="' + c.href + '"><span data-i18n="' + c.key + '">' + t(c.key, c.en) + "</span>" +
               '<span data-i18n="' + c.d + '">' + t(c.d, c.den) + "</span></a>";
      }).join("");
      return '<li><a class="top' + (active ? " on" : "") + '" href="' + g.children[0].href + '">' +
             '<span data-i18n="' + g.key + '">' + t(g.key, g.en) + "</span></a>" +
             '<div class="drop">' + kids + "</div></li>";
    }).join("");

    return '<nav class="nav"><div class="wrap">' +
      '<a class="brand" href="index.html"><span class="mk">NF</span>' +
      "<span>Napell Farmer Connect<small>Napell BIO</small></span></a>" +
      '<button class="burger" id="burger" aria-label="Menu">☰</button>' +
      '<ul class="menu" id="menu">' + items + "</ul>" +
      '<div class="nav-right">' +
        '<span class="led" id="chainLed"><span class="dot"></span><span id="chainLedText">verifying…</span></span>' +
        '<span class="lang" id="langSwitch"></span>' +
      "</div></div></nav>";
  }

  function footerHtml() {
    var cols = FOOTER_COLS.map(function (col, i) {
      var h = FOOTER_HEADS[i];
      return '<div><h5 data-i18n="' + h.key + '">' + t(h.key, h.en) + "</h5>" +
        col.map(function (l) {
          return '<a href="' + l[0] + '" data-i18n="' + l[1] + '">' + t(l[1], l[2]) + "</a>";
        }).join("") + "</div>";
    }).join("");
    return '<footer><div class="wrap"><div class="cols">' +
      '<div><h5>Napell Farmer Connect</h5>' +
      '<p class="sm" data-i18n="f.tag">' + t("f.tag", "Identity, traceability and compliance network for aeroponic coffee.") + "</p>" +
      '<p class="tiny dim mono">napell.life · jebiwork.com</p></div>' +
      cols +
      '</div><div class="fine"><span data-i18n="f.rights">' +
      t("f.rights", "Napell BIO · Napell Farmer Connect") + "</span>" +
      '<span><span data-i18n="f.built">' + t("f.built", "Offline demo build") + "</span> · " +
      '<span data-i18n="f.demo">' + t("f.demo", "Synthetic data for product demonstration") + "</span></span>" +
      "</div></div></footer>";
  }

  function mount() {
    var host = document.getElementById("chrome");
    if (host) host.outerHTML = navHtml();
    var fhost = document.getElementById("chrome-footer");
    if (fhost) fhost.outerHTML = footerHtml();
    else if (!document.querySelector("footer")) document.body.insertAdjacentHTML("beforeend", footerHtml());

    var sw = document.getElementById("langSwitch");
    if (sw) {
      sw.innerHTML = (window.NAPI18N ? NAPI18N.languages : [{ code: "en", label: "EN" }])
        .map(function (l) { return '<button data-lang="' + l.code + '">' + l.label + "</button>"; }).join("");
      sw.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-lang]");
        if (b) NAPI18N.setLang(b.dataset.lang);
      });
    }

    var burger = document.getElementById("burger");
    if (burger) burger.addEventListener("click", function () {
      document.getElementById("menu").classList.toggle("open");
    });

    if (window.NAPI18N) NAPI18N.apply(document);
    checkChain();
    document.dispatchEvent(new CustomEvent("chrome:ready"));
  }

  function checkChain() {
    var led = document.getElementById("chainLed");
    var txt = document.getElementById("chainLedText");
    if (!led || !window.NFApi) return;
    NFApi.get("/ledger/verify").then(function (v) {
      var ok = v && v.ok;
      var snap = window.NFApi.mode() === "snapshot";
      led.querySelector(".dot").className = "dot" + (ok ? (snap ? " snap" : "") : " bad");
      txt.textContent = (snap ? "snapshot · " : "") +
        (ok ? (v.length + " events · chain ok") : "chain broken");
      txt.title = ok
        ? (snap
          ? "Static build — this is a read-only capture of the ledger taken at export time. " +
            "Head hash " + v.head_hash
          : v.head_hash)
        : (v.reason || "integrity failure");
    }).catch(function () {
      led.querySelector(".dot").className = "dot bad";
      txt.textContent = "api unreachable";
    });
  }

  window.NFChrome = { mount: mount, checkChain: checkChain };
  document.addEventListener("DOMContentLoaded", mount);
  /* the read-only fallback can engage after first paint — re-label when it does */
  document.addEventListener("nf-mode", function () { checkChain(); });
  window.addEventListener("langchange", function () { if (window.NAPI18N) NAPI18N.apply(document); });
})();
