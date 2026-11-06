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
-- 4. Shop orders per day with day-over-day change using LAG (cancelled orders give no revenue)
-- =========================================================================
WITH daily AS (
    SELECT
        DATE(created_at) AS order_date,
        COUNT(*) AS orders,
        SUM(CASE WHEN status <> 'cancelled' THEN total ELSE 0 END) AS revenue
    FROM shop_orders
    GROUP BY DATE(created_at)
)
SELECT
    order_date,
    orders,
    revenue,
    revenue - LAG(revenue) OVER (ORDER BY order_date) AS revenue_change
FROM daily
ORDER BY order_date DESC;

-- =========================================================================
-- 5. Best-selling shop items ranked with DENSE_RANK
-- =========================================================================
SELECT
    l.title,
    SUM(l.quantity) AS quantity,
    SUM(l.line_total) AS revenue,
    DENSE_RANK() OVER (ORDER BY SUM(l.quantity) DESC) AS sales_rank
FROM shop_order_lines l
JOIN shop_orders o ON o.order_id = l.order_id
WHERE o.status <> 'cancelled'
GROUP BY l.title
ORDER BY sales_rank
LIMIT 10;

-- =========================================================================
-- 6. Time spent in each order status using LEAD over the status history (needs shop_order_events, SCRUM-27)
-- =========================================================================
WITH steps AS (
    SELECT
        order_id,
        status,
        created_at,
        LEAD(created_at) OVER (PARTITION BY order_id ORDER BY created_at) AS next_at
    FROM shop_order_events
)
SELECT
    status,
    COUNT(*) AS transitions,
    ROUND(AVG(EXTRACT(EPOCH FROM next_at - created_at)) / 3600, 2) AS avg_hours_in_status
FROM steps
WHERE next_at IS NOT NULL
GROUP BY status
ORDER BY avg_hours_in_status DESC;
