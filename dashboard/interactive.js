(function () {
  const CFG = window.__subsidyFilter;
  if (!CFG) return;

  const multEl = document.getElementById("cut-signer-mult");
  const ratioEl = document.getElementById("cut-tx-ratio");
  const multVal = document.getElementById("cut-signer-mult-val");
  const ratioVal = document.getElementById("cut-tx-ratio-val");
  const fig2 = document.getElementById("fig2-chart");
  const fig2Main = document.getElementById("fig2-chart-main");
  const fig3 = document.getElementById("fig3-chart");
  const monthlyBody = document.getElementById("monthly-tbody");
  const burstBody = document.getElementById("burst-tbody");
  const burstCountEl = document.getElementById("burst-day-count");
  const feb16Note = document.getElementById("feb16-note");
  const params = new URLSearchParams(window.location.search);
  const filmMode = params.get("film") === "1";
  if (filmMode) document.body.classList.add("film-mode");

  function fmtInt(n) {
    return Math.round(n).toLocaleString("en-US");
  }

  function fmtPct(x) {
    return (x * 100).toFixed(1) + "%";
  }

  function isBurst(row, mult, ratio) {
    if (row.sm == null || row.tm == null || row.tm === 0) return false;
    return row.s > mult * row.sm && row.t < ratio * row.tm;
  }

  function compute(mult, ratio) {
    const flagged = CFG.daily.filter((row) => isBurst(row, mult, ratio));
    const byMo = {};
    for (const row of flagged) {
      const mo = row.d.slice(0, 7);
      byMo[mo] = (byMo[mo] || 0) + 1;
    }
    return { flagged, byMo };
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function svgLineChart(rows, yKey, yMax, burstDates, opts) {
    const W = 1000;
    const H = opts.height || 440;
    const pad = { l: 56, r: 24, t: 20, b: 44 };
    const innerW = W - pad.l - pad.r;
    const innerH = H - pad.t - pad.b;
    const n = rows.length;
    if (n < 2) return "";
    const burstSet = new Set(burstDates);
    const xAt = (i) => pad.l + (i / (n - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - (v / yMax) * innerH;
    let path = "";
    rows.forEach((row, i) => {
      const y = yAt(row[yKey]);
      path += (i === 0 ? "M" : "L") + xAt(i).toFixed(2) + " " + y.toFixed(2);
    });
    const grey = CFG.colors.grey;
    const charcoal = CFG.colors.charcoal;
    const cream = CFG.colors.cream;
    let circles = "";
    rows.forEach((row, i) => {
      if (!burstSet.has(row.d)) return;
      const cx = xAt(i).toFixed(2);
      const cy = yAt(row[yKey]).toFixed(2);
      circles +=
        '<circle cx="' +
        cx +
        '" cy="' +
        cy +
        '" r="7" fill="' +
        cream +
        '" stroke="' +
        charcoal +
        '" stroke-width="1.1"/>';
    });
    const yTicks = opts.yTicks || [];
    let grid = "";
  yTicks.forEach((tv) => {
      const y = yAt(tv).toFixed(2);
      grid +=
        '<line x1="' +
        pad.l +
        '" y1="' +
        y +
        '" x2="' +
        (W - pad.r) +
        '" y2="' +
        y +
        '" stroke="' +
        CFG.colors.rule +
        '" stroke-width="0.6"/>';
    });
    return (
      '<svg viewBox="0 0 ' +
      W +
      " " +
      H +
      '" width="100%" height="auto" xmlns="http://www.w3.org/2000/svg" role="img">' +
      grid +
      '<path d="' +
      path +
      '" fill="none" stroke="' +
      grey +
      '" stroke-width="1" stroke-linecap="round"/>' +
      circles +
      "</svg>"
    );
  }

  function renderCharts(mult, ratio) {
    const { flagged } = compute(mult, ratio);
    const burstDates = flagged.map((r) => r.d);
    const signersMax = Math.max(...CFG.daily.map((r) => r.s)) * 1.08;
    const txMax = Math.max(...CFG.daily.map((r) => r.t)) * 1.08;
    const step = 100000;
    const yTicks = [];
    for (let v = 0; v <= signersMax; v += step) yTicks.push(v);
    const svg2 = svgLineChart(CFG.daily, "s", signersMax, burstDates, {
      height: 440,
      yTicks,
    });
    if (fig2) fig2.innerHTML = svg2;
    if (fig2Main) fig2Main.innerHTML = svg2;
    if (fig3) {
      fig3.innerHTML = svgLineChart(CFG.daily, "t", txMax, burstDates, {
        height: 420,
        yTicks: [0, 5, 10, 15, 20],
      });
    }
  }

  function renderMonthly(mult, ratio) {
    const { byMo } = compute(mult, ratio);
    const minFlag = CFG.burstDaysToFlagMonth;
    let html = "";
    for (const row of CFG.monthly) {
      const bd = byMo[row.mo] || 0;
      const flag = bd >= minFlag ? "yes" : "no";
      const moLabel = row.partial ? row.mo + "†" : row.mo;
      html +=
        "<tr>" +
        "<td>" +
        esc(moLabel) +
        "</td>" +
        '<td class="num">' +
        fmtInt(row.all_signers) +
        "</td>" +
        '<td class="num accent">' +
        fmtInt(row.net_demand) +
        "</td>" +
        '<td class="num">' +
        fmtPct(row.net_demand_share) +
        "</td>" +
        '<td class="num">' +
        flag +
        "</td>" +
        '<td class="num">' +
        bd +
        "</td>" +
        '<td class="num">' +
        fmtPct(row.top_receiver_share_median_day) +
        "</td>" +
        "</tr>";
    }
    if (monthlyBody) monthlyBody.innerHTML = html;
  }

  function renderBurstTable(mult, ratio) {
    const { flagged } = compute(mult, ratio);
    flagged.sort((a, b) => (a.d < b.d ? -1 : 1));
    if (burstCountEl) burstCountEl.textContent = String(flagged.length);
    if (!burstBody) return;
    if (!flagged.length) {
      burstBody.innerHTML =
        '<tr><td colspan="6">No day in the report window meets both cuts at this threshold.</td></tr>';
      return;
    }
    let html = "";
    for (const row of flagged) {
      const sm = row.sm;
      const tm = row.tm;
      const signerMult = sm ? row.s / sm : 0;
      const txRatio = tm ? row.t / tm : 0;
      html +=
        "<tr>" +
        "<td>" +
        esc(row.d) +
        "</td>" +
        '<td class="num">' +
        fmtInt(row.s) +
        "</td>" +
        '<td class="num">' +
        signerMult.toFixed(2) +
        "×</td>" +
        '<td class="num">' +
        txRatio.toFixed(2) +
        "</td>" +
        "<td>" +
        esc(row.tr) +
        "</td>" +
        '<td class="num">' +
        (row.ts != null ? fmtPct(row.ts) : "—") +
        "</td>" +
        "</tr>";
    }
    burstBody.innerHTML = html;
  }

  function updateFeb16Note(mult) {
    if (!feb16Note) return;
    const row = CFG.daily.find((r) => r.d === "2026-02-16");
    if (!row || row.sm == null) {
      feb16Note.hidden = true;
      return;
    }
    const on = isBurst(row, mult, parseFloat(ratioEl.value));
    feb16Note.hidden = !on;
    if (on) {
      feb16Note.textContent =
        "2026-02-16 now flags: " +
        fmtInt(row.s) +
        " signers (" +
        (row.s / row.sm).toFixed(2) +
        "× the trailing median, tx/signer at " +
        (row.t / row.tm).toFixed(2) +
        " of its median). At 2.5× it sits just below the cut.";
    }
  }

  function apply() {
    const mult = parseFloat(multEl.value);
    const ratio = parseFloat(ratioEl.value);
    multVal.textContent = mult.toFixed(2) + "×";
    ratioVal.textContent = Math.round(ratio * 100) + "%";
    renderCharts(mult, ratio);
    renderMonthly(mult, ratio);
    renderBurstTable(mult, ratio);
    updateFeb16Note(mult);
    window.__subsidyFilterState = { mult, ratio };
  }

  multEl.addEventListener("input", apply);
  ratioEl.addEventListener("input", apply);
  apply();

  const filmApi = {
    prepare() {
      apply();
    },
    seek(t) {
      const tt = Math.max(0, Math.min(t, CFG.filmDuration || 64));
      if (tt < 22) {
        multEl.value = String(CFG.defaultMult);
        ratioEl.value = String(CFG.defaultRatio);
      } else if (tt < 36) {
        const p = (tt - 22) / 14;
        const target = 2.4;
        const v = CFG.defaultMult + (target - CFG.defaultMult) * Math.min(1, p);
        multEl.value = String(v);
        ratioEl.value = String(CFG.defaultRatio);
      } else {
        multEl.value = "2.4";
        ratioEl.value = String(CFG.defaultRatio);
      }
      apply();
    },
  };
  window.__film = filmApi;
})();
