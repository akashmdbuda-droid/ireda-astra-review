(function () {
  "use strict";

  let STATE = null;
  let ACTIVE_TF = "daily";
  let BAR_WINDOW = 90;
  let HOVER_IDX = -1;
  const CUSTOM_DOWNSIDE = [];

  const esc = (v) => {
    if (v === null || v === undefined) return "—";
    return String(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  };

  const fmtNum = (v, d = 2) => {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "unavailable";
    return Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  };

  const fmtSign = (v, prefix = "", suffix = "", d = 2) => {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "unavailable";
    const n = Number(v);
    const sign = n > 0 ? "+" : "";
    return `${sign}${prefix}${fmtNum(n, d)}${suffix}`;
  };

  const shortTs = (ts) => {
    if (!ts) return "—";
    const s = String(ts);
    return s.length > 16 ? s.slice(0, 16).replace("T", " ") : s;
  };

  const postureLabel = (p) => {
    const map = {
      ABOVE_FAST_AND_SLOW_MA: "Above Fast & Slow MA",
      BELOW_FAST_ABOVE_SLOW_MA: "Below Fast / Above Slow MA",
      ABOVE_FAST_BELOW_SLOW_MA: "Above Fast / Below Slow MA",
      BELOW_FAST_AND_SLOW_MA: "Below Fast & Slow MA",
    };
    return map[p] || String(p || "UNAVAILABLE");
  };

  const postureBadge = (p) => {
    if (p === "ABOVE_FAST_AND_SLOW_MA") return "badge-fresh";
    if (p === "BELOW_FAST_AND_SLOW_MA") return "badge-failed";
    if (p === "BELOW_FAST_ABOVE_SLOW_MA" || p === "ABOVE_FAST_BELOW_SLOW_MA") return "badge-provisional";
    return "badge-unavailable";
  };

  const badgeClass = (st) => {
    const s = String(st || "").toLowerCase();
    if (["current", "fresh", "eligible", "confirmed", "verified", "verified_broker", "bullish", "bullish_breakout", "available", "live_quote_supplied"].includes(s)) return "badge-fresh";
    if (["stale", "provisional", "provisional_bar", "experimental", "diagnostic_only", "pending", "mixed_bullish_tilt", "mixed_bearish_tilt", "range", "degraded", "insufficient_sample"].includes(s)) return "badge-provisional";
    if (["failed", "invalidated", "bearish", "bearish_breakdown", "rejected_future", "unverified_or_flagged"].includes(s)) return "badge-failed";
    return "badge-unavailable";
  };

  function wrapTable(label, tableHtml) {
    return `<div tabindex="0" role="region" aria-label="${esc(label)}" class="table-wrapper">${tableHtml}</div>`;
  }

  function renderHeaderAndExecutive(state) {
    const meta = state.meta || {};
    const eh = state.evidence_health || {};
    const mo = state.market_overview || {};
    const st = mo.stock || {};
    const lq = mo.live_quote || {};
    const tfs = mo.timeframes_summary || [];

    document.getElementById("instrumentTitle").textContent = `${meta.instrument || "UNKNOWN"}`;

    const heroPrice = lq.last_price ?? st.close;
    const headerChip = document.getElementById("headerPriceChip");
    if (heroPrice !== null && heroPrice !== undefined) {
      const chg = lq.last_price !== null && lq.last_price !== undefined ? lq.net_change_pct : st.daily_change_pct;
      const chgStr = chg !== null && chg !== undefined ? ` (${fmtSign(chg, "", "%", 2)})` : "";
      const tag = lq.last_price !== null && lq.last_price !== undefined ? "PROV" : "CLOSE";
      headerChip.innerHTML = `₹${fmtNum(heroPrice)} <span class="${(chg ?? 0) >= 0 ? "pos-text" : "neg-text"}">${esc(chgStr)}</span> <span class="badge ${lq.last_price != null ? "badge-provisional" : "badge-fresh"}">${tag}</span>`;
    } else {
      headerChip.textContent = "Price unavailable";
    }

    const runBadge = document.getElementById("runStatusBadge");
    runBadge.textContent = String(eh.run_status || "unavailable").replace(/_/g, " ").toUpperCase();
    runBadge.className = `badge ${badgeClass(eh.run_status)}`;

    const freshBadge = document.getElementById("freshnessBadge");
    freshBadge.textContent = `FRESHNESS: ${String(eh.freshness || "unknown").toUpperCase()}`;
    freshBadge.className = `badge ${badgeClass(eh.freshness)}`;

    const shortRun = meta.run_id ? String(meta.run_id).slice(0, 8) : "none";
    const shortHash = meta.market_hash ? String(meta.market_hash).slice(0, 10) : "none";
    document.getElementById("runMetaStrip").innerHTML = `
      <span>As-Of: ${esc(shortTs(eh.last_update))}</span>
      <span>Session: ${esc(eh.session_status || "unknown")}</span>
      <span>Provider: ${esc(meta.provider)}</span>
      <span>Run: ${esc(shortRun)}…</span>
      <span>Hash: ${esc(shortHash)}…</span>
    `;

    // Global banner with plain-English quality breakdown
    const banner = document.getElementById("globalHealthBanner");
    const qf = eh.quality_failures || [];
    const qs = eh.quality_summary || {};
    const qParts = [];
    if (qs.price_diff) qParts.push(`${qs.price_diff} cross-source price diffs`);
    if (qs.missing_session) qParts.push(`${qs.missing_session} session/interval gaps`);
    if (qs.corporate_action) qParts.push(`${qs.corporate_action} dividend/split adjustment`);
    if (qs.intraday_provisional) qParts.push(`provisional intraday bar`);

    if (!eh.is_current || eh.run_status === "failed" || eh.run_status === "unavailable" || eh.run_status === "stale") {
      banner.className = eh.run_status === "diagnostic_only" ? "alert-banner warn" : "alert-banner";
      const summaryText = qParts.length ? qParts.join(" · ") : `${qf.length} quality checks flagged`;
      banner.innerHTML = `
        <div>
          <strong>${eh.run_status === "diagnostic_only" ? "DIAGNOSTIC RUN (NON-PUBLISHABLE)" : String(eh.run_status).toUpperCase()}:</strong>
          ${esc(summaryText)}. Indicators &amp; charts are shown for inspection; trade triggers stay abstained until checks clear.
        </div>
        <a href="#evidenceHealthPanel" class="banner-link">Inspect ${qf.length} Checks ↓</a>
      `;
    } else if (qf.length > 0) {
      banner.className = "alert-banner warn";
      banner.innerHTML = `<div><strong>CURRENT WITH SCOPED WARNINGS (${qf.length}):</strong> ${esc(qf.map((f) => f.code).join(", "))}</div><a href="#evidenceHealthPanel" class="banner-link">Details ↓</a>`;
    } else {
      banner.className = "alert-banner ok";
      banner.textContent = `VALIDATED RUN CURRENT · Hash Verified=${eh.verify_hash_ok} · As-Of=${shortTs(eh.last_update)}`;
    }

    // Executive Hero Panel
    document.getElementById("heroObservedMeta").textContent = `Latest Bar: ${shortTs(eh.observed_latest_bar)} | Daily Close: ${shortTs(st.observed_at)}`;
    const ind = st.indicators || {};
    const totalFvgActive = tfs.reduce((acc, t) => acc + (t.active_fvg_bull || 0) + (t.active_fvg_bear || 0), 0);
    const bullCount = tfs.filter((t) => t.posture === "ABOVE_FAST_AND_SLOW_MA").length;
    const bearCount = tfs.filter((t) => t.posture === "BELOW_FAST_AND_SLOW_MA").length;
    const mixedCount = tfs.length - bullCount - bearCount;

    const closeCardHtml = `
      <div class="subcard subcard-highlight">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="kv-label">Completed Daily Close</span>
          <span class="badge badge-fresh">${st.observed_at ? esc(String(st.observed_at).slice(0, 10)) : "UNAVAILABLE"}</span>
        </div>
        <div class="kv-hero" style="margin-top:6px;">${st.close !== null && st.close !== undefined ? `₹${fmtNum(st.close)}` : "unavailable"}</div>
        <div class="muted" style="margin-top:4px;">
          ${st.daily_change !== null && st.daily_change !== undefined
            ? `<span class="${st.daily_change >= 0 ? "pos-text" : "neg-text"} mono">${fmtSign(st.daily_change, "₹")} (${fmtSign(st.daily_change_pct, "", "%")})</span> vs prior close · `
            : ""}
          Posture: <strong>${esc(postureLabel(st.posture))}</strong>
        </div>
        <div class="mini-stats">
          <div><span class="mini-stat-label">EMA 21 / 50</span><span class="mini-stat-val">₹${fmtNum(ind.ema21)} / ₹${fmtNum(ind.ema50)}</span></div>
          <div><span class="mini-stat-label">EMA 200</span><span class="mini-stat-val">${ind.ema200 !== null && ind.ema200 !== undefined ? `₹${fmtNum(ind.ema200)}` : "unavailable"}</span></div>
          <div><span class="mini-stat-label">Daily RSI(14)</span><span class="mini-stat-val ${Number(ind.rsi14) >= 70 ? "warn-text" : ""}">${ind.rsi14 !== null && ind.rsi14 !== undefined ? fmtNum(ind.rsi14) : "unavailable"}</span></div>
          <div><span class="mini-stat-label">ATR(14) / Open RVOL</span><span class="mini-stat-val">${ind.atr14 !== null && ind.atr14 !== undefined ? `₹${fmtNum(ind.atr14)}` : "n/a"} · ${st.opening_volume_ratio !== null && st.opening_volume_ratio !== undefined ? `${fmtNum(st.opening_volume_ratio)}×` : "n/a"}</span></div>
        </div>
      </div>
    `;

    const provDeltaCls = (lq.net_change ?? 0) >= 0 ? "pos-text" : "neg-text";
    const liveCardHtml = `
      <div class="subcard">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="kv-label">Intraday Live / Provisional</span>
          <span class="badge ${badgeClass(lq.status)}">${esc(lq.source || lq.status || "unavailable")}</span>
        </div>
        <div class="kv-hero" style="margin-top:6px;">${lq.last_price !== null && lq.last_price !== undefined ? `₹${fmtNum(lq.last_price)}` : "unavailable"}</div>
        <div class="muted" style="margin-top:4px;">
          ${lq.net_change !== null && lq.net_change !== undefined
            ? `<span class="${provDeltaCls} mono">${fmtSign(lq.net_change, "₹")} (${fmtSign(lq.net_change_pct, "", "%")})</span> vs prev close · `
            : ""}
          At ${esc(shortTs(lq.observed_at))}
        </div>
        <div class="mini-stats">
          <div><span class="mini-stat-label">Day Range (L – H)</span><span class="mini-stat-val">${lq.day_low !== null && lq.day_high !== null ? `₹${fmtNum(lq.day_low)} – ₹${fmtNum(lq.day_high)}` : "unavailable"}</span></div>
          <div><span class="mini-stat-label">VWAP / Avg Price</span><span class="mini-stat-val">${lq.average_price !== null ? `₹${fmtNum(lq.average_price)}` : "n/a (bar mode)"}</span></div>
          <div><span class="mini-stat-label">52W Range</span><span class="mini-stat-val">${lq.week_52_low !== null && lq.week_52_high !== null ? `₹${fmtNum(lq.week_52_low)} – ₹${fmtNum(lq.week_52_high)}` : "n/a"}</span></div>
          <div><span class="mini-stat-label">Volume</span><span class="mini-stat-val">${lq.volume !== null ? fmtNum(lq.volume, 0) : "unavailable"}</span></div>
        </div>
      </div>
    `;

    const scList = state.scenarios || [];
    const perf = state.performance || {};
    const summaryPoints = [];
    if (tfs.length) {
      summaryPoints.push(`<li><strong>Timeframe Split:</strong> ${bullCount} bullish MA posture, ${mixedCount} mixed/transition, ${bearCount} bearish across ${tfs.length} timeframes.</li>`);
    }
    if (ind.ema200 && st.close) {
      const dist200 = ((st.close - ind.ema200) / ind.ema200) * 100;
      summaryPoints.push(`<li><strong>Key Overhead / Support:</strong> Daily close ₹${fmtNum(st.close)} sits <span class="mono">${fmtSign(dist200, "", "%")}</span> vs 200-EMA (₹${fmtNum(ind.ema200)}), above EMA21 (₹${fmtNum(ind.ema21)}).</li>`);
    }
    summaryPoints.push(`<li><strong>Active Fair Value Gaps:</strong> ${totalFvgActive} untouched/partial FVGs tracked across M/W/D/60m/15m.</li>`);
    summaryPoints.push(`<li><strong>Scenario Gate:</strong> ${scList.length ? `${scList.length} scenario card(s) active/monitored` : `Abstained cleanly (${esc(eh.run_status)} / missing verified external consensus)`}.</li>`);
    if (perf.status && perf.status !== "unavailable") {
      summaryPoints.push(`<li><strong>Walk-Forward Backtest (After Costs):</strong> Net ${fmtSign(perf.total_net_return_pct, "", "%")} (n=${esc(perf.sample_size)}, Win=${fmtNum(perf.win_rate_pct)}%) vs Buy &amp; Hold ${fmtSign((perf.baselines || {}).buy_and_hold?.net_return_pct, "", "%")}.</li>`);
    }

    const digestCardHtml = `
      <div class="subcard">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="kv-label">What Is Happening (Factual Readout)</span>
          <span class="badge ${badgeClass(meta.assessment_kind === "diagnostic_only" ? "diagnostic_only" : eh.run_status)}">${esc(meta.assessment_kind || "publishable")}</span>
        </div>
        <ul style="margin:8px 0 0;padding-left:18px;font-size:0.8rem;display:flex;flex-direction:column;gap:5px;">
          ${summaryPoints.join("")}
        </ul>
      </div>
    `;

    document.getElementById("heroOverviewGrid").innerHTML = closeCardHtml + liveCardHtml + digestCardHtml;
  }

  function renderTimeframeMatrix(state) {
    const tfs = (state.market_overview || {}).timeframes_summary || [];
    const el = document.getElementById("tfMatrixCards");
    if (!tfs.length) {
      el.innerHTML = `<div class="subcard muted">No multi-timeframe summaries available for this run.</div>`;
      return;
    }
    el.innerHTML = tfs
      .map((t) => {
        const active = t.timeframe === ACTIVE_TF ? "is-active" : "";
        const provTag = t.provisional_present
          ? `<span class="badge badge-provisional">Prov ${t.provisional_close !== null ? `₹${fmtNum(t.provisional_close)}` : ""}</span>`
          : `<span class="badge badge-fresh">${esc(t.period_status)}</span>`;
        const macdColor = t.macd !== null && t.macd_signal !== null ? (t.macd >= t.macd_signal ? "pos-text" : "neg-text") : "";
        return `
          <button type="button" class="tf-card ${active}" data-jump-tf="${esc(t.timeframe)}">
            <div class="tf-card-head">
              <strong>${esc(t.label)} <span class="muted mono tf-bar-count">(${esc(t.completed_bars)} bars)</span></strong>
              ${provTag}
            </div>
            <div class="tf-price-row">
              <span class="kv-val tf-price">${t.close !== null ? `₹${fmtNum(t.close)}` : "n/a"}</span>
              <span class="badge ${postureBadge(t.posture)}">${esc(postureLabel(t.posture))}</span>
            </div>
            <div class="mini-stats" style="margin-top:2px;">
              <div><span class="mini-stat-label">${esc(t.fast_ma_label)} / ${esc(t.slow_ma_label)}</span><span class="mini-stat-val">${fmtNum(t.fast_ma)} / ${fmtNum(t.slow_ma)}</span></div>
              <div><span class="mini-stat-label">RSI(${esc(t.rsi_period || 14)}) / MACD</span><span class="mini-stat-val ${macdColor}">${t.rsi !== null ? fmtNum(t.rsi) : "n/a"} · ${t.macd !== null ? fmtSign(t.macd) : "n/a"}</span></div>
              <div><span class="mini-stat-label">Active FVGs</span><span class="mini-stat-val"><span class="pos-text">${esc(t.active_fvg_bull)}↑</span> / <span class="neg-text">${esc(t.active_fvg_bear)}↓</span> (${esc(t.total_fvgs)})</span></div>
              <div><span class="mini-stat-label">ATR(14) / BB%</span><span class="mini-stat-val">${t.atr_14 !== null ? `₹${fmtNum(t.atr_14)}` : "n/a"} · ${t.bb_width_pct !== null ? `${fmtNum(t.bb_width_pct, 1)}%` : "n/a"}</span></div>
            </div>
          </button>
        `;
      })
      .join("");

    el.querySelectorAll("[data-jump-tf]").forEach((card) => {
      card.addEventListener("click", () => {
        switchTimeframe(card.dataset.jumpTf);
        document.getElementById("chartPanel").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function renderEvidenceHealth(state) {
    const meta = state.meta || {};
    const eh = state.evidence_health || {};
    const qf = eh.quality_failures || [];
    const qs = eh.quality_summary || {};
    document.getElementById("evidenceUpdateMeta").textContent = `Last update: ${shortTs(eh.last_update)} | Latest Bar: ${shortTs(eh.observed_latest_bar)}`;

    const provKeys = Object.entries(eh.provisional_periods || {})
      .filter(([, v]) => v && (v.provisional_present || v.period_status === "provisional" || v.period_status === "unknown"))
      .map(([k, v]) => `${k}:${v.period_status}`);

    document.getElementById("evidenceHealthGrid").innerHTML = `
      <div class="subcard"><div class="kv-label">Provider &amp; Reconciliation</div><div class="kv-val">${esc(eh.provider)}</div><div class="muted">Reconcil: ${esc(eh.reconciliation_status)} · HashOK: ${esc(eh.verify_hash_ok)}</div></div>
      <div class="subcard"><div class="kv-label">Session &amp; Calendar</div><div class="kv-val">${esc(eh.session_status)}</div><div class="muted">Cal: ${esc(eh.calendar_source)}</div></div>
      <div class="subcard"><div class="kv-label">Missing External Domains</div><div class="kv-val">${(eh.missing_inputs || []).length}</div><div class="muted">${esc((eh.missing_inputs || []).join(", ") || "none")}</div></div>
      <div class="subcard"><div class="kv-label">Quality Checks &amp; Provisional</div><div class="kv-val">${qf.length} flagged</div><div class="muted">Prov: ${esc(provKeys.join(", ") || "none")}</div></div>
    `;

    const chipSummary = Object.entries(qs)
      .filter(([, count]) => Number(count) > 0)
      .map(([k, count]) => `<span class="reason-chip">${esc(k)}: <strong>${esc(count)}</strong></span>`)
      .join("");

    const qRows = qf.length
      ? wrapTable(
          "Quality Failures",
          `<table><thead><tr><th>Code</th><th>Severity</th><th>Scope</th><th>Message</th></tr></thead><tbody>${qf
            .map((q) => `<tr><td class="mono">${esc(q.code)}</td><td><span class="badge ${badgeClass(q.severity === "error" ? "failed" : "provisional")}">${esc(q.severity)}</span></td><td>${esc(q.scope)}</td><td>${esc(q.message)}</td></tr>`)
            .join("")}</tbody></table>`
        )
      : `<p class="muted">No quality failures reported.</p>`;

    const pRows = wrapTable(
      "Provisional Periods",
      `<table><thead><tr><th>Timeframe</th><th>Status</th><th>Provisional</th><th>Excluded</th><th>Period Window</th><th>Reason</th></tr></thead><tbody>${Object.entries(eh.provisional_periods || {})
        .map(([tf, p]) => `<tr><td class="mono">${esc(tf)}</td><td>${esc(p.period_status)}</td><td>${p.provisional_present ? "Yes" : "No"}</td><td>${esc(p.provisional_excluded)}</td><td class="mono">${esc(shortTs(p.period_start))} → ${esc(shortTs(p.period_end))}</td><td>${esc(p.completion_reason || "—")}</td></tr>`)
        .join("")}</tbody></table>`
    );

    document.getElementById("evidenceDetailsBody").innerHTML = `
      <div class="reason-chips">${chipSummary || '<span class="muted">No categorized issues</span>'}</div>
      <p class="mono muted" style="font-size:0.72rem;margin-top:8px;">
        Run: ${esc(meta.run_id)} | MarketHash: ${esc(meta.market_hash)}<br/>
        EvidenceFP: ${esc(meta.evidence_fingerprint)} | RawHash: ${esc(meta.raw_evidence_hash)}<br/>
        ValidationReceipt: ${esc((meta.validation_receipt || {}).digest || "none")}
      </p>
      ${qRows}
      ${pRows}
      <p class="muted" style="margin-top:8px;"><strong>Limitations:</strong> ${esc((eh.limitations || []).join(" · ") || "none")}</p>
    `;
  }

  function renderMarketOverview(state) {
    const mo = state.market_overview || {};
    const b = mo.benchmark || {};
    const s = mo.sector || {};
    const st = mo.stock || {};
    const ind = st.indicators || {};

    const extCard = (title, obj) => `
      <div class="subcard">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="kv-label">${esc(title)}</span>
          <span class="badge ${badgeClass(obj.status)}">${esc(obj.status || "unavailable")}</span>
        </div>
        <div class="kv-val" style="margin-top:6px;">${esc(obj.direction || "UNAVAILABLE")}</div>
        <div class="muted" style="margin-top:4px;">${esc(obj.name || "")} ${obj.value !== null && obj.value !== undefined ? `· ${fmtNum(obj.value)}` : ""} ${obj.change_pct !== null && obj.change_pct !== undefined ? `(${fmtSign(obj.change_pct, "", "%")})` : ""}</div>
        <div class="muted" style="font-size:0.75rem;margin-top:6px;">${esc(obj.note || "External domain evidence not supplied.")}</div>
        <details><summary>Provenance</summary><div class="mono" style="font-size:0.72rem;">Source: ${esc(obj.source)}<br/>Observed: ${esc(obj.observed_at)}<br/>Note: ${esc(obj.note)}</div></details>
      </div>
    `;

    const stockCard = `
      <div class="subcard">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
          <span class="kv-label">Stock (${esc(st.instrument)})</span>
          <span class="badge ${badgeClass(st.status)}">${esc(st.status || "unavailable")}</span>
        </div>
        <div class="kv-val" style="margin-top:6px;">${esc(st.direction !== "UNAVAILABLE" ? st.direction : postureLabel(st.posture))}</div>
        <div class="muted" style="margin-top:4px;">
          Close: <strong class="mono">${st.close !== null && st.close !== undefined ? `₹${fmtNum(st.close)}` : "unavailable"}</strong>
          · RSI14: <span class="mono">${ind.rsi14 !== null && ind.rsi14 !== undefined ? fmtNum(ind.rsi14) : "n/a"}</span>
          · RVOL: <span class="mono">${st.rvol ?? st.opening_volume_ratio ?? "n/a"}</span>
        </div>
        <div class="muted" style="font-size:0.75rem;margin-top:6px;">${esc(st.note)}</div>
        <details><summary>Family Balance (Deduplicated)</summary><div class="mono" style="font-size:0.72rem;">Bull: ${esc(st.bullish_family_count)} | Bear: ${esc(st.bearish_family_count)} | Neutral: ${esc(st.neutral_family_count)}</div></details>
      </div>
    `;
    const ed = mo.external_details || {};
    const fund = ed.company_fundamentals || {};
    const mac = ed.macro || {};
    const nw = ed.news || {};
    const vix = mac.india_vix || {};
    const usdinr = mac.usdinr || {};
    const brent = mac.brent_crude || {};
    const us10 = mac.us10y || {};
    const mcapCr = fund.market_cap ? `₹${fmtNum(Number(fund.market_cap) / 1e7, 0)} Cr` : "n/a";
    const headlinesHtml = (nw.headlines || []).slice(0, 5)
      .map((h) => `<li>${esc(h.title)} <span class="muted">(${esc(h.publisher || "")} · ${esc(shortTs(h.published_at))})</span></li>`)
      .join("");
    const extDrawer = (fund.status === "verified" || mac.status === "verified" || nw.status === "verified")
      ? `<details style="margin-top:10px;"><summary>Verified Macro, Fundamentals &amp; News (${esc((nw.headlines || []).length)} headlines · VIX ${vix.value ?? "n/a"})</summary>
          <div class="grid-3" style="margin-top:8px;">
            <div class="subcard"><div class="kv-label">Macro Pulse (${esc(mac.source)})</div><div class="mono" style="font-size:0.76rem;margin-top:4px;">India VIX: ${vix.value ?? "n/a"} (${fmtSign(vix.change_pct, "", "%")})<br/>USD/INR: ${usdinr.value ?? "n/a"} (${fmtSign(usdinr.change_pct, "", "%")})<br/>Brent: $${brent.value ?? "n/a"} (${fmtSign(brent.change_pct, "", "%")})<br/>US 10Y: ${us10.value ?? "n/a"}%</div></div>
            <div class="subcard"><div class="kv-label">Fundamentals (${esc(fund.source)})</div><div class="mono" style="font-size:0.76rem;margin-top:4px;">MCap: ${esc(mcapCr)}<br/>PE: ${fund.pe_ratio ? fmtNum(fund.pe_ratio) : "n/a"} · PB: ${fund.pb_ratio ? fmtNum(fund.pb_ratio) : "n/a"}<br/>ROE: ${fund.roe ? `${fmtNum(fund.roe * 100, 1)}%` : "n/a"} · DivYld: ${fund.dividend_yield ?? "n/a"}%<br/>D/E: ${fund.debt_to_equity ? fmtNum(fund.debt_to_equity, 1) : "n/a"}</div></div>
            <div class="subcard"><div class="kv-label">Latest Headlines (${esc(nw.source)})</div><ul style="margin:6px 0 0;padding-left:16px;font-size:0.74rem;display:flex;flex-direction:column;gap:4px;">${headlinesHtml || "<li>No recent headlines within cutoff.</li>"}</ul></div>
          </div>
        </details>`
      : "";

    document.getElementById("marketOverviewGrid").innerHTML = extCard("Benchmark", b) + extCard("Sector", s) + stockCard;
    let extContainer = document.getElementById("marketExternalDetails");
    if (!extContainer) {
      extContainer = document.createElement("div");
      extContainer.id = "marketExternalDetails";
      document.getElementById("marketOverviewPanel").appendChild(extContainer);
    }
    extContainer.innerHTML = extDrawer;
  }

  function visibleBarsForActiveTf() {
    const chartData = (STATE && STATE.chart) || {};
    const tf = (chartData.timeframes || {})[ACTIVE_TF] || {};
    const allBars = tf.bars || [];
    const bars = BAR_WINDOW > 0 && allBars.length > BAR_WINDOW ? allBars.slice(-BAR_WINDOW) : allBars;
    return { tf, allBars, bars };
  }

  function updateInspectBar(bar, tfKey) {
    const barEl = document.getElementById("chartInspectBar");
    if (!bar) {
      barEl.innerHTML = `Tap or move across the <strong>${esc(tfKey.toUpperCase())}</strong> chart to inspect candle OHLCV, EMAs, and RSI.`;
      return;
    }
    const provTag = bar.is_provisional ? `<span class="badge badge-provisional">PROVISIONAL</span>` : `<span class="badge badge-fresh">COMPLETED</span>`;
    barEl.innerHTML = `${esc(shortTs(bar.t))} ${provTag} &nbsp; O:<strong>${fmtNum(bar.o)}</strong> H:<strong>${fmtNum(bar.h)}</strong> L:<strong>${fmtNum(bar.l)}</strong> C:<strong>${fmtNum(bar.c)}</strong> V:${fmtNum(bar.v, 0)} &nbsp;|&nbsp; FastMA:${fmtNum(bar.ema_fast)} SlowMA:${fmtNum(bar.ema_slow)} RSI:${fmtNum(bar.rsi)}`;
  }

  function getChartPadding(W) {
    return W < 520 ? { left: 8, right: 58, top: 18, bottom: 26 } : { left: 14, right: 72, top: 20, bottom: 26 };
  }

  function drawChart() {
    if (!STATE) return;
    const canvas = document.getElementById("candleCanvas");
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const W = Math.max(280, Math.floor(rect.width || 600));
    const H = Math.max(280, Math.floor(rect.height || 380));
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.fillStyle = "#0c111b";
    ctx.fillRect(0, 0, W, H);

    const chartData = STATE.chart || {};
    const { tf, allBars, bars } = visibleBarsForActiveTf();

    document.getElementById("chartBarMeta").textContent = `${ACTIVE_TF.toUpperCase()} · Showing ${bars.length}/${allBars.length} bars · Completed: ${tf.completed_bars || 0} · Prov: ${tf.provisional_bars || 0}`;

    if (!bars.length) {
      ctx.fillStyle = "#94a3b8";
      ctx.font = "600 13px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`TIMEFRAME UNAVAILABLE (${ACTIVE_TF.toUpperCase()}): ${tf.reason || tf.status || "no bars"}`, W / 2, H / 2);
      updateInspectBar(null, ACTIVE_TF);
      return;
    }

    const pad = getChartPadding(W);
    const volH = Math.round(H * 0.16);
    const priceH = H - pad.top - pad.bottom - volH - 10;
    const plotW = W - pad.left - pad.right;

    let minP = Infinity;
    let maxP = -Infinity;
    let maxV = 0;
    for (const b of bars) {
      if (b.l !== null && b.l < minP) minP = b.l;
      if (b.h !== null && b.h > maxP) maxP = b.h;
      if (b.v !== null && b.v > maxV) maxV = b.v;
    }

    const togBb = document.getElementById("togBb").checked;
    const togEma = document.getElementById("togEma").checked;
    const togFvgActive = document.getElementById("togFvgActive").checked;
    const togFvgFilled = document.getElementById("togFvgFilled").checked;
    const togGeom = document.getElementById("togGeom").checked;
    const togFib = document.getElementById("togFib").checked;
    const togAvwap = document.getElementById("togAvwap").checked;

    if (togBb) {
      for (const b of bars) {
        if (b.bb_lower !== null && b.bb_lower < minP) minP = b.bb_lower;
        if (b.bb_upper !== null && b.bb_upper > maxP) maxP = b.bb_upper;
      }
    }
    if (!Number.isFinite(minP) || !Number.isFinite(maxP) || maxP <= minP) {
      minP = 90;
      maxP = 130;
    }
    const pMargin = (maxP - minP) * 0.08;
    minP -= pMargin;
    maxP += pMargin;

    const xFor = (i) => pad.left + ((i + 0.5) / bars.length) * plotW;
    const yFor = (p) => pad.top + ((maxP - p) / (maxP - minP)) * priceH;

    // Grid & Right Price Axis
    ctx.strokeStyle = "#192234";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#8a95ab";
    ctx.font = `${W < 520 ? 10 : 11}px Consolas, monospace`;
    ctx.textAlign = "left";
    for (let g = 0; g <= 5; g++) {
      const val = minP + ((maxP - minP) * g) / 5;
      const y = yFor(val);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(W - pad.right, y);
      ctx.stroke();
      ctx.fillText(val.toFixed(1), W - pad.right + 5, y + 3);
    }

    // X-Axis Time Labels
    const labelCount = W < 520 ? 4 : 6;
    ctx.fillStyle = "#7e8da8";
    ctx.textAlign = "center";
    for (let s = 0; s < labelCount; s++) {
      const idx = Math.min(bars.length - 1, Math.floor((s / Math.max(1, labelCount - 1)) * (bars.length - 1)));
      const rawT = String(bars[idx].t || "");
      const lbl = ACTIVE_TF === "15m" || ACTIVE_TF === "60m" ? rawT.slice(5, 16).replace("T", " ") : rawT.slice(0, 10);
      ctx.fillText(lbl, xFor(idx), H - 7);
    }
    ctx.textAlign = "left";

    // Fibonacci overlay
    if (togFib) {
      const fibMap = chartData.fibonacci || {};
      const fib = ACTIVE_TF === "daily" ? (fibMap.daily_185 || fibMap.daily_45) : (ACTIVE_TF === "weekly" ? fibMap.weekly_90 : (ACTIVE_TF === "monthly" ? fibMap.monthly_37 : null));
      if (fib && fib.levels) {
        for (const [lvl, price] of Object.entries(fib.levels)) {
          if (price === null || price === undefined || price < minP || price > maxP) continue;
          const y = yFor(price);
          ctx.save();
          ctx.strokeStyle = lvl === "61.8" ? "rgba(251, 191, 36, 0.55)" : "rgba(56, 189, 248, 0.35)";
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(pad.left, y);
          ctx.lineTo(W - pad.right, y);
          ctx.stroke();
          ctx.fillStyle = "rgba(12, 17, 27, 0.85)";
          const lblTxt = `Fib ${lvl}% (${Number(price).toFixed(1)})`;
          ctx.fillRect(pad.left + 4, y - 12, ctx.measureText(lblTxt).width + 6, 12);
          ctx.fillStyle = "#93c5fd";
          ctx.fillText(lblTxt, pad.left + 6, y - 2);
          ctx.restore();
        }
      }
    }

    // FVG zones
    const timeToIdx = new Map();
    bars.forEach((b, i) => timeToIdx.set(String(b.t).slice(0, 16), i));
    const findStartIdx = (tStr) => {
      if (!tStr) return 0;
      const key = String(tStr).slice(0, 16);
      if (timeToIdx.has(key)) return timeToIdx.get(key);
      for (let i = 0; i < bars.length; i++) {
        if (String(bars[i].t) >= String(tStr)) return i;
      }
      return 0;
    };

    for (const fvg of tf.fvgs || []) {
      const isAct = Boolean(fvg.active);
      if (isAct && !togFvgActive) continue;
      if (!isAct && !togFvgFilled) continue;
      if (fvg.bottom === null || fvg.top === null) continue;
      if (fvg.top < minP || fvg.bottom > maxP) continue;
      const sIdx = findStartIdx(fvg.formed_at);
      const x1 = xFor(sIdx);
      const x2 = W - pad.right;
      const y1 = yFor(Math.min(maxP, fvg.top));
      const y2 = yFor(Math.max(minP, fvg.bottom));
      ctx.save();
      const bull = fvg.direction === "bullish";
      ctx.fillStyle = isAct ? (bull ? "rgba(45, 212, 191, 0.14)" : "rgba(248, 113, 113, 0.14)") : "rgba(148, 163, 184, 0.07)";
      ctx.strokeStyle = isAct ? (bull ? "rgba(45, 212, 191, 0.55)" : "rgba(248, 113, 113, 0.55)") : "rgba(148, 163, 184, 0.3)";
      if (!isAct) ctx.setLineDash([3, 3]);
      ctx.fillRect(x1, y1, Math.max(4, x2 - x1), Math.max(2, y2 - y1));
      ctx.strokeRect(x1, y1, Math.max(4, x2 - x1), Math.max(2, y2 - y1));
      ctx.restore();
    }

    // AVWAP & POC
    if (togAvwap && ACTIVE_TF === "daily") {
      const vp = chartData.volume_profile || {};
      if (vp.status === "available" && vp.poc !== null) {
        const y = yFor(vp.poc);
        if (y >= pad.top && y <= pad.top + priceH) {
          ctx.save();
          ctx.strokeStyle = "#f472b6";
          ctx.setLineDash([6, 3]);
          ctx.beginPath();
          ctx.moveTo(pad.left, y);
          ctx.lineTo(W - pad.right, y);
          ctx.stroke();
          ctx.fillStyle = "#f472b6";
          ctx.fillText(`POC ${Number(vp.poc).toFixed(1)}`, pad.left + 8, y - 4);
          ctx.restore();
        }
      }
      const av = chartData.avwap || {};
      const lines = [];
      if (av.trough_avwap && av.trough_avwap.trough_avwap) lines.push({ label: "Trough AVWAP", v: av.trough_avwap.trough_avwap, c: "#22d3ee" });
      for (const p of av.peak_avwaps || []) {
        if (p.peak_avwap) lines.push({ label: `Peak ${p.window}D`, v: p.peak_avwap, c: "#fb923c" });
      }
      for (const ln of lines) {
        if (ln.v < minP || ln.v > maxP) continue;
        const y = yFor(ln.v);
        ctx.save();
        ctx.strokeStyle = ln.c;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();
        ctx.fillStyle = ln.c;
        ctx.fillText(`${ln.label} ${Number(ln.v).toFixed(1)}`, Math.max(pad.left + 8, W - pad.right - 115), y - 3);
        ctx.restore();
      }
    }

    // Bollinger Bands
    if (togBb) {
      const drawSeries = (field, color) => {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        let started = false;
        bars.forEach((b, i) => {
          if (b[field] === null || b[field] === undefined || b.is_provisional) return;
          const x = xFor(i);
          const y = yFor(b[field]);
          if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.restore();
      };
      drawSeries("bb_upper", "rgba(56, 189, 248, 0.5)");
      drawSeries("bb_lower", "rgba(56, 189, 248, 0.5)");
    }

    // EMAs / SMAs
    if (togEma) {
      const drawMa = (field, color, width = 1.4) => {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        let started = false;
        bars.forEach((b, i) => {
          if (b[field] === null || b[field] === undefined || b.is_provisional) return;
          const x = xFor(i);
          const y = yFor(b[field]);
          if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.restore();
      };
      drawMa("ema_fast", "#38bdf8", 1.4);
      drawMa("ema_slow", "#f59e0b", 1.4);
      if (ACTIVE_TF === "daily") drawMa("ema200", "#c084fc", 1.5);
    }

    // Geometry & Trendlines
    if (togGeom && tf.trendlines && tf.trendlines.status === "fitted") {
      const drawTl = (tl, color) => {
        if (!tl || !Array.isArray(tl.anchors) || tl.anchors.length < 2) return;
        const first = tl.anchors[0];
        const sIdx = findStartIdx(first.date);
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(xFor(sIdx), yFor(first.price));
        ctx.lineTo(xFor(bars.length - 1), yFor(tl.projected_current));
        ctx.stroke();
        ctx.restore();
      };
      drawTl(tf.trendlines.upper, "#f87171");
      drawTl(tf.trendlines.lower, "#34d399");
    }

    // Candlesticks & Volume
    const bw = Math.max(2, Math.min(13, (plotW / bars.length) * 0.68));
    let firstProvIdx = -1;
    bars.forEach((b, i) => {
      if (b.is_provisional && firstProvIdx === -1) firstProvIdx = i;
      const x = xFor(i);
      const isUp = (b.c ?? 0) >= (b.o ?? 0);
      const col = b.is_provisional ? "#fbbf24" : (isUp ? "#2dd4bf" : "#f87171");

      if (b.h !== null && b.l !== null) {
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.1;
        ctx.beginPath();
        ctx.moveTo(x, yFor(b.h));
        ctx.lineTo(x, yFor(b.l));
        ctx.stroke();
      }
      if (b.o !== null && b.c !== null) {
        const yO = yFor(b.o);
        const yC = yFor(b.c);
        const top = Math.min(yO, yC);
        const bh = Math.max(1.5, Math.abs(yC - yO));
        if (b.is_provisional) {
          ctx.save();
          ctx.fillStyle = "rgba(251, 191, 36, 0.28)";
          ctx.strokeStyle = "#fbbf24";
          ctx.setLineDash([2, 2]);
          ctx.fillRect(x - bw / 2, top, bw, bh);
          ctx.strokeRect(x - bw / 2, top, bw, bh);
          ctx.restore();
        } else {
          ctx.fillStyle = col;
          ctx.fillRect(x - bw / 2, top, bw, bh);
        }
      }
      if (maxV > 0 && b.v !== null) {
        const vh = (b.v / maxV) * volH;
        const vy = H - pad.bottom - vh;
        ctx.fillStyle = b.is_provisional ? "rgba(251, 191, 36, 0.45)" : (isUp ? "rgba(45, 212, 191, 0.32)" : "rgba(248, 113, 113, 0.32)");
        ctx.fillRect(x - bw / 2, vy, bw, vh);
      }
    });

    if (firstProvIdx !== -1) {
      const px = xFor(firstProvIdx) - bw;
      ctx.save();
      ctx.strokeStyle = "#fbbf24";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(px, pad.top);
      ctx.lineTo(px, H - pad.bottom);
      ctx.stroke();
      ctx.fillStyle = "#fbbf24";
      ctx.font = "bold 10px Consolas, monospace";
      ctx.fillText("PROV", Math.max(pad.left + 4, px - 32), pad.top + 11);
      ctx.restore();
    }

    // Current Last Price Tag on Right Axis
    const lastBar = bars[bars.length - 1];
    if (lastBar && lastBar.c !== null) {
      const ly = Math.max(pad.top + 8, Math.min(pad.top + priceH - 8, yFor(lastBar.c)));
      ctx.save();
      ctx.strokeStyle = lastBar.is_provisional ? "rgba(251, 191, 36, 0.55)" : "rgba(56, 189, 248, 0.55)";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(pad.left, ly);
      ctx.lineTo(W - pad.right, ly);
      ctx.stroke();
      ctx.fillStyle = lastBar.is_provisional ? "#fbbf24" : "#38bdf8";
      ctx.fillRect(W - pad.right + 2, ly - 9, pad.right - 4, 18);
      ctx.fillStyle = "#0a0f18";
      ctx.font = "bold 10px Consolas, monospace";
      ctx.fillText(Number(lastBar.c).toFixed(1), W - pad.right + 6, ly + 3);
      ctx.restore();
    }

    // Crosshair
    if (HOVER_IDX >= 0 && HOVER_IDX < bars.length) {
      const hx = xFor(HOVER_IDX);
      ctx.save();
      ctx.strokeStyle = "rgba(226, 232, 240, 0.45)";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hx, pad.top);
      ctx.lineTo(hx, H - pad.bottom);
      ctx.stroke();
      ctx.restore();
      updateInspectBar(bars[HOVER_IDX], ACTIVE_TF);
    } else {
      updateInspectBar(lastBar, ACTIVE_TF);
    }
  }

  function renderChartDetails(state) {
    const ch = state.chart || {};
    const tf = (ch.timeframes || {})[ACTIVE_TF] || {};
    const av = ch.avwap || {};
    const vp = ch.volume_profile || {};
    const fibs = ch.fibonacci || {};

    const avRows = (av.peak_avwaps || [])
      .map((a) => `<tr><td>Peak ${esc(a.window)}D</td><td class="mono">${fmtNum(a.peak_avwap)}</td><td class="mono">${esc(a.anchor_at)}</td><td>${esc(a.anchor_rule)}</td><td>${a.material_difference_detected ? "Yes" : "No"}</td></tr>`)
      .join("");
    const tAv = av.trough_avwap || {};
    const tRow = tAv.status === "available"
      ? `<tr><td>Trough ${esc(tAv.window)}D</td><td class="mono">${fmtNum(tAv.trough_avwap)}</td><td class="mono">${esc(tAv.anchor_at)}</td><td>${esc(tAv.anchor_rule)}</td><td>—</td></tr>`
      : "";

    const fibRows = Object.entries(fibs)
      .filter(([, f]) => f && f.levels)
      .map(([k, f]) => `<tr><td class="mono">${esc(k)}</td><td>${esc(f.orientation || f.sequence)}</td><td class="mono">${fmtNum(f.swing_low)} → ${fmtNum(f.swing_high)}</td><td class="mono">38.2%: ${fmtNum(f.levels["38.2"])} | 50%: ${fmtNum(f.levels["50.0"])} | 61.8%: ${fmtNum(f.levels["61.8"])}</td></tr>`)
      .join("");

    const fvgRows = (tf.fvgs || [])
      .slice(-12)
      .map((g) => `<tr><td class="mono">${esc(g.id)}</td><td>${esc(g.direction)}</td><td class="mono">${fmtNum(g.bottom)} – ${fmtNum(g.top)}</td><td><span class="badge ${g.active ? "badge-fresh" : "badge-unavailable"}">${esc(g.state)}</span></td><td class="mono">${esc(shortTs(g.formed_at))}</td></tr>`)
      .join("");

    const patRows = (tf.patterns || [])
      .map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.direction)}</td><td>${esc(p.status)}</td><td class="mono">Break: ${fmtNum(p.breakout_level)} / Inv: ${fmtNum(p.invalidation_level)}</td></tr>`)
      .join("");

    document.getElementById("chartDetailsBody").innerHTML = `
      <div class="subcard" style="margin-top:8px;">
        <div class="kv-label">Volume Profile &amp; Detectors</div>
        <div class="mono" style="font-size:0.75rem;">Status: ${esc(vp.status)} | POC: ${fmtNum(vp.poc)} | VAL: ${fmtNum(vp.val)} | VAH: ${fmtNum(vp.vah)}</div>
        <div class="muted" style="font-size:0.72rem;margin-top:4px;">Withdrawn Detectors: ${esc(Object.keys(tf.withdrawn_detectors || {}).join(", ") || "none")}</div>
      </div>
      ${wrapTable("AVWAP Anchors", `<table><thead><tr><th>AVWAP Anchor</th><th>Value</th><th>Anchor At</th><th>Rule</th><th>Diff</th></tr></thead><tbody>${tRow}${avRows || "<tr><td colspan='5' class='muted'>Unavailable (eligible packet required)</td></tr>"}</tbody></table>`)}
      ${wrapTable("Fibonacci Levels", `<table><thead><tr><th>Fib Window</th><th>Orientation</th><th>Endpoints</th><th>Retracements</th></tr></thead><tbody>${fibRows || "<tr><td colspan='4' class='muted'>Unavailable (eligible packet required)</td></tr>"}</tbody></table>`)}
      ${wrapTable("Fair Value Gaps", `<table><thead><tr><th>FVG ID (${esc(ACTIVE_TF)})</th><th>Direction</th><th>Range</th><th>State</th><th>Formed At</th></tr></thead><tbody>${fvgRows || "<tr><td colspan='5' class='muted'>No FVGs</td></tr>"}</tbody></table>`)}
      ${wrapTable("Validated Geometry", `<table><thead><tr><th>Geometry (${esc(ACTIVE_TF)})</th><th>Direction</th><th>Status</th><th>Levels</th></tr></thead><tbody>${patRows || "<tr><td colspan='4' class='muted'>No validated pattern detected</td></tr>"}</tbody></table>`)}
    `;
  }

  function renderScenarios(state) {
    const items = state.scenarios || [];
    const eh = state.evidence_health || {};
    if (!items.length) {
      document.getElementById("scenariosContainer").innerHTML = `
        <div class="subcard">
          <span class="badge badge-unavailable">ABSTAINED / FAIL-CLOSED</span>
          <p class="muted" style="margin:8px 0 0;">
            No conditional breakout/range scenarios emitted because the run status is <strong>${esc(eh.run_status)}</strong> (${esc((eh.quality_failures || []).length)} quality check(s) flagged). Directional triggers remain withheld to prevent false signals on unverified reconciliation data.
          </p>
        </div>
      `;
      return;
    }
    document.getElementById("scenariosContainer").innerHTML = items
      .map(
        (sc) => `
      <div class="subcard" style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;">
          <strong>${esc(sc.name)} <span class="badge badge-neutral">${esc(sc.horizon)}</span></strong>
          <span>
            <span class="badge ${badgeClass(sc.status)}">${esc(sc.status)}</span>
            <span class="badge badge-unavailable">Δ: ${esc(sc.change_since_previous)}</span>
          </span>
        </div>
        <div style="margin-top:6px;">
          <div><strong>Confirm (${esc(sc.logical_operator)}):</strong> ${esc((sc.confirmation_conditions || []).join(" ; ") || sc.condition)}</div>
          <div><strong>Invalidation:</strong> ${esc(sc.invalidation_condition)}</div>
          <div class="muted mono" style="font-size:0.72rem;margin-top:3px;">Activated: ${esc(sc.activated_at || "unactivated")} | Expires: ${esc(sc.expires_at)} (${esc(sc.expires_after)})</div>
        </div>
        <details><summary>Families, Specs &amp; Anchors</summary><div class="mono" style="font-size:0.72rem;">Supporting: ${esc((sc.supporting_families || []).join(", "))}<br/>Conflicting: ${esc((sc.conflicting_families || []).join(", ") || "none")}<br/>Trigger: ${esc(JSON.stringify(sc.trigger_spec))}<br/>Invalidation: ${esc(JSON.stringify(sc.invalidation_spec))}</div></details>
      </div>`
      )
      .join("");
  }

  function renderForecasts(state) {
    const fc = state.forecasts || {};
    const badge = document.getElementById("forecastOverallBadge");
    badge.textContent = String(fc.status || "unavailable").toUpperCase();
    badge.className = `badge ${badgeClass(fc.status)}`;

    const items = fc.items || [];
    document.getElementById("forecastsContainer").innerHTML = items
      .map((f) => {
        const minReq = f.required_min_samples || 30;
        const driftInline = f.drift_status && f.drift_status !== "unknown" && f.drift_status !== "unavailable" ? ` | Drift: ${esc(f.drift_status)}` : "";
        return `
      <div class="subcard" style="margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;">
          <strong>${esc(f.name)} (${esc(f.horizon_sessions)}D)</strong>
          <span class="badge ${badgeClass(f.calibration_status)}">${esc(f.calibration_status)}</span>
        </div>
        <div class="mono" style="margin-top:6px;">Probability: <strong>${esc(f.probability_display)}</strong> · n=${esc(f.sample_size)}/${esc(minReq)} min</div>
        <div class="muted" style="font-size:0.75rem;margin-top:3px;">Uncertainty: ${esc(f.uncertainty)}${driftInline}</div>
        <div class="muted" style="font-size:0.75rem;margin-top:3px;">${esc(f.event_definition)}</div>
        <details><summary>Calibration &amp; Ledger Notes</summary><div class="mono" style="font-size:0.72rem;">Cutoff: ${esc(f.training_cutoff)} | Drift: ${esc(f.drift_status)} | Brier: ${esc(f.brier_score)} | LogLoss: ${esc(f.log_loss)} | Revisions: ${esc(f.revision_count)}<br/>Notes: ${esc(f.notes)}</div></details>
      </div>`;
      })
      .join("");
  }

  function renderPosition(state) {
    const pos = state.position_exposure || {};
    const badge = document.getElementById("holdingsBadge");
    badge.textContent = String(pos.holdings_status || "unavailable").toUpperCase();
    badge.className = `badge ${badgeClass(pos.holdings_status)}`;

    document.getElementById("positionSummary").innerHTML = `
      <div class="grid-2">
        <div class="subcard">
          <div class="kv-label">Verified Holdings (${esc(pos.holdings_source)})</div>
          <div class="kv-val">${pos.quantity !== null && pos.quantity !== undefined ? `${fmtNum(pos.quantity, 0)} sh` : "not supplied"}</div>
          <div class="muted">Cost Basis: ${pos.cost_basis !== null && pos.cost_basis !== undefined ? `₹${fmtNum(pos.cost_basis)}` : "not supplied"}</div>
        </div>
        <div class="subcard">
          <div class="kv-label">Completed-Close vs Quote P&amp;L</div>
          <div class="kv-val">${pos.candle_close_pnl !== null && pos.candle_close_pnl !== undefined ? `₹${fmtNum(pos.candle_close_pnl)} (${fmtNum(pos.candle_close_pnl_pct)}%)` : (pos.candle_close_price !== null ? `Close ₹${fmtNum(pos.candle_close_price)}` : "unavailable")}</div>
          <div class="muted">Quote (${esc(pos.quote_status)}): ${pos.quote_price !== null && pos.quote_price !== undefined ? `₹${fmtNum(pos.quote_price)}` : "unavailable"}${pos.quote_pnl !== null && pos.quote_pnl !== undefined ? ` · P&L ₹${fmtNum(pos.quote_pnl)} (${fmtNum(pos.quote_pnl_pct)}%)` : ""}</div>
        </div>
      </div>
      <div class="muted" style="font-size:0.74rem;margin-top:6px;">${esc(pos.decoupling_note)}</div>
    `;
    renderDownsideResults();
  }

  function renderDownsideResults() {
    const pos = (STATE && STATE.position_exposure) || {};
    const st = (STATE && STATE.market_overview && STATE.market_overview.stock) || {};
    const el = document.getElementById("downsideResults");
    if (!CUSTOM_DOWNSIDE.length) {
      el.innerHTML = `<p class="muted" style="margin:6px 0 0;font-size:0.78rem;">No downside scenarios entered yet.</p>`;
      return;
    }
    const qty = Number(pos.quantity || 0);
    const refP = Number(pos.quote_price || pos.candle_close_price || st.provisional_price || st.close || 0);
    const cost = Number(pos.cost_basis || 0);
    const rows = CUSTOM_DOWNSIDE.map((s) => {
      const scenarioPrice = s.mode === "pct" ? refP * (1 + s.val / 100) : s.val;
      const shockPct = refP > 0 ? ((scenarioPrice - refP) / refP) * 100 : 0;
      const pnlFromRef = qty > 0 && refP > 0 ? qty * (scenarioPrice - refP) : null;
      const pnlFromCost = qty > 0 && cost > 0 ? qty * (scenarioPrice - cost) : null;
      return `<tr>
        <td class="mono">₹${fmtNum(scenarioPrice)}</td>
        <td class="mono">${fmtSign(shockPct, "", "%")}</td>
        <td class="mono">${pnlFromRef !== null ? `₹${fmtNum(pnlFromRef)}` : "qty not supplied"}</td>
        <td class="mono">${pnlFromCost !== null ? `₹${fmtNum(pnlFromCost)}` : "unavailable"}</td>
      </tr>`;
    }).join("");
    el.innerHTML = wrapTable("Downside Scenarios", `<table><thead><tr><th>Scenario Price</th><th>Shock vs Ref</th><th>P&amp;L vs Current</th><th>P&amp;L vs Cost</th></tr></thead><tbody>${rows}</tbody></table>`);
  }

  function renderAlerts(state) {
    const al = state.alerts || {};
    document.getElementById("alertsMeta").textContent = `Shown: ${al.deduplicated_count || 0} | Suppressed: ${al.suppressed_duplicates || 0}`;
    const items = al.items || [];
    if (!items.length) {
      document.getElementById("alertsContainer").innerHTML = `<div class="subcard muted">No material scenario transition alerts recorded for this run. Unchanged ticks are suppressed by deduplication.</div>`;
      return;
    }
    document.getElementById("alertsContainer").innerHTML = items
      .slice(0, 20)
      .map((ev) => {
        const ctxLabel = ev.scenario_id || (ev.horizon && ev.horizon !== "n/a" ? ev.horizon : ev.severity || "alert");
        const bodyHtml = (ev.new_state || ev.previous_state)
          ? `${esc(ev.previous_state || "init")} → <strong>${esc(ev.new_state)}</strong> · ${esc(ev.reason)}`
          : `${esc(ev.reason || ev.severity)}`;
        return `
      <div class="timeline-item ${esc(ev.severity)}">
        <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <strong>${esc(ev.event_type)} <span class="muted">(${esc(ctxLabel)})</span></strong>
          <span class="mono muted" style="font-size:0.72rem;">${esc(shortTs(ev.timestamp))}</span>
        </div>
        <div>${bodyHtml}</div>
        <details><summary>Audit IDs</summary><div class="mono" style="font-size:0.72rem;">Event: ${esc(ev.event_id)} | Run: ${esc(ev.run_id)} | Hash: ${esc(ev.market_hash)}</div></details>
      </div>`;
      })
      .join("");
  }

  function renderPerformance(state) {
    const perf = state.performance || {};
    const badge = document.getElementById("perfStatusBadge");
    badge.textContent = String(perf.status || "unavailable").toUpperCase();
    badge.className = `badge ${badgeClass(perf.status)}`;

    const bl = perf.baselines || {};
    const maxAbsRet = Math.max(
      1,
      Math.abs(Number(perf.total_net_return_pct || 0)),
      Math.abs(Number((bl.buy_and_hold || {}).net_return_pct || 0)),
      Math.abs(Number((bl.benchmark || {}).net_return_pct || 0)),
      Math.abs(Number((bl.simple_rule || {}).net_return_pct || 0))
    );

    const barHtml = (ret) => {
      if (ret === null || ret === undefined) return "";
      const pct = Math.min(100, Math.round((Math.abs(Number(ret)) / maxAbsRet) * 100));
      const color = Number(ret) >= 0 ? "var(--bull)" : "var(--bear)";
      return `<div class="bar-track"><div class="bar-fill" style="inline-size:${pct}%;background:${color};"></div></div>`;
    };

    const blRow = (label, b) => `
      <tr>
        <td>${esc(label)}</td>
        <td><span class="badge ${badgeClass(b.status)}">${esc(b.status)}</span></td>
        <td class="mono">${b.net_return_pct !== null && b.net_return_pct !== undefined ? `${fmtSign(b.net_return_pct, "", "%")}${barHtml(b.net_return_pct)}` : "unavailable"}</td>
        <td class="mono">${b.max_drawdown_pct !== null && b.max_drawdown_pct !== undefined ? `${fmtNum(b.max_drawdown_pct)}%` : "unavailable"}</td>
      </tr>`;

    const stratRow = perf.total_net_return_pct !== null && perf.total_net_return_pct !== undefined
      ? blRow(`Strategy (${perf.hypothesis_id || "tested"})`, { status: perf.status, net_return_pct: perf.total_net_return_pct, max_drawdown_pct: perf.max_drawdown_pct })
      : "";

    document.getElementById("performanceContainer").innerHTML = `
      <div class="grid-4">
        <div class="subcard"><div class="kv-label">Net Return / Expectancy</div><div class="kv-val ${Number(perf.total_net_return_pct ?? perf.net_expectancy ?? 0) >= 0 ? "pos-text" : "neg-text"}">${perf.total_net_return_pct !== null && perf.total_net_return_pct !== undefined ? fmtSign(perf.total_net_return_pct, "", "%") : (perf.net_expectancy !== null ? fmtNum(perf.net_expectancy, 2) : "unavailable")}</div><div class="muted">Expectancy: ${perf.net_expectancy !== null ? `₹${fmtNum(perf.net_expectancy)}` : "n/a"} · n=${esc(perf.sample_size)}</div></div>
        <div class="subcard"><div class="kv-label">Win Rate &amp; Profit Factor</div><div class="kv-val">${perf.win_rate_pct !== null && perf.win_rate_pct !== undefined ? `${fmtNum(perf.win_rate_pct)}%` : "unavailable"}</div><div class="muted">PF: ${perf.profit_factor !== null ? fmtNum(perf.profit_factor, 2) : "n/a"} · MaxDD: ${perf.max_drawdown_pct !== null ? `${fmtNum(perf.max_drawdown_pct)}%` : "n/a"}</div></div>
        <div class="subcard"><div class="kv-label">Turnover &amp; Exposure</div><div class="kv-val">${perf.turnover !== null ? `${fmtNum(perf.turnover, 2)}×` : "unavailable"}</div><div class="muted">Exposure: ${perf.exposure_pct !== null ? `${fmtNum(perf.exposure_pct)}%` : "n/a"} · Tail: ${perf.tail_loss_pct !== null ? `${fmtNum(perf.tail_loss_pct)}%` : "n/a"}</div></div>
        <div class="subcard"><div class="kv-label">Deflated Sharpe / Budget</div><div class="kv-val">${perf.deflated_sharpe !== null ? fmtNum(perf.deflated_sharpe, 3) : "unavailable"}</div><div class="muted">Search Trials: ${esc(perf.search_budget ?? "n/a")}</div></div>
      </div>
      ${wrapTable("Baseline Comparison", `<table><thead><tr><th>Comparison Series</th><th>Status</th><th>Net Return (After Costs)</th><th>Max Drawdown</th></tr></thead><tbody>${stratRow}${blRow("Stock Buy & Hold", bl.buy_and_hold || {})}${blRow("Benchmark / Sector", bl.benchmark || {})}${blRow("Simple Rule Baseline", bl.simple_rule || {})}</tbody></table>`)}
      <p class="muted" style="margin-top:8px;font-size:0.76rem;">${esc(perf.notes)} | Cost Model: ${esc(perf.cost_model)}</p>
    `;
  }

  function switchTimeframe(tfKey) {
    if (!tfKey) return;
    ACTIVE_TF = tfKey;
    HOVER_IDX = -1;
    document.querySelectorAll(".tf-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.tf === tfKey);
    });
    document.querySelectorAll("[data-jump-tf]").forEach((c) => {
      c.classList.toggle("is-active", c.dataset.jumpTf === tfKey);
    });
    drawChart();
    if (STATE) renderChartDetails(STATE);
  }

  function renderAll(state) {
    STATE = state;
    renderHeaderAndExecutive(state);
    renderTimeframeMatrix(state);
    renderEvidenceHealth(state);
    renderMarketOverview(state);
    drawChart();
    renderChartDetails(state);
    renderScenarios(state);
    renderForecasts(state);
    renderPosition(state);
    renderAlerts(state);
    renderPerformance(state);
  }

  function bindEvents() {
    document.querySelectorAll(".tf-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchTimeframe(btn.dataset.tf));
    });

    document.querySelectorAll(".zoom-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".zoom-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        BAR_WINDOW = Number(btn.dataset.bars || 0);
        HOVER_IDX = -1;
        drawChart();
      });
    });

    ["togEma", "togBb", "togFvgActive", "togFvgFilled", "togGeom", "togFib", "togAvwap"].forEach((id) => {
      document.getElementById(id).addEventListener("change", drawChart);
    });

    const canvas = document.getElementById("candleCanvas");
    const inspectAtClientX = (clientX) => {
      if (!STATE) return;
      const { bars } = visibleBarsForActiveTf();
      if (!bars.length) return;
      const rect = canvas.getBoundingClientRect();
      const pad = getChartPadding(rect.width);
      const plotW = Math.max(1, rect.width - pad.left - pad.right);
      const x = clientX - rect.left;
      const idx = Math.max(0, Math.min(bars.length - 1, Math.floor(((x - pad.left) / plotW) * bars.length)));
      if (idx !== HOVER_IDX) {
        HOVER_IDX = idx;
        drawChart();
      }
    };

    canvas.addEventListener("pointerdown", (e) => inspectAtClientX(e.clientX));
    canvas.addEventListener("pointermove", (e) => {
      if (e.pointerType === "mouse" || e.buttons > 0) inspectAtClientX(e.clientX);
    });
    canvas.addEventListener("pointerleave", (e) => {
      if (e.pointerType === "mouse") {
        HOVER_IDX = -1;
        drawChart();
      }
    });

    document.getElementById("addDownsideBtn").addEventListener("click", () => {
      const pctStr = document.getElementById("shockPctInput").value.trim();
      const prStr = document.getElementById("targetPriceInput").value.trim();
      if (pctStr !== "" && Number.isFinite(Number(pctStr))) {
        CUSTOM_DOWNSIDE.push({ mode: "pct", val: Number(pctStr) });
      } else if (prStr !== "" && Number.isFinite(Number(prStr)) && Number(prStr) > 0) {
        CUSTOM_DOWNSIDE.push({ mode: "price", val: Number(prStr) });
      }
      renderDownsideResults();
    });

    document.getElementById("clearDownsideBtn").addEventListener("click", () => {
      CUSTOM_DOWNSIDE.length = 0;
      renderDownsideResults();
    });

    window.addEventListener("resize", drawChart);
  }

  async function boot() {
    bindEvents();
    try {
      const resp = await fetch("./dashboard_snapshot.json", { cache: "no-store" });
      const data = await resp.json();
      renderAll(data);
    } catch (err) {
      document.getElementById("globalHealthBanner").className = "alert-banner";
      document.getElementById("globalHealthBanner").textContent = `Failed to load ./dashboard_snapshot.json: ${err}`;
    }
  }

  boot();
})();
