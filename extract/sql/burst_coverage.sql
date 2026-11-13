-- Top receivers (excluding HOT) and signer coverage on burst days.
-- Coverage uses distinct signers who touched any of the top-N receivers,
-- not a sum of per-receiver counts (which double-counts).
-- Partition filter: block_date IN six fixed burst days (literal list).

WITH day_totals AS (
  SELECT
    block_date,
    COUNT(DISTINCT signer_account_id) AS day_signers
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date IN (
    DATE '2026-02-15',
    DATE '2026-02-17',
    DATE '2026-10-03',
    DATE '2026-10-04',
    DATE '2026-10-07',
    DATE '2026-11-10'
  )
  GROUP BY 1
),
non_hot AS (
  SELECT
    block_date,
    signer_account_id,
    receiver_account_id
  FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
  WHERE block_date IN (
    DATE '2026-02-15',
    DATE '2026-02-17',
    DATE '2026-10-03',
    DATE '2026-10-04',
    DATE '2026-10-07',
    DATE '2026-11-10'
  )
    AND receiver_account_id NOT LIKE '%hot.tg'
),
per_receiver AS (
  SELECT
    block_date,
    receiver_account_id,
    COUNT(DISTINCT signer_account_id) AS receiver_signers
  FROM non_hot
  GROUP BY 1, 2
),
ranked AS (
  SELECT
    block_date,
    receiver_account_id,
    receiver_signers,
    ROW_NUMBER() OVER (
      PARTITION BY block_date
      ORDER BY receiver_signers DESC, receiver_account_id
    ) AS receiver_rank
  FROM per_receiver
),
top_rows AS (
  SELECT
    block_date,
    'top' AS row_kind,
    receiver_account_id,
    receiver_rank,
    receiver_signers,
    receiver_signers / day_signers AS receiver_share,
    day_signers,
    CAST(NULL AS FLOAT64) AS cover_10,
    CAST(NULL AS FLOAT64) AS cover_20,
    CAST(NULL AS FLOAT64) AS cover_50
  FROM ranked
  JOIN day_totals USING (block_date)
  WHERE receiver_rank <= 30
),
signer_min_rank AS (
  SELECT
    nh.block_date,
    nh.signer_account_id,
    MIN(ranked.receiver_rank) AS min_rank
  FROM non_hot nh
  JOIN ranked
    ON nh.block_date = ranked.block_date
   AND nh.receiver_account_id = ranked.receiver_account_id
  GROUP BY 1, 2
),
coverage AS (
  SELECT
    block_date,
    'coverage' AS row_kind,
    CAST(NULL AS STRING) AS receiver_account_id,
    CAST(NULL AS INT64) AS receiver_rank,
    CAST(NULL AS INT64) AS receiver_signers,
    CAST(NULL AS FLOAT64) AS receiver_share,
    day_signers,
    COUNTIF(min_rank <= 10) / day_signers AS cover_10,
    COUNTIF(min_rank <= 20) / day_signers AS cover_20,
    COUNTIF(min_rank <= 50) / day_signers AS cover_50
  FROM signer_min_rank
  JOIN day_totals USING (block_date)
  GROUP BY block_date, day_signers
)
SELECT * FROM top_rows
UNION ALL
SELECT * FROM coverage
ORDER BY block_date, row_kind DESC, receiver_rank;
