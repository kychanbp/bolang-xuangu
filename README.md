# 波浪选股 · daily A-share screen

Every day at 06:00 Singapore time a GitHub Actions job downloads the latest community A-share
Qlib bundle ([chenditc/investment_data](https://github.com/chenditc/investment_data)), checks
every Shanghai/Shenzhen stock against the rules in `screen.py`, and publishes the result page
via GitHub Pages. Daily results are kept in `history/<date>.csv`.

Run locally: `python screen.py --qlib <qlib_data dir> --out site`.

Research only, not investment advice. Backtest 2008–2026: the pattern's average return matched
the market over the same days (no significant excess return).
