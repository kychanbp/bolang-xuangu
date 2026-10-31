// 波浪选股 · adjustable screen. Loads cands.json (written by screen.py export()) and runs the same
// rules as screen.py check() in the browser, so a reader can change every rule's numbers.
"use strict";
const PCT = (x, d = 1) => (x * 100).toFixed(d);
const EPS = 1e-6;  // same as screen.py: a value equal to a limit passes
const round = (x, k) => Math.round(x * 10 ** k) / 10 ** k;

// same logic as screen.py check(); positions are counted back from today (0 = today)
function check(s, q, bullWindows) {
  const e = s.lb[q.high_lookback];
  if (!e) return null;
  const [aH, aL, keep, bull] = e;
  if (keep > (1 - q.drop) * (1 + EPS) || aL > q.max_days_after_low) return null;
  const bi = bullWindows.indexOf(q.bull_window);
  const nlu = bull[2 * bi], hiOverLow = bull[2 * bi + 1];
  if (nlu < q.min_limitups || hiOverLow < (1 + q.bull_runup) * (1 - EPS)) return null;
  const c = s.c, T = c.length - 1, iL = T - aL;
  let d = -1;
  for (let k = iL; k <= Math.min(iL + q.candle_window, T); k++) {
    if ((s.chg[k] ?? 0) >= q.rebound - EPS) { d = k; break; }
  }
  if (d < 0) return null;
  const vr = s.vr[d];
  if ((vr !== null && vr !== undefined && vr < q.spike * (1 - EPS)) || T - d < q.min_pullback_days + 1) return null;
  const S = c[d];
  let tP = -1;
  for (let k = d + 1; k <= T; k++) if (c[k] !== null && (tP < 0 || c[k] > c[tP])) tP = k;
  const C = c[T], O = s.o, L = s.l, V = s.v[T], VD = s.v[d];
  const fails = [];
  if (T - tP < q.min_pullback_days) fails.push("还在第一波上涨中");
  if (Math.abs(C - O) > (q.doji + EPS) * O) fails.push(`不是十字星（实体 ${PCT(Math.abs(C - O) / O)}%）`);
  const broken = L < S * (1 - EPS) || C < S * (1 - EPS);
  if (broken) fails.push("跌破支撑线");
  if (C > S * (1 + q.near_support) * (1 + EPS)) fails.push(`离支撑线 ${PCT(C / S - 1)}%（需 ≤ ${round(q.near_support * 100, 4)}%）`);
  if (V > q.vol_ratio * VD * (1 + EPS)) fails.push(`量为阳线当天的 ${(V / VD * 100).toFixed(0)}%（需 ≤ ${round(q.vol_ratio * 100, 4)}%）`);
  return {
    code: s.code, buy: !fails.length, broken, missing: fails.join("；"), drop: keep - 1, nlu,
    aH, aL, aD: T - d, aP: T - tP, S, C, above: C / S - 1, daysLeft: q.max_days_after_low - aL,
  };
}
if (typeof module !== "undefined") module.exports = { check };

typeof document !== "undefined" && (() => {
  const $ = (id) => document.getElementById(id);
  // key, label, unit, min, max, step; "pct" values are shown in % and stored as fractions
  // adjustable now: rule ① minimum drop, rule ③ candle rise and days after the low (others fixed at default)
  const PARAMS = [
    ["①", "drop", "高点到低点的最小跌幅", "%", 40, 70, 1, "pct"],
    ["③", "rebound", "止跌阳线最小涨幅", "%", 5, 15, 0.5, "pct"],
    ["③", "candle_window", "低点当天起几个交易日内找止跌阳线", "日", 0, 20, 1],
  ];
  let D, DEF, Q, shardCache = {};

  function show(p, v) { return p[7] === "pct" ? round(v * 100, 4) : v; }
  function store(p, v) { return p[7] === "pct" ? round(v / 100, 6) : v; }

  function readHash() {
    const q = { ...DEF };
    const h = new URLSearchParams(location.hash.slice(1));
    for (const p of PARAMS) {
      if (!h.has(p[1])) continue;
      const x = Number(h.get(p[1]));
      if (!Number.isFinite(x)) continue;
      if (typeof p[4] === "string") { if (D.adjust[p[4]].includes(x)) q[p[1]] = x; }
      else q[p[1]] = store(p, Math.min(p[5], Math.max(p[4], x)));
    }
    return q;
  }
  function writeHash() {
    const h = new URLSearchParams();
    for (const p of PARAMS) if (Q[p[1]] !== DEF[p[1]]) h.set(p[1], show(p, Q[p[1]]));
    const s = h.toString();
    history.replaceState(null, "", s ? "#" + s : location.pathname + location.search);
  }

  const day = (age) => D.calendar[D.calendar.length - 1 - age];

  function svgChart(r, k) {
    const m = k.c.length, T = m - 1, a = Math.max(0, T - r.aH - 30);
    const W = 900, H1 = 260, H2 = 70, n = T - a + 1, bw = W / n;
    let hi = -Infinity, lo = Infinity, vm = 0;
    for (let i = a; i <= T; i++) {
      if (k.h[i] !== null) { hi = Math.max(hi, k.h[i]); lo = Math.min(lo, k.l[i]); vm = Math.max(vm, k.v[i]); }
    }
    hi *= 1.08; lo *= 0.96;
    const y = (p) => 8 + (hi - p) / (hi - lo) * (H1 - 16);
    let g = "";
    for (let i = a; i <= T; i++) {
      if (k.c[i] === null) continue;
      const x = (i - a) * bw, up = k.c[i] >= k.o[i], col = up ? "#d63031" : "#20a162";
      const y1 = y(Math.max(k.o[i], k.c[i])), y2 = y(Math.min(k.o[i], k.c[i]));
      g += `<line x1="${x + bw / 2}" x2="${x + bw / 2}" y1="${y(k.h[i])}" y2="${y(k.l[i])}" stroke="${col}" stroke-width="1"/>`;
      g += `<rect x="${x + bw * 0.15}" width="${bw * 0.7}" y="${y1}" height="${Math.max(y2 - y1, 0.8)}" fill="${col}"/>`;
      const vh = k.v[i] / vm * (H2 - 6);
      g += `<rect x="${x + bw * 0.15}" width="${bw * 0.7}" y="${H1 + H2 - vh}" height="${vh}" fill="${col}" opacity=".8"/>`;
    }
    g += `<line x1="0" x2="${W}" y1="${y(r.S)}" y2="${y(r.S)}" stroke="#0984e3" stroke-width="1.2"/>`;
    const marks = [[r.aH, "高点", "#c0392b"], [r.aL, "低点", "#636e72"], [r.aD, "阳线", "#0984e3"],
      [r.aP, "第一波高点", "#e67e22"], [0, "今天", "#00b894"]];
    marks.forEach(([age, lab, col], j) => {
      const x = (T - age - a) * bw + bw / 2;
      g += `<line x1="${x}" x2="${x}" y1="0" y2="${H1 + H2}" stroke="${col}" stroke-dasharray="4 3" stroke-width="1"/>`;
      g += `<text x="${Math.min(x + 3, W - 70)}" y="${14 + 13 * j}" fill="${col}" font-size="12">${lab}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H1 + H2}" role="img" aria-label="${r.code} 日K线">${g}</svg>`;
  }
  function shardOf(code) { return Number(code.slice(2)) % D.shards; }
  async function drawChart(el, r) {
    const i = shardOf(r.code);
    try {
      shardCache[i] = shardCache[i] || fetch(`k/${i}.json?d=${D.date}`).then((x) => x.json());
      const k = (await shardCache[i])[r.code];
      el.innerHTML = k ? svgChart(r, k) : "";
    } catch (e) { el.textContent = "图表加载失败"; }
  }

  function card(r) {
    const kind = r.buy ? "buy" : "watch";
    return `<article class="card"><header><span class="badge ${kind}">${r.buy ? "买点" : "观察"}</span>
<h3>${r.code}</h3></header><p class="why">${r.buy ? "今天符合全部规则" : "还差：" + r.missing}</p>
<div class="chart" data-code="${r.code}"></div>
<dl><div><dt>跌幅</dt><dd>${PCT(r.drop, 0)}%</dd></div><div><dt>高点前涨停</dt><dd>${r.nlu} 次</dd></div>
<div><dt>低点</dt><dd>${day(r.aL)}</dd></div><div><dt>止跌阳线</dt><dd>${day(r.aD)}</dd></div>
<div><dt>收盘价</dt><dd>${r.C.toFixed(2)}</dd></div><div><dt>支撑线</dt><dd>${r.S.toFixed(2)}</dd></div><div><dt>高于支撑线</dt><dd>${PCT(r.above)}%</dd></div>
<div><dt>剩余天数</dt><dd>${r.daysLeft} 日</dd></div></dl></article>`;
  }

  function rulesText(q) {
    const p = (x) => round(x * 100, 4);
    return `<li>高位到低位跌幅 ≥ ${p(q.drop)}%：高点为最近 ${q.high_lookback} 个交易日最高价，低点为高点之后最低价。</li>
<li>高点前 ${q.bull_window} 个交易日是牛股：高点 ≥ 区间最低价 × ${round(1 + q.bull_runup, 4)}，且 ≥ ${q.min_limitups} 次涨停收盘（主板 10%，创业板/科创板 20%）。</li>
<li>止跌时单日涨 ≥ ${p(q.rebound)}%：低点当天起 ${q.candle_window} 日内第一根 ≥ ${p(q.rebound)}% 阳线，当天量 ≥ 前 20 日均量 ${q.spike} 倍；其收盘价为支撑线。</li>
<li>缩量回调收十字星：第一波高点至少在 ${q.min_pullback_days} 日前；今天 |收−开| ≤ 开盘价 ${p(q.doji)}%，最低价 ≥ 支撑线，收盘 ≤ 支撑线 × ${round(1 + q.near_support, 4)}，成交量 ≤ 阳线当天的 ${p(q.vol_ratio)}%；距低点 ≤ ${q.max_days_after_low} 个交易日。</li>`;
  }

  function render() {
    const rows = D.stocks.map((s) => check(s, Q, D.adjust.bull_windows)).filter(Boolean);
    const buys = rows.filter((r) => r.buy);
    const live = rows.filter((r) => !r.buy && !r.broken)
      .sort((a, b) => (a.missing.split("；").length - b.missing.split("；").length) || (a.above - b.above));
    const custom = PARAMS.some((p) => Q[p[1]] !== DEF[p[1]]);
    $("nb").textContent = buys.length; $("nl").textContent = live.length;
    $("nx").textContent = rows.filter((r) => r.broken).length;
    $("custom").hidden = !custom;
    $("buys").innerHTML = buys.map(card).join("") || '<p class="empty">今天没有股票符合全部规则。</p>';
    $("watch").innerHTML = live.slice(0, 8).map(card).join("") || '<p class="empty">暂无。</p>';
    $("tbl").innerHTML = "<tr><th>代码</th><th>高于支撑线</th><th>剩余天数</th><th>今天还差</th></tr>" +
      (live.map((r) => `<tr><td>${r.code}</td><td>${r.above >= 0 ? "+" : ""}${PCT(r.above)}%</td><td>${r.daysLeft}</td><td>${r.missing}</td></tr>`).join("")
        || '<tr><td colspan="4">暂无</td></tr>');
    $("rules").innerHTML = rulesText(Q);
    const byCode = Object.fromEntries(rows.map((r) => [r.code, r]));
    document.querySelectorAll(".chart[data-code]").forEach((el) => drawChart(el, byCode[el.dataset.code]));
  }

  function form() {
    let html = "", grp = "";
    const names = { "①": "① 大跌", "③": "③ 放量止跌阳线" };
    for (const p of PARAMS) {
      if (p[0] !== grp) { html += (grp ? "</fieldset>" : "") + `<fieldset><legend>${names[p[0]]}</legend>`; grp = p[0]; }
      const v = show(p, Q[p[1]]), d = show(p, DEF[p[1]]);
      const input = typeof p[4] === "string"
        ? `<select id="q_${p[1]}">${D.adjust[p[4]].map((x) => `<option value="${x}"${x === Q[p[1]] ? " selected" : ""}>${x}</option>`).join("")}</select>`
        : `<input id="q_${p[1]}" type="number" inputmode="decimal" min="${p[4]}" max="${p[5]}" step="${p[6]}" value="${v}">`;
      html += `<label><span>${p[2]}</span><span class="in">${input}<i>${p[3]}</i></span><small>默认 ${d}${typeof p[4] === "string" ? "" : `（可选 ${p[4]}–${p[5]}）`}</small></label>`;
    }
    $("form").innerHTML = html + "</fieldset>";
    for (const p of PARAMS) {
      $("q_" + p[1]).addEventListener("input", (ev) => {
        const x = Number(ev.target.value);
        if (ev.target.value === "" || !Number.isFinite(x)) return;
        Q[p[1]] = typeof p[4] === "string" ? x : store(p, Math.min(p[5], Math.max(p[4], x)));
        writeHash(); render();
      });
      // show the clamped value when the reader leaves the box (range is limited by cands.json)
      $("q_" + p[1]).addEventListener("change", (ev) => { ev.target.value = show(p, Q[p[1]]); });
    }
  }

  async function main() {
    try {
      D = await (await fetch("cands.json?d=" + Date.now().toString().slice(0, 7))).json();
    } catch (e) { $("pstatus").textContent = "参数数据加载失败，下面是默认参数的结果。"; return; }
    DEF = { ...D.rules };
    Q = readHash();
    $("pstatus").textContent = `可调整 ${PARAMS.length} 个参数，结果在浏览器里即时重算（共 ${D.stocks.length} 只候选股）。`;
    $("reset").hidden = false;
    $("reset").addEventListener("click", () => { Q = { ...DEF }; writeHash(); form(); render(); });
    form(); render();
  }
  main();
})();
