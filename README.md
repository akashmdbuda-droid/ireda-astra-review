# IREDA.NS — Astra Review Handoff Folder (`astra_handoff_20261115`)

> **Target Instrument:** `IREDA.NS` (`NSE: IREDA`, Dhan `securityId: 20261`, ISIN: `INE202E01016`)  
> **Latest Captured Market Session:** `2026-11-13 15:46 IST` (`CLOSED (post_close)`)  
> **Packaged On:** `2026-11-15 IST`  
> **Sanitization:** Read-only & market-only (`portfolio.json` / broker holdings and Dhan API credentials excluded). Prior submission bundle [`reports/review_ireda_20261113/`](../review_ireda_20261113/) left untouched.

---

## Folder Contents

| File / Folder | Purpose |
| :--- | :--- |
| [`report.md`](report.md) | Supervised multi-timeframe neutral Markdown report (`run_id: a073c6e6feaf49fb934bed0cba11b02b`, `status: diagnostic_only`, `market_hash: 05448813c989b6e736c64233bb3be06af13abc953aabe49d399c3479f0d0ce46`) |
| [`dashboard_snapshot.json`](dashboard_snapshot.json) | Single-run `/api/state` dashboard snapshot (sanitized: zero personal holdings) |
| [`mtf_chart.png`](mtf_chart.png) | 6-panel Monthly / Weekly / Daily / 60m / 15m chart bound to the market packet |
| [`chart.png`](chart.png) | Primary daily candlestick + MA + FVG chart bound to the market packet |
| [`live_quote.json`](live_quote.json) | Post-close Dhan `/v2/marketfeed/quote` snapshot (`₹118.30`, `2026-11-13T15:28:04+05:30`) |
| [`sessions.json`](sessions.json) | Observed NSE session calendar (`nse-holiday-lists-web-2023-2026`) |
| [`neutral_out/`](neutral_out/) | Full frozen neutral pipeline directory (`current.json`, `runs/a073c6e6feaf49fb934bed0cba11b02b/report.json`, `evidence/`, `evidence_mtf/`) |
| [`research_out/`](research_out/) | Walk-forward `forecast_ledger.jsonl` (`1D`, `5D`, `20D` horizons) + `research_performance.json` (`Strategy -17.28%` vs `Hold -29.96%`, `Benchmark +16.83%`, `Simple Rule +53.77%`) |
| [`monitor_replay_out/`](monitor_replay_out/) | 2-cycle monitoring replay (`alerts_log.json`, `monitor_state.json`, `current.json`) |

## Key Provenance & Status Disclosures

- **`run_status: diagnostic_only` / `evidence_status: insufficient_data`:** Scenarios stay `ABSTAINED / FAIL-CLOSED` because historical Dhan-vs-Yahoo reconciliation flagged `17` issues (`1` unadjusted dividend, `9` historical OHLC price differences on `2024-01-15`/`2025-03-18`/`2025-05-02`, `6` session mismatches, and `missing_completed_interval` on `2026-11-13 15:15`).
- **EOD Daily vs Provisional Candle:** Dhan `/v2/charts/historical` ends at `2026-11-12` (`₹119.85`), while Dhan `/v2/charts/intraday` stops at `15:00` (`₹118.30`). Live quote & provisional Daily bar reflect `₹118.30`.
- **Forecast Calibration (`insufficient_sample`):** Sample sizes (`n=15` for `1D`, `n=12` for `5D`, `n=11` for `20D`) are below `DEFAULT_MIN_CALIBRATION_SAMPLES = 30`, so calibrated probabilities remain `probability unavailable`.

---

## Automated Daily Macro Cockpit (`cockpit.html`)

Alongside the frozen Astra review bundle above, this repository also serves a live, automated 1-screen **Daily Macro Cockpit** on GitHub Pages at [`./cockpit.html`](cockpit.html) (strictly read-only & market-only — zero personal holdings or broker credentials are stored in the repository; the optional P&L calculator saves inputs only in browser `localStorage`).

| File | Purpose |
| :--- | :--- |
| [`cockpit.html`](cockpit.html) | Simplified 1-screen dashboard: 3-second action signal (`HOLD & RIDE` / `ALERT` / `EXIT`), 5 macro traffic lights (`Brent`, `India 10Y Bond ETF`, `USD/INR`, `India VIX`, `Global Risk`), expandable Daily/Weekly trendline chart drawer, IREDA price ladder, 1Y **Master Synchronized Timeline** (Stacked Tracks + Pair Overlay with fixed red ceilings & click-to-pin crosshair), and auto-graded prediction scorecard |
| [`scripts/daily_update.py`](scripts/daily_update.py) | Zero-dependency Python 3 updater that fetches Yahoo Finance Daily/Weekly OHLCV for 10 assets, computes EMAs/RSI/ATR & structural trendlines, evaluates the 5 lights, auto-grades pending predictions, and writes `cockpit_state.json` |
| [`cockpit_state.json`](cockpit_state.json) | Auto-updated market snapshot & chart payload consumed by `cockpit.html` |
| [`daily_ledger.jsonl`](daily_ledger.jsonl) | Falsifiable prediction-vs-reality ledger automatically graded (`HIT` / `MISS` / `EXPIRED`) on subsequent daily bars |
| [`daily_history.jsonl`](daily_history.jsonl) | Append-only daily log of IREDA close, RSI, Macro Score, Red Lights, and Action Signal |
| [`.github/workflows/daily_cockpit.yml`](.github/workflows/daily_cockpit.yml) | Scheduled GitHub Actions runner: **08:15 AM IST** (Mon–Fri pre-market), **04:15 PM IST** (Mon–Fri post-NSE close & grading), **06:00 PM IST** (Sunday weekly reset), plus manual `workflow_dispatch` |

