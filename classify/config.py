"""Named constants for the extract window and burst detector.

Change a number here. Do not hunt through charts or SQL for thresholds.
Extract SQL ends at DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY).
Displayed date ranges are max(block_date) in data/raw/daily_activity.csv.
"""

from datetime import datetime, timedelta, timezone

# --- GCP / cost -------------------------------------------------------------

GCP_PROJECT = "tessera-496904"

# Linked Analytics Hub dataset. `bq show` reports location us-east1,
# not the US multi-region. Jobs must run in this location.
BQ_LOCATION = "us-east1"

# Refuse to run any query whose dry-run estimate exceeds this.
# 50 GB = 50 * 10^9 bytes (BigQuery console GB, not GiB).
MAX_BYTES_PER_QUERY = 50 * 1_000_000_000

# --- Window -----------------------------------------------------------------
# DATE_START is the first reporting day. DATE_EXTRACT_START is 28 days
# before that so the trailing-median detector has a full baseline.
#
# Never include the current UTC day. A partial day reads as a collapse
# (2026-11-12 extracted mid-day showed 37,519 signers vs a normal ~77,000
# and became the lowest point on Figure 2). The extract SQL ends at
# DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY). Displayed ranges must
# come from max(block_date) in data/raw/daily_activity.csv, not from
# this constant, so the header cannot claim a date the CSV does not have.

DATE_START = "2025-11-01"
DATE_END = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
DATE_EXTRACT_START = "2025-10-04"

# --- HOT filter -------------------------------------------------------------
# HOT Telegram game. SQL uses LIKE '%hot.tg' (see monthly_net_demand.sql).
# A receiver counts as HOT when this substring appears in the account id.
# Covers game.hot.tg and other *.hot.tg contracts. Change here and in
# monthly_net_demand.sql together.

HOT_RECEIVER_SUBSTRING = "hot.tg"

# --- Burst detector ---------------------------------------------------------
# A day is flagged as a burst when BOTH conditions hold against the
# trailing median of the prior TRAILING_WINDOW_DAYS days (current day
# excluded). This is the signature of a quota campaign: many new
# accounts, each doing very little.

TRAILING_WINDOW_DAYS = 28
# Why 28: four weeks of prior days. Long enough that one noisy weekend
# does not move the baseline; short enough that a regime change is
# visible within a month. Median, not mean, so a previous burst does
# not inflate the bar for the next one.

SIGNER_BURST_MULTIPLE = 2.5
# Why 2.5: distinct signers must exceed 2.5x the trailing 28-day median.
# Weekly seasonality on a chain like this is typically well below 2x.
# A quota campaign that spins up a large fresh cohort in one day clears
# 2.5x. Lower this to flag more days; raise it if you think 2.5x still
# catches ordinary product launches.

TX_PER_SIGNER_DROP_RATIO = 0.60
# Why 0.60: tx-per-signer must fall below 60% of its trailing 28-day
# median. Campaigns that pay per account produce many signers who send
# one transaction and stop, so intensity drops while headcount spikes.
# A genuine product launch more often keeps or raises tx-per-signer.
# Both this AND SIGNER_BURST_MULTIPLE must fire.

BURST_DAYS_TO_FLAG_MONTH = 1
# A reporting month is burst-flagged when it contains at least this many
# burst days. 1 means a single qualifying day flags the month.

TOP_RECEIVERS_PER_DAY = 20
# Rows kept per day in daily_top_receivers.sql. Matches the verified
# one-day attribution query (LIMIT 20). classify/ uses rank 1 of these
# to compute top_receiver_share.

# --- Derived monthly metric -------------------------------------------------
# classify/ always writes both:
#   top_receiver_share_median_day — median of daily #1 shares that month
#     (typical-day HOT dominance; this is what the monthly table shows)
#   top_receiver_share_peak_day   — #1 share on the day with the most
#     signers (collapses in burst months; kept in the CSV, not the table)
# TOP_RECEIVER_SHARE_AGG is unused by the table; both columns are always
# computed so a reader can disagree in the CSV without re-extracting.

TOP_RECEIVER_SHARE_AGG = "median_day"
