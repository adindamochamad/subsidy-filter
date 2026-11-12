-- Top 20 receiver contracts per day by distinct signers.
-- Generalizes the verified one-day attribution query across the extract
-- window so burst days can be attributed offline after classification,
-- with no second BigQuery round-trip.
-- top_receiver_share is computed in classify/ as
--   (signers of the day's #1 receiver) / (that day's distinct signers).
-- Columns read: block_date, receiver_account_id, signer_account_id.
-- Partition filter: block_date BETWEEN DATE '2025-10-04' AND
--   DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY).
-- Window matches daily_activity.sql. End bound is the last fully-closed
-- UTC day. Never include today.

WITH per_receiver AS (
  SELECT
    block_date,
    receiver_account_id,
    COUNT(DISTINCT signer_account_id) AS signers
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date BETWEEN DATE '2025-10-04'
    AND DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY)
  GROUP BY 1, 2
),
ranked AS (
  SELECT
    block_date,
    receiver_account_id,
    signers,
    ROW_NUMBER() OVER (
      PARTITION BY block_date
      ORDER BY signers DESC, receiver_account_id
    ) AS rn
  FROM per_receiver
)
SELECT
  block_date,
  receiver_account_id,
  signers
FROM ranked
WHERE rn <= 20
ORDER BY block_date, signers DESC;
