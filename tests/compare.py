#!/usr/bin/env python3
"""Check that the page (app.js) gives the same result as screen.py check() for random settings.

python tests/compare.py --qlib <qlib_data dir> [--days 20 --sets 15]
For several past trading days and random settings inside screen.ADJUST, compare every stock's
(buy, broken, number of missing rules) from Python with the result of app.js check() run in node."""
import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import screen  # noqa: E402

NODE = """const {check}=require(process.argv[1]);const D=require(process.argv[2]);const out=[];
for(const q of D.sets){out.push(D.stocks.map(s=>check(s,q,D.bw)).filter(Boolean).map(r=>[r.code,r.buy,r.broken,r.missing?r.missing.split("；").length:0]));}
console.log(JSON.stringify(out));"""


def run_node(f):
    r = subprocess.run(["node", "-e", NODE, str(ROOT / "app.js"), str(f)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("node failed:\n" + r.stderr)
    return json.loads(r.stdout)


def rand_set(rng):
    return dict(screen.RULES, drop=rng.choice([0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]),
                rebound=rng.choice([0.05, 0.06, 0.07, 0.075, 0.08, 0.1, 0.15]),
                candle_window=rng.choice([0, 1, 3, 5, 10, 15, 20]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qlib", default="qlib_data")
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--sets", type=int, default=15)
    a = ap.parse_args()
    p = screen.load(Path(a.qlib))
    rng = random.Random(1)
    T = len(p["dates"]) - 1
    bad = total = 0
    for t in range(T, T - 3 * a.days, -3):
        sets = [dict(screen.RULES)] + [rand_set(rng) for _ in range(a.sets)]
        stocks, _ = screen.export(p, t)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            f.write_text(json.dumps(dict(stocks=stocks, sets=sets, bw=screen.ADJUST["bull_windows"])))
            js = run_node(f)
        checked = np.flatnonzero(np.isfinite(p["close"][t]) & (t - p["first"] >= screen.RULES["min_listed_days"] + 21))
        for q, got in zip(sets, js):
            py = []
            for j in checked:
                r = screen.check(int(j), t, p, q)
                if r:
                    py.append([r["code"], r["buy"], r["broken"], r["missing"].count("；") + 1 if r["missing"] else 0])
            A, B = {tuple(x) for x in py}, {tuple(x) for x in got}
            total += 1
            if A != B:
                bad += 1
                print(p["dates"][t].date(), {k: q[k] for k in q if q[k] != screen.RULES.get(k)},
                      "python only:", sorted(A - B)[:5], "page only:", sorted(B - A)[:5])
        print(p["dates"][t].date(), "done", flush=True)
    print(f"{total - bad} of {total} (day, setting) pairs match exactly")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
