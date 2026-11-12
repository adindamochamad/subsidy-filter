"""Classify daily activity into burst flags and monthly Net Demand.

Reads only data/raw/*.csv. No BigQuery, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from classify.config import (
    BURST_DAYS_TO_FLAG_MONTH,
    DATE_START,
    HOT_RECEIVER_SUBSTRING,
    SIGNER_BURST_MULTIPLE,
    TRAILING_WINDOW_DAYS,
    TX_PER_SIGNER_DROP_RATIO,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def _require(name: str) -> Path:
    path = RAW / name
    if not path.exists():
        raise SystemExit(
            f"Missing {path.relative_to(ROOT)}. "
            "Run `make extract` if you have BigQuery credentials, "
            "or check out the committed CSVs."
        )
    return path


def _is_hot(receiver: str) -> bool:
    return HOT_RECEIVER_SUBSTRING in str(receiver)


def classify_daily(activity: pd.DataFrame, top: pd.DataFrame) -> pd.DataFrame:
    daily = activity.copy()
    daily["block_date"] = pd.to_datetime(daily["block_date"]).dt.normalize()
    daily = daily.sort_values("block_date").reset_index(drop=True)
    daily["tx"] = daily["tx"].astype("int64")
    daily["signers"] = daily["signers"].astype("int64")
    daily["tx_per_signer"] = daily["tx"] / daily["signers"]

    prior = daily.shift(1)
    daily["signers_median_28"] = (
        prior["signers"].rolling(TRAILING_WINDOW_DAYS, min_periods=TRAILING_WINDOW_DAYS).median()
    )
    daily["tx_per_signer_median_28"] = (
        prior["tx_per_signer"]
        .rolling(TRAILING_WINDOW_DAYS, min_periods=TRAILING_WINDOW_DAYS)
        .median()
    )
    daily["burst_flag"] = (
        (daily["signers"] > SIGNER_BURST_MULTIPLE * daily["signers_median_28"])
        & (
            daily["tx_per_signer"]
            < TX_PER_SIGNER_DROP_RATIO * daily["tx_per_signer_median_28"]
        )
    )
    daily["burst_flag"] = daily["burst_flag"].fillna(False)

    top = top.copy()
    top["block_date"] = pd.to_datetime(top["block_date"]).dt.normalize()
    top["signers"] = top["signers"].astype("int64")
    top = top.sort_values(["block_date", "signers", "receiver_account_id"], ascending=[True, False, True])
    top1 = top.groupby("block_date", as_index=False).first()
    top1 = top1.rename(
        columns={
            "receiver_account_id": "top_receiver",
            "signers": "top_receiver_signers",
        }
    )
    daily = daily.merge(top1, on="block_date", how="left")
    daily["top_receiver_share"] = daily["top_receiver_signers"] / daily["signers"]
    daily["top_receiver_is_hot"] = daily["top_receiver"].map(_is_hot)

    start = pd.Timestamp(DATE_START)
    # End of the report window is max(block_date) in the extract, not a
    # constant. The CSV is already cut at the last fully-closed UTC day.
    daily["in_report_window"] = daily["block_date"] >= start
    daily["mo"] = daily["block_date"].dt.strftime("%Y-%m")
    return daily


def classify_monthly(daily: pd.DataFrame, monthly_raw: pd.DataFrame) -> pd.DataFrame:
    window = daily[daily["in_report_window"]].copy()
    peak_idx = window.groupby("mo")["signers"].idxmax()
    peak_share = window.loc[peak_idx].set_index("mo")["top_receiver_share"]
    median_share = window.groupby("mo")["top_receiver_share"].median()
    burst_days = window.groupby("mo")["burst_flag"].sum().astype("int64")
    month_flag = burst_days >= BURST_DAYS_TO_FLAG_MONTH

    out = monthly_raw.copy()
    out["mo"] = out["mo"].astype(str)
    out["all_signers"] = out["all_signers"].astype("int64")
    out["net_demand"] = out["net_demand"].astype("int64")
    out["hot_only"] = out["all_signers"] - out["net_demand"]
    out["net_demand_share"] = out["net_demand"] / out["all_signers"]
    out = out.merge(
        peak_share.rename("top_receiver_share_peak_day"),
        left_on="mo",
        right_index=True,
        how="left",
    )
    out = out.merge(
        median_share.rename("top_receiver_share_median_day"),
        left_on="mo",
        right_index=True,
        how="left",
    )
    out = out.merge(burst_days.rename("burst_days"), left_on="mo", right_index=True, how="left")
    out = out.merge(month_flag.rename("burst_flag"), left_on="mo", right_index=True, how="left")
    out["burst_days"] = out["burst_days"].fillna(0).astype("int64")
    out["burst_flag"] = out["burst_flag"].fillna(False)
    out = out.sort_values("mo").reset_index(drop=True)
    return out


def burst_day_table(daily: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "block_date",
        "tx",
        "signers",
        "tx_per_signer",
        "signers_median_28",
        "tx_per_signer_median_28",
        "top_receiver",
        "top_receiver_signers",
        "top_receiver_share",
        "top_receiver_is_hot",
    ]
    bursts = daily[daily["burst_flag"] & daily["in_report_window"]][cols].copy()
    bursts["signer_multiple"] = bursts["signers"] / bursts["signers_median_28"]
    bursts["tx_per_signer_ratio"] = bursts["tx_per_signer"] / bursts["tx_per_signer_median_28"]
    return bursts.reset_index(drop=True)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if "block_date" in out.columns:
        out["block_date"] = pd.to_datetime(out["block_date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
    print(f"WROTE {path.relative_to(ROOT)} ({len(out)} rows)", flush=True)


def _print_verify(monthly: pd.DataFrame, bursts: pd.DataFrame) -> None:
    print("\n== monthly (source of every headline number) ==", flush=True)
    show = monthly[
        [
            "mo",
            "all_signers",
            "net_demand",
            "net_demand_share",
            "burst_flag",
            "burst_days",
            "top_receiver_share_median_day",
            "top_receiver_share_peak_day",
        ]
    ].copy()
    print(show.to_string(index=False), flush=True)
    print("\n== burst days in report window ==", flush=True)
    if bursts.empty:
        print("(none)", flush=True)
    else:
        print(
            bursts[
                [
                    "block_date",
                    "signers",
                    "signer_multiple",
                    "tx_per_signer_ratio",
                    "top_receiver",
                    "top_receiver_share",
                ]
            ].to_string(index=False),
            flush=True,
        )


def main() -> int:
    activity = pd.read_csv(_require("daily_activity.csv"))
    monthly_raw = pd.read_csv(_require("monthly_net_demand.csv"))
    top = pd.read_csv(_require("daily_top_receivers.csv"))

    daily = classify_daily(activity, top)
    monthly = classify_monthly(daily, monthly_raw)
    bursts = burst_day_table(daily)

    _write_csv(daily, PROCESSED / "daily.csv")
    _write_csv(monthly, PROCESSED / "monthly.csv")
    _write_csv(bursts, PROCESSED / "burst_days.csv")
    end = daily.loc[daily["in_report_window"], "block_date"].max()
    print(
        f"WINDOW {DATE_START} to {pd.Timestamp(end).strftime('%Y-%m-%d')} "
        f"(max(block_date) in data/raw/daily_activity.csv)",
        flush=True,
    )
    _print_verify(monthly, bursts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
