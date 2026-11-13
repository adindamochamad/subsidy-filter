# Subsidy Filter

Window start: 2025-11-01. Window end: `max(block_date)` in `data/raw/daily_activity.csv` — the last fully-closed UTC day when `make extract` last ran. The current UTC day is never included; a partial day reads as a collapse. November 2026 is a partial month ending on that date. Every figure below is in `data/processed/monthly.csv` or `data/processed/burst_days.csv`, which are computed from the committed files in `data/raw/`.

The monthly table reports `top_receiver_share_median_day` (median of daily #1-contract shares that month). `top_receiver_share_peak_day` is also in `monthly.csv`: it is the #1 share on the day with the most signers (0.236 on 15 Feb, 0.550 on 10 Nov). The table uses the median so burst months do not understate typical-day HOT dominance (November median 94.1%).

## The claim, in one sentence.

NEAR’s headline active-account numbers are dominated by one Telegram game (`game.hot.tg`) and by episodic campaign bursts; Net Demand — distinct signers with some activity outside `*hot.tg` — is the figure a long-term thesis should rest on, and in quiet months that figure is a fraction of the headline.

## Evidence for it, each point citing a chart and its query.

1. **`game.hot.tg` is the #1 receiver on 375 of 376 reporting days.** Figure 4, from `extract/sql/daily_top_receivers.sql` joined in `classify/` to `extract/sql/daily_activity.sql`. On non-burst days its median share of that day’s signers is 95.4%. The single exception is 2026-11-10 (see point 5). A chain whose typical day concentrates 19 in 20 active signers on one consumer game is not a diversified activity print.

2. **In months without a burst flag, Net Demand is a minority of the headline.** Figure 1 and the monthly table, from `extract/sql/monthly_net_demand.sql`. Ten months are unflagged. In those months Net Demand / reported ranges from 28.0% (2026-07: 70,617 / 252,587) to 63.9% (2025-12: 584,720 / 915,686), median 35.2%. Seven of thirteen months sit below 40%. August 2026 is the trough: 215,609 reported, 63,134 Net Demand (29.3%). Figure 1 is log-scaled so that gap is readable; the widest monthly gap is July 2026 at 72.0% of the headline.

3. **Six days match the burst signature: headcount up, intensity down.** Figure 2 and Figure 3, from `extract/sql/daily_activity.sql`, thresholds in `classify/config.py` (`SIGNER_BURST_MULTIPLE = 2.5`, `TX_PER_SIGNER_DROP_RATIO = 0.60`, `TRAILING_WINDOW_DAYS = 28`). The flagged days are 2026-02-15 (592,250 signers, 3.39× the trailing median, tx/signer at 0.32 of its median), 2026-02-17 (541,983, 2.54×, 0.41), 2026-10-03 (176,719, 2.87×, 0.27), 2026-10-04 (177,196, 2.87×, 0.33), 2026-10-07 (175,774, 2.85×, 0.39), and 2026-11-10 (177,510, 3.32×, 0.49). Median non-burst day: 123,953 signers. Median burst day: 177,353 signers and 5.5 tx/signer.

4. **HOT-only signers do not produce the headline spikes.** Monthly `all_signers − net_demand` (HOT-only) falls steadily from 359,553 (2025-11) to 104,151 (2026-10). February’s headline is 3,791,961; its HOT-only count is 270,368, in line with the months on either side. The game is a large, slowly shrinking exclusive base. It is not the burst. November 2026 HOT-only is 121,705 over a partial month ending at `max(block_date)` and is not comparable to a 30-day month.

5. **Worked example: 10 November 2026 is attributed to one receiver.** Figure 2, Figure 4, `extract/sql/daily_top_receivers.sql`. 2026-11-10 has 177,510 distinct signers against a 28-day trailing median of 53,513 (3.32×), with tx/signer at 0.49 of its median, so it flags. The #1 receiver that day is `3d9ccff55cef5a3efd1fe14b14509b726123910845243ef1671b45e46f214324`, with 97,716 distinct signers (55.0% of the day). On 2026-11-11 the same receiver has 80 distinct signers. That is a one-day concentration, then gone. November 2026 is a partial month ending at `max(block_date)` in `data/raw/daily_activity.csv`. One attributed burst does not attribute February or October.

## Evidence AGAINST it.

The claim has two parts — (a) HOT dominates the print, (b) bursts are campaigns one should strip before taking a thesis number. (a) holds on typical days. (b) is weaker than the claim needs, and (a) is not what drives the two largest months.

1. **One of three bursts is now attributed to a single receiver; February and October remain unexplained.** 10 November 2026 is named in the top-20 extract (point 5). That does not attribute the other two. On every February and October flagged day the #1 contract is still `game.hot.tg`, but its share of that day’s signers falls to 23.6%–26.4% (Figure 4). Summing distinct signers across the top 20 receivers on 2026-02-15 covers 24.8% of that day’s 592,250 signers — and that sum double-counts anyone who touched two of those contracts. The extra headcount is in the long tail, which this extract does not name. A reader who thinks February and October were product launches is not contradicted by the November contract.

2. **Those unattributed bursts inflate Net Demand, so stripping HOT does not strip them.** February 2026: 3,791,961 reported, 3,521,593 Net Demand (92.9%). October 2026: 826,700 reported, 722,549 Net Demand (87.4%). Figure 1’s rust line spikes with the grey line. If the thesis number is “signers outside HOT,” February and October remain enormous. The claim that Net Demand is the clean figure is false for those two months.

3. **The detector is a knife-edge around a multi-day episode.** 2026-02-03 through 2026-02-18 is one visual episode on Figure 2. Only the 15th and 17th clear 2.5×. 2026-02-16 is 2.42× (below the cut) with tx/signer at 0.43 of median. 2026-02-18 is 2.00×. December 18 2025 reached 366,653 signers (1.61×) with tx/signer at 0.62 of median, one hundredth above the 0.60 intensity cut, and was not flagged; that month’s Net Demand is 584,720, the highest unflagged value. A different constant in `classify/config.py` would reclassify both the February shoulder and December. `top_receiver_share_median_day` corroborates the undercount independently: non-burst months run 0.88–0.96, while February is 0.591 and October 0.833 — HOT’s share is depressed across those whole months, not only on the flagged days. December 2025 is the control (peak day 0.550, median day 0.947): one anomalous day inside an otherwise normal month. February was month-long; the detector caught two days of it. The day-level flag undercounts a month-scale episode. The median-day column is the better instrument for episode extent; the day-level flag is the better instrument for onset. Thresholds are left as they are.

4. **A non-HOT base exists and is not small.** Even in the quiet trough, 63,134 monthly signers did something outside `*hot.tg`. December 2025’s 584,720 Net Demand, unflagged, is not a rounding error. Treating Net Demand as “the leftover after the fake activity” oversells how much of it is residual.

5. **Persistence after February argues against a retained product launch — but that is not attribution.** February Net Demand is 26.4× March (3,521,593 → 133,640). A launch that kept its users would not collapse that far in one month. That is evidence against the launch reading, not identification of a farm. October’s following month is now in the extract, but it is a partial November 2026 ending at `max(block_date)` and includes its own 10 Nov burst, so it is not a clean retention test.

## What result would change my mind, stated as a falsifiable condition.

Three independent conditions. Any one falsifies the corresponding part of the claim on a later window built with the same SQL and the same constants.

- **Concentration.** In a subsequent 12-month window, if `game.hot.tg` is the daily #1 receiver on fewer than 183 days, or if the median non-burst daily `top_receiver_share` is below 50%, the “one Telegram game dominates the typical day” claim is false.
- **Bursts as campaigns, not launches.** If a burst month’s Net Demand in each of the next two months remains at least 50% of that burst month’s Net Demand, the “episode does not stick, so it is not demand” reading is false. February 2026 fails this test in the present window (March is 3.8% of February). October 2026 cannot be tested cleanly here: the next month is partial (ending at `max(block_date)`) and itself contains a burst.
- **Net Demand as the thesis number.** If, in a subsequent 12-month window, Net Demand / reported is at least 80% in 10 or more months, exclusive HOT activity is no longer large enough to justify substituting Net Demand for the headline.

## Method limitations: what this cannot measure from these sources.

- **People.** `signer_account_id` is an account, not a human. One person with many accounts counts many times. Shared keys count once.
- **USD, tokens, or fees.** The extract never reads amounts. `receipt_actions` would, at 14 TB unfiltered; it is not used.
- **What the transaction did.** No function name, no success/failure filter (`status` is in the table and unused, matching the verified queries), no inner receipts. The 10 Nov receiver is an implicit account id; this extract cannot say what the contract did.
- **New versus returning.** Monthly distinct signers do not say whether February’s 3.5 million Net Demand accounts were new that month.
- **The long tail.** Top 20 receivers per day cannot name the contracts that held ~75% of signers on the February and October burst days.
- **HOT-adjacent activity that does not match `%hot.tg`.** A related contract under another suffix is Net Demand. A single `wrap.near` transfer in the same month moves a HOT-only signer into Net Demand. Both bias Net Demand up.
- **Slow farms.** A campaign that ramps over weeks without a 2.5× one-day jump never flags.
- **Anything after `max(block_date)` in the extract.** Re-run `make extract` only after the UTC day you want has closed. Later HOT share is not measured.
- **Other chains, developers, TVL, price.** Out of scope by construction.
- **Partial November.** 2026-11 counts run from 1 Nov through `max(block_date)`. They are not a 30-day month and must not be compared as one.
