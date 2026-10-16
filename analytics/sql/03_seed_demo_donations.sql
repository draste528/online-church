-- Demo donations (US dollars) so that the statistics block has something to show.
-- Safe to run repeatedly: rows are identified by transaction_reference ('SEED-...') and are not inserted twice.
-- Needs the `donations` table from docs/church_db_init.sql.
--
-- docker compose loads this file automatically on the FIRST start of an empty database volume.
-- For an existing database run:
--   docker compose exec -T postgres_dwh psql -U church_admin -d church_dwh < analytics/sql/03_seed_demo_donations.sql
--
-- Times are given in UTC: peaks at 06-09 UTC (09-12 Moscow, after the liturgy) and 15-18 UTC (evening).
-- The last two rows are NOT completed and must be ignored by the statistics.

INSERT INTO donations
    (amount, currency, target_fund, payment_status, minecraft_blocks_awarded, transaction_reference, created_at)
SELECT
    v.amount,
    'USD',
    v.fund,
    v.status,
    CASE WHEN v.fund = 'minecraft_church' AND v.status = 'completed' THEN floor(v.amount)::int ELSE 0 END,
    v.ref,
    (date_trunc('day', NOW() AT TIME ZONE 'UTC') - v.days_ago * INTERVAL '1 day'
        + v.hour * INTERVAL '1 hour' + v.minute * INTERVAL '1 minute') AT TIME ZONE 'UTC'
FROM (VALUES
    ('SEED-0001',   25.00, 'general',            'completed', 1,  6, 15),
    ('SEED-0002',   50.00, 'temple_restoration', 'completed', 1,  7, 40),
    ('SEED-0003',   15.00, 'choir',              'completed', 1,  8, 5),
    ('SEED-0004',   10.00, 'general',            'completed', 1, 16, 30),
    ('SEED-0005',  100.00, 'temple_restoration', 'completed', 2,  7, 10),
    ('SEED-0006',    8.00, 'charity',            'completed', 2,  8, 45),
    ('SEED-0007',   35.00, 'minecraft_church',   'completed', 2, 17, 20),
    ('SEED-0008',   25.00, 'general',            'completed', 3,  6, 50),
    ('SEED-0009',    5.00, 'charity',            'completed', 3,  9, 5),
    ('SEED-0010',   75.00, 'minecraft_church',   'completed', 3, 15, 55),
    ('SEED-0011',   12.50, 'choir',              'completed', 4,  7, 25),
    ('SEED-0012',  150.00, 'temple_restoration', 'completed', 4,  8, 10),
    ('SEED-0013',   20.00, 'general',            'completed', 4, 18, 35),
    ('SEED-0014',   30.00, 'charity',            'completed', 5,  6, 5),
    ('SEED-0015',   17.50, 'general',            'completed', 5,  7, 55),
    ('SEED-0016',   40.00, 'minecraft_church',   'completed', 5, 16, 15),
    ('SEED-0017',    6.00, 'general',            'completed', 6,  9, 30),
    ('SEED-0018',  100.00, 'temple_restoration', 'completed', 6, 17, 45),
    ('SEED-0019',   22.50, 'choir',              'completed', 6,  7, 35),
    ('SEED-0020',   45.00, 'charity',            'completed', 7,  8, 20),
    ('SEED-0021',   25.00, 'general',            'completed', 7, 15, 10),
    ('SEED-0022',   13.75, 'general',            'completed', 8,  7, 5),
    ('SEED-0023',   60.00, 'minecraft_church',   'completed', 8, 16, 50),
    ('SEED-0024',    9.00, 'charity',            'completed', 9,  6, 40),
    ('SEED-P001',   49.99, 'general',            'pending',   1, 12, 0),
    ('SEED-F001',   49.99, 'choir',              'failed',    2, 12, 0)
) AS v(ref, amount, fund, status, days_ago, hour, minute)
ON CONFLICT (transaction_reference) DO NOTHING;
