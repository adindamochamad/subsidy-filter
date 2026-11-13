"""Build dashboard/index.html from classified CSVs. Offline, no BigQuery."""

from __future__ import annotations

import html
import io
import json
import sys
from pathlib import Path

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator, NullLocator

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

from calendar import monthrange

from classify.config import (
    BURST_DAYS_TO_FLAG_MONTH,
    DATE_START,
    HOT_RECEIVER_SUBSTRING,
    SIGNER_BURST_MULTIPLE,
    TRAILING_WINDOW_DAYS,
    TX_PER_SIGNER_DROP_RATIO,
)
from dashboard.style import ACCENT, ACCENT_HI, CHARCOAL, CREAM, FONT_MONO, GREY, INK, MUTED, RULE

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
SQL_DIR = ROOT / "extract" / "sql"
OUT = ROOT / "dashboard" / "index.html"
DOCS_OUT = ROOT / "docs" / "index.html"
INTERACTIVE_JS = Path(__file__).resolve().parent / "interactive.js"
THESIS_URL = "https://github.com/adindamochamad/subsidy-filter/blob/main/THESIS.md"


def _require(name: str) -> Path:
    path = PROCESSED / name
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(ROOT)}. Run `make classify` first.")
    return path


def fmt_int(n) -> str:
    return f"{int(n):,}"


def fmt_pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def csv_end(daily: pd.DataFrame) -> pd.Timestamp:
    window = daily[daily["in_report_window"]] if "in_report_window" in daily.columns else daily
    return pd.to_datetime(window["block_date"]).max()


def partial_month_label(end: pd.Timestamp) -> str | None:
    last = monthrange(end.year, end.month)[1]
    if end.day < last:
        return (
            f"{end.strftime('%Y-%m')} is a partial month "
            f"(1–{end.day} {end.strftime('%b')}), equal to max(block_date) "
            f"in data/raw/daily_activity.csv"
        )
    return None


def _setup_mpl() -> None:
    plt.rcParams.update(
        {
            "font.family": "monospace",
            "font.monospace": [FONT_MONO, "DejaVu Sans Mono"],
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
            "figure.facecolor": CREAM,
            "savefig.facecolor": CREAM,
            "axes.facecolor": CREAM,
            "text.color": CHARCOAL,
            "axes.labelcolor": CHARCOAL,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.edgecolor": CHARCOAL,
            "axes.linewidth": 0.6,
        }
    )


def _style_ax(ax) -> None:
    ax.set_facecolor(CREAM)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(CHARCOAL)
    ax.spines["bottom"].set_color(CHARCOAL)
    ax.tick_params(length=3, labelsize=9)
    ax.yaxis.grid(True, color=RULE, linewidth=0.6)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def fig_to_svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    raw = buf.getvalue()
    start = raw.find("<svg")
    return raw[start:] if start >= 0 else raw


def _millions(_x, _pos) -> str:
    if _x == 0:
        return "0"
    return f"{_x / 1_000_000:.0f}M"


def _thousands(_x, _pos) -> str:
    if _x == 0:
        return "0"
    return f"{_x / 1_000:.0f}k"


def _log_signers(x, _pos) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:.0f}M"
    return f"{x / 1_000:.0f}k"


def chart_hero(monthly: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10.2, 5.0))
    _style_ax(ax)
    x = pd.to_datetime(monthly["mo"] + "-01")
    y_rep = monthly["all_signers"].astype(float)
    y_net = monthly["net_demand"].astype(float)
    ax.set_yscale("log")
    ax.plot(x, y_rep, color=GREY, linewidth=1.8, solid_capstyle="round")
    ax.plot(x, y_net, color=ACCENT, linewidth=1.8, solid_capstyle="round")
    ax.scatter(x.iloc[-1], y_rep.iloc[-1], color=GREY, s=12, zorder=3)
    ax.scatter(x.iloc[-1], y_net.iloc[-1], color=ACCENT, s=12, zorder=3)
    ax.set_ylabel("Monthly distinct signers, log scale", fontsize=8, color=MUTED)
    ax.yaxis.set_major_locator(FixedLocator([5e4, 1e5, 2e5, 5e5, 1e6, 2e6, 4e6]))
    ax.yaxis.set_major_formatter(FuncFormatter(_log_signers))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(x.iloc[0] - pd.Timedelta(days=10), x.iloc[-1] + pd.Timedelta(days=4))
    ax.set_ylim(y_net.min() * 0.72, y_rep.max() * 1.35)
    last_x = x.iloc[-1]
    ax.annotate(
        "Reported",
        xy=(last_x, y_rep.iloc[-1]),
        xytext=(8, 6),
        textcoords="offset points",
        color=GREY,
        fontsize=9,
        ha="left",
        va="bottom",
        fontfamily=FONT_MONO,
        clip_on=False,
    )
    ax.annotate(
        "Net Demand",
        xy=(last_x, y_net.iloc[-1]),
        xytext=(8, -6),
        textcoords="offset points",
        color=ACCENT,
        fontsize=9,
        ha="left",
        va="top",
        fontfamily=FONT_MONO,
        clip_on=False,
    )
    peak_i = int(y_rep.idxmax())
    ax.annotate(
        f"{fmt_int(y_rep.iloc[peak_i])}",
        xy=(x.iloc[peak_i], y_rep.iloc[peak_i]),
        xytext=(0, 8),
        textcoords="offset points",
        color=GREY,
        fontsize=8,
        ha="center",
        fontfamily=FONT_MONO,
    )
    jul = monthly.loc[monthly["mo"] == "2026-07"].iloc[0]
    jx = pd.Timestamp("2026-07-01")
    y_hi = float(jul["all_signers"])
    y_lo = float(jul["net_demand"])
    gap_pct = (1.0 - float(jul["net_demand_share"])) * 100
    bx = jx + pd.Timedelta(days=14)
    cap = pd.Timedelta(days=8)
    ax.plot([bx, bx], [y_lo, y_hi], color=CHARCOAL, linewidth=0.8, clip_on=False)
    ax.plot([bx - cap, bx], [y_hi, y_hi], color=CHARCOAL, linewidth=0.8, clip_on=False)
    ax.plot([bx - cap, bx], [y_lo, y_lo], color=CHARCOAL, linewidth=0.8, clip_on=False)
    ax.text(
        bx + pd.Timedelta(days=6),
        (y_hi * y_lo) ** 0.5,
        f"{gap_pct:.1f}%",
        ha="left",
        va="center",
        color=CHARCOAL,
        fontsize=8,
        fontfamily=FONT_MONO,
        clip_on=False,
    )
    return fig_to_svg(fig)


def chart_daily_signers(daily: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10.2, 4.4))
    _style_ax(ax)
    d = daily[daily["in_report_window"]].copy()
    ax.plot(d["block_date"], d["signers"], color=GREY, linewidth=1.0)
    bursts = d[d["burst_flag"]]
    ax.scatter(
        bursts["block_date"],
        bursts["signers"],
        color=CHARCOAL,
        s=22,
        zorder=3,
        facecolors=CREAM,
        edgecolors=CHARCOAL,
        linewidths=1.1,
    )
    ax.set_ylabel("Daily distinct signers", fontsize=8, color=MUTED)
    ax.yaxis.set_major_locator(MultipleLocator(100_000))
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(d["block_date"].min(), d["block_date"].max())
    ax.set_ylim(0, d["signers"].max() * 1.08)
    if not bursts.empty:
        top = bursts.loc[bursts["signers"].idxmax()]
        ax.annotate(
            pd.Timestamp(top["block_date"]).strftime("%d %b %Y"),
            xy=(top["block_date"], top["signers"]),
            xytext=(10, 8),
            textcoords="offset points",
            color=CHARCOAL,
            fontsize=8,
            fontfamily=FONT_MONO,
        )
    fig.tight_layout()
    return fig_to_svg(fig)


def chart_tx_per_signer(daily: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10.2, 4.2))
    _style_ax(ax)
    d = daily[daily["in_report_window"]].copy()
    ax.plot(d["block_date"], d["tx_per_signer"], color=GREY, linewidth=1.0)
    bursts = d[d["burst_flag"]]
    ax.scatter(
        bursts["block_date"],
        bursts["tx_per_signer"],
        color=CHARCOAL,
        s=22,
        zorder=3,
        facecolors=CREAM,
        edgecolors=CHARCOAL,
        linewidths=1.1,
    )
    ax.set_ylabel("Transactions per signer", fontsize=8, color=MUTED)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(d["block_date"].min(), d["block_date"].max())
    ax.set_ylim(0, d["tx_per_signer"].max() * 1.08)
    fig.tight_layout()
    return fig_to_svg(fig)


def chart_top_share(daily: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10.2, 4.2))
    _style_ax(ax)
    d = daily[daily["in_report_window"]].copy()
    ax.plot(d["block_date"], d["top_receiver_share"], color=GREY, linewidth=1.0)
    bursts = d[d["burst_flag"]]
    ax.scatter(
        bursts["block_date"],
        bursts["top_receiver_share"],
        color=CHARCOAL,
        s=22,
        zorder=3,
        facecolors=CREAM,
        edgecolors=CHARCOAL,
        linewidths=1.1,
    )
    ax.set_ylabel("Share of daily signers, #1 contract", fontsize=8, color=MUTED)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x * 100:.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(d["block_date"].min(), d["block_date"].max())
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    return fig_to_svg(fig)


def _sql_block(filename: str) -> str:
    sql = (SQL_DIR / filename).read_text(encoding="utf-8").strip()
    return html.escape(sql)


def _takeaways(monthly: pd.DataFrame, daily: pd.DataFrame, bursts: pd.DataFrame) -> dict[str, str]:
    window = daily[daily["in_report_window"]]
    quiet = monthly[~monthly["burst_flag"]]
    nonburst = window[~window["burst_flag"]]
    lo = monthly.loc[monthly["all_signers"].idxmin()]
    hi = monthly.loc[monthly["all_signers"].idxmax()]
    n_mo = len(monthly)
    n_below = int((monthly["net_demand_share"] < 0.4).sum())
    hot_days = int((window["top_receiver"] == "game.hot.tg").sum())
    partial = partial_month_label(csv_end(daily))
    return {
        "hero": (
            f"Reported monthly signers ran from {fmt_int(lo['all_signers'])} "
            f"({lo['mo']}) to {fmt_int(hi['all_signers'])} ({hi['mo']}); "
            f"Net Demand was below 40% of the headline in "
            f"{n_below} of {n_mo} months."
            + (f" {partial}." if partial else "")
        ),
        "daily": (
            f"Median distinct signers on a non-burst day were "
            f"{fmt_int(nonburst['signers'].median())}; "
            f"{len(bursts)} days cleared the "
            f"{SIGNER_BURST_MULTIPLE}x-signer and "
            f"{fmt_pct(TX_PER_SIGNER_DROP_RATIO, 0)}-intensity test, "
            f"peaking at {fmt_int(window['signers'].max())} on "
            f"{pd.Timestamp(window.loc[window['signers'].idxmax(), 'block_date']).strftime('%d %b %Y')}."
        ),
        "txps": (
            f"On those burst days, transactions per signer fell to "
            f"{bursts['tx_per_signer_ratio'].min():.2f}–"
            f"{bursts['tx_per_signer_ratio'].max():.2f} of the trailing "
            f"{TRAILING_WINDOW_DAYS}-day median, the intensity half of the burst detector."
        ),
        "share": (
            f"game.hot.tg was the #1 receiver on {hot_days} of "
            f"{int(window.shape[0])} days, taking a median "
            f"{fmt_pct(nonburst['top_receiver_share'].median())} of signers "
            f"on non-burst days. The one exception is 2026-11-10, when a "
            f"single implicit account took "
            f"{fmt_pct(float(bursts.loc[bursts['block_date']==pd.Timestamp('2026-11-10'), 'top_receiver_share'].iloc[0]))} "
            f"of that day’s signers."
        ),
        "quiet_range": (
            f"In the ten months without a burst flag, Net Demand was "
            f"{fmt_pct(quiet['net_demand_share'].min())}–"
            f"{fmt_pct(quiet['net_demand_share'].max())} of reported signers "
            f"(median {fmt_pct(quiet['net_demand_share'].median())})."
        ),
    }


def _monthly_table(monthly: pd.DataFrame, end: pd.Timestamp) -> str:
    last_mo = pd.Timestamp(end).strftime("%Y-%m")
    last_dom = monthrange(end.year, end.month)[1]
    rows = []
    for _, r in monthly.iterrows():
        flag = "yes" if bool(r["burst_flag"]) else "no"
        mo = str(r["mo"])
        mo_label = f"{mo}†" if mo == last_mo and end.day < last_dom else mo
        rows.append(
            "<tr>"
            f"<td>{html.escape(mo_label)}</td>"
            f"<td class='num'>{fmt_int(r['all_signers'])}</td>"
            f"<td class='num accent'>{fmt_int(r['net_demand'])}</td>"
            f"<td class='num'>{fmt_pct(r['net_demand_share'])}</td>"
            f"<td class='num'>{html.escape(flag)}</td>"
            f"<td class='num'>{int(r['burst_days'])}</td>"
            f"<td class='num'>{fmt_pct(r['top_receiver_share_median_day'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _august_hero(monthly: pd.DataFrame) -> dict[str, str]:
    row = monthly.loc[monthly["mo"] == "2026-08"].iloc[0]
    return {
        "reported": fmt_int(row["all_signers"]),
        "net": fmt_int(row["net_demand"]),
        "share": fmt_pct(row["net_demand_share"]),
    }


def _daily_payload(daily: pd.DataFrame) -> list[dict]:
    window = daily[daily["in_report_window"]].copy().sort_values("block_date")
    out: list[dict] = []
    for _, r in window.iterrows():
        sm = r["signers_median_28"]
        tm = r["tx_per_signer_median_28"]
        out.append(
            {
                "d": pd.Timestamp(r["block_date"]).strftime("%Y-%m-%d"),
                "s": int(r["signers"]),
                "t": float(r["tx_per_signer"]),
                "sm": None if pd.isna(sm) else float(sm),
                "tm": None if pd.isna(tm) else float(tm),
                "tr": "" if pd.isna(r.get("top_receiver")) else str(r["top_receiver"]),
                "ts": None if pd.isna(r.get("top_receiver_share")) else float(r["top_receiver_share"]),
            }
        )
    return out


def _monthly_payload(monthly: pd.DataFrame, end: pd.Timestamp) -> list[dict]:
    last_mo = pd.Timestamp(end).strftime("%Y-%m")
    last_dom = monthrange(end.year, end.month)[1]
    rows: list[dict] = []
    for _, r in monthly.iterrows():
        mo = str(r["mo"])
        rows.append(
            {
                "mo": mo,
                "partial": mo == last_mo and end.day < last_dom,
                "all_signers": int(r["all_signers"]),
                "net_demand": int(r["net_demand"]),
                "net_demand_share": float(r["net_demand_share"]),
                "top_receiver_share_median_day": float(r["top_receiver_share_median_day"]),
            }
        )
    return rows


def _interactive_script(daily: pd.DataFrame, monthly: pd.DataFrame, end: pd.Timestamp) -> str:
    cfg = {
        "daily": _daily_payload(daily),
        "monthly": _monthly_payload(monthly, end),
        "defaultMult": SIGNER_BURST_MULTIPLE,
        "defaultRatio": TX_PER_SIGNER_DROP_RATIO,
        "burstDaysToFlagMonth": BURST_DAYS_TO_FLAG_MONTH,
        "filmDuration": 64.0,
        "colors": {
            "grey": GREY,
            "charcoal": CHARCOAL,
            "cream": CREAM,
            "rule": RULE,
        },
    }
    js_body = INTERACTIVE_JS.read_text(encoding="utf-8")
    return (
        "<script>\n"
        f"window.__subsidyFilter = {json.dumps(cfg)};\n"
        "</script>\n"
        f"<script>\n{js_body}\n</script>"
    )


def _coverage_html() -> str:
    path = RAW / "burst_coverage.csv"
    if not path.exists():
        return (
            "<p class='note' id='coverage-note'>"
            "On 2026-02-15, the top 20 receivers (excluding HOT) name about a "
            "quarter of that day’s signers; that sum double-counts anyone who "
            "touched two contracts. See THESIS.md for method limits."
            "</p>"
        )
    cov = pd.read_csv(path)
    parts: list[str] = []
    for day in ("2026-02-15", "2026-02-17", "2026-10-03", "2026-10-04", "2026-10-07"):
        sub = cov[(cov["block_date"] == day) & (cov["row_kind"] == "coverage")]
        if sub.empty:
            continue
        r = sub.iloc[0]
        parts.append(
            f"{day}: top-10 receivers cover {fmt_pct(float(r['cover_10']))}, "
            f"top-20 {fmt_pct(float(r['cover_20']))}, top-50 {fmt_pct(float(r['cover_50']))} "
            f"of {fmt_int(r['day_signers'])} signers (excluding <span class='mono'>%hot.tg</span>)."
        )
    ctrl = cov[
        (cov["block_date"] == "2026-11-10")
        & (cov["row_kind"] == "top")
        & (cov["receiver_rank"] == 1)
    ]
    ctrl_line = ""
    if not ctrl.empty:
        top = ctrl.iloc[0]
        rid = str(top["receiver_account_id"])
        if rid.startswith("3d9ccff55"):
            ctrl_line = (
                f" Control day 2026-11-10: #1 receiver "
                f"<span class='mono'>{html.escape(rid[:16])}…</span> "
                f"took {fmt_pct(float(top['receiver_share']))} of signers."
            )
    if not parts:
        return (
            "<p class='note' id='coverage-note'>"
            "Coverage extract present but no summary rows. See data/raw/burst_coverage.csv."
            "</p>"
        )
    return (
        "<p class='note' id='coverage-note'>"
        + " ".join(parts)
        + ctrl_line
        + "</p>"
    )


def _burst_table(bursts: pd.DataFrame) -> str:
    if bursts.empty:
        return "<p>No day in the report window met both burst thresholds.</p>"
    rows = []
    for _, r in bursts.iterrows():
        day = pd.Timestamp(r["block_date"]).strftime("%Y-%m-%d")
        rows.append(
            "<tr>"
            f"<td>{day}</td>"
            f"<td class='num'>{fmt_int(r['signers'])}</td>"
            f"<td class='num'>{r['signer_multiple']:.2f}x</td>"
            f"<td class='num'>{r['tx_per_signer_ratio']:.2f}</td>"
            f"<td>{html.escape(str(r['top_receiver']))}</td>"
            f"<td class='num'>{fmt_pct(r['top_receiver_share'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render(monthly: pd.DataFrame, daily: pd.DataFrame, bursts: pd.DataFrame) -> str:
    takes = _takeaways(monthly, daily, bursts)
    hero = chart_hero(monthly)
    share_svg = chart_top_share(daily)
    aug = _august_hero(monthly)
    interactive = _interactive_script(daily, monthly, csv_end(daily))
    coverage_block = _coverage_html()
    sql_monthly = _sql_block("monthly_net_demand.sql")
    sql_daily = _sql_block("daily_activity.sql")
    sql_top = _sql_block("daily_top_receivers.sql")
    end = csv_end(daily)
    end_s = pd.Timestamp(end).strftime("%Y-%m-%d")
    partial = partial_month_label(end)
    dagger = (
        f"<p class='note'><span class='mono'>†</span> {html.escape(partial)}.</p>"
        if partial
        else ""
    )
    last_mo = pd.Timestamp(end).strftime("%Y-%m")
    nov_note = (
        f" The last month in the extract ({html.escape(last_mo)}) has a named "
        f"receiver on 10 Nov; one attributed burst does not attribute the others."
        if last_mo >= "2026-11"
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Subsidy Filter — NEAR active accounts, Nov 2025–Nov 2026</title>
<link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=instrument-serif@400,400i,600,700&amp;display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&amp;display=swap">
<style>
  :root {{
    --cream: {CREAM};
    --charcoal: {CHARCOAL};
    --accent: {ACCENT};
    --accent-hi: {ACCENT_HI};
    --grey: {GREY};
    --muted: {MUTED};
    --rule: {RULE};
    --ink: {INK};
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    background: var(--cream);
    color: var(--charcoal);
    margin: 0;
  }}
  body {{
    font-family: "Instrument Serif", "Times New Roman", Times, serif;
    font-size: 1.25rem;
    line-height: 1.45;
    font-weight: 400;
  }}
  .page {{
    max-width: 40rem;
    margin: 0 auto;
    padding: 2.4rem 1.4rem 6rem;
  }}
  .hero-band {{
    background: var(--ink);
    color: var(--cream);
    padding: 4.5rem 1.4rem 3.4rem;
  }}
  .hero-inner {{
    max-width: 40rem;
    margin: 0 auto;
  }}
  .kicker {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--cream);
    margin: 0;
  }}
  .hero-band h1 {{
    font-weight: 400;
    font-size: 3.05rem;
    line-height: 1.05;
    letter-spacing: -0.02em;
    margin: 0.7rem 0 0.85rem;
    color: var(--cream);
  }}
  .standfirst {{
    font-style: italic;
    font-size: 1.28rem;
    color: var(--cream);
    margin: 0;
    max-width: 36rem;
  }}
  h1 {{
    font-weight: 400;
    font-size: 3.35rem;
    line-height: 1.02;
    letter-spacing: -0.02em;
    margin: 0.55rem 0 0.6rem;
  }}
  h2 {{
    font-weight: 400;
    font-size: 1.55rem;
    margin: 3.2rem 0 0.7rem;
  }}
  p {{ margin: 0 0 1.05rem; }}
  a {{ color: var(--charcoal); }}
  .mono {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.86em;
    font-style: normal;
    letter-spacing: 0;
    white-space: nowrap;
  }}
  figure {{
    margin: 3.1rem 0;
  }}
  figcaption {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.65rem;
  }}
  figure .chart {{
    margin: 0 -0.2rem 0.85rem;
  }}
  figure .chart svg {{
    width: 100%;
    height: auto;
    display: block;
  }}
  .take {{
    font-size: 1.05rem;
    margin: 0 0 0.55rem;
  }}
  details {{
    margin: 0.35rem 0 0;
  }}
  details summary {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    cursor: pointer;
    list-style: none;
  }}
  details summary::-webkit-details-marker {{ display: none; }}
  details pre {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.68rem;
    line-height: 1.45;
    background: var(--cream);
    border-top: 1px solid var(--rule);
    padding: 0.85rem 0 0;
    overflow-x: auto;
    color: var(--charcoal);
    margin: 0.55rem 0 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
    margin: 0.6rem 0 1.4rem;
  }}
  th, td {{
    border-bottom: 1px solid var(--rule);
    padding: 0.45rem 0.35rem;
    vertical-align: bottom;
  }}
  th {{
    text-align: left;
    font-weight: 500;
    color: var(--muted);
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  th.num, td.num {{
    text-align: right;
  }}
  td {{
    overflow-wrap: anywhere;
  }}
  td.accent {{ color: var(--accent); }}
  .note {{
    font-size: 1.05rem;
    color: var(--charcoal);
  }}
  footer {{
    margin-top: 3.5rem;
    padding-top: 1.1rem;
    border-top: 1px solid var(--rule);
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem;
    color: var(--muted);
    letter-spacing: 0.02em;
  }}
  .hero-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 1.8rem 2.4rem;
    margin: 1.4rem 0 0.2rem;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.78rem;
    letter-spacing: 0.02em;
  }}
  .hero-stat strong {{
    display: block;
    font-size: 1.55rem;
    font-weight: 500;
    color: var(--accent-hi);
    letter-spacing: -0.02em;
    margin-top: 0.2rem;
  }}
  .hero-stat span {{
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    color: var(--grey);
  }}
  .controls {{
    margin: 2.2rem 0 0.4rem;
    padding: 1.1rem 0;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
  }}
  .controls label {{
    display: block;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin: 0.85rem 0 0.35rem;
  }}
  .controls input[type="range"] {{
    width: 100%;
    accent-color: var(--accent);
  }}
  .controls .readout {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.85rem;
    margin-top: 0.25rem;
  }}
  #feb16-note {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.78rem;
    color: var(--accent);
    margin: 0.6rem 0 0;
  }}
  body.film-mode .page > *:not(#film-stage),
  body.film-mode footer,
  body.film-mode .controls,
  body.film-mode .hero-band h1,
  body.film-mode .standfirst {{
    display: none !important;
  }}
  body.film-mode {{
    overflow: hidden;
    background: var(--ink);
    width: 1920px;
    min-height: 1080px;
    margin: 0 auto;
  }}
  body.film-mode .hero-band {{
    padding: 3rem 2rem 1.5rem;
    min-height: 100vh;
  }}
  body.film-mode .hero-inner {{
    max-width: 56rem;
  }}
  body.film-mode #film-stage {{
    display: block !important;
    margin-top: 2rem;
  }}
  body.film-mode .hero-stats {{
    gap: 2.5rem 4rem;
  }}
  body.film-mode .hero-stat strong {{
    font-size: 2.4rem;
  }}
  #film-stage {{
    display: none;
  }}
</style>
</head>
<body>
<header class="hero-band">
  <div class="hero-inner">
    <p class="kicker">Subsidy Filter · NEAR public transactions · {DATE_START} to {end_s}</p>
    <h1>Most of NEAR’s active accounts are one Telegram game.</h1>
    <p class="standfirst">After removing HOT and flagging burst days, quiet-month Net Demand is a fraction of the headline.{(" " + html.escape(partial) + ".") if partial else ""}</p>
    <div class="hero-stats" data-august="2026-08">
      <div class="hero-stat"><span>Aug 2026 reported</span><strong>{aug['reported']}</strong></div>
      <div class="hero-stat"><span>Net Demand</span><strong>{aug['net']}</strong></div>
      <div class="hero-stat"><span>Net / reported</span><strong>{aug['share']}</strong></div>
    </div>
  </div>
</header>
<article class="page">
  <div id="film-stage">
    <figure>
      <figcaption>Figure 2 · Daily distinct signers. Open circles follow the cuts below.</figcaption>
      <div class="chart" id="fig2-chart"></div>
    </figure>
  </div>

  <div class="controls no-film-hide">
    <p class="note">Move the burst cuts. Figures 2–3, the monthly burst column, and the burst-day table recompute from <span class="mono">data/processed/daily.csv</span> in the browser. Defaults match <span class="mono">classify/config.py</span>.</p>
    <label for="cut-signer-mult">Signer burst multiple (vs trailing {TRAILING_WINDOW_DAYS}d median)</label>
    <input type="range" id="cut-signer-mult" min="2.0" max="3.0" step="0.05" value="{SIGNER_BURST_MULTIPLE}">
    <p class="readout" id="cut-signer-mult-val">{SIGNER_BURST_MULTIPLE}×</p>
    <label for="cut-tx-ratio">Tx-per-signer intensity cut (fraction of trailing median)</label>
    <input type="range" id="cut-tx-ratio" min="0.45" max="0.75" step="0.01" value="{TX_PER_SIGNER_DROP_RATIO}">
    <p class="readout" id="cut-tx-ratio-val">{fmt_pct(TX_PER_SIGNER_DROP_RATIO, 0)}</p>
    <p id="feb16-note" hidden></p>
  </div>

  <figure>
    <figcaption>Figure 1 · Reported active accounts and Net Demand</figcaption>
    <div class="chart">{hero}</div>
    <p class="take">{html.escape(takes['hero'])}</p>
    <details>
      <summary>SQL</summary>
      <pre>{sql_monthly}</pre>
    </details>
  </figure>

  <p>NEAR’s reported active accounts are a count of distinct <span class="mono">signer_account_id</span> values. This note splits that count into signers who did something other than transact with a <span class="mono">hot.tg</span> receiver, and flags days where headcount spikes while transactions-per-signer collapse. Thresholds live in <span class="mono">classify/config.py</span>. The argument, including what cuts against it, is in <a href="{html.escape(THESIS_URL)}">THESIS.md</a>.</p>

  <figure>
    <figcaption>Figure 2 · Daily distinct signers. Open circles are burst days.</figcaption>
    <div class="chart" id="fig2-chart-main"></div>
    <p class="take">{html.escape(takes['daily'])}</p>
    <details>
      <summary>SQL</summary>
      <pre>{sql_daily}</pre>
    </details>
  </figure>

  <figure>
    <figcaption>Figure 3 · Transactions per signer. Open circles are burst days.</figcaption>
    <div class="chart" id="fig3-chart"></div>
    <p class="take">{html.escape(takes['txps'])}</p>
    <details>
      <summary>SQL</summary>
      <pre>{sql_daily}</pre>
    </details>
  </figure>

  <figure>
    <figcaption>Figure 4 · Share of daily signers taken by the #1 contract</figcaption>
    <div class="chart">{share_svg}</div>
    <p class="take">{html.escape(takes['share'])}</p>
    <details>
      <summary>SQL</summary>
      <pre>{sql_top}</pre>
    </details>
  </figure>

  <h2>Monthly figures</h2>
  <p class="note">{html.escape(takes['quiet_range'])} The monthly table reports <span class="mono">top_receiver_share_median_day</span> (median of daily #1-contract shares). <span class="mono">top_receiver_share_peak_day</span> is in <span class="mono">data/processed/monthly.csv</span> and is the share on the loudest day; it is not shown here because it understates typical-day HOT dominance in burst months. Burst months are flagged when at least one day meets both detector cuts (signers &gt; {SIGNER_BURST_MULTIPLE}× the trailing {TRAILING_WINDOW_DAYS}-day median, and tx/signer &lt; {fmt_pct(TX_PER_SIGNER_DROP_RATIO, 0)} of that median).</p>
  <table>
    <thead>
      <tr>
        <th>month</th>
        <th class="num">reported</th>
        <th class="num">net demand</th>
        <th class="num">net / reported</th>
        <th class="num">burst</th>
        <th class="num">burst days</th>
        <th class="num">median #1 share</th>
      </tr>
    </thead>
    <tbody id="monthly-tbody">
      {_monthly_table(monthly, end)}
    </tbody>
  </table>
  {dagger}

  <h2>Burst days</h2>
  <p class="note">A day is flagged only when both conditions hold (<span id="burst-day-count">{len(bursts)}</span> days at default cuts). On 2026-11-10 the #1 receiver is a single implicit account (55.0% of that day’s signers). On the February and October burst days the #1 receiver is still game.hot.tg at 23.6%–26.4%; those two episodes remain unattributed.</p>
  {coverage_block}
  <table>
    <thead>
      <tr>
        <th>day</th>
        <th class="num">signers</th>
        <th class="num">vs 28d median</th>
        <th class="num">tx/signer vs median</th>
        <th>top receiver</th>
        <th class="num">#1 share</th>
      </tr>
    </thead>
    <tbody id="burst-tbody">
      {_burst_table(bursts)}
    </tbody>
  </table>

  <h2>How to read this</h2>
  <p>Net Demand does not subtract burst windows. It only subtracts signers whose monthly activity is exclusively with receivers matching <span class="mono">%{html.escape(HOT_RECEIVER_SUBSTRING)}</span>. February and October therefore remain large on the Net Demand line. That is a finding, not a bug: those bursts are not HOT-only, and they are not attributed.{nov_note} See <a href="{html.escape(THESIS_URL)}">THESIS.md</a>.</p>
  <p>Rebuild this page from the committed CSVs with <span class="mono">make all</span>. No BigQuery credentials are required.</p>

  <footer>
    Source: bigquery-public-data.crypto_near_mainnet_us.transactions. Charts rebuilt from data/raw/*.csv. MIT license.
  </footer>
</article>
{interactive}
</body>
</html>
"""


def main() -> int:
    _setup_mpl()
    monthly = pd.read_csv(_require("monthly.csv"))
    daily = pd.read_csv(_require("daily.csv"), parse_dates=["block_date"])
    daily["burst_flag"] = daily["burst_flag"].astype(bool)
    daily["in_report_window"] = daily["in_report_window"].astype(bool)
    bursts = pd.read_csv(_require("burst_days.csv"), parse_dates=["block_date"])
    html_out = render(monthly, daily, bursts)
    OUT.write_text(html_out, encoding="utf-8")
    print(f"WROTE {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)", flush=True)
    DOCS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.write_text(html_out, encoding="utf-8")
    print(f"WROTE {DOCS_OUT.relative_to(ROOT)} ({DOCS_OUT.stat().st_size:,} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
