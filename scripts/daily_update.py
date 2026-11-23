#!/usr/bin/env python3
"""Daily market updater & auto-grading prediction ledger for IREDA Daily Cockpit.

Zero external dependencies (Python 3 standard library only).
Sanitized & market-only: never stores personal holdings, quantities, or credentials.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "cockpit_state.json"
LEDGER_FILE = REPO_ROOT / "daily_ledger.jsonl"
HISTORY_FILE = REPO_ROOT / "daily_history.jsonl"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

TICKERS: dict[str, dict[str, Any]] = {
    "IREDA": {"symbol": "IREDA.NS", "name": "IREDA.NS", "unit": "₹", "dec": 2, "clean": None},
    "BRENT": {"symbol": "BZ=F", "name": "Brent Crude", "unit": "$", "dec": 2, "clean": None},
    "GOLD": {"symbol": "GC=F", "name": "COMEX Gold", "unit": "$", "dec": 1, "clean": None},
    "US10Y": {"symbol": "^TNX", "name": "US 10Y Yield", "unit": "%", "dec": 3, "clean": 0.15},
    "IN10Y_ETF": {"symbol": "LTGILTBEES.NS", "name": "India 10Y Bond ETF", "unit": "₹", "dec": 2, "clean": 0.015},
    "DXY": {"symbol": "DX-Y.NYB", "name": "DXY Dollar Index", "unit": "", "dec": 2, "clean": None},
    "USDINR": {"symbol": "USDINR=X", "name": "USD / INR", "unit": "₹", "dec": 2, "clean": 0.032},
    "NIFTY": {"symbol": "^NSEI", "name": "Nifty 50", "unit": "", "dec": 1, "clean": None},
    "NDX": {"symbol": "^NDX", "name": "Nasdaq 100", "unit": "", "dec": 1, "clean": None},
    "INDIAVIX": {"symbol": "^INDIAVIX", "name": "India VIX", "unit": "", "dec": 2, "clean": None},
}

# Validated pivot-to-pivot structural trendlines (date1, date2, kind, label, color)
CURATED_TRENDLINES: dict[str, dict[str, list[dict[str, str]]]] = {
    "IREDA": {
        "1d": [
            {"d1": "2026-04-22", "d2": "2026-09-28", "kind": "res", "label": "6M Channel Top", "color": "#f43f5e"},
            {"d1": "2026-03-30", "d2": "2026-10-26", "kind": "sup", "label": "2026 Floor", "color": "#06b6d4"},
            {"d1": "2026-10-26", "d2": "2026-11-17", "kind": "sup", "label": "Nov Rally TL", "color": "#22c55e"},
        ],
        "1wk": [
            {"d1": "2026-01-04", "d2": "2026-04-19", "kind": "res", "label": "Outer 2026 Res", "color": "#f43f5e"},
            {"d1": "2025-06-08", "d2": "2026-04-19", "kind": "res", "label": "18M Wedge Top", "color": "#f97316"},
            {"d1": "2025-03-16", "d2": "2026-10-25", "kind": "sup", "label": "18M Wedge Floor", "color": "#06b6d4"},
        ],
    },
    "BRENT": {
        "1d": [
            {"d1": "2026-04-30", "d2": "2026-10-30", "kind": "res", "label": "War Peak Cap", "color": "#f43f5e"},
            {"d1": "2026-07-02", "d2": "2026-11-10", "kind": "sup", "label": "Rising Neckline", "color": "#f97316"},
            {"d1": "2026-09-22", "d2": "2026-11-10", "kind": "sup", "label": "Lower Channel", "color": "#06b6d4"},
        ],
        "1wk": [
            {"d1": "2026-04-27", "d2": "2026-10-26", "kind": "res", "label": "LH Double Top", "color": "#f43f5e"},
            {"d1": "2025-12-15", "d2": "2026-06-29", "kind": "sup", "label": "2026 Uptrend", "color": "#22c55e"},
        ],
    },
    "IN10Y_ETF": {
        "1d": [
            {"d1": "2026-07-02", "d2": "2026-11-16", "kind": "res", "label": "4M Bond Res", "color": "#f43f5e"},
            {"d1": "2026-09-08", "d2": "2026-11-05", "kind": "res", "label": "Sep Down TL", "color": "#f97316"},
        ],
        "1wk": [
            {"d1": "2025-12-07", "d2": "2026-09-06", "kind": "res", "label": "Bond Ceiling", "color": "#f43f5e"},
            {"d1": "2024-12-29", "d2": "2026-03-22", "kind": "sup", "label": "2Y Bond Uptrend", "color": "#22c55e"},
        ],
    },
    "USDINR": {
        "1d": [
            {"d1": "2026-05-18", "d2": "2026-10-07", "kind": "res", "label": "Triple Top Cap", "color": "#f43f5e"},
            {"d1": "2026-05-12", "d2": "2026-08-25", "kind": "sup", "label": "Broken Neckline", "color": "#f97316"},
        ],
        "1wk": [
            {"d1": "2026-05-17", "d2": "2026-10-04", "kind": "res", "label": "Triple Top Cap", "color": "#f43f5e"},
            {"d1": "2025-07-13", "d2": "2026-03-09", "kind": "sup", "label": "Weekly Rising Sup", "color": "#22c55e"},
        ],
    },
    "INDIAVIX": {
        "1d": [
            {"d1": "2026-04-24", "d2": "2026-10-26", "kind": "res", "label": "7M Descending Lid", "color": "#f43f5e"},
            {"d1": "2026-09-01", "d2": "2026-11-09", "kind": "res", "label": "Rising Vol Top", "color": "#f97316"},
            {"d1": "2026-02-19", "d2": "2026-09-23", "kind": "sup", "label": "2026 Vol Floor", "color": "#22c55e"},
        ],
        "1wk": [
            {"d1": "2026-07-12", "d2": "2026-11-01", "kind": "sup", "label": "Rising Vol Base", "color": "#f97316"},
        ],
    },
    "US10Y": {
        "1d": [
            {"d1": "2026-10-07", "d2": "2026-11-13", "kind": "res", "label": "Lower-High Cap", "color": "#f43f5e"},
            {"d1": "2026-07-17", "d2": "2026-11-06", "kind": "sup", "label": "4M Rising Sup", "color": "#22c55e"},
            {"d1": "2026-04-08", "d2": "2026-06-25", "kind": "sup", "label": "Outer Support", "color": "#06b6d4"},
        ],
        "1wk": [
            {"d1": "2025-04-07", "d2": "2026-10-05", "kind": "res", "label": "Weekly Ceiling", "color": "#f43f5e"},
            {"d1": "2026-02-23", "d2": "2026-06-22", "kind": "sup", "label": "2026 Weekly Sup", "color": "#22c55e"},
        ],
    },
    "GOLD": {
        "1d": [
            {"d1": "2026-01-29", "d2": "2026-08-25", "kind": "res", "label": "Primary Bear TL", "color": "#f43f5e"},
            {"d1": "2026-08-25", "d2": "2026-11-09", "kind": "res", "label": "Steep Bear TL", "color": "#f97316"},
            {"d1": "2026-03-23", "d2": "2026-10-30", "kind": "sup", "label": "Triangle Floor", "color": "#06b6d4"},
        ],
        "1wk": [
            {"d1": "2026-01-26", "d2": "2026-08-24", "kind": "res", "label": "2026 Bear TL", "color": "#f43f5e"},
            {"d1": "2026-03-23", "d2": "2026-06-29", "kind": "sup", "label": "Bear Channel", "color": "#06b6d4"},
        ],
    },
    "NDX": {
        "1d": [
            {"d1": "2026-08-05", "d2": "2026-10-06", "kind": "res", "label": "Broadening Top", "color": "#f43f5e"},
            {"d1": "2026-05-19", "d2": "2026-11-05", "kind": "sup", "label": "Broken Mid Sup", "color": "#f97316"},
            {"d1": "2026-05-19", "d2": "2026-07-29", "kind": "sup", "label": "Lower Channel Floor", "color": "#22c55e"},
        ],
        "1wk": [
            {"d1": "2025-04-07", "d2": "2026-03-30", "kind": "sup", "label": "AI Bull TL (Broken)", "color": "#f97316"},
        ],
    },
    "DXY": {
        "1d": [
            {"d1": "2026-08-13", "d2": "2026-10-14", "kind": "res", "label": "Steep Upper Lid", "color": "#f43f5e"},
            {"d1": "2026-01-15", "d2": "2026-10-05", "kind": "res", "label": "Channel Top", "color": "#f97316"},
            {"d1": "2026-08-21", "d2": "2026-11-04", "kind": "sup", "label": "Steep Rally Sup", "color": "#22c55e"},
        ],
        "1wk": [
            {"d1": "2026-01-26", "d2": "2026-08-17", "kind": "sup", "label": "2026 Rising Floor", "color": "#22c55e"},
        ],
    },
    "NIFTY": {
        "1d": [
            {"d1": "2026-05-26", "d2": "2026-08-03", "kind": "res", "label": "10-Touch Asc Res", "color": "#f43f5e"},
            {"d1": "2026-01-05", "d2": "2026-08-03", "kind": "res", "label": "Broken Bear TL", "color": "#f97316"},
            {"d1": "2026-03-30", "d2": "2026-10-08", "kind": "sup", "label": "Double Bottom Base", "color": "#22c55e"},
        ],
        "1wk": [
            {"d1": "2024-09-22", "d2": "2026-01-04", "kind": "res", "label": "ATH Lid", "color": "#f43f5e"},
            {"d1": "2024-03-17", "d2": "2026-10-04", "kind": "sup", "label": "Multi-Year Floor", "color": "#22c55e"},
        ],
    },
}

DEFAULT_SEED_PREDICTIONS: list[dict[str, Any]] = [
    {
        "id": "seed_ireda_hold_20261122",
        "kind": "macro_swing",
        "asset": "IREDA",
        "logged_date": "2026-11-20",
        "due_date": "2026-12-18",
        "prediction": "IREDA defends ₹119.50 breakout floor and tests ₹142+ (Apr peak)",
        "rule_text": "HIT if High ≥ ₹142.00 · MISS if Close < ₹119.50",
        "hit_field": "h", "hit_op": "ge", "hit_val": 142.0,
        "miss_field": "c", "miss_op": "lt", "miss_val": 119.5,
        "status": "PENDING",
        "resolved_date": None, "resolved_price": None, "outcome_note": "",
    },
    {
        "id": "seed_ireda_throwback_20261122",
        "kind": "short_term",
        "asset": "IREDA",
        "logged_date": "2026-11-20",
        "due_date": "2026-12-04",
        "prediction": "Overbought RSI (77.3) cools via throwback ≤ ₹127 before closing > ₹140",
        "rule_text": "HIT if Low ≤ ₹127.00 · MISS if Close > ₹140.00 first",
        "hit_field": "l", "hit_op": "le", "hit_val": 127.0,
        "miss_field": "c", "miss_op": "gt", "miss_val": 140.0,
        "status": "PENDING",
        "resolved_date": None, "resolved_price": None, "outcome_note": "",
    },
    {
        "id": "seed_brent_sub93_20261122",
        "kind": "macro_lead",
        "asset": "BRENT",
        "logged_date": "2026-11-20",
        "due_date": "2026-12-04",
        "prediction": "Brent holds broken neckline (< $95) and tests $85.5–$87.5 support",
        "rule_text": "HIT if Low ≤ $87.50 · MISS if Close > $95.00",
        "hit_field": "l", "hit_op": "le", "hit_val": 87.5,
        "miss_field": "c", "miss_op": "gt", "miss_val": 95.0,
        "status": "PENDING",
        "resolved_date": None, "resolved_price": None, "outcome_note": "",
    },
    {
        "id": "seed_gold_shelf_20261122",
        "kind": "macro_lead",
        "asset": "GOLD",
        "logged_date": "2026-11-20",
        "due_date": "2026-12-04",
        "prediction": "Gold holds 2025 shelf (> $3,400) and bounces ≥ $3,650 (no liquidity crunch)",
        "rule_text": "HIT if Close ≥ $3,650 · MISS if Close < $3,400",
        "hit_field": "c", "hit_op": "ge", "hit_val": 3650.0,
        "miss_field": "c", "miss_op": "lt", "miss_val": 3400.0,
        "status": "PENDING",
        "resolved_date": None, "resolved_price": None, "outcome_note": "",
    },
]

CATALYSTS = [
    {"date": "2026-11-23", "title": "NSE Monthly F&O Expiry", "note": "Tue Nov 24 is Guru Nanak Jayanti holiday; expect expiry chop."},
    {"date": "2026-11-29", "title": "OPEC+ Monthly Meeting", "note": "Decides Jan 2027 quotas; watch Brent $95 Red Line vs $85.5 target."},
    {"date": "2026-11-30", "title": "IREDA Monthly Close", "note": "Confirms monthly close above 12-EMA (~₹125.9) snapping 6M losing streak."},
    {"date": "2026-12-04", "title": "RBI MPC Rate Decision", "note": "+25 bps to 5.75% priced; watch LTGILTBEES ₹30.02 lid vs ₹29.40 Red Line."},
    {"date": "2026-12-09", "title": "US FOMC + 2027 Dot Plot", "note": "Hits NSE Dec 10 open; US 10Y apex (4.85% vs 5.14%) resolves here."},
    {"date": "2027-01-08", "title": "IREDA Q3 FY27 Earnings (Est.)", "note": "Must prove 15%+ loan growth converts into YoY PAT growth as provisions ease."},
]


def fetch_yahoo(symbol: str, rng: str, interval: str, retries: int = 3) -> list[dict[str, Any]]:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        f"?range={rng}&interval={interval}&includePrePost=false"
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            res = payload["chart"]["result"][0]
            ts = res.get("timestamp") or []
            q = res["indicators"]["quote"][0]
            bars: list[dict[str, Any]] = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                v = (q.get("volume") or [0] * len(ts))[i]
                if None in (o, h, l, c):
                    continue
                d_str = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
                bars.append({"d": d_str, "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": int(v or 0)})
            if not bars:
                raise ValueError(f"Empty bars for {symbol} {interval}")
            return bars
        except Exception as exc:
            last_err = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Failed fetching {symbol} ({interval}): {last_err}")


def clean_bars(key: str, tf: str, bars: list[dict[str, Any]], dec: int, tol: float | None) -> list[dict[str, Any]]:
    out = [dict(b) for b in bars]
    # Drop zero-range weekend stub bar on FX feeds (e.g. USDINR Sunday placeholder)
    if key == "USDINR" and tf == "1d" and len(out) >= 2:
        last_d = dt.date.fromisoformat(out[-1]["d"])
        if last_d.weekday() >= 5 and abs(out[-1]["h"] - out[-1]["l"]) < 1e-6:
            out.pop()
    # Drop corrupt duplicate-week stub bar (e.g. Yahoo Friday stub with h <= 0)
    if tf == "1wk" and len(out) >= 2 and out[-1]["h"] <= 0:
        out.pop()
    # Deduplicate identical dates keeping latest
    dedup: dict[str, dict[str, Any]] = {}
    for b in out:
        dedup[b["d"]] = b
    out = [dedup[k] for k in sorted(dedup.keys())]

    for i, b in enumerate(out):
        prev_c = out[i - 1]["c"] if i > 0 else b["c"]
        if tol is not None and prev_c > 0:
            if b["o"] <= 0 or abs(b["o"] - prev_c) / prev_c > tol:
                b["o"] = prev_c
            bhi, blo = max(b["o"], b["c"]), min(b["o"], b["c"])
            if b["l"] <= 0 or b["l"] < blo * (1 - tol):
                b["l"] = blo * (1 - tol * 0.25)
            if b["h"] > bhi * (1 + tol):
                b["h"] = bhi * (1 + tol * 0.25)
        bhi, blo = max(b["o"], b["c"]), min(b["o"], b["c"])
        if b["h"] < bhi:
            b["h"] = bhi
        if b["l"] > blo or b["l"] <= 0:
            b["l"] = blo
        b["o"] = round(b["o"], dec)
        b["h"] = round(b["h"], dec)
        b["l"] = round(b["l"], dec)
        b["c"] = round(b["c"], dec)
    return out


def compute_ema(vals: list[float], period: int, dec: int) -> list[float | None]:
    if len(vals) < period:
        return [None] * len(vals)
    k = 2.0 / (period + 1)
    out: list[float | None] = [None] * (period - 1)
    cur = sum(vals[:period]) / period
    out.append(round(cur, dec))
    for v in vals[period:]:
        cur = v * k + cur * (1.0 - k)
        out.append(round(cur, dec))
    return out


def compute_rsi(vals: list[float], period: int = 14) -> list[float | None]:
    if len(vals) <= period:
        return [None] * len(vals)
    gains = [max(vals[i] - vals[i - 1], 0.0) for i in range(1, len(vals))]
    losses = [max(vals[i - 1] - vals[i], 0.0) for i in range(1, len(vals))]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    out: list[float | None] = [None] * period + [round(100.0 - 100.0 / (1.0 + (ag / al if al > 0 else 1e9)), 1)]
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        out.append(round(100.0 - 100.0 / (1.0 + (ag / al if al > 0 else 1e9)), 1))
    return out


def compute_atr(bars: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(bars) <= period:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return round(atr, 2)


def project_trendlines(key: str, tf: str, full_bars: list[dict[str, Any]], window_len: int, dec: int) -> list[dict[str, Any]]:
    defs = CURATED_TRENDLINES.get(key, {}).get(tf, [])
    date_map = {b["d"]: i for i, b in enumerate(full_bars)}
    n_full = len(full_bars)
    offset = max(0, n_full - window_len)
    out = []
    for tl in defs:
        d1, d2 = tl["d1"], tl["d2"]
        if d1 not in date_map or d2 not in date_map:
            continue
        i1_full, i2_full = date_map[d1], date_map[d2]
        if i2_full <= i1_full:
            continue
        y1 = full_bars[i1_full]["h"] if tl["kind"] == "res" else full_bars[i1_full]["l"]
        y2 = full_bars[i2_full]["h"] if tl["kind"] == "res" else full_bars[i2_full]["l"]
        slope = (y2 - y1) / (i2_full - i1_full)
        now_y = round(y1 + slope * (n_full - 1 - i1_full), dec)
        p10_y = round(y1 + slope * (n_full - 1 + 10 - i1_full), dec)
        out.append({
            "i1": i1_full - offset, "d1": d1, "y1": round(y1, dec),
            "i2": i2_full - offset, "d2": d2, "y2": round(y2, dec),
            "kind": tl["kind"], "label": tl["label"], "color": tl["color"],
            "now": now_y, "p10": p10_y,
        })
    return out


def eval_five_lights(snap: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    brent = snap["BRENT"]["last"]
    in10 = snap["IN10Y_ETF"]["last"]
    usdinr = snap["USDINR"]["last"]
    vix = snap["INDIAVIX"]["last"]
    us10 = snap["US10Y"]["last"]
    gold = snap["GOLD"]["last"]
    dxy = snap["DXY"]["last"]
    ndx = snap["NDX"]["last"]

    # 1. Brent Crude (#1 macro driver, r = -0.45 IREDA / -0.63 Nifty)
    if brent < 92.5:
        b_st, b_note = "GREEN", "Below 200 EMA ($92.5) — tailwind for India & IREDA"
    elif brent <= 95.0:
        b_st, b_note = "AMBER", "Testing $92.5–$95 resistance zone — watch closely"
    else:
        b_st, b_note = "RED", "Above $95 — inflation / RBI hike / FII outflow risk"

    # 2. India 10Y Bond ETF (LTGILTBEES — inverse of India 10Y yield, r = +0.40 IREDA)
    if in10 >= 30.0:
        i_st, i_note = "GREEN", "Bond breakout ≥ ₹30.00 (yields easing — bullish NBFCs)"
    elif in10 >= 29.40:
        i_st, i_note = "AMBER", "Pressing ₹30.02 lid ahead of RBI MPC — hold > ₹29.40"
    else:
        i_st, i_note = "RED", "Below ₹29.40 200-EMA floor (India 10Y spiking > 7.40%)"

    # 3. USD / INR (#3 lead, r = -0.35 IREDA / -0.49 Nifty)
    if usdinr < 93.50:
        fx_st, fx_note = "GREEN", "Below 93.50 broken neckline — supports FII inflows"
    elif usdinr <= 94.50:
        fx_st, fx_note = "AMBER", "Re-testing 93.5–94.5 resistance — watch FII flow"
    else:
        fx_st, fx_note = "RED", "Above 94.50 — rupee weakness erodes FII returns"

    # 4. India VIX (Volatility / Institutional Hedging Alarm)
    if vix < 15.50:
        v_st, v_note = "GREEN", "Calm volatility regime (< 15.5) — smooth trend"
    elif vix <= 18.44:
        v_st, v_note = "AMBER", "Elevated hedging near 18.44 resistance lid"
    else:
        v_st, v_note = "RED", "Broke > 18.44 — active panic / sharp pullback risk"

    # 5. Global Liquidity & AI Contagion Composite (US10Y + Gold + DXY + NDX)
    phase2_crash = (ndx < 24800 and (gold < 3400 or dxy > 105.0))
    yield_shock = (us10 > 5.15 and dxy > 105.0)
    if phase2_crash or yield_shock:
        g_st = "RED"
        g_note = "Phase-2 global liquidity / AI contagion triggered!"
    elif us10 < 4.85 and gold >= 3475 and dxy < 103.5 and ndx >= 24800:
        g_st = "GREEN"
        g_note = "US yields easing, Gold holding shelf, DXY cooling"
    else:
        g_st = "AMBER"
        g_note = f"US10Y {us10:.2f}% · DXY {dxy:.1f} · Gold ${gold:.0f} · NDX {ndx:.0f}"

    lights = [
        {
            "id": "BRENT", "title": "1. Brent Crude", "value": f"${brent:.2f}",
            "chg_pct": snap["BRENT"]["chg_pct"], "status": b_st, "corr": "r = -0.45 IREDA",
            "note": b_note, "red_rule": "RED if > $95.00", "green_rule": "GREEN if < $92.50",
            "stale": snap["BRENT"].get("stale", False),
        },
        {
            "id": "IN10Y_ETF", "title": "2. India 10Y Bond", "value": f"₹{in10:.2f}",
            "chg_pct": snap["IN10Y_ETF"]["chg_pct"], "status": i_st, "corr": "r = +0.40 IREDA",
            "note": i_note, "red_rule": "RED if < ₹29.40", "green_rule": "GREEN if ≥ ₹30.00",
            "stale": snap["IN10Y_ETF"].get("stale", False),
        },
        {
            "id": "USDINR", "title": "3. USD / INR", "value": f"₹{usdinr:.2f}",
            "chg_pct": snap["USDINR"]["chg_pct"], "status": fx_st, "corr": "r = -0.35 IREDA",
            "note": fx_note, "red_rule": "RED if > ₹94.50", "green_rule": "GREEN if < ₹93.50",
            "stale": snap["USDINR"].get("stale", False),
        },
        {
            "id": "INDIAVIX", "title": "4. India VIX", "value": f"{vix:.2f}",
            "chg_pct": snap["INDIAVIX"]["chg_pct"], "status": v_st, "corr": "r = -0.39 IREDA",
            "note": v_note, "red_rule": "RED if > 18.44", "green_rule": "GREEN if < 15.50",
            "stale": snap["INDIAVIX"].get("stale", False),
        },
        {
            "id": "US10Y", "title": "5. Global Risk", "value": f"{us10:.2f}% / ${gold:.0f}",
            "chg_pct": snap["NDX"]["chg_pct"], "chg_prefix": "NDX ", "status": g_st, "corr": "US10Y / Gold / NDX",
            "note": g_note, "red_rule": "RED: NDX<24.8k + Gold<$3.4k/DXY>105", "green_rule": "GREEN: 10Y<4.85% + Gold≥$3475",
            "stale": any(snap[k].get("stale", False) for k in ("US10Y", "GOLD", "DXY", "NDX")),
        },
    ]

    score = sum(2 if x["status"] == "GREEN" else (1 if x["status"] == "AMBER" else 0) for x in lights)
    reds = sum(1 for x in lights if x["status"] == "RED")
    return lights, score, reds


def compute_action_signal(ireda: dict[str, Any], score: int, reds: int) -> dict[str, str]:
    px = ireda["last"]
    rsi = ireda.get("rsi") or 50.0
    if reds >= 3 or px < 119.50:
        return {
            "code": "EXIT_PROTECT",
            "label": "EXIT · PROTECT PROFIT",
            "tone": "error",
            "summary": (
                f"Danger triggered ({reds}/5 Red Lights; IREDA ₹{px:.2f}). "
                "Global macro or the ₹119.50 breakout floor broke — step out to protect profits."
            ),
        }
    if reds == 2 or px < 121.00:
        return {
            "code": "ALERT_PROTECT",
            "label": "ALERT · ARM TRAILING EXIT",
            "tone": "warning",
            "summary": (
                f"Caution ({reds}/5 Red Lights; IREDA ₹{px:.2f}). "
                "Macro stress is building — arm a strict closing stop below ₹119.50–₹121.00 and watch tomorrow's close."
            ),
        }
    stretch_note = (
        f" Short-term D-RSI is elevated ({rsi:.1f}); normal pullbacks into ₹121–₹127 are healthy inside the weekly breakout."
        if rsi >= 72
        else " Trend structure & macro lights are aligned to let winners run."
    )
    return {
        "code": "HOLD_AND_RIDE",
        "label": "HOLD & RIDE TREND",
        "tone": "success",
        "summary": (
            f"All clear ({reds}/5 Red Lights, Macro Score {score}/10; IREDA ₹{px:.2f} above 200 EMA ₹{ireda['e200']:.2f})."
            + stretch_note
        ),
    }


def _cmp(val: float, op: str, thr: float) -> bool:
    if op == "ge":
        return val >= thr
    if op == "gt":
        return val > thr
    if op == "le":
        return val <= thr
    if op == "lt":
        return val < thr
    return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + ("\n" if rows else "")
    path.write_text(text, encoding="utf-8")


NSE_ASSETS = {"IREDA", "IN10Y_ETF", "NIFTY", "INDIAVIX"}


def is_bar_closed(asset: str, bar_date: str, now_ist: dt.datetime) -> bool:
    """Return True if the daily bar for `asset` on `bar_date` is an official completed close."""
    if asset in NSE_ASSETS:
        today_ist = now_ist.date().isoformat()
        if bar_date < today_ist:
            return True
        if bar_date == today_ist and (now_ist.hour, now_ist.minute) >= (15, 40):
            return True
        return False
    now_utc = now_ist.astimezone(dt.timezone.utc)
    today_utc = now_utc.date().isoformat()
    if bar_date < today_utc:
        return True
    if bar_date == today_utc and now_utc.hour >= 22:
        return True
    return False


def update_and_grade_ledger(
    daily_bars: dict[str, list[dict[str, Any]]],
    signal: dict[str, str],
    ireda_snap: dict[str, Any],
    now_ist: dt.datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_jsonl(LEDGER_FILE)
    if not rows:
        rows = [dict(r) for r in DEFAULT_SEED_PREDICTIONS]

    for pred in rows:
        if pred.get("status") != "PENDING":
            continue
        bars = daily_bars.get(pred["asset"]) or []
        if not bars:
            continue
        logged = pred["logged_date"]
        due = pred["due_date"]
        post_bars = [b for b in bars if b["d"] > logged and b["d"] <= due]
        resolved = False
        for b in post_bars:
            closed = is_bar_closed(pred["asset"], b["d"], now_ist)
            hit_val = b[pred["hit_field"]]
            miss_val = b[pred["miss_field"]]
            hit_ok = (
                False
                if (pred["hit_field"] == "c" and not closed)
                else _cmp(hit_val, pred["hit_op"], float(pred["hit_val"]))
            )
            miss_ok = (
                False
                if (pred["miss_field"] == "c" and not closed)
                else _cmp(miss_val, pred["miss_op"], float(pred["miss_val"]))
            )
            if miss_ok and not hit_ok:
                pred["status"] = "MISS"
                pred["resolved_date"] = b["d"]
                pred["resolved_price"] = miss_val
                pred["outcome_note"] = f"Invalidated on {b['d']} at {miss_val}"
                resolved = True
                break
            if hit_ok:
                pred["status"] = "HIT"
                pred["resolved_date"] = b["d"]
                pred["resolved_price"] = hit_val
                pred["outcome_note"] = f"Target reached on {b['d']} at {hit_val}"
                resolved = True
                break
        closed_bars = [b for b in bars if is_bar_closed(pred["asset"], b["d"], now_ist)]
        if not resolved and closed_bars and closed_bars[-1]["d"] > due:
            pred["status"] = "EXPIRED"
            pred["resolved_date"] = closed_bars[-1]["d"]
            pred["resolved_price"] = closed_bars[-1]["c"]
            pred["outcome_note"] = f"Window ended ({due}); close {closed_bars[-1]['c']}"

    # Auto-roll a fresh 14-calendar-day (~10 session) IREDA regime call whenever no IREDA swing/regime call is pending
    has_ireda_regime_pending = any(
        r.get("asset") == "IREDA" and r.get("kind") in ("auto_regime", "macro_swing") and r.get("status") == "PENDING"
        for r in rows
    )
    ireda_bars = daily_bars.get("IREDA") or []
    if not has_ireda_regime_pending and ireda_bars:
        last_d = ireda_bars[-1]["d"]
        last_c = ireda_bars[-1]["c"]
        due_d = (dt.date.fromisoformat(last_d) + dt.timedelta(days=14)).isoformat()
        if signal["code"] == "EXIT_PROTECT":
            tgt = round(last_c * 0.94, 2)
            inv = round(last_c * 1.05, 2)
            rows.insert(0, {
                "id": f"auto_ireda_{last_d.replace('-', '')}",
                "kind": "auto_regime",
                "asset": "IREDA",
                "logged_date": last_d,
                "due_date": due_d,
                "prediction": f"EXIT regime: IREDA tests lower support ≤ ₹{tgt:.2f} within 14d",
                "rule_text": f"HIT if Low ≤ ₹{tgt:.2f} · MISS if Close ≥ ₹{inv:.2f}",
                "hit_field": "l", "hit_op": "le", "hit_val": tgt,
                "miss_field": "c", "miss_op": "ge", "miss_val": inv,
                "status": "PENDING",
                "resolved_date": None, "resolved_price": None, "outcome_note": "",
            })
        else:
            tgt = round(last_c * 1.06, 2)
            inv = round(min(119.50, last_c * 0.92), 2)
            rows.insert(0, {
                "id": f"auto_ireda_{last_d.replace('-', '')}",
                "kind": "auto_regime",
                "asset": "IREDA",
                "logged_date": last_d,
                "due_date": due_d,
                "prediction": f"{signal['label']}: IREDA stays > ₹{inv:.2f} and reaches ₹{tgt:.2f}+",
                "rule_text": f"HIT if High ≥ ₹{tgt:.2f} · MISS if Close < ₹{inv:.2f}",
                "hit_field": "h", "hit_op": "ge", "hit_val": tgt,
                "miss_field": "c", "miss_op": "lt", "miss_val": inv,
                "status": "PENDING",
                "resolved_date": None, "resolved_price": None, "outcome_note": "",
            })

    # Auto-roll a fresh 14-calendar-day Brent macro call once the current Brent call resolves
    has_brent_pending = any(r.get("asset") == "BRENT" and r.get("status") == "PENDING" for r in rows)
    brent_bars = daily_bars.get("BRENT") or []
    if not has_brent_pending and brent_bars:
        bd = brent_bars[-1]["d"]
        bc = brent_bars[-1]["c"]
        bdue = (dt.date.fromisoformat(bd) + dt.timedelta(days=14)).isoformat()
        if bc <= 95.0:
            btgt = round(bc * 0.95, 2)
            rows.insert(0, {
                "id": f"auto_brent_{bd.replace('-', '')}",
                "kind": "auto_macro",
                "asset": "BRENT",
                "logged_date": bd,
                "due_date": bdue,
                "prediction": f"Brent stays capped < $95.00 and cools to ≤ ${btgt:.2f} (tailwind for IREDA)",
                "rule_text": f"HIT if Low ≤ ${btgt:.2f} · MISS if Close > $95.00",
                "hit_field": "l", "hit_op": "le", "hit_val": btgt,
                "miss_field": "c", "miss_op": "gt", "miss_val": 95.0,
                "status": "PENDING",
                "resolved_date": None, "resolved_price": None, "outcome_note": "",
            })
        else:
            btgt = round(bc * 1.04, 2)
            rows.insert(0, {
                "id": f"auto_brent_{bd.replace('-', '')}",
                "kind": "auto_macro",
                "asset": "BRENT",
                "logged_date": bd,
                "due_date": bdue,
                "prediction": f"Brent breakout > $95 extends ≥ ${btgt:.2f} (macro headwind for IREDA)",
                "rule_text": f"HIT if High ≥ ${btgt:.2f} · MISS if Close < $92.50",
                "hit_field": "h", "hit_op": "ge", "hit_val": btgt,
                "miss_field": "c", "miss_op": "lt", "miss_val": 92.5,
                "status": "PENDING",
                "resolved_date": None, "resolved_price": None, "outcome_note": "",
            })

    save_jsonl(LEDGER_FILE, rows)
    hits = sum(1 for r in rows if r["status"] == "HIT")
    misses = sum(1 for r in rows if r["status"] == "MISS")
    expired = sum(1 for r in rows if r["status"] == "EXPIRED")
    pending = sum(1 for r in rows if r["status"] == "PENDING")
    graded = hits + misses
    stats = {
        "total": len(rows),
        "hits": hits,
        "misses": misses,
        "expired": expired,
        "pending": pending,
        "graded": graded,
        "hit_rate_pct": round(hits / graded * 100.0, 1) if graded > 0 else None,
    }
    return rows, stats


def update_history(now_ist: dt.datetime, ireda_snap: dict[str, Any], score: int, reds: int, signal: dict[str, str], stats: dict[str, Any], lights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hist = load_jsonl(HISTORY_FILE)
    day_key = ireda_snap["last_date"]
    entry = {
        "date": day_key,
        "updated_ist": now_ist.strftime("%Y-%m-%d %H:%M IST"),
        "ireda_close": ireda_snap["last"],
        "ireda_chg_pct": ireda_snap["chg_pct"],
        "ireda_rsi": ireda_snap["rsi"],
        "macro_score": score,
        "red_lights": reds,
        "signal": signal["code"],
        "signal_label": signal["label"],
        "lights_summary": {x["id"]: x["status"] for x in lights},
        "hit_rate_pct": stats["hit_rate_pct"],
    }
    replaced = False
    for idx, row in enumerate(hist):
        if row.get("date") == day_key:
            hist[idx] = entry
            replaced = True
            break
    if not replaced:
        hist.append(entry)
    hist.sort(key=lambda r: r["date"])
    hist = hist[-180:]
    save_jsonl(HISTORY_FILE, hist)
    return hist


def main() -> int:
    now_ist = dt.datetime.now(IST)
    prev_state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}

    daily_bars: dict[str, list[dict[str, Any]]] = {}
    weekly_bars: dict[str, list[dict[str, Any]]] = {}
    snap: dict[str, dict[str, Any]] = {}
    charts: dict[str, Any] = {}
    fetch_errors: list[str] = []

    for key, meta in TICKERS.items():
        dec = meta["dec"]
        try:
            d_raw = fetch_yahoo(meta["symbol"], "2y", "1d")
            w_raw = fetch_yahoo(meta["symbol"], "3y", "1wk")
            d_clean = clean_bars(key, "1d", d_raw, dec, meta["clean"])
            w_clean = clean_bars(key, "1wk", w_raw, dec, meta["clean"])
            daily_bars[key] = d_clean
            weekly_bars[key] = w_clean

            d_closes = [b["c"] for b in d_clean]
            e20 = compute_ema(d_closes, 20, dec)
            e50 = compute_ema(d_closes, 50, dec)
            e200 = compute_ema(d_closes, 200, dec)
            r14 = compute_rsi(d_closes, 14)
            atr14 = compute_atr(d_clean, 14)

            w_closes = [b["c"] for b in w_clean]
            we20 = compute_ema(w_closes, 20, dec)
            we50 = compute_ema(w_closes, 50, dec)
            wr14 = compute_rsi(w_closes, 14)

            last_c = d_clean[-1]["c"]
            prev_c = d_clean[-2]["c"] if len(d_clean) >= 2 else last_c
            chg_pct = round((last_c / prev_c - 1.0) * 100.0, 2) if prev_c else 0.0

            snap[key] = {
                "name": meta["name"],
                "symbol": meta["symbol"],
                "unit": meta["unit"],
                "dec": dec,
                "last": last_c,
                "prev_close": prev_c,
                "chg_pct": chg_pct,
                "last_date": d_clean[-1]["d"],
                "e20": e20[-1], "e50": e50[-1], "e200": e200[-1],
                "rsi": r14[-1], "atr14": atr14,
                "w_e20": we20[-1], "w_e50": we50[-1], "w_rsi": wr14[-1],
                "stale": False,
            }

            d_tail = d_clean[-260:]
            w_tail = w_clean[-115:]
            charts[key] = {
                "name": meta["name"], "unit": meta["unit"], "dec": dec,
                "1d": {
                    "bars": [
                        [b["d"], b["o"], b["h"], b["l"], b["c"], e20[len(d_clean) - len(d_tail) + i], e50[len(d_clean) - len(d_tail) + i], e200[len(d_clean) - len(d_tail) + i], r14[len(d_clean) - len(d_tail) + i]]
                        for i, b in enumerate(d_tail)
                    ],
                    "tls": project_trendlines(key, "1d", d_clean, len(d_tail), dec),
                },
                "1wk": {
                    "bars": [
                        [b["d"], b["o"], b["h"], b["l"], b["c"], we20[len(w_clean) - len(w_tail) + i], we50[len(w_clean) - len(w_tail) + i], None, wr14[len(w_clean) - len(w_tail) + i]]
                        for i, b in enumerate(w_tail)
                    ],
                    "tls": project_trendlines(key, "1wk", w_clean, len(w_tail), dec),
                },
            }
        except Exception as exc:
            fetch_errors.append(f"{key}: {exc}")
            if prev_state and key in prev_state.get("snapshots", {}):
                cached = dict(prev_state["snapshots"][key])
                cached["stale"] = True
                snap[key] = cached
                if key in prev_state.get("charts", {}):
                    charts[key] = prev_state["charts"][key]
            else:
                raise

    lights, macro_score, red_lights = eval_five_lights(snap)
    signal = compute_action_signal(snap["IREDA"], macro_score, red_lights)
    ledger_rows, pred_stats = update_and_grade_ledger(daily_bars, signal, snap["IREDA"], now_ist)
    history_rows = update_history(now_ist, snap["IREDA"], macro_score, red_lights, signal, pred_stats, lights)

    # Upcoming catalysts (only show dates >= today - 1 day)
    today_iso = now_ist.date().isoformat()
    upcoming = [c for c in CATALYSTS if c["date"] >= today_iso][:4]
    is_nse_live = (
        now_ist.weekday() < 5
        and (9, 15) <= (now_ist.hour, now_ist.minute) <= (15, 35)
        and snap["IREDA"]["last_date"] == today_iso
    )

    state = {
        "schema_version": "cockpit-v1",
        "updated_at_ist": now_ist.strftime("%Y-%m-%d %H:%M IST"),
        "updated_at_utc": now_ist.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "market_session": "LIVE INTRADAY (NSE)" if is_nse_live else "EOD / PRE-MARKET",
        "sanitized_market_only": True,
        "fetch_errors": fetch_errors,
        "macro_score": macro_score,
        "red_lights": red_lights,
        "signal": signal,
        "lights": lights,
        "ireda": snap["IREDA"],
        "snapshots": snap,
        "prediction_stats": pred_stats,
        "predictions": ledger_rows[:20],
        "history": history_rows[-30:],
        "catalysts": upcoming,
        "charts": charts,
    }

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"[OK] Updated {STATE_FILE.name} @ {state['updated_at_ist']} | "
        f"IREDA=₹{snap['IREDA']['last']} (RSI {snap['IREDA']['rsi']}) | "
        f"Score={macro_score}/10 | Reds={red_lights}/5 | Signal={signal['code']} | "
        f"Preds={pred_stats['hits']}H/{pred_stats['misses']}M/{pred_stats['pending']}P"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
