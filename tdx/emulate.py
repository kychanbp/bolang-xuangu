#!/usr/bin/env python3
"""emulate — evaluate the 通达信 formula 波浪选股.txt (TDX semantics: suspended days have no bar)
on the last bar of every stock, to check it picks the same stocks as screen.py."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import screen  # noqa: E402


def xg(o, h, l, c, v, chg, code, dates):
    n = len(c); t = n - 1
    if n < 82:
        return False
    def ref(x, k): return x[t - k]
    w = h[max(0, t - 250):]; NH = len(w) - 1 - int(np.argmax(w[::-1]))   # most recent max? TDX: nearest
    NH = t - (max(0, t - 250) + int(np.argmax(w)))                        # first occurrence (matches screen.py)
    HH = h[t - NH]
    seg = l[t - NH:]; NL = t - (t - NH + int(np.argmin(seg))); LL = l[t - NL]
    if not (NH > 0 and NL > 0 and NL <= 60 and LL <= HH * 0.45):
        return False
    after = dates >= np.datetime64("2020-08-24")
    zf = np.where(code[2:].startswith("688") | (code[2:].startswith(("300", "301")) & after), 0.2, 0.1) if True else 0
    zt = (np.nan_to_num(chg) >= zf - 0.003) & (c >= h * 0.999)
    tH = t - NH
    if not (zt[max(0, tH - 120):tH + 1].sum() >= 3 and HH >= 2 * l[max(0, tH - 120):tH + 1].min() and n - NH > 61):
        return False
    a8 = np.nan_to_num(chg) >= 0.08
    ND = 0
    for k in range(0, 11):
        if NL >= k and a8[t - (NL - k)]:
            ND = NL - k; break
    if not (ND >= 3 and v[t - ND] >= 1.5 * v[t - ND - 20:t - ND].mean()):
        return False
    ZC = c[t - ND]
    s = c[t - ND + 1:]; hb = len(s) - 1 - int(np.argmax(s))
    return hb >= 2 and abs(c[t] - o[t]) <= o[t] * 0.01 and l[t] >= ZC and c[t] <= ZC * 1.05 and v[t] <= 0.5 * v[t - ND]


if __name__ == "__main__":
    p = screen.load(Path(sys.argv[1]))
    D = p["dates"].values
    hits = []
    for j, code in enumerate(p["codes"]):
        m = np.isfinite(p["close"][:, j])
        if not m[-1]:
            continue
        cols = [p[k][m, j] for k in ("open", "high", "low", "close", "volume", "chg")]
        if xg(*cols, str(code), D[m]):
            hits.append(str(code))
    print("TDX formula picks:", hits)
