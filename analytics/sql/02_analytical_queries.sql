-- =========================================================================
-- 1. Deduplication using ROW_NUMBER: select the latest transaction entry
-- =========================================================================
WITH RankedTransactions AS (
    SELECT 
        raw_id,
        transaction_id,
        user_id,
        amount,
        currency,
        fund_type,
        ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id 
            ORDER BY ingested_at DESC
        ) AS row_num
    FROM staging.stg_donations
)
SELECT 
    transaction_id,
    user_id,
    amount,
    currency,
    fund_type,
    ingested_at
FROM RankedTransactions
WHERE row_num = 1;

-- =========================================================================
-- 2. Day-over-day collection dynamics using LAG
-- =========================================================================
SELECT 
    report_date,
    SUM(total_amount) AS daily_total,
    LAG(SUM(total_amount), 1) OVER (
        ORDER BY report_date
    ) AS previous_day_total,
    ROUND(
        SUM(total_amount) - LAG(SUM(total_amount), 1) OVER (ORDER BY report_date),
        2
    ) AS absolute_change_rub
FROM marts.mart_daily_finances
GROUP BY report_date
ORDER BY report_date;

-- =========================================================================
-- 3. Top benefactors ranking using DENSE_RANK
-- =========================================================================
SELECT 
    user_id,
    COUNT(fact_id) AS donations_count,
    SUM(amount_base_currency) AS total_donated_rub,
    DENSE_RANK() OVER (
        ORDER BY SUM(amount_base_currency) DESC
    ) AS benefactor_rank
FROM core.fact_donations
WHERE user_id IS NOT NULL
GROUP BY user_id
LIMIT 10;
EOFcat << 'EOF' > analytics/sql/02_analytical_queries.sql
-- =========================================================================
-- 1. Deduplication using ROW_NUMBER: select the latest transaction entry
-- =========================================================================
WITH RankedTransactions AS (
    SELECT 
        raw_id,
        transaction_id,
        user_id,
        amount,
        currency,
        fund_type,
        ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id 
            ORDER BY ingested_at DESC
        ) AS row_num
    FROM staging.stg_donations
)
SELECT 
    transaction_id,
    user_id,
    amount,
    currency,
    fund_type,
    ingested_at
FROM RankedTransactions
WHERE row_num = 1;

-- =========================================================================
-- 2. Day-over-day collection dynamics using LAG
-- =========================================================================
SELECT 
    report_date,
    SUM(total_amount) AS daily_total,
    LAG(SUM(total_amount), 1) OVER (
        ORDER BY report_date
    ) AS previous_day_total,
    ROUND(
        SUM(total_amount) - LAG(SUM(total_amount), 1) OVER (ORDER BY report_date),
        2
    ) AS absolute_change_rub
FROM marts.mart_daily_finances
GROUP BY report_date
ORDER BY report_date;

-- =========================================================================
-- 3. Top benefactors ranking using DENSE_RANK
-- =========================================================================
SELECT 
    user_id,
    COUNT(fact_id) AS donations_count,
    SUM(amount_base_currency) AS total_donated_rub,
    DENSE_RANK() OVER (
        ORDER BY SUM(amount_base_currency) DESC
    ) AS benefactor_rank
FROM core.fact_donations
WHERE user_id IS NOT NULL
GROUP BY user_id
LIMIT 10;
