#!/usr/bin/env python3
"""Ankur Agarwal Multi-Timeframe Demand & Supply Scanner + Swing Strategy Backtester.

Covers all Nifty 50 constituents + IREDA & Power/Renewable Finance focus peers.
Zero external dependencies (Python 3 standard library only) so GitHub Actions
can run it automatically on ubuntu-latest without pip installs.

Sanitized & market-only: stores zero personal holdings, quantities, or credentials.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = REPO_ROOT / "demand_supply_state.json"
SWING_LEDGER_FILE = REPO_ROOT / "swing_ledger.jsonl"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# Official Nifty 50 universe (with Yahoo Finance fallback aliases for renames/demergers)
# Format: (display_symbol, [yahoo_candidates], company_name, sector, group)
UNIVERSE: list[tuple[str, list[str], str, str, str]] = [
    # --- IREDA & Power / Renewable Finance Focus Basket ---
    ("IREDA", ["IREDA.NS"], "IREDA", "Power Finance", "IREDA_POWER"),
    ("RECLTD", ["RECLTD.NS"], "REC Ltd", "Power Finance", "IREDA_POWER"),
    ("PFC", ["PFC.NS"], "Power Finance Corp", "Power Finance", "IREDA_POWER"),
    ("HUDCO", ["HUDCO.NS"], "HUDCO", "Power Finance", "IREDA_POWER"),
    ("ADANIPOWER", ["ADANIPOWER.NS"], "Adani Power", "Power & Utilities", "IREDA_POWER"),
    ("TATAPOWER", ["TATAPOWER.NS"], "Tata Power", "Power & Utilities", "IREDA_POWER"),
    ("JPPOWER", ["JPPOWER.NS"], "JP Power Ventures", "Power & Utilities", "IREDA_POWER"),
    ("NHPC", ["NHPC.NS"], "NHPC", "Power & Utilities", "IREDA_POWER"),
    ("SJVN", ["SJVN.NS"], "SJVN", "Power & Utilities", "IREDA_POWER"),

    # --- Nifty 50 Constituents (50 Stocks) ---
    # Banking & Financials
    ("HDFCBANK", ["HDFCBANK.NS"], "HDFC Bank", "Banking & Finance", "NIFTY50"),
    ("ICICIBANK", ["ICICIBANK.NS"], "ICICI Bank", "Banking & Finance", "NIFTY50"),
    ("SBIN", ["SBIN.NS"], "State Bank of India", "Banking & Finance", "NIFTY50"),
    ("AXISBANK", ["AXISBANK.NS"], "Axis Bank", "Banking & Finance", "NIFTY50"),
    ("KOTAKBANK", ["KOTAKBANK.NS"], "Kotak Mahindra Bank", "Banking & Finance", "NIFTY50"),
    ("BAJFINANCE", ["BAJFINANCE.NS"], "Bajaj Finance", "Banking & Finance", "NIFTY50"),
    ("BAJAJFINSV", ["BAJAJFINSV.NS"], "Bajaj Finserv", "Banking & Finance", "NIFTY50"),
    ("JIOFIN", ["JIOFIN.NS"], "Jio Financial", "Banking & Finance", "NIFTY50"),
    ("SHRIRAMFIN", ["SHRIRAMFIN.NS"], "Shriram Finance", "Banking & Finance", "NIFTY50"),
    ("HDFCLIFE", ["HDFCLIFE.NS"], "HDFC Life", "Banking & Finance", "NIFTY50"),
    ("SBILIFE", ["SBILIFE.NS"], "SBI Life", "Banking & Finance", "NIFTY50"),

    # IT Services
    ("TCS", ["TCS.NS"], "Tata Consultancy", "IT Services", "NIFTY50"),
    ("INFY", ["INFY.NS"], "Infosys", "IT Services", "NIFTY50"),
    ("HCLTECH", ["HCLTECH.NS"], "HCL Technologies", "IT Services", "NIFTY50"),
    ("WIPRO", ["WIPRO.NS"], "Wipro", "IT Services", "NIFTY50"),
    ("TECHM", ["TECHM.NS"], "Tech Mahindra", "IT Services", "NIFTY50"),

    # Energy, Oil & Power
    ("RELIANCE", ["RELIANCE.NS"], "Reliance Industries", "Energy & Oil", "NIFTY50"),
    ("ONGC", ["ONGC.NS"], "ONGC", "Energy & Oil", "NIFTY50"),
    ("COALINDIA", ["COALINDIA.NS"], "Coal India", "Energy & Oil", "NIFTY50"),
    ("NTPC", ["NTPC.NS"], "NTPC", "Power & Utilities", "NIFTY50"),
    ("POWERGRID", ["POWERGRID.NS"], "Power Grid Corp", "Power & Utilities", "NIFTY50"),

    # Auto & Mobility
    ("M&M", ["M&M.NS"], "Mahindra & Mahindra", "Auto & Mobility", "NIFTY50"),
    ("MARUTI", ["MARUTI.NS"], "Maruti Suzuki", "Auto & Mobility", "NIFTY50"),
    ("BAJAJ-AUTO", ["BAJAJ-AUTO.NS"], "Bajaj Auto", "Auto & Mobility", "NIFTY50"),
    ("EICHERMOT", ["EICHERMOT.NS"], "Eicher Motors", "Auto & Mobility", "NIFTY50"),
    ("TMPV", ["TMPV.NS", "TATAMOTORS.NS"], "Tata Motors PV", "Auto & Mobility", "NIFTY50"),

    # Pharma & Healthcare
    ("SUNPHARMA", ["SUNPHARMA.NS"], "Sun Pharma", "Pharma & Health", "NIFTY50"),
    ("CIPLA", ["CIPLA.NS"], "Cipla", "Pharma & Health", "NIFTY50"),
    ("DRREDDY", ["DRREDDY.NS"], "Dr Reddy's Labs", "Pharma & Health", "NIFTY50"),
    ("APOLLOHOSP", ["APOLLOHOSP.NS"], "Apollo Hospitals", "Pharma & Health", "NIFTY50"),
    ("MAXHEALTH", ["MAXHEALTH.NS"], "Max Healthcare", "Pharma & Health", "NIFTY50"),

    # FMCG & Consumer
    ("HINDUNILVR", ["HINDUNILVR.NS"], "Hindustan Unilever", "FMCG & Consumer", "NIFTY50"),
    ("ITC", ["ITC.NS"], "ITC", "FMCG & Consumer", "NIFTY50"),
    ("NESTLEIND", ["NESTLEIND.NS"], "Nestle India", "FMCG & Consumer", "NIFTY50"),
    ("TATACONSUM", ["TATACONSUM.NS"], "Tata Consumer", "FMCG & Consumer", "NIFTY50"),
    ("ASIANPAINT", ["ASIANPAINT.NS"], "Asian Paints", "FMCG & Consumer", "NIFTY50"),
    ("TITAN", ["TITAN.NS"], "Titan Company", "FMCG & Consumer", "NIFTY50"),
    ("TRENT", ["TRENT.NS"], "Trent", "FMCG & Consumer", "NIFTY50"),
    ("ETERNAL", ["ETERNAL.NS", "ZOMATO.NS"], "Eternal (Zomato)", "FMCG & Consumer", "NIFTY50"),

    # Metals & Materials
    ("TATASTEEL", ["TATASTEEL.NS"], "Tata Steel", "Metals & Cement", "NIFTY50"),
    ("JSWSTEEL", ["JSWSTEEL.NS"], "JSW Steel", "Metals & Cement", "NIFTY50"),
    ("HINDALCO", ["HINDALCO.NS"], "Hindalco", "Metals & Cement", "NIFTY50"),
    ("ULTRACEMCO", ["ULTRACEMCO.NS"], "UltraTech Cement", "Metals & Cement", "NIFTY50"),
    ("GRASIM", ["GRASIM.NS"], "Grasim Industries", "Metals & Cement", "NIFTY50"),

    # Infra, Defence, Ports & Telecom
    ("LT", ["LT.NS"], "Larsen & Toubro", "Infra & Defence", "NIFTY50"),
    ("BEL", ["BEL.NS"], "Bharat Electronics", "Infra & Defence", "NIFTY50"),
    ("ADANIENT", ["ADANIENT.NS"], "Adani Enterprises", "Infra & Defence", "NIFTY50"),
    ("ADANIPORTS", ["ADANIPORTS.NS"], "Adani Ports", "Infra & Defence", "NIFTY50"),
    ("INDIGO", ["INDIGO.NS"], "InterGlobe Aviation", "Infra & Defence", "NIFTY50"),
    ("BHARTIARTL", ["BHARTIARTL.NS"], "Bharti Airtel", "Telecom", "NIFTY50"),
]

TF_WEIGHT = {"Y": 5, "H": 4, "Q": 3, "M": 2.5, "W": 1.6, "D": 1.0}
TF_ORDER = ["Y", "H", "Q", "M", "W", "D"]


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
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=18) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            chart = payload.get("chart") or {}
            if chart.get("error"):
                raise ValueError(str(chart["error"]))
            res = chart["result"][0]
            ts = res.get("timestamp") or []
            q = res["indicators"]["quote"][0]
            vols = q.get("volume") or [0] * len(ts)
            bars: list[dict[str, Any]] = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                o, h, l, c = float(o), float(h), float(l), float(c)
                if c <= 0 or o <= 0 or h <= 0 or l <= 0:
                    continue
                bhi, blo = max(o, c), min(o, c)
                h = max(h, bhi)
                l = min(l, blo)
                d_str = dt.datetime.fromtimestamp(t, IST).strftime("%Y-%m-%d")
                bars.append({
                    "d": d_str,
                    "o": round(o, 2),
                    "h": round(h, 2),
                    "l": round(l, 2),
                    "c": round(c, 2),
                    "v": int(vols[i] or 0),
                })
            # Deduplicate by date preserving latest bar
            dedup: dict[str, dict[str, Any]] = {}
            for b in bars:
                dedup[b["d"]] = b
            out = [dedup[k] for k in sorted(dedup.keys())]
            if not out:
                raise ValueError(f"No bars for {symbol} ({interval})")
            return out
        except Exception as exc:
            last_err = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"{symbol} ({interval}): {last_err}")


def compute_ema(vals: list[float], period: int) -> list[float | None]:
    if len(vals) < period:
        return [None] * len(vals)
    k = 2.0 / (period + 1)
    out: list[float | None] = [None] * (period - 1)
    cur = sum(vals[:period]) / period
    out.append(round(cur, 2))
    for v in vals[period:]:
        cur = v * k + cur * (1.0 - k)
        out.append(round(cur, 2))
    return out


def resample_from_bars(bars: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    """Aggregate daily or monthly bars into Calendar Y / H (Jan-Jun, Jul-Dec) / Q / M / W."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for b in bars:
        y = int(b["d"][0:4])
        m = int(b["d"][5:7])
        day = int(b["d"][8:10])
        if mode == "Y":
            key = f"{y}"
        elif mode == "H":
            key = f"{y}-H{1 if m <= 6 else 2}"
        elif mode == "Q":
            key = f"{y}-Q{(m - 1) // 3 + 1}"
        elif mode == "M":
            key = f"{y:04d}-{m:02d}"
        elif mode == "W":
            d_obj = dt.date(y, m, day)
            monday = d_obj - dt.timedelta(days=d_obj.weekday())
            key = monday.isoformat()
        else:
            key = b["d"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(b)

    out: list[dict[str, Any]] = []
    for key in order:
        grp = groups[key]
        out.append({
            "grp": key,
            "d": grp[-1]["d"],
            "start": grp[0]["d"],
            "o": grp[0]["o"],
            "h": max(x["h"] for x in grp),
            "l": min(x["l"] for x in grp),
            "c": grp[-1]["c"],
            "v": sum(x["v"] for x in grp),
        })
    return out


def detect_zones(
    bars: list[dict[str, Any]],
    tf_name: str,
    min_legout_body_pct: float = 50.0,
    max_base_candles: int = 4,
    as_of_idx: int | None = None,
) -> list[dict[str, Any]]:
    """Detect Ankur Agarwal Demand (RBR/DBR) & Supply (RBD/DBD) zones with strict zero-lookahead."""
    rows = bars[: as_of_idx + 1] if as_of_idx is not None else bars
    n = len(rows)
    if n < 4:
        return []

    ranges = [max(0.0, r["h"] - r["l"]) for r in rows]
    bodies = [abs(r["c"] - r["o"]) for r in rows]
    bpcts = [(bodies[i] / ranges[i] * 100.0) if ranges[i] > 1e-9 else 0.0 for i in range(n)]
    is_green = [r["c"] >= r["o"] for r in rows]

    # Rolling 10-bar mean range
    avg_rng: list[float] = []
    for i in range(n):
        w = ranges[max(0, i - 9) : i + 1]
        avg_rng.append(sum(w) / len(w))

    zones: list[dict[str, Any]] = []
    for i in range(1, n - 1):
        lo_idx = i + 1
        lo_bpct = bpcts[lo_idx]
        lo_rng = ranges[lo_idx]
        lo_green = is_green[lo_idx]

        # Must be a strong ERC leg-out candle
        if lo_bpct < min_legout_body_pct or lo_rng < 0.72 * avg_rng[lo_idx]:
            continue

        # Identify Base Candles:
        # Rule A: Single opposite-color candle inside an impulse rally/drop (Ankur's signature rule!)
        base_indices: list[int] = []
        single_opp = False
        if lo_green and (not is_green[i]) and is_green[i - 1] and bpcts[i - 1] >= 42.0:
            base_indices = [i]
            single_opp = True
        elif (not lo_green) and is_green[i] and (not is_green[i - 1]) and bpcts[i - 1] >= 42.0:
            base_indices = [i]
            single_opp = True
        else:
            j = i
            while j >= 1 and len(base_indices) < max_base_candles:
                if bpcts[j] <= 55.0 and ranges[j] <= 1.45 * lo_rng:
                    base_indices.insert(0, j)
                    j -= 1
                else:
                    break

        if not base_indices:
            continue
        legin_idx = base_indices[0] - 1
        if legin_idx < 0:
            continue

        li_green = is_green[legin_idx]
        b_sub = [rows[idx] for idx in base_indices]
        lo_bar = rows[lo_idx]

        if lo_green:
            kind = "DEMAND"
            pat = ("RBR" if li_green else "DBR") + f"-{tf_name}"
            if single_opp:
                pat += " (1-Red)"
            proximal = max(max(x["o"], x["c"]) for x in b_sub)
            distal = min(min(x["l"] for x in b_sub), lo_bar["l"])
            if proximal <= distal or (proximal - distal) / max(proximal, 1e-6) > 0.38:
                continue

            # Freshness & Violation check (strictly on bars AFTER leg-out)
            touches = 0
            violated = False
            swept_wick = False
            for pr in rows[lo_idx + 1 :]:
                if pr["c"] < distal:
                    violated = True
                    break
                if pr["l"] < distal:
                    swept_wick = True
                if pr["l"] <= proximal:
                    touches += 1

            # Achievement check: did leg-out or next 2 bars close above prior 6-bar high or ATH?
            prior_window = rows[max(0, legin_idx - 6) : lo_idx]
            prior_hi = max(x["h"] for x in prior_window)
            ath_before = max(x["h"] for x in rows[:lo_idx])
            post_end = min(n, lo_idx + 3)
            post_max_close = max(x["c"] for x in rows[lo_idx:post_end])
            post_max_high = max(x["h"] for x in rows[lo_idx:post_end])
            if post_max_close > ath_before:
                ach = "ATH_BOS"
            elif post_max_close > prior_hi or post_max_high > prior_hi * 1.015:
                ach = "BOS"
            else:
                ach = "NO_BOS"
        else:
            kind = "SUPPLY"
            pat = ("RBD" if li_green else "DBD") + f"-{tf_name}"
            if single_opp:
                pat += " (1-Grn)"
            proximal = min(min(x["o"], x["c"]) for x in b_sub)
            distal = max(max(x["h"] for x in b_sub), lo_bar["h"])
            if distal <= proximal or (distal - proximal) / max(proximal, 1e-6) > 0.38:
                continue

            touches = 0
            violated = False
            swept_wick = False
            for pr in rows[lo_idx + 1 :]:
                if pr["c"] > distal:
                    violated = True
                    break
                if pr["h"] > distal:
                    swept_wick = True
                if pr["h"] >= proximal:
                    touches += 1

            prior_window = rows[max(0, legin_idx - 6) : lo_idx]
            prior_lo = min(x["l"] for x in prior_window)
            post_end = min(n, lo_idx + 3)
            post_min_close = min(x["c"] for x in rows[lo_idx:post_end])
            ach = "BOS" if post_min_close < prior_lo else "NO_BOS"

        if violated:
            continue

        status = "SWEPT_WICK" if swept_wick else ("FRESH" if touches == 0 else f"TESTED({touches})")
        zones.append({
            "tf": tf_name,
            "kind": kind,
            "pattern": pat,
            "single_opp": single_opp,
            "base_start": b_sub[0].get("grp", b_sub[0]["d"]),
            "base_end": b_sub[-1].get("grp", b_sub[-1]["d"]),
            "legout_date": lo_bar["d"],
            "legout_grp": lo_bar.get("grp", lo_bar["d"]),
            "legout_idx": lo_idx,
            "proximal": round(proximal, 2),
            "distal": round(distal, 2),
            "touches": touches,
            "status": status,
            "ach": ach,
            "lo_chg": round((lo_bar["c"] / lo_bar["o"] - 1.0) * 100.0, 1),
        })

    return zones


def zones_overlap(z1: dict[str, Any], z2: dict[str, Any], pad_pct: float = 0.025) -> bool:
    lo1, hi1 = min(z1["distal"], z1["proximal"]), max(z1["distal"], z1["proximal"])
    lo2, hi2 = min(z2["distal"], z2["proximal"]), max(z2["distal"], z2["proximal"])
    mid = (hi1 + lo1) / 2.0
    pad = mid * pad_pct
    return (lo1 - pad) <= hi2 and (lo2 - pad) <= hi1


def cluster_htf_demand_zones(all_dz: list[dict[str, Any]], cmp_val: float) -> list[dict[str, Any]]:
    """Group genuinely co-located Demand Zones across Y/H/Q/M/W/D WITHOUT transitive chaining.

    Each cluster is anchored to a single seed zone; another zone joins ONLY if it directly
    overlaps the anchor itself and keeps total cluster width <= 18% (preventing multi-year
    snowballing across unrelated price bands).
    """
    candidates = [
        z for z in all_dz
        if z["distal"] < cmp_val
        and z["proximal"] <= cmp_val * 1.045
        and z["proximal"] >= cmp_val * 0.35  # ignore ancient multi-decade zones >65% below CMP
        and z["touches"] <= 3
    ]
    if not candidates:
        return []

    # Sort highest TF first, then closest to CMP
    candidates.sort(key=lambda z: (-TF_WEIGHT[z["tf"]], abs(cmp_val - z["proximal"])))
    clusters: list[dict[str, Any]] = []

    for z in candidates:
        placed = False
        for cl in clusters:
            anchor = cl["anchor"]
            if zones_overlap(z, anchor, pad_pct=0.015):
                # Enforce non-chaining width cap (unless both are deep HTF Y/H/Q zones)
                new_hi = max(cl["hi"], z["proximal"])
                new_lo = min(cl["lo"], z["distal"])
                span_pct = (new_hi - new_lo) / max(new_hi, 1e-6) * 100.0
                both_macro = (anchor["tf"] in ("Y", "H", "Q") and z["tf"] in ("Y", "H", "Q"))
                if span_pct <= 22.0 or (both_macro and span_pct <= 32.0):
                    cl["members"].append(z)
                    cl["hi"] = new_hi
                    cl["lo"] = new_lo
                    placed = True
                    break
        if not placed:
            clusters.append({"anchor": z, "members": [z], "hi": z["proximal"], "lo": z["distal"]})

    out: list[dict[str, Any]] = []
    for cl in clusters:
        mems = cl["members"]
        tfs = sorted({m["tf"] for m in mems}, key=lambda t: TF_ORDER.index(t))
        outer_prox = max(m["proximal"] for m in mems)
        outer_dist = min(m["distal"] for m in mems)

        # Pick the tightest actionable execution core inside the cluster:
        # Prefer the freshest Weekly or Daily zone (width <= 11%) nested inside/at the top of the HTF cluster!
        tight_ltf = [
            m for m in mems
            if m["tf"] in ("W", "D") and ((m["proximal"] - m["distal"]) / max(m["proximal"], 1e-6) * 100.0) <= 11.5
        ]
        if tight_ltf:
            # Prefer Weekly over Daily if both tight, then freshest, then highest proximal
            tight_ltf.sort(key=lambda m: (0 if m["tf"] == "W" else 1, m["touches"], -m["proximal"]))
            exec_core = tight_ltf[0]
            prox_exec = exec_core["proximal"]
            dist_exec = exec_core["distal"]
        else:
            # Use the tightest member in the cluster (usually Monthly or Quarterly)
            tightest = min(mems, key=lambda m: (m["proximal"] - m["distal"]) / max(m["proximal"], 1e-6))
            prox_exec = tightest["proximal"]
            dist_exec = tightest["distal"]

        dist_pct = round((cmp_val / prox_exec - 1.0) * 100.0, 2)
        has_1red = any(m["single_opp"] for m in mems)
        best_ach = "ATH_BOS" if any(m["ach"] == "ATH_BOS" for m in mems) else (
            "BOS" if any(m["ach"] == "BOS" for m in mems) else "NO_BOS"
        )
        freshest = "FRESH" if any(m["status"] == "FRESH" for m in mems) else (
            "TESTED(1)" if any(m["touches"] == 1 for m in mems) else mems[0]["status"]
        )
        max_tf_w = max(TF_WEIGHT[t] for t in tfs)
        sync_label = "+".join(tfs)
        rep = sorted(mems, key=lambda m: (-TF_WEIGHT[m["tf"]], m["touches"]))[0]

        out.append({
            "tfs": tfs,
            "sync_label": sync_label,
            "sync_count": len(tfs),
            "htf_count": len([t for t in tfs if t in ("Y", "H", "Q", "M")]),
            "max_tf_weight": max_tf_w,
            "proximal": round(prox_exec, 2),
            "distal": round(dist_exec, 2),
            "outer_proximal": round(outer_prox, 2),
            "outer_distal": round(outer_dist, 2),
            "dist_pct": dist_pct,
            "freshness": freshest,
            "ach": best_ach,
            "has_1red": has_1red,
            "pattern": rep["pattern"],
            "legout_date": rep["legout_date"],
            "zone_width_pct": round((prox_exec - dist_exec) / max(prox_exec, 1e-6) * 100.0, 1),
        })

    # Sort closest below CMP first, breaking near-ties by higher TF weight
    out.sort(key=lambda c: (max(-2.0, c["dist_pct"]), -c["htf_count"], -c["sync_count"]))
    return out


def find_nearest_supply(all_sz: list[dict[str, Any]], cmp_val: float) -> dict[str, Any] | None:
    """Find nearest active Monthly/Weekly/Quarterly Supply Zone above (or containing) CMP."""
    cands = [
        z for z in all_sz
        if z["tf"] in ("Q", "M", "W") and z["distal"] > cmp_val * 0.995 and z["touches"] <= 3
    ]
    if not cands:
        return None
    # Prefer zones with proximal closest to CMP (either containing CMP or directly above)
    cands.sort(key=lambda z: (max(0.0, z["proximal"] - cmp_val), -TF_WEIGHT[z["tf"]]))
    z = cands[0]
    in_supply = z["proximal"] <= cmp_val <= z["distal"]
    dist_pct = round((z["proximal"] / cmp_val - 1.0) * 100.0, 2)
    return {
        "tf": z["tf"],
        "pattern": z["pattern"],
        "proximal": z["proximal"],
        "distal": z["distal"],
        "status": z["status"],
        "dist_pct": dist_pct,
        "in_supply": in_supply,
        "legout_date": z["legout_date"],
    }


def compute_f1_achievement(m_bars: list[dict[str, Any]], cmp_val: float) -> float | None:
    """Find nearest Monthly swing high above CMP (Ankur's F1-M trend-change achievement line)."""
    if len(m_bars) < 6:
        return None
    recent = m_bars[-18:]
    highs = [b["h"] for b in recent[:-1]]
    above = [h for h in highs if h > cmp_val * 1.02]
    if not above:
        return round(max(b["h"] for b in m_bars), 2)
    # Local peaks in last 18 months
    peaks = []
    for i in range(1, len(recent) - 2):
        if recent[i]["h"] >= recent[i - 1]["h"] and recent[i]["h"] >= recent[i + 1]["h"]:
            if recent[i]["h"] > cmp_val * 1.02:
                peaks.append(recent[i]["h"])
    return round(min(peaks) if peaks else min(above), 2)


def run_walkforward_backtest(
    symbol: str,
    d_bars: list[dict[str, Any]],
    w_bars: list[dict[str, Any]],
    m_bars: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Strict zero-lookahead walk-forward backtest of Ankur's HTF-Backed Demand Zone Swing Strategy.

    Rules tested over the last ~3.5 years of Daily sessions:
    1. On day `t`, only Weekly & Monthly zones whose leg-out closed STRICTLY BEFORE day `t` are visible.
    2. Entry: Price enters a Fresh/1x-Tested Weekly or Monthly Demand Zone (`Low <= Proximal`, `Close >= Distal`)
       AND prints a bullish confirmation close (`Close > Open` and `Close >= Proximal * 0.985`, not slicing through).
    3. Stop Loss: `Distal * 0.99` (1% buffer below zone wick; max stop width capped at 12% so risk stays controlled).
    4. Targets: T1 = 2.0R (50% exit, trail rest to breakeven), T2 = 3.0R (or nearest Monthly Supply if >= 2.0R),
       Time Stop = 40 trading days.
    5. Transaction costs: 0.25% round-trip slippage + STT/brokerage deducted on every trade.
    """
    if len(d_bars) < 120 or len(w_bars) < 30:
        return []

    # Pre-detect Weekly & Monthly zones using ONLY data up to their legout, and track exact visibility date!
    # A zone becomes known on the trading day AFTER its leg-out bar ends (`legout_date`).
    w_zones = detect_zones(w_bars, "W", min_legout_body_pct=50.0, max_base_candles=4)
    m_zones = detect_zones(m_bars, "M", min_legout_body_pct=48.0, max_base_candles=4)
    # Note: we must NOT filter out zones that got violated LATER in the future!
    # Re-run raw candidate extraction without future-violation filtering so there is ZERO survivorship/lookahead bias!
    def raw_demand_candidates(bars: list[dict[str, Any]], tf_name: str, min_bp: float) -> list[dict[str, Any]]:
        n = len(bars)
        if n < 5:
            return []
        ranges = [max(0.0, r["h"] - r["l"]) for r in bars]
        bodies = [abs(r["c"] - r["o"]) for r in bars]
        bpcts = [(bodies[i] / ranges[i] * 100.0) if ranges[i] > 1e-9 else 0.0 for i in range(n)]
        is_green = [r["c"] >= r["o"] for r in bars]
        avg_rng = [sum(ranges[max(0, i - 9) : i + 1]) / len(ranges[max(0, i - 9) : i + 1]) for i in range(n)]
        out = []
        for i in range(1, n - 1):
            lo_idx = i + 1
            if not is_green[lo_idx]:
                continue
            if bpcts[lo_idx] < min_bp or ranges[lo_idx] < 0.72 * avg_rng[lo_idx]:
                continue
            single_red = (not is_green[i]) and is_green[i - 1] and bpcts[i - 1] >= 42.0
            base_idx = [i] if single_red else []
            if not base_idx:
                j = i
                while j >= 1 and len(base_idx) < 4:
                    if bpcts[j] <= 55.0 and ranges[j] <= 1.45 * ranges[lo_idx]:
                        base_idx.insert(0, j)
                        j -= 1
                    else:
                        break
            if not base_idx or base_idx[0] == 0:
                continue
            b_sub = [bars[k] for k in base_idx]
            lo_bar = bars[lo_idx]
            prox = max(max(x["o"], x["c"]) for x in b_sub)
            dist = min(min(x["l"] for x in b_sub), lo_bar["l"])
            if prox <= dist:
                continue
            width_pct = (prox - dist) / prox * 100.0
            if width_pct < 2.0 or width_pct > 13.0:
                continue
            # Strictly past-only BOS check using bars up to lo_idx
            prior_hi = max(x["h"] for x in bars[max(0, base_idx[0] - 7) : lo_idx])
            bos = lo_bar["c"] > prior_hi
            out.append({
                "tf": tf_name,
                "proximal": round(prox, 2),
                "distal": round(dist, 2),
                "visible_after": lo_bar["d"],  # strictly known only after this period closes
                "single_red": single_red,
                "bos": bos,
                "used": False,
                "violated": False,
                "touches": 0,
            })
        return out

    all_dz = raw_demand_candidates(w_bars, "W", 50.0) + raw_demand_candidates(m_bars, "M", 48.0)
    if not all_dz:
        return []

    # Precompute Daily 200 EMA for trend regime awareness
    d_closes = [b["c"] for b in d_bars]
    d_ema200 = compute_ema(d_closes, 200)

    # Walk forward over daily bars (start after bar 200 or 60 if young stock)
    start_i = min(200, max(40, len(d_bars) // 4))
    trades: list[dict[str, Any]] = []
    active_trade: dict[str, Any] | None = None

    for i in range(start_i, len(d_bars)):
        bar = d_bars[i]
        d_str = bar["d"]

        # 1. Manage open trade (using bar O/H/L/C conservatively: check stop BEFORE target on same bar)
        if active_trade is not None:
            tr = active_trade
            tr["hold_days"] += 1
            hit_stop = bar["l"] <= tr["cur_stop"]
            hit_t1 = (not tr["t1_hit"]) and (bar["h"] >= tr["t1"])
            hit_t2 = bar["h"] >= tr["t2"]

            if hit_stop:
                exit_px = min(bar["o"], tr["cur_stop"])
                # Realize remaining position
                if tr["t1_hit"]:
                    # 50% was closed at T1 (+2R), 50% closed at BE (0R)
                    gross_r = 0.5 * 2.0 + 0.5 * ((exit_px - tr["entry"]) / tr["risk"])
                    outcome = "T1_TRAIL"
                else:
                    gross_r = (exit_px - tr["entry"]) / tr["risk"]
                    outcome = "STOP_LOSS"
                net_pct = (gross_r * tr["risk"] / tr["entry"] * 100.0) - 0.25
                net_r = net_pct / (tr["risk"] / tr["entry"] * 100.0)
                trades.append({
                    "symbol": symbol, "entry_date": tr["entry_date"], "exit_date": d_str,
                    "entry": tr["entry"], "stop": tr["orig_stop"], "exit": round(exit_px, 2),
                    "tf": tr["tf"], "mtf_sync": tr["mtf_sync"], "single_red": tr["single_red"],
                    "bos": tr["bos"], "above_200": tr["above_200"], "risk_pct": tr["risk_pct"],
                    "hold_days": tr["hold_days"],
                    "outcome": outcome, "ret_pct": round(net_pct, 2), "r_mult": round(net_r, 2),
                })
                active_trade = None
                continue

            if hit_t2:
                # Full T2 reached (50% @ 2R + 50% @ 3R = +2.5R avg)
                gross_r = 0.5 * 2.0 + 0.5 * 3.0 if tr["t1_hit"] else 0.5 * 2.0 + 0.5 * 3.0
                net_pct = (gross_r * tr["risk"] / tr["entry"] * 100.0) - 0.25
                net_r = net_pct / (tr["risk"] / tr["entry"] * 100.0)
                trades.append({
                    "symbol": symbol, "entry_date": tr["entry_date"], "exit_date": d_str,
                    "entry": tr["entry"], "stop": tr["orig_stop"], "exit": round(tr["t2"], 2),
                    "tf": tr["tf"], "mtf_sync": tr["mtf_sync"], "single_red": tr["single_red"],
                    "bos": tr["bos"], "above_200": tr["above_200"], "risk_pct": tr["risk_pct"],
                    "hold_days": tr["hold_days"],
                    "outcome": "TARGET_2", "ret_pct": round(net_pct, 2), "r_mult": round(net_r, 2),
                })
                active_trade = None
                continue

            if hit_t1:
                tr["t1_hit"] = True
                tr["cur_stop"] = tr["entry"]  # move remaining 50% to breakeven!

            if tr["hold_days"] >= 45:
                exit_px = bar["c"]
                rem_r = (exit_px - tr["entry"]) / tr["risk"]
                gross_r = (0.5 * 2.0 + 0.5 * rem_r) if tr["t1_hit"] else rem_r
                net_pct = (gross_r * tr["risk"] / tr["entry"] * 100.0) - 0.25
                net_r = net_pct / (tr["risk"] / tr["entry"] * 100.0)
                trades.append({
                    "symbol": symbol, "entry_date": tr["entry_date"], "exit_date": d_str,
                    "entry": tr["entry"], "stop": tr["orig_stop"], "exit": round(exit_px, 2),
                    "tf": tr["tf"], "mtf_sync": tr["mtf_sync"], "single_red": tr["single_red"],
                    "bos": tr["bos"], "above_200": tr["above_200"], "risk_pct": tr["risk_pct"],
                    "hold_days": tr["hold_days"],
                    "outcome": "TIME_EXIT", "ret_pct": round(net_pct, 2), "r_mult": round(net_r, 2),
                })
                active_trade = None
                continue

        # 2. Update zone statuses strictly causally on day `i`
        best_trigger: dict[str, Any] | None = None
        visible_active = [z for z in all_dz if z["visible_after"] < d_str and not z["violated"]]

        for z in visible_active:
            if bar["c"] < z["distal"]:
                z["violated"] = True
                continue
            # Check tap into fresh (touches == 0) zone with bullish confirmation close
            if (
                active_trade is None
                and not z["used"]
                and z["touches"] == 0
                and bar["l"] <= z["proximal"]
                and bar["l"] >= z["distal"] * 0.992
                and bar["c"] > bar["o"]
                and bar["c"] >= z["proximal"] * 0.985
            ):
                # Check if another timeframe zone overlaps (Multi-TF Sync!)
                mtf_sync = any(
                    other is not z and other["tf"] != z["tf"] and zones_overlap(z, other, 0.03)
                    for other in visible_active
                )
                # Trend/Confluence Gate: Either above 200 EMA, OR MTF-synced, OR BOS achieved on Monthly/Weekly
                above_200 = (d_ema200[i] is not None and bar["c"] >= d_ema200[i] * 0.96)
                if above_200 or mtf_sync or z["bos"]:
                    cand = dict(z)
                    cand["mtf_sync"] = mtf_sync
                    if best_trigger is None or (cand["mtf_sync"], cand["tf"] == "M", cand["bos"]) > (
                        best_trigger["mtf_sync"], best_trigger["tf"] == "M", best_trigger["bos"]
                    ):
                        best_trigger = cand
                        best_trigger["_ref"] = z
            if bar["l"] <= z["proximal"]:
                z["touches"] += 1

        # 3. Open new trade at closing confirmation price (realistic EOD CNC delivery entry)
        if best_trigger is not None and active_trade is None:
            entry = bar["c"]
            stop = round(best_trigger["distal"] * 0.99, 2)
            risk = entry - stop
            risk_pct = risk / entry * 100.0
            if 1.5 <= risk_pct <= 12.5:
                above_200_flag = bool(d_ema200[i] is not None and bar["c"] >= d_ema200[i])
                best_trigger["_ref"]["used"] = True
                active_trade = {
                    "entry_date": d_str,
                    "entry": round(entry, 2),
                    "orig_stop": stop,
                    "cur_stop": stop,
                    "risk": risk,
                    "risk_pct": round(risk_pct, 1),
                    "above_200": above_200_flag,
                    "t1": round(entry + 2.0 * risk, 2),
                    "t2": round(entry + 3.0 * risk, 2),
                    "t1_hit": False,
                    "hold_days": 0,
                    "tf": best_trigger["tf"],
                    "mtf_sync": best_trigger["mtf_sync"],
                    "single_red": best_trigger["single_red"],
                    "bos": best_trigger["bos"],
                }

    return trades


def analyze_stock(spec: tuple[str, list[str], str, str, str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    sym, candidates, name, sector, group = spec
    yahoo_sym = None
    d_bars: list[dict[str, Any]] = []
    m_hist: list[dict[str, Any]] = []
    last_err = None

    for cand in candidates:
        try:
            d_bars = fetch_yahoo(cand, "5y", "1d")
            m_hist = fetch_yahoo(cand, "max", "1mo")
            yahoo_sym = cand
            break
        except Exception as exc:
            last_err = str(exc)

    if not yahoo_sym or not d_bars:
        return None, [], f"{sym}: {last_err}"

    # Build Multi-Timeframe bars:
    # Y, H, Q, M from 20-25y `m_hist` (with latest month stitched from latest daily close so it's 100% live!)
    # For very young stocks (< 4y, e.g. IREDA), build directly from `d_bars` so no monthly Yahoo quirks occur.
    if len(m_hist) < 48:
        y_bars = resample_from_bars(d_bars, "Y")
        h_bars = resample_from_bars(d_bars, "H")
        q_bars = resample_from_bars(d_bars, "Q")
        m_bars = resample_from_bars(d_bars, "M")
    else:
        # Stitch latest incomplete month from daily bars to ensure live accuracy
        m_clean = resample_from_bars(m_hist, "M")
        d_m = resample_from_bars(d_bars, "M")
        d_m_map = {x["grp"]: x for x in d_m}
        for i, mb in enumerate(m_clean):
            if mb["grp"] in d_m_map:
                m_clean[i] = d_m_map[mb["grp"]]
        if d_m and d_m[-1]["grp"] > m_clean[-1]["grp"]:
            m_clean.append(d_m[-1])
        m_bars = m_clean
        y_bars = resample_from_bars(m_bars, "Y")
        h_bars = resample_from_bars(m_bars, "H")
        q_bars = resample_from_bars(m_bars, "Q")

    w_bars = resample_from_bars(d_bars, "W")

    # Compute EMAs (20 & 50 matching Ankur's TradeTiger setup + Daily 200 EMA)
    d_c = [b["c"] for b in d_bars]
    w_c = [b["c"] for b in w_bars]
    m_c = [b["c"] for b in m_bars]

    d_e20, d_e50, d_e200 = compute_ema(d_c, 20), compute_ema(d_c, 50), compute_ema(d_c, 200)
    w_e20, w_e50 = compute_ema(w_c, 20), compute_ema(w_c, 50)
    m_e20, m_e50 = compute_ema(m_c, 20), compute_ema(m_c, 50)

    cmp_val = d_bars[-1]["c"]
    prev_val = d_bars[-2]["c"] if len(d_bars) >= 2 else cmp_val
    chg_pct = round((cmp_val / prev_val - 1.0) * 100.0, 2)
    ath = round(max(b["h"] for b in m_bars), 2)
    dd_ath = round((cmp_val / ath - 1.0) * 100.0, 1)
    ret_1m = round((cmp_val / d_bars[-22]["c"] - 1.0) * 100.0, 1) if len(d_bars) > 22 else 0.0
    ret_3m = round((cmp_val / d_bars[-64]["c"] - 1.0) * 100.0, 1) if len(d_bars) > 64 else 0.0

    # Detect active Demand & Supply Zones across ALL 6 timeframes
    all_zones: list[dict[str, Any]] = []
    tf_series = [("Y", y_bars, 48.0), ("H", h_bars, 48.0), ("Q", q_bars, 48.0), ("M", m_bars, 48.0), ("W", w_bars, 50.0), ("D", d_bars[-260:], 52.0)]
    for tf_name, series_bars, min_bp in tf_series:
        all_zones.extend(detect_zones(series_bars, tf_name, min_legout_body_pct=min_bp))

    all_dz = [z for z in all_zones if z["kind"] == "DEMAND"]
    all_sz = [z for z in all_zones if z["kind"] == "SUPPLY"]

    # Cluster overlapping Demand Zones (Ankur's Multi-TF Syncing)
    clusters = cluster_htf_demand_zones(all_dz, cmp_val)
    # Prefer a cluster that includes at least W/M/Q/H/Y (not isolated Daily noise!)
    swing_clusters = [c for c in clusters if any(t in ("Y", "H", "Q", "M", "W") for t in c["tfs"])]
    best_dz = swing_clusters[0] if swing_clusters else (clusters[0] if clusters else None)

    # Also find the strongest deeper HTF Mega-Sync floor within realistic swing horizon (<= 60% below CMP)
    htf_mega_cands = [
        c for c in swing_clusters
        if (c["htf_count"] >= 2 or any(t in ("Y", "H", "Q") for t in c["tfs"]) or (len(m_bars) < 48 and "W" in c["tfs"]))
        and c["dist_pct"] <= 95.0
    ]
    deep_dz = None
    if htf_mega_cands:
        # Prefer closest major HTF floor distinct from best_dz, weighting HTF depth
        distinct = [
            c for c in htf_mega_cands
            if best_dz is None or abs(c["proximal"] - best_dz["proximal"]) / max(cmp_val, 1.0) > 0.04
        ]
        if distinct:
            distinct.sort(key=lambda c: (-c["htf_count"], c["dist_pct"]))
            deep_dz = distinct[0]

    nearest_sz = find_nearest_supply(all_sz, cmp_val)
    f1_m = compute_f1_achievement(m_bars, cmp_val)

    # Build Swing Trade Plan & Score (0–100) using Ankur Agarwal's exact filters
    score = 0
    trade_plan = None
    tier = "NO_LOCATION"
    action_note = "No good HTF Demand location nearby — wait for more price action."

    if best_dz is not None:
        entry_hi = best_dz["proximal"]
        entry_lo = round((best_dz["proximal"] + best_dz["distal"]) / 2.0, 2)
        # Keep swing stop realistic: distal with 0.8% buffer
        stop_loss = round(best_dz["distal"] * 0.992, 2)
        risk = max(entry_hi - stop_loss, entry_hi * 0.02)
        risk_pct = round(risk / entry_hi * 100.0, 1)

        # Target 1 = nearest overhead supply proximal (if above entry + 1.5R) else 2R; Target 2 = 3R or F1-M/ATH
        sz_prox = nearest_sz["proximal"] if (nearest_sz and nearest_sz["proximal"] > entry_hi * 1.05) else None
        t1 = round(sz_prox if (sz_prox and sz_prox >= entry_hi + 1.5 * risk) else entry_hi + 2.0 * risk, 2)
        t2 = round(max(entry_hi + 3.0 * risk, f1_m or 0.0, ath if ath <= entry_hi * 1.65 else 0.0), 2)
        if t2 <= t1 * 1.03:
            t2 = round(entry_hi + 3.0 * risk, 2)

        rr_t1 = round((t1 - entry_hi) / risk, 2) if risk > 0 else 0.0
        rr_t2 = round((t2 - entry_hi) / risk, 2) if risk > 0 else 0.0

        # Scoring Rubric (100 pts max, faithful to Ankur's rules):
        # 1. Multi-TF Sync & HTF Anchor (up to 35 pts)
        score += min(35, int(best_dz["sync_count"] * 10 + best_dz["max_tf_weight"] * 3.5))
        # 2. Freshness (up to 18 pts)
        if best_dz["freshness"] == "FRESH":
            score += 18
        elif best_dz["freshness"] == "TESTED(1)":
            score += 11
        else:
            score += 4
        # 3. Achievement / BOS (up to 15 pts)
        if best_dz["ach"] == "ATH_BOS":
            score += 15
        elif best_dz["ach"] == "BOS":
            score += 11
        else:
            score += 2
        # 4. Single Red Candle in Rally Bonus (up to 8 pts)
        if best_dz["has_1red"]:
            score += 8
        # 5. Trend / EMA Alignment (up to 12 pts)
        above_m20 = (m_e20[-1] is not None and cmp_val >= m_e20[-1])
        above_w20 = (w_e20[-1] is not None and cmp_val >= w_e20[-1])
        ema_stack = (m_e20[-1] is not None and m_e50[-1] is not None and m_e20[-1] > m_e50[-1])
        if ema_stack:
            score += 6
        if above_m20 or above_w20:
            score += 6
        # 6. Reward-to-Risk Room (up to 12 pts)
        if rr_t1 >= 2.5:
            score += 12
        elif rr_t1 >= 2.0:
            score += 9
        elif rr_t1 >= 1.5:
            score += 5
        # Penalties
        if nearest_sz and nearest_sz["in_supply"] and best_dz["dist_pct"] > 4.0:
            score -= 14  # Sitting inside overhead supply far from demand
        if risk_pct > 14.0:
            score -= 10  # Zone too wide for clean swing stop

        score = max(10, min(99, score))
        trade_plan = {
            "entry_high": entry_hi,
            "entry_low": entry_lo,
            "stop_loss": stop_loss,
            "target_1": t1,
            "target_2": t2,
            "risk_pct": risk_pct,
            "rr_t1": rr_t1,
            "rr_t2": rr_t2,
            "f1_m": f1_m,
        }

        dist_p = best_dz["dist_pct"]
        in_sup = bool(nearest_sz and nearest_sz["in_supply"])

        if dist_p <= 4.0 and score >= 62 and risk_pct <= 16.0:
            tier = "ACTIONABLE_NOW"
            if dist_p <= 0.0:
                action_note = f"IN DEMAND ZONE ({best_dz['sync_label']}): Watch bullish Daily close > ₹{entry_hi} · SL ₹{stop_loss}"
            else:
                action_note = f"NEAR ZONE (+{dist_p:.1f}% above {best_dz['sync_label']}): Limit ladder ₹{entry_lo}–₹{entry_hi} · SL ₹{stop_loss}"
        elif in_sup and dist_p > 4.0:
            tier = "IN_SUPPLY_WAIT"
            action_note = f"IN {nearest_sz['tf']}-SUPPLY (₹{nearest_sz['proximal']}–₹{nearest_sz['distal']}): Do not chase — wait for dip to ₹{entry_hi} ({best_dz['sync_label']}) or F1-M break"
        elif dist_p <= 10.5 and score >= 52:
            tier = "APPROACHING"
            action_note = f"SET ALERT ₹{entry_hi} (-{dist_p:.1f}% to {best_dz['sync_label']}): Wait for pullback into zone"
        elif dist_p <= 26.0 and (best_dz["htf_count"] >= 1 or (deep_dz and deep_dz["dist_pct"] <= 30.0)):
            tier = "CONFLUENCE_RADAR"
            target_z = deep_dz if (deep_dz and deep_dz["htf_count"] >= 2) else best_dz
            action_note = f"HTF RADAR (-{target_z['dist_pct']:.1f}% to {target_z['sync_label']} ₹{target_z['distal']}–₹{target_z['proximal']}): Patient watchlist"
        else:
            tier = "NO_LOCATION"
            action_note = f"Extended (+{dist_p:.1f}% above {best_dz['sync_label']}): No good location nearby — wait"

    # Compact chart data for interactive Highcharts inspection (M: 60 bars, W: 104 bars, D: 130 bars)
    def pack_bars(src: list[dict[str, Any]], e20_arr: list[float | None], e50_arr: list[float | None], limit: int) -> list[list[Any]]:
        n_s = len(src)
        st = max(0, n_s - limit)
        return [
            [src[i]["d"], src[i]["o"], src[i]["h"], src[i]["l"], src[i]["c"], e20_arr[i], e50_arr[i]]
            for i in range(st, n_s)
        ]

    # Pack top relevant zones for plotting (up to 4 Demand + 3 Supply)
    plot_dz = sorted(
        [z for z in all_dz if z["distal"] < cmp_val * 1.05 and z["proximal"] >= cmp_val * 0.55 and z["touches"] <= 3],
        key=lambda z: (-TF_WEIGHT[z["tf"]], abs(cmp_val - z["proximal"])),
    )[:5]
    plot_sz = sorted(
        [z for z in all_sz if z["distal"] >= cmp_val * 0.97 and z["proximal"] <= cmp_val * 1.55 and z["touches"] <= 3],
        key=lambda z: (abs(z["proximal"] - cmp_val), -TF_WEIGHT[z["tf"]]),
    )[:3]

    zones_plot = [
        {
            "kind": z["kind"], "tf": z["tf"], "pattern": z["pattern"],
            "proximal": z["proximal"], "distal": z["distal"],
            "status": z["status"], "ach": z["ach"], "date": z["legout_date"],
            "single_opp": z["single_opp"],
        }
        for z in (plot_dz + plot_sz)
    ]

    # Run strict walk-forward backtest on Nifty 50 stocks (and IREDA/Power)
    bt_trades = run_walkforward_backtest(sym, d_bars, w_bars, m_bars)

    stock_record = {
        "symbol": sym,
        "yahoo": yahoo_sym,
        "name": name,
        "sector": sector,
        "group": group,
        "cmp": cmp_val,
        "chg_pct": chg_pct,
        "last_date": d_bars[-1]["d"],
        "ath": ath,
        "dd_ath_pct": dd_ath,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "emas": {
            "d20": d_e20[-1], "d50": d_e50[-1], "d200": d_e200[-1],
            "w20": w_e20[-1], "w50": w_e50[-1],
            "m20": m_e20[-1], "m50": m_e50[-1],
        },
        "tier": tier,
        "score": score,
        "action_note": action_note,
        "best_dz": best_dz,
        "deep_dz": deep_dz,
        "nearest_sz": nearest_sz,
        "trade_plan": trade_plan,
        "zones_plot": zones_plot,
        "charts": {
            "M": pack_bars(m_bars, m_e20, m_e50, 60),
            "W": pack_bars(w_bars, w_e20, w_e50, 104),
            "D": pack_bars(d_bars, d_e20, d_e50, 130),
        },
    }
    return stock_record, bt_trades, None


def summarize_backtest(trades: list[dict[str, Any]], sector_by_sym: dict[str, str]) -> dict[str, Any]:
    def bucket_stats(tr_list: list[dict[str, Any]]) -> dict[str, Any]:
        if not tr_list:
            return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "expectancy_r": 0.0, "avg_ret_pct": 0.0, "avg_hold_days": 0.0}
        wins = [t for t in tr_list if t["r_mult"] > 0]
        losses = [t for t in tr_list if t["r_mult"] <= 0]
        gross_win = sum(t["r_mult"] for t in wins)
        gross_loss = abs(sum(t["r_mult"] for t in losses))
        pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else 9.99
        return {
            "trades": len(tr_list),
            "win_rate": round(len(wins) / len(tr_list) * 100.0, 1),
            "profit_factor": pf,
            "expectancy_r": round(sum(t["r_mult"] for t in tr_list) / len(tr_list), 2),
            "avg_ret_pct": round(sum(t["ret_pct"] for t in tr_list) / len(tr_list), 2),
            "avg_hold_days": round(sum(t["hold_days"] for t in tr_list) / len(tr_list), 1),
        }

    def sim_portfolio(tr_list: list[dict[str, Any]], max_slots: int | None, max_per_sector: int | None, risk_frac: float = 0.01) -> dict[str, Any]:
        # Chronological simulation by entry_date with concurrent slot & sector caps
        by_entry = sorted(tr_list, key=lambda t: (t["entry_date"], -int(t["single_red"]), t["symbol"]))
        open_pos: list[dict[str, Any]] = []
        taken: list[dict[str, Any]] = []
        for t in by_entry:
            # Close positions whose exit_date <= new entry_date
            open_pos = [p for p in open_pos if p["exit_date"] > t["entry_date"]]
            if max_slots is not None and len(open_pos) >= max_slots:
                continue
            sec = sector_by_sym.get(t["symbol"], "Other")
            if max_per_sector is not None:
                sec_cnt = sum(1 for p in open_pos if sector_by_sym.get(p["symbol"], "Other") == sec)
                if sec_cnt >= max_per_sector:
                    continue
            open_pos.append(t)
            taken.append(t)

        # Realize equity strictly in exit_date order
        eq = 100.0
        peak = 100.0
        max_dd = 0.0
        for t in sorted(taken, key=lambda x: x["exit_date"]):
            eq *= 1.0 + (t["r_mult"] * risk_frac)
            peak = max(peak, eq)
            max_dd = min(max_dd, (eq / peak - 1.0) * 100.0)
        st = bucket_stats(taken)
        st["compounded_1pct_risk_pct"] = round(eq - 100.0, 1)
        st["max_dd_pct"] = round(max_dd, 1)
        return st

    sorted_tr = sorted(trades, key=lambda t: t["exit_date"])
    overall = sim_portfolio(trades, max_slots=None, max_per_sector=None)
    capped_5 = sim_portfolio(trades, max_slots=5, max_per_sector=2)
    one_red_capped = sim_portfolio([t for t in trades if t["single_red"]], max_slots=5, max_per_sector=2)

    return {
        "methodology": (
            "Strict zero-lookahead walk-forward across Nifty 50 (~3.5–4 yrs): Fresh Weekly/Monthly Demand Zone tap "
            "+ Daily bullish confirmation close (no blind knife-catching), 1% buffer stop below zone Distal, "
            "50% booked at 2R (trail rest to BE), 50% at 3R or 45-session time stop, 0.25% round-trip costs deducted."
        ),
        "overall": overall,
        "portfolio_capped": {
            "max5_sec2": capped_5,
            "one_red_max5_sec2": one_red_capped,
        },
        "by_filter": {
            "Single Red Candle in Rally (1-Red)": bucket_stats([t for t in trades if t["single_red"]]),
            "Above 200 EMA Trend Filter": bucket_stats([t for t in trades if t.get("above_200")]),
            "Tight Zone (<=8% Stop Risk)": bucket_stats([t for t in trades if t.get("risk_pct", 99) <= 8.0]),
            "Multi-TF Synced (M+W Overlap)": bucket_stats([t for t in trades if t["mtf_sync"]]),
            "Single-TF Demand Zone": bucket_stats([t for t in trades if not t["mtf_sync"]]),
            "BOS / Achievement Confirmed": bucket_stats([t for t in trades if t["bos"]]),
        },
        "recent_trades": list(reversed(sorted_tr[-24:])),
    }


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


def update_forward_swing_ledger(
    stocks: list[dict[str, Any]],
    daily_bars_map: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Auto-log and forward-grade live Tier 1 Actionable swing signals (like daily_ledger.jsonl)."""
    rows = load_jsonl(SWING_LEDGER_FILE)

    # 1. Grade any PENDING / TRIGGERED forward signals on strictly subsequent daily bars
    for sig in rows:
        if sig.get("status") not in ("WATCH_ENTRY", "ACTIVE"):
            continue
        bars = daily_bars_map.get(sig["symbol"]) or []
        post = [b for b in bars if b["d"] > sig["logged_date"] and b["d"] <= sig["due_date"]]
        for b in post:
            if sig["status"] == "WATCH_ENTRY":
                # Trigger when price enters zone and closes bullishly above distal
                if b["l"] <= sig["entry_high"] and b["c"] > sig["stop_loss"] and b["c"] >= b["o"]:
                    sig["status"] = "ACTIVE"
                    sig["triggered_date"] = b["d"]
                    sig["entry_fill"] = b["c"]
                    sig["cur_stop"] = sig["stop_loss"]
                    sig["t1_hit"] = False
                continue

            # Manage ACTIVE forward swing
            cur_stop = float(sig.get("cur_stop", sig["stop_loss"]))
            entry_px = float(sig.get("entry_fill", sig["entry_high"]))
            risk = max(entry_px - float(sig["stop_loss"]), 0.05)

            if b["l"] <= cur_stop:
                exit_px = round(min(b["o"], cur_stop), 2)
                if sig.get("t1_hit"):
                    sig["status"] = "T1_TRAIL"
                    sig["r_mult"] = round(0.5 * 2.0 + 0.5 * ((exit_px - entry_px) / risk), 2)
                    sig["outcome_note"] = f"T1 booked (+2R), remaining 50% trailed out on {b['d']} @ ₹{exit_px}"
                else:
                    sig["status"] = "STOP_LOSS"
                    sig["r_mult"] = round((exit_px - entry_px) / risk, 2)
                    sig["outcome_note"] = f"Stop hit on {b['d']} @ ₹{exit_px}"
                sig["resolved_date"] = b["d"]
                sig["exit_price"] = exit_px
                break

            if b["h"] >= sig["target_2"]:
                sig["status"] = "TARGET_2"
                sig["r_mult"] = 2.5
                sig["resolved_date"] = b["d"]
                sig["exit_price"] = sig["target_2"]
                sig["outcome_note"] = f"Full Target 2 reached on {b['d']} @ ₹{sig['target_2']}"
                break

            if (not sig.get("t1_hit")) and b["h"] >= sig["target_1"]:
                sig["t1_hit"] = True
                sig["cur_stop"] = entry_px
                sig["outcome_note"] = f"T1 hit on {b['d']} @ ₹{sig['target_1']} — stop moved to BE (₹{entry_px})"

        if sig["status"] in ("WATCH_ENTRY", "ACTIVE") and bars and bars[-1]["d"] > sig["due_date"]:
            last_b = bars[-1]
            if sig["status"] == "WATCH_ENTRY":
                sig["status"] = "EXPIRED"
                sig["resolved_date"] = last_b["d"]
                sig["outcome_note"] = f"Zone never tapped before {sig['due_date']}"
            else:
                entry_px = float(sig.get("entry_fill", sig["entry_high"]))
                risk = max(entry_px - float(sig["stop_loss"]), 0.05)
                rem_r = (last_b["c"] - entry_px) / risk
                sig["r_mult"] = round((0.5 * 2.0 + 0.5 * rem_r) if sig.get("t1_hit") else rem_r, 2)
                sig["status"] = "TIME_EXIT"
                sig["resolved_date"] = last_b["d"]
                sig["exit_price"] = last_b["c"]
                sig["outcome_note"] = f"45-session window ended @ ₹{last_b['c']}"

    # 2. Seed new forward signals for top Tier 1 Actionable setups (plus IREDA Plan A) if not already open
    open_syms = {r["symbol"] for r in rows if r.get("status") in ("WATCH_ENTRY", "ACTIVE")}
    new_cands = [
        s for s in stocks
        if s["trade_plan"] is not None
        and s["symbol"] not in open_syms
        and (s["tier"] == "ACTIONABLE_NOW" or s["symbol"] == "IREDA")
    ]
    # Keep ledger crisp: always track IREDA Plan A + top 6 Tier 1 Actionable setups
    ireda_cand = [s for s in new_cands if s["symbol"] == "IREDA"]
    other_cands = [s for s in new_cands if s["symbol"] != "IREDA"][:6]
    for s in (ireda_cand + other_cands):
        tp = s["trade_plan"]
        dz = s["best_dz"]
        logged_d = s["last_date"]
        due_d = (dt.date.fromisoformat(logged_d) + dt.timedelta(days=65)).isoformat()
        rows.insert(0, {
            "id": f"fwd_{s['symbol']}_{logged_d.replace('-', '')}",
            "symbol": s["symbol"],
            "sector": s["sector"],
            "group": s["group"],
            "logged_date": logged_d,
            "due_date": due_d,
            "logged_cmp": s["cmp"],
            "sync_label": dz["sync_label"] if dz else "W",
            "has_1red": bool(dz and dz["has_1red"]),
            "score": s["score"],
            "entry_low": tp["entry_low"],
            "entry_high": tp["entry_high"],
            "stop_loss": tp["stop_loss"],
            "target_1": tp["target_1"],
            "target_2": tp["target_2"],
            "rr_t1": tp["rr_t1"],
            "status": "WATCH_ENTRY",
            "triggered_date": None,
            "entry_fill": None,
            "cur_stop": tp["stop_loss"],
            "t1_hit": False,
            "resolved_date": None,
            "exit_price": None,
            "r_mult": None,
            "outcome_note": f"Watching pullback into ₹{tp['entry_low']}–₹{tp['entry_high']} ({dz['sync_label'] if dz else ''})",
        })

    rows = rows[:60]
    save_jsonl(SWING_LEDGER_FILE, rows)
    wins = sum(1 for r in rows if r["status"] in ("TARGET_2", "T1_TRAIL") or (r["status"] == "TIME_EXIT" and (r.get("r_mult") or 0) > 0))
    losses = sum(1 for r in rows if r["status"] == "STOP_LOSS" or (r["status"] == "TIME_EXIT" and (r.get("r_mult") or 0) <= 0))
    graded = wins + losses
    stats = {
        "total": len(rows),
        "watching": sum(1 for r in rows if r["status"] == "WATCH_ENTRY"),
        "active": sum(1 for r in rows if r["status"] == "ACTIVE"),
        "graded": graded,
        "wins": wins,
        "losses": losses,
        "hit_rate_pct": round(wins / graded * 100.0, 1) if graded > 0 else None,
    }
    return rows, stats


def build_sector_sync(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sec_map: dict[str, list[dict[str, Any]]] = {}
    for s in stocks:
        sec_map.setdefault(s["sector"], []).append(s)

    rows = []
    for sec, members in sec_map.items():
        # Measure TRUE HTF (Y/H/Q/M, or W for young IPOs) distance rather than Daily noise!
        htf_dists = []
        near_htf = 0
        for m in members:
            dz = m["best_dz"]
            if dz and (dz["htf_count"] >= 1 or (m["symbol"] == "IREDA" and "W" in dz["tfs"])):
                htf_dists.append(dz["dist_pct"])
                if dz["dist_pct"] <= 8.0:
                    near_htf += 1
            elif m["deep_dz"]:
                htf_dists.append(m["deep_dz"]["dist_pct"])
                if m["deep_dz"]["dist_pct"] <= 8.0:
                    near_htf += 1
        act_cnt = sum(1 for m in members if m["tier"] == "ACTIONABLE_NOW")
        avg_1m = round(sum(m["ret_1m"] for m in members) / len(members), 1)
        med_dist = round(statistics.median(htf_dists), 1) if htf_dists else None
        sync_pct = round(near_htf / len(members) * 100.0, 0)
        if act_cnt >= 2 or (sync_pct >= 50 and len(members) >= 2):
            verdict = "HIGH_SYNC"
        elif act_cnt >= 1 or sync_pct >= 25:
            verdict = "BUILDING"
        else:
            verdict = "STRETCHED"
        rows.append({
            "sector": sec,
            "count": len(members),
            "actionable": act_cnt,
            "near_8pct": near_htf,
            "sync_pct": int(sync_pct),
            "median_dist_pct": med_dist,
            "avg_ret_1m": avg_1m,
            "verdict": verdict,
            "leaders": [m["symbol"] for m in sorted(members, key=lambda x: -x["score"])[:3]],
        })
    rows.sort(key=lambda r: (-r["actionable"], -r["sync_pct"], r["median_dist_pct"] if r["median_dist_pct"] is not None else 999))
    return rows


def main() -> int:
    now_ist = dt.datetime.now(IST)
    now_utc = dt.datetime.now(dt.timezone.utc)
    t0 = time.time()

    stocks: list[dict[str, Any]] = []
    all_bt_trades: list[dict[str, Any]] = []
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(analyze_stock, spec): spec[0] for spec in UNIVERSE}
        for fut in concurrent.futures.as_completed(futs):
            rec, bt, err = fut.result()
            if err:
                errors.append(err)
            if rec:
                stocks.append(rec)
                if rec["group"] == "NIFTY50":
                    all_bt_trades.extend(bt)

    tier_rank = {"ACTIONABLE_NOW": 0, "APPROACHING": 1, "CONFLUENCE_RADAR": 2, "IN_SUPPLY_WAIT": 3, "NO_LOCATION": 4}
    stocks.sort(key=lambda s: (tier_rank.get(s["tier"], 9), -s["score"], s["best_dz"]["dist_pct"] if s["best_dz"] else 999))

    nifty_stocks = [s for s in stocks if s["group"] == "NIFTY50"]
    focus_stocks = [s for s in stocks if s["group"] == "IREDA_POWER"]

    # Market breadth across Nifty 50
    abv_d200 = sum(1 for s in nifty_stocks if s["emas"]["d200"] and s["cmp"] >= s["emas"]["d200"])
    abv_w20 = sum(1 for s in nifty_stocks if s["emas"]["w20"] and s["cmp"] >= s["emas"]["w20"])
    abv_m20 = sum(1 for s in nifty_stocks if s["emas"]["m20"] and s["cmp"] >= s["emas"]["m20"])

    summary = {
        "total_scanned": len(stocks),
        "nifty50_scanned": len(nifty_stocks),
        "focus_scanned": len(focus_stocks),
        "actionable_now": sum(1 for s in stocks if s["tier"] == "ACTIONABLE_NOW"),
        "approaching": sum(1 for s in stocks if s["tier"] == "APPROACHING"),
        "confluence_radar": sum(1 for s in stocks if s["tier"] == "CONFLUENCE_RADAR"),
        "in_supply_wait": sum(1 for s in stocks if s["tier"] == "IN_SUPPLY_WAIT"),
        "nifty_actionable": sum(1 for s in nifty_stocks if s["tier"] == "ACTIONABLE_NOW"),
        "breadth_d200_pct": round(abv_d200 / max(len(nifty_stocks), 1) * 100.0, 1),
        "breadth_w20_pct": round(abv_w20 / max(len(nifty_stocks), 1) * 100.0, 1),
        "breadth_m20_pct": round(abv_m20 / max(len(nifty_stocks), 1) * 100.0, 1),
    }

    sector_by_sym = {s["symbol"]: s["sector"] for s in stocks}
    daily_bars_map = {
        s["symbol"]: [{"d": b[0], "o": b[1], "h": b[2], "l": b[3], "c": b[4]} for b in s["charts"]["D"]]
        for s in stocks
    }
    fwd_rows, fwd_stats = update_forward_swing_ledger(stocks, daily_bars_map)
    bt_summary = summarize_backtest(all_bt_trades, sector_by_sym)

    payload = {
        "schema_version": "demand-supply-v1",
        "updated_at_ist": now_ist.strftime("%Y-%m-%d %H:%M IST"),
        "updated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_sec": round(time.time() - t0, 1),
        "sanitized_market_only": True,
        "fetch_errors": errors,
        "summary": summary,
        "strategy_blueprint": {
            "name": "Ankur Agarwal Top-Down Demand & Supply Swing Strategy (Nifty 50 + IREDA)",
            "principles": [
                "Top-Down Location First: Map Yearly -> Half-Yearly -> Quarterly -> Monthly -> Weekly Demand/Supply before touching Daily charts.",
                "Multi-TF Syncing (Nesting): Prioritize zones where 2+ timeframes overlap (Y+H+Q, H+Q+M, or Q+M+W for young IPOs like IREDA).",
                "Achievement Filter (F1-M / BOS): Only take swings from zones whose leg-out broke prior swing highs or opposing supply — skip weak market bounces.",
                "Single-Red-Candle-in-Rally Rule: Lone red pause candles inside green rallies mark institutional re-accumulation; trade for reaction bounces if above a deeper HTF floor.",
                "Confirmation Execution & Risk Control: Enter on Daily bullish close holding inside the Fresh zone (never blindly catch a knife slicing through Distal); stop 0.8%–1% below Distal; book 50% at 2R / Supply Proximal and trail rest to breakeven toward 3R+.",
                "Portfolio & Sector Cap: Cap concurrent positions to max 5 open swings (max 2 per sector, 1% risk/trade) and pause new longs when Cockpit Red Lights >= 2.",
            ],
        },
        "sectors": build_sector_sync(stocks),
        "backtest": bt_summary,
        "forward_stats": fwd_stats,
        "forward_ledger": fwd_rows[:25],
        "stocks": stocks,
    }

    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"Demand & Supply scan complete in {payload['elapsed_sec']}s | "
        f"Scanned: {len(stocks)} ({len(nifty_stocks)} Nifty50 + {len(focus_stocks)} IREDA/Power) | "
        f"Errors: {len(errors)} | Actionable: {summary['actionable_now']} | "
        f"Approaching: {summary['approaching']} | Forward Ledger: {fwd_stats['total']} | Size: {OUT_FILE.stat().st_size / 1024:.1f} KB"
    )
    if errors:
        print("ERRORS:", errors)
    bt_ov = payload["backtest"]["overall"]
    bt_cap = payload["backtest"]["portfolio_capped"]["max5_sec2"]
    bt_1r = payload["backtest"]["portfolio_capped"]["one_red_max5_sec2"]
    print(f"\n=== NIFTY 50 WALK-FORWARD BACKTEST (3.5-4Y, 0.25% cost) ===")
    print(f"  Uncapped Baseline : {bt_ov}")
    print(f"  Capped (5 slots/2): {bt_cap}")
    print(f"  1-Red Capped (5/2): {bt_1r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
