/* ==========================================================================
   ui — shared renderers. Charts, journey timelines, impact bars, toasts.
   Every page uses these so the same number never looks different twice.
   ========================================================================== */
(function () {
  var C = {
    acc: "#1d9bf0", up: "#00ba7c", down: "#f4212e", warn: "#ffd400",
    coffee: "#c8a27a", water: "#4fa8d8", leaf: "#4ea72e",
    line: "#2f3336", grid: "#212428", txt: "#e7e9ea", txt2: "#9ba1a6", txt3: "#71767b"
  };

  /* ---------------------------------------------------------------- toast */
  var toastEl, toastTimer;
  function toast(msg, kind) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "toast";
      document.body.appendChild(toastEl);
    }
    toastEl.className = "toast on " + (kind || "");
    toastEl.textContent = msg;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.className = "toast " + (kind || ""); }, 3200);
  }

  /* ---------------------------------------------------------------- chart */
  var charts = new WeakMap();
  function baseOption() {
    return {
      textStyle: { color: C.txt2, fontSize: 12 },
      grid: { left: 48, right: 18, top: 26, bottom: 30, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1c1f24", borderColor: C.line, borderWidth: 1,
        textStyle: { color: C.txt, fontSize: 12 },
        axisPointer: { lineStyle: { color: C.txt3, type: "dashed" } }
      },
      animationDuration: 420
    };
  }
  function axisCategory(data, rotate) {
    return {
      type: "category", data: data, boundaryGap: false,
      axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false },
      axisLabel: { color: C.txt3, fontSize: 11, hideOverlap: true, rotate: rotate || 0 }
    };
  }
  function axisValue(name, fmt) {
    return {
      type: "value", name: name || "", nameTextStyle: { color: C.txt3, fontSize: 11, padding: [0, 0, 0, -6] },
      splitLine: { lineStyle: { color: C.grid } },
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: C.txt3, fontSize: 11, formatter: fmt }
    };
  }
  function render(el, option) {
    if (typeof el === "string") el = document.getElementById(el);
    if (!el || !window.echarts) return null;
    var inst = charts.get(el);
    if (!inst) { inst = echarts.init(el, null, { renderer: "canvas" }); charts.set(el, inst); }
    inst.setOption(option, true);
    inst.resize();
    if (!el.dataset.resizeBound) {
      el.dataset.resizeBound = "1";
      window.addEventListener("resize", function () { inst.resize(); });
    }
    return inst;
  }
  function line(el, spec) {
    var opt = baseOption();
    opt.grid.top = spec.title ? 40 : 26;
    opt.xAxis = axisCategory(spec.labels);
    opt.yAxis = spec.axes.map(function (a) {
      return Object.assign(axisValue(a.name, a.fmt), a.axis || {});
    });
    opt.series = spec.series.map(function (s) {
      return {
        name: s.name, type: "line", data: s.data, yAxisIndex: s.axis || 0,
        showSymbol: false, smooth: s.smooth === undefined ? 0.25 : s.smooth,
        lineStyle: { width: 1.6, color: s.color },
        itemStyle: { color: s.color },
        areaStyle: s.area ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: s.color + "44" }, { offset: 1, color: s.color + "00" }
          ])
        } : null,
        markLine: s.markLine || undefined
      };
    });
    if (spec.legend !== false) {
      opt.legend = {
        top: 0, right: 0, icon: "roundRect", itemWidth: 9, itemHeight: 9,
        textStyle: { color: C.txt2, fontSize: 11 }
      };
    }
    return render(el, opt);
  }
  function barsH(el, spec) {
    var opt = {
      textStyle: { color: C.txt2, fontSize: 12 },
      grid: { left: 6, right: 46, top: 6, bottom: 6, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
        backgroundColor: "#1c1f24", borderColor: C.line, textStyle: { color: C.txt, fontSize: 12 } },
      xAxis: { type: "value", splitLine: { lineStyle: { color: C.grid } },
        axisLabel: { color: C.txt3, fontSize: 11 } },
      yAxis: { type: "category", data: spec.labels, inverse: true,
        axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false },
        axisLabel: { color: C.txt2, fontSize: 12 } },
      series: spec.series.map(function (s) {
        return { name: s.name, type: "bar", data: s.data, barMaxWidth: 13,
          itemStyle: { color: s.color, borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: "right", color: C.txt2, fontSize: 11,
                   formatter: s.label || "{c}" } };
      })
    };
    return render(el, opt);
  }

  /* ----------------------------------------------------------- impact bars */
  function impactBars(el, legs) {
    var rows = legs.map(function (l) {
      var better = l.better;
      var cls = better ? "good" : "bad";
      var delta = l.delta_pct === null ? "—" : Fmt.pct(l.delta_pct);
      var dcls = l.delta_pct === null ? "dim" : (better ? "v-up" : "v-down");
      var conv = l.conventional === 0 ? 0
        : Math.max(l.aeroponic / l.conventional, l.conventional / l.aeroponic);
      var maxScale = Math.max(1, Math.min(conv, 30));
      var aeroW = l.conventional === 0 ? 100
        : Math.max(2, Math.min(100, (l.aeroponic / Math.max(l.aeroponic, l.conventional)) * 100 / maxScale * maxScale));
      var convW = l.conventional === 0 ? 0
        : Math.max(2, Math.min(100, (l.conventional / Math.max(l.aeroponic, l.conventional)) * 100 / maxScale * maxScale));
      return '' +
        '<div class="bar-row" style="grid-template-columns:1fr">' +
          '<div class="between" style="align-items:baseline">' +
            '<span class="bl"><strong>' + Fmt.esc(l.label) + "</strong> " +
              '<span class="dim tiny">' + Fmt.esc(l.unit) + "</span></span>" +
            '<span class="bv ' + dcls + '">' + delta + "</span>" +
          "</div>" +
          '<div class="stack" style="gap:5px;margin-top:6px">' +
            '<div class="row" style="gap:8px;flex-wrap:nowrap">' +
              '<span class="tiny dim nowrap" style="width:92px">Aeroponic</span>' +
              '<span class="meter" style="flex:1"><i class="' + cls + '" style="width:' + aeroW + '%"></i></span>' +
              '<span class="mono tiny nowrap" style="width:78px;text-align:right">' + Fmt.num(l.aeroponic, l.aeroponic < 10 ? 3 : 1) + "</span>" +
            "</div>" +
            '<div class="row" style="gap:8px;flex-wrap:nowrap">' +
              '<span class="tiny dim nowrap" style="width:92px">Conventional</span>' +
              '<span class="meter" style="flex:1"><i class="" style="width:' + convW + '%;background:#5f5e5a"></i></span>' +
              '<span class="mono tiny nowrap" style="width:78px;text-align:right">' + Fmt.num(l.conventional, l.conventional < 10 ? 3 : 1) + "</span>" +
            "</div>" +
          "</div>" +
          (l.note ? '<div class="tiny dim" style="margin-top:6px">' + Fmt.esc(l.note) + "</div>" : "") +
        "</div>";
    }).join("");
    if (typeof el === "string") el = document.getElementById(el);
    if (el) el.innerHTML = rows;
  }

  /* stage labels are authored as "中文 / English"; keep only the active half */
  function stage(label) {
    if (!label) return "";
    var parts = String(label).split(" / ");
    if (parts.length < 2) return label;
    var lang = (window.NAPI18N && NAPI18N.current()) || "en";
    return lang === "zh" ? parts[0] : parts[1];
  }

  /* ------------------------------------------------------------- timeline */
  function timeline(el, stages, currentStage) {
    var html = stages.map(function (s, i) {
      var cls = s.completed ? (s.stage === currentStage ? "done current" : "done") : "todo";
      var payload = s.payload && Object.keys(s.payload).length
        ? '<details class="payload"><summary>' + Fmt.t("c.detail", "Event payload") + "</summary>" +
          "<pre>" + Fmt.esc(JSON.stringify(s.payload, null, 2)) + "</pre></details>"
        : "";
      var hash = s.hash
        ? '<code class="hash">' + Fmt.esc(s.hash) + "</code>"
        : "";
      return '<div class="tl-item ' + cls + '">' +
        '<span class="tl-dot">' + (s.completed ? "✓" : (i + 1)) + "</span>" +
        '<div class="tl-h"><strong>' + Fmt.esc(stage(s.label)) + "</strong>" +
          (s.at ? '<span class="tl-when">' + Fmt.dateStr(s.at) + "</span>" : '<span class="tl-when dim">pending</span>') +
          (s.seq ? '<span class="chip">#' + s.seq + "</span>" : "") +
        "</div>" +
        '<div class="tl-p">' + Fmt.esc(s.description) + "</div>" +
        (s.actor ? '<div class="tiny dim mono" style="margin-top:3px">' + Fmt.esc(s.actor) + "</div>" : "") +
        hash + payload +
      "</div>";
    }).join("");
    if (typeof el === "string") el = document.getElementById(el);
    if (el) el.innerHTML = html || '<div class="empty">' + Fmt.t("c.empty", "No data") + "</div>";
  }

  /* ------------------------------------------------------------ miscllany */
  function statCard(k, v, sub, cls, vcls) {
    return '<div class="stat ' + (cls || "") + '"><div class="k" data-i18n="' + (k.i18n || "") + '">' +
      Fmt.esc(k.text || "") + '</div><div class="v ' + (vcls || "") + '">' + v + "</div>" +
      (sub ? '<div class="s">' + sub + "</div>" : "") + "</div>";
  }

  function stageRow(mix) {
    var total = mix.reduce(function (a, m) { return a + m.c; }, 0) || 1;
    return mix.map(function (m) {
      return '<div class="bar-row" style="grid-template-columns:120px 1fr 56px">' +
        '<span class="bl">' + Fmt.esc(m.status) + "</span>" +
        '<span class="meter"><i style="width:' + (m.c / total * 100) + '%"></i></span>' +
        '<span class="bv">' + m.c + "</span></div>";
    }).join("");
  }

  function spinner(label) {
    return '<div class="empty"><span class="spin"></span> ' +
      Fmt.esc(label || Fmt.t("c.loading", "Loading…")) + "</div>";
  }
  function fail(el, err) {
    if (typeof el === "string") el = document.getElementById(el);
    if (el) el.innerHTML = '<div class="empty">' + Fmt.esc(String(err.message || err)) +
      '<div style="margin-top:12px"><button class="btn sm" onclick="location.reload()">' +
      Fmt.esc(Fmt.t("c.retry", "Retry")) + "</button></div></div>";
  }

  function copy(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(function () {
        toast(Fmt.t("c.copied", "Copied"), "ok");
      });
    }
  }

  /* aeroponic leaf mark for the facility map */
  function worldMap(el, facilities, opts) {
    opts = opts || {};
    var W = 660, H = 300;
    var px = function (lon) { return 40 + (lon + 180) / 360 * (W - 80); };
    var py = function (lat) { return 30 + (90 - lat) / 180 * (H - 60); };
    var dots = facilities.map(function (f) {
      if (f.lat === null || f.lon === undefined) return "";
      var x = px(f.lon), y = py(f.lat);
      var r = opts.radius ? opts.radius(f) : 6;
      return '<g class="node" data-code="' + Fmt.esc(f.code) + '">' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + (r + 9) + '" fill="' + C.up + '" opacity="0.14" class="node-pulse"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + C.up + '" opacity="0.9"/>' +
        '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="none" stroke="#000" stroke-width="1.5"/>' +
        '<text x="' + (x + r + 8) + '" y="' + (y + 4) + '" fill="' + C.txt + '" font-size="11" ' +
          'font-family="ui-monospace,monospace">' + Fmt.esc(f.city || f.code) + "</text>" +
        "</g>";
    }).join("");
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" role="img" aria-label="Facility locations">' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#08090b"/>' +
      '<g stroke="#212428" stroke-width="0.5">' +
      [-60, -30, 0, 30, 60].map(function (lat) {
        return '<line x1="40" y1="' + py(lat) + '" x2="' + (W - 40) + '" y2="' + py(lat) + '"/>';
      }).join("") +
      [-120, -60, 0, 60, 120].map(function (lon) {
        return '<line x1="' + px(lon) + '" y1="30" x2="' + px(lon) + '" y2="' + (H - 30) + '"/>';
      }).join("") + "</g>" +
      '<line x1="40" y1="' + py(0) + '" x2="' + (W - 40) + '" y2="' + py(0) + '" stroke="#3a3f44" stroke-width="0.8"/>' +
      '<text x="46" y="' + (py(0) - 6) + '" fill="#4b5157" font-size="10" font-family="ui-monospace,monospace">EQUATOR</text>' +
      dots + "</svg>";
    if (typeof el === "string") el = document.getElementById(el);
    if (el) el.innerHTML = svg;
  }

  window.NFUI = {
    C: C, toast: toast, line: line, barsH: barsH, impactBars: impactBars,
    timeline: timeline, statCard: statCard, stageRow: stageRow, stage: stage,
    spinner: spinner, fail: fail, copy: copy, worldMap: worldMap, render: render
  };
})();
