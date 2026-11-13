# Subsidy Filter

**Dashboard:** https://adindamochamad.github.io/subsidy-filter/

Counts NEAR active accounts with and without the HOT Telegram game, and flags days that match a burst signature (headcount up, intensity down).

## The problem

NEAR headline active-account numbers mix three things: a consumer Telegram game (`game.hot.tg` and other `*hot.tg` receivers), short bursts of one-transaction accounts, and everything else. A long-term thesis that uses the headline without splitting those is using a contaminated series.

## How NEAR data makes it possible

`bigquery-public-data.crypto_near_mainnet_us.transactions` is a public, hourly-updated table partitioned on `block_date`. It has `signer_account_id` and `receiver_account_id`. Distinct signers per month is the headline. Distinct signers who touched at least one receiver not matching `%hot.tg` is Net Demand. Daily `tx / signers` versus a 28-day trailing median is the burst detector. This repo does not use `receipt_actions` (14 TB).

Queries are in `extract/sql/`. Thresholds are named constants in `classify/config.py`. Window start: 2025-11-01. Window end: `max(block_date)` in `data/raw/daily_activity.csv` (last fully-closed UTC day at extract time; the current UTC day is never included). Daily extracts start 2025-10-04 for the trailing median. November 2026 is a partial month ending on that `max(block_date)`.

## Reproduce in 3 minutes

No BigQuery credentials. No network is required after the pip install (Fontshare/Google Fonts are referenced by the HTML but are not needed to build it).

1. `python3 -m venv .venv && .venv/bin/pip install pandas matplotlib`
   -> pip reports pandas and matplotlib installed.
2. `.venv/bin/python -m classify.run` from the repo root with `PYTHONPATH=.`
   -> prints `WINDOW 2025-11-01 to` followed by `max(block_date)` from `data/raw/daily_activity.csv`, then the 13-row monthly table. Expected last lines of that table:

```
2026-08       215609       63134          0.292817       False           0                       0.960865                     0.960936
2026-09       302272      160431          0.530750       False           0                       0.886432                     0.957826
2026-10       826700      722549          0.874016        True           3                       0.833327                     0.263939
2026-11       259859      138154          0.531650        True           1                       0.940642                     0.550482
```

   Columns after burst_days are `top_receiver_share_median_day` then `top_receiver_share_peak_day`. Six burst days: 2026-02-15, 2026-02-17, 2026-10-03, 2026-10-04, 2026-10-07, 2026-11-10. The dashboard kicker date equals that WINDOW end, not a constant.
   Also writes `data/processed/monthly.csv`, `data/processed/daily.csv`, `data/processed/burst_days.csv`.
3. `PYTHONPATH=. .venv/bin/python -m dashboard.build`
   -> prints `WROTE dashboard/index.html` and a byte size. Open `dashboard/index.html`. Figure 1 has two lines labelled Reported and Net Demand on a log y-axis; the monthly table matches step 2.

Equivalent: `PYTHONPATH=. make all PYTHON=.venv/bin/python`.

`make extract` is the only target that talks to BigQuery. Do not run it unless you have ADC on project `tessera-496904`. Every extract query is dry-run first and refused above 50 GB. Dataset location is `us-east1`.

## Headline findings

From `data/raw/monthly_net_demand.csv` and `data/processed/*.csv`. Full argument in `THESIS.md`. Dashboard in `dashboard/index.html`.

- `game.hot.tg` is the #1 receiver by distinct signers on 375 / 376 days. Median share of a non-burst day’s signers: 95.4%.
- Ten months have no burst flag. In those months Net Demand is 28.0%–63.9% of reported signers (median 35.2%). August 2026: 215,609 reported, 63,134 Net Demand. July 2026 is the widest gap: 72.0% of the headline is not Net Demand.
- Six burst days (2.5× trailing-median signers and tx/signer below 60% of its trailing median): 2026-02-15 (592,250 signers), 2026-02-17 (541,983), 2026-10-03 (176,719), 2026-10-04 (177,196), 2026-10-07 (175,774), 2026-11-10 (177,510).
- 2026-11-10 is attributed: `3d9ccff55cef5a3efd1fe14b14509b726123910845243ef1671b45e46f214324` received from 97,716 distinct signers that day and from 80 the next day. February and October bursts are not named in the top 20 beyond `game.hot.tg` at 24–26% share; they may be product launches. See THESIS.md. November 2026 is a partial month ending at `max(block_date)`. The monthly table uses `top_receiver_share_median_day` (November 94.1%), not the peak-day share (55.0% on 10 Nov).
- February 2026: 3,791,961 reported, 3,521,593 Net Demand (92.9%). March 2026 Net Demand: 133,640.

## Out of scope

Interactive filters. Live refresh. Wallet connect. Smart contracts. ML or forecasting. Multi-chain comparison. User accounts. Dark mode. `receipt_actions`. USD or token volumes. Inner receipts. Function names. Human identity.

## License

MIT. See `LICENSE`.
