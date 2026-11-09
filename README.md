# 波浪选股 · daily A-share screen

On each trading day, after the market closes, a GitHub Actions job downloads the latest community A-share
Qlib bundle ([chenditc/investment_data](https://github.com/chenditc/investment_data)), checks
every Shanghai/Shenzhen stock against the rules in `screen.py`, and publishes the result page
via GitHub Pages. Daily results are kept in `history/<date>.csv`.

When it runs: the data bundle comes out at a different time each day (16:18 to 23:59 Singapore time
in late Oct to early Nov 2026). So the job tries at 16:30, 18:30, 20:00, 22:00 and 23:30 SGT on
weekdays, and once more at 06:00 SGT the next morning. A try stops after the download if that
trading day is already in `history/`. GitHub can start a scheduled job late (up to 3 hours was seen).
To refresh now, run the workflow by hand (Actions, daily-screen, Run workflow).

Run locally: `python screen.py --qlib <qlib_data dir> --out site`.

Research only, not investment advice. Backtest 2008–2026: the pattern's average return matched
the market over the same days (no significant excess return).

## Adjustable settings on the page

The page has a "调整参数" panel. Right now a reader can change three numbers in `RULES`: the minimum
drop (`drop`, rule ①, 40–70%), the minimum rise of the rebound candle (`rebound`, rule ③, 5–15%) and
the days after the low to look for that candle (`candle_window`, rule ③, 0–20). The result is calculated again in the browser (`app.js`). All other
rules stay at their defaults. The settings go into the page address, so a link keeps them. The daily
`history/` CSV always uses the default `RULES`.

How it works: `screen.py` writes `cands.json` with the raw measures of every stock that can pass
under some setting inside `ADJUST`. Chart data is in `k/<n>.json` (64 files; the page loads only the
ones it shows). To open more settings later: widen `ADJUST` in `screen.py` and add the setting to
`PARAMS` in `app.js` (the browser check already reads every rule).

Check that the page gives the same result as Python: `python tests/compare.py --qlib <qlib_data dir>`
(needs node).
