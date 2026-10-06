#!/usr/bin/env python3
"""Daily 选股模型 screen for China A-shares.

Reads the community Qlib A-share bundle (github.com/chenditc/investment_data), checks every
Shanghai/Shenzhen stock on the latest trading day against the rules below, and writes a static
page (index.html + data.json + charts) to --out.

Rules (literal reading of the handwritten note; defaults in RULES):
 1. Fall >= 55%: high H = highest high in the last 250 trading days; low L = lowest low after H; L <= 0.45 H.
 2. Bull stock before H: within 120 days before H, H >= 2x that window's low and >= 3 limit-up closes.
 3. Within 10 days of L (L day included), the first day up >= 8% on volume >= 1.5x its prior 20-day mean.
    Its close is the support line.
 4. Buy day: first-wave peak (highest close after the 8% day) >= 2 days earlier; today a doji
    (|close-open| <= 1% of open), today's low >= support, close <= support x 1.05,
    volume <= 50% of the 8% day's volume; within 60 trading days of L.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RULES = dict(high_lookback=250, drop=0.55, bull_window=120, bull_runup=1.0, min_limitups=3,
             rebound=0.08, candle_window=10, spike=1.5, min_pullback_days=2, doji=0.01,
             near_support=0.05, vol_ratio=0.5, max_days_after_low=60, min_listed_days=60)
WINDOW = 460          # trading days loaded per stock (enough for 250 + 120 + 20-day volume base)
FIELDS = ["open", "high", "low", "close", "volume", "change", "factor"]


def load(qdir: Path):
    cal = pd.to_datetime(open(qdir / "calendars" / "day.txt").read().split())
    inst = pd.read_csv(qdir / "instruments" / "all.txt", sep="\t", header=None, names=["code", "a", "b"])
    inst = inst[inst.code.str[:2].isin(["SH", "SZ"])]
    # last day with real data = latest end date in the instrument list
    last = pd.Timestamp(inst.b.max())
    T1 = int(cal.get_loc(last)) + 1
    T0 = T1 - WINDOW
    dates = cal[T0:T1]
    codes, arr, first = [], {f: [] for f in FIELDS}, []
    for c in inst.code:
        d = qdir / "features" / c.lower()
        if not (d / "close.day.bin").exists():
            continue
        cols = {}
        for f in FIELDS:
            a = np.fromfile(d / f"{f}.day.bin", dtype="<f4")
            s = int(a[0])
            out = np.full(WINDOW, np.nan, dtype=np.float32)
            lo, hi = max(s, T0), min(s + len(a) - 1, T1)
            if hi > lo:
                out[lo - T0:hi - T0] = a[1 + lo - s:1 + hi - s]
            cols[f] = out
            if f == "close":
                first.append(s - T0)
        codes.append(c)
        for f in FIELDS:
            arr[f].append(cols[f])
    p = {f: np.stack(v, axis=1) for f, v in arr.items()}
    trade = np.isfinite(p["close"]) & (p["volume"] > 0)
    for f in ("open", "high", "low", "close", "volume"):
        p[f] = np.where(trade, p[f], np.nan)
    p["chg"] = p.pop("change")
    p["dates"], p["codes"], p["first"] = dates, np.array(codes), np.array(first)
    after = np.asarray(dates >= "2020-08-24")
    lim = np.zeros(p["close"].shape, dtype=np.float32)
    for j, c in enumerate(codes):
        n = c[2:]
        lim[:, j] = 0.20 if n.startswith("688") else (np.where(after, 0.20, 0.10) if n.startswith(("300", "301")) else 0.10)
    p["is_lu"] = (np.nan_to_num(p["chg"]) >= lim - 0.003) & (p["close"] >= p["high"] * 0.999)
    return p


def check(j, t, p, q=RULES):
    o, h, l, c, v, chg = (p[k][:, j] for k in ("open", "high", "low", "close", "volume", "chg"))
    start = max(int(p["first"][j]) + q["min_listed_days"], 21, 0)
    if t < start or not np.isfinite(c[t]):
        return None
    w = np.arange(max(t - q["high_lookback"], start), t + 1)
    if not np.isfinite(h[w]).any():
        return None
    tH = int(w[np.nanargmax(h[w])])
    H = h[tH]
    if tH >= t:
        return None
    w2 = np.arange(tH, t + 1)
    tL = int(w2[np.nanargmin(l[w2])])
    Lo = l[tL]
    if Lo > H * (1 - q["drop"]) or tL >= t or t - tL > q["max_days_after_low"]:
        return None
    wb = np.arange(max(tH - q["bull_window"], start), tH + 1)
    nlu = int(p["is_lu"][wb, j].sum())
    if nlu < q["min_limitups"] or H < (1 + q["bull_runup"]) * np.nanmin(l[wb]):
        return None
    ds = [k for k in range(tL, min(tL + q["candle_window"], t) + 1) if np.nan_to_num(chg[k]) >= q["rebound"]]
    if not ds:
        return None
    d = ds[0]
    if d < 20 or not np.isfinite(v[d]) or v[d] < q["spike"] * np.nanmean(v[d - 20:d]) or t - d < q["min_pullback_days"] + 1:
        return None
    S = float(c[d])
    tP = d + 1 + int(np.nanargmax(c[d + 1:t + 1]))
    fails = []
    if t - tP < q["min_pullback_days"]:
        fails.append("还在第一波上涨中")
    if abs(c[t] - o[t]) > q["doji"] * o[t]:
        fails.append(f"不是十字星（实体 {abs(c[t] - o[t]) / o[t] * 100:.1f}%）")
    if l[t] < S or c[t] < S:
        fails.append("跌破支撑线")
    if c[t] > S * (1 + q["near_support"]):
        fails.append(f"离支撑线 {(c[t] / S - 1) * 100:.1f}%（需 ≤ 5%）")
    if v[t] > q["vol_ratio"] * v[d]:
        fails.append(f"量为 8% 阳线的 {v[t] / v[d] * 100:.0f}%（需 ≤ 50%）")
    D = p["dates"]
    f = float(p["factor"][t, j])            # raw price = adjusted price / factor
    return dict(code=str(p["codes"][j]), j=j, tH=tH, tL=tL, d=d, tP=tP, t=t, support=S, close=float(c[t]),
                support_px=S / f, close_px=float(c[t]) / f,
                high_date=str(D[tH].date()), low_date=str(D[tL].date()), candle_date=str(D[d].date()),
                drop=float(Lo / H - 1), n_limitup=nlu, above=float(c[t] / S - 1), days_since_low=t - tL,
                days_left=q["max_days_after_low"] - (t - tL), buy=not fails,
                broken=any(f.startswith("跌破") for f in fails), missing="；".join(fails))


def chart(r, p, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        if Path(f).exists():
            font_manager.fontManager.addfont(f)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()
            break
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 9})
    j = r["j"]
    o, h, l, c, v = (p[k][:, j] for k in ("open", "high", "low", "close", "volume"))
    a, b = max(r["tH"] - 60, 0), r["t"]
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(10, 4.2), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    for i in range(a, b + 1):
        if not np.isfinite(c[i]):
            continue
        col = "#d63031" if c[i] >= o[i] else "#20a162"
        ax.vlines(i - a, l[i], h[i], color=col, lw=0.6)
        ax.add_patch(plt.Rectangle((i - a - 0.35, min(o[i], c[i])), 0.7, max(abs(c[i] - o[i]), (h[i] - l[i]) * 0.02 + 1e-9), color=col))
        axv.bar(i - a, v[i], color=col, width=0.7)
    ax.axhline(r["support"], color="#0984e3", lw=1)
    ymax = np.nanmax(h[a:b + 1])
    for k, (t, lab, col) in enumerate([(r["tH"], "高点", "#c0392b"), (r["tL"], "低点", "#636e72"), (r["d"], "8%阳线", "#0984e3"),
                                       (r["tP"], "第一波高点", "#e67e22"), (r["t"], "今天", "#00b894")]):
        ax.axvline(t - a, color=col, lw=0.7, ls="--")
        ax.text(t - a + 0.5, ymax * (1.07 - 0.05 * k), lab, color=col, fontsize=8, va="top")
    ax.set_ylim(np.nanmin(l[a:b + 1]) * 0.95, ymax * 1.09)
    ticks = list(range(0, b - a + 1, max((b - a) // 6, 1)))
    axv.set_xticks(ticks, [p["dates"][a + t].strftime("%Y-%m") for t in ticks])
    axv.set_yticks([])
    for s in (ax, axv):
        s.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def page(day, n_checked, rows, out):
    buys = [r for r in rows if r["buy"]]
    live = sorted([r for r in rows if not r["buy"] and not r["broken"]], key=lambda r: (r["missing"].count("；"), r["above"]))
    def card(r, kind):
        return f'''<article class="card"><header><span class="badge {kind}">{"买点" if kind == "buy" else "观察"}</span>
<h3>{r["code"]}</h3></header><p class="why">{"今天符合全部规则" if r["buy"] else "还差：" + r["missing"]}</p>
<img loading="lazy" src="charts/{r["code"]}.png" alt="{r["code"]} 日K线">
<dl><div><dt>跌幅</dt><dd>{r["drop"]*100:.0f}%</dd></div><div><dt>高点前涨停</dt><dd>{r["n_limitup"]} 次</dd></div>
<div><dt>低点</dt><dd>{r["low_date"]}</dd></div><div><dt>8% 阳线</dt><dd>{r["candle_date"]}</dd></div>
<div><dt>收盘价</dt><dd>{r["close_px"]:.2f}</dd></div><div><dt>支撑线</dt><dd>{r["support_px"]:.2f}</dd></div><div><dt>高于支撑线</dt><dd>{r["above"]*100:.1f}%</dd></div>
<div><dt>剩余天数</dt><dd>{r["days_left"]} 日</dd></div></dl></article>'''
    rows_html = "".join(f'<tr><td>{r["code"]}</td><td>{r["above"]*100:+.1f}%</td><td>{r["days_left"]}</td><td>{r["missing"]}</td></tr>' for r in live)
    tpl = (Path(__file__).parent / "template.html").read_text()
    html = (tpl.replace("{{DAY}}", day).replace("{{N}}", f"{n_checked:,}").replace("{{NB}}", str(len(buys)))
            .replace("{{NL}}", str(len(live))).replace("{{NX}}", str(sum(r["broken"] for r in rows)))
            .replace("{{BUYS}}", "".join(card(r, "buy") for r in buys) or '<p class="empty">今天没有股票符合全部规则。</p>')
            .replace("{{WATCH}}", "".join(card(r, "watch") for r in live[:8]) or '<p class="empty">暂无。</p>')
            .replace("{{TABLE}}", rows_html or '<tr><td colspan="4">暂无</td></tr>'))
    (out / "index.html").write_text(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qlib", default="qlib_data")
    ap.add_argument("--out", default="site")
    ap.add_argument("--history", default="history")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    p = load(Path(a.qlib))
    t = len(p["dates"]) - 1
    day = str(p["dates"][t].date())
    traded = np.isfinite(p["close"][t])
    checked = traded & (t - p["first"] >= RULES["min_listed_days"] + 21)
    rows = [r for j in np.flatnonzero(checked) if (r := check(int(j), t, p))]
    live = [r for r in rows if not r["broken"]]
    live.sort(key=lambda r: (not r["buy"], r["missing"].count("；"), r["above"]))
    for r in [r for r in live if r["buy"]] + [r for r in live if not r["buy"]][:8]:
        chart(r, p, out / "charts" / f"{r['code']}.png")
    page(day, int(checked.sum()), rows, out)
    keep = ["code", "buy", "broken", "missing", "high_date", "low_date", "candle_date", "drop", "n_limitup", "support_px", "close_px", "above", "days_left"]
    data = dict(date=day, checked=int(checked.sum()), rules=RULES, results=[{k: r[k] for k in keep} for r in rows])
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    Path(a.history).mkdir(exist_ok=True)
    pd.DataFrame(data["results"], columns=keep).to_csv(Path(a.history) / f"{day}.csv", index=False)
    print(f"{day}: checked {checked.sum()}, setups {len(rows)}, live {len(live)}, buy {sum(r['buy'] for r in rows)}")


if __name__ == "__main__":
    main()
