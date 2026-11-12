-- Monthly headline signers vs Net Demand.
-- Net Demand = distinct signers who transacted with at least one receiver
-- whose account id does NOT contain 'hot.tg' (the HOT Telegram game,
-- including game.hot.tg). A signer who used both HOT and something else
-- still counts in net_demand; a HOT-only signer does not.
-- Columns read: block_date, signer_account_id, receiver_account_id.
-- Partition filter: block_date BETWEEN DATE '2025-11-01' AND
--   DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY).
-- End bound is the last fully-closed UTC day. Never include today.

SELECT
  FORMAT_DATE('%Y-%m', block_date) AS mo,
  COUNT(DISTINCT signer_account_id) AS all_signers,
  COUNT(DISTINCT IF(receiver_account_id NOT LIKE '%hot.tg',
                    signer_account_id, NULL)) AS net_demand
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN DATE '2025-11-01'
  AND DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 1 DAY)
GROUP BY 1
ORDER BY 1;
