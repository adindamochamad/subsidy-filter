-- Daily transaction count and distinct signers.
-- tx / signers is the intensity ratio used by classify/ to detect quota
-- bursts (headcount spikes while tx-per-signer falls).
-- Columns read: block_date, signer_account_id.
-- Partition filter: block_date BETWEEN DATE '2025-10-04' AND
--   DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY).
-- Window starts 28 days before the reporting start (2025-11-01) so the
-- trailing-median burst detector has a full baseline in November 2025.
-- End bound is the last fully-closed UTC day. Never include today:
-- a partial day reads as a collapse on the daily chart.

SELECT
  block_date,
  COUNT(*) AS tx,
  COUNT(DISTINCT signer_account_id) AS signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE '2025-10-04'
  AND DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY)
GROUP BY 1
ORDER BY 1;
