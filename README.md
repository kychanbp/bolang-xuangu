# 波浪选股 · daily A-share screen

Every day at 06:00 Singapore time a GitHub Actions job downloads the latest community A-share
Qlib bundle ([chenditc/investment_data](https://github.com/chenditc/investment_data)), checks
every Shanghai/Shenzhen stock against the rules in `screen.py`, and publishes the result page
via GitHub Pages. Daily results are kept in `history/<date>.csv`.

Run locally: `python screen.py --qlib <qlib_data dir> --out site`.

Research only, not investment advice. Backtest 2008–2026: the pattern's average return matched
the market over the same days (no significant excess return).

## Adjustable settings on the page

The page has a "调整参数" panel. Right now a reader can change two numbers in `RULES`: the minimum
drop (`drop`, rule ①, 40–70%) and the days after the low to look for the rebound candle
(`candle_window`, rule ③, 0–20). The result is calculated again in the browser (`app.js`). All other
rules stay at their defaults. The settings go into the page address, so a link keeps them. The daily
`history/` CSV always uses the default `RULES`.

How it works: `screen.py` writes `cands.json` with the raw measures of every stock that can pass
under some setting inside `ADJUST`. Chart data is in `k/<n>.json` (64 files; the page loads only the
ones it shows). To open more settings later: widen `ADJUST` in `screen.py` and add the setting to
`PARAMS` in `app.js` (the browser check already reads every rule).

Check that the page gives the same result as Python: `python tests/compare.py --qlib <qlib_data dir>`
(needs node).
