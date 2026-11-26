BEGIN;

CREATE SCHEMA IF NOT EXISTS appointment_events;
CREATE SCHEMA IF NOT EXISTS appointment_metrics;

CREATE TABLE IF NOT EXISTS appointment_events.events (
    appointment_id uuid NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('requested', 'approved', 'rejected', 'completed')),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (appointment_id, event_type)
);
CREATE INDEX IF NOT EXISTS appointment_events_occurred_at_idx
    ON appointment_events.events (occurred_at);

CREATE TABLE IF NOT EXISTS appointment_metrics.coverage (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    started_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS appointment_metrics.weekly (
    week_start date PRIMARY KEY CHECK (extract(isodow FROM week_start) = 1),
    requested bigint NOT NULL CHECK (requested >= 0),
    approved bigint NOT NULL CHECK (approved >= 0),
    rejected bigint NOT NULL CHECK (rejected >= 0),
    completed bigint NOT NULL CHECK (completed >= 0)
);

-- Call from the same transaction as the booking mutation. The writer chooses neither the
-- timestamp nor the contents of an existing event. The DWH never reads individual IDs.
CREATE OR REPLACE FUNCTION appointment_events.record(booking_id uuid, transition text)
RETURNS void LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    INSERT INTO appointment_events.events (appointment_id, event_type)
    VALUES (booking_id, transition)
    ON CONFLICT (appointment_id, event_type) DO NOTHING;
$$;

-- Run after the transactional writer is live. Repeated calls preserve the initial start.
CREATE OR REPLACE FUNCTION appointment_metrics.enable()
RETURNS timestamptz LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    LOCK TABLE appointment_events.events IN SHARE ROW EXCLUSIVE MODE;
    INSERT INTO appointment_metrics.coverage (started_at)
    VALUES (clock_timestamp())
    ON CONFLICT (singleton) DO NOTHING;
    RETURN (SELECT c.started_at FROM appointment_metrics.coverage AS c);
END;
$$;

-- Only fully covered weeks among the last eight closed calendar weeks qualify.
-- A week enters the visible window at 01:00 Moscow time on the following Monday.
CREATE OR REPLACE FUNCTION appointment_metrics.report_weeks(as_of timestamptz)
RETURNS TABLE (week_start date, starts_at timestamptz, ends_at timestamptz)
LANGUAGE sql STABLE SET search_path = pg_catalog, pg_temp AS $$
    SELECT w.week_start, w.starts_at, w.ends_at
    FROM appointment_metrics.coverage AS c
    CROSS JOIN generate_series(1, 8) AS n(weeks_back)
    CROSS JOIN LATERAL (
        SELECT date_trunc('week', as_of AT TIME ZONE 'Europe/Moscow')::date - 7 * n.weeks_back AS week_start
    ) AS d
    CROSS JOIN LATERAL (
        SELECT d.week_start,
               d.week_start::timestamp AT TIME ZONE 'Europe/Moscow' AS starts_at,
               (d.week_start + 7)::timestamp AT TIME ZONE 'Europe/Moscow' AS ends_at
    ) AS w
    WHERE w.starts_at >= c.started_at AND as_of >= w.ends_at + interval '1 hour';
$$;

CREATE OR REPLACE FUNCTION appointment_metrics.refresh()
RETURNS integer LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    snapshot record;
    inserted integer := 0;
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Appointment refresh requires READ COMMITTED isolation' USING ERRCODE = '55000';
    END IF;

    -- Drain in-flight event writers before taking the read snapshot and serialize refreshes.
    -- Writers admitted after this lock have a database-assigned timestamp outside the closed weeks.
    LOCK TABLE appointment_events.events IN SHARE ROW EXCLUSIVE MODE;
    IF NOT EXISTS (SELECT 1 FROM appointment_metrics.coverage) THEN
        RAISE EXCEPTION 'Appointment analytics coverage is not enabled' USING ERRCODE = '55000';
    END IF;

    FOR snapshot IN
        SELECT w.week_start,
               count(*) FILTER (WHERE e.event_type = 'requested') AS requested,
               count(*) FILTER (WHERE e.event_type = 'approved') AS approved,
               count(*) FILTER (WHERE e.event_type = 'rejected') AS rejected,
               count(*) FILTER (WHERE e.event_type = 'completed') AS completed
        FROM appointment_metrics.report_weeks(clock_timestamp()) AS w
        LEFT JOIN appointment_events.events AS e ON e.occurred_at >= w.starts_at AND e.occurred_at < w.ends_at
        GROUP BY w.week_start
    LOOP
        INSERT INTO appointment_metrics.weekly (week_start, requested, approved, rejected, completed)
        VALUES (snapshot.week_start, snapshot.requested, snapshot.approved, snapshot.rejected, snapshot.completed)
        ON CONFLICT (week_start) DO NOTHING;

        IF FOUND THEN
            inserted := inserted + 1;
        ELSIF NOT EXISTS (
            SELECT 1 FROM appointment_metrics.weekly AS w
            WHERE w.week_start = snapshot.week_start
              AND (w.requested, w.approved, w.rejected, w.completed) =
                  (snapshot.requested, snapshot.approved, snapshot.rejected, snapshot.completed)
        ) THEN
            -- Publishing revised counts would let a reader recover small changes by subtraction.
            RAISE EXCEPTION 'Published appointment counts differ for week %', snapshot.week_start
                USING ERRCODE = '55000';
        END IF;
    END LOOP;

    RETURN inserted;
END;
$$;

CREATE OR REPLACE FUNCTION appointment_metrics.summary()
RETURNS TABLE (week_start date, requested bigint, approved bigint, rejected bigint, completed bigint, suppressed boolean)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM appointment_metrics.coverage) OR EXISTS (
        SELECT 1 FROM appointment_metrics.report_weeks(statement_timestamp()) AS expected
        LEFT JOIN appointment_metrics.weekly AS w USING (week_start)
        WHERE w.week_start IS NULL
    ) THEN
        RAISE EXCEPTION 'Appointment metrics are not available' USING ERRCODE = '55000';
    END IF;

    RETURN QUERY
        SELECT w.week_start,
               CASE WHEN NOT privacy.suppressed THEN w.requested END,
               CASE WHEN NOT privacy.suppressed THEN w.approved END,
               CASE WHEN NOT privacy.suppressed THEN w.rejected END,
               CASE WHEN NOT privacy.suppressed THEN w.completed END,
               privacy.suppressed
        FROM appointment_metrics.report_weeks(statement_timestamp()) AS expected
        JOIN appointment_metrics.weekly AS w ON w.week_start = expected.week_start
        CROSS JOIN LATERAL (
            SELECT w.requested BETWEEN 1 AND 4 OR w.approved BETWEEN 1 AND 4
                OR w.rejected BETWEEN 1 AND 4 OR w.completed BETWEEN 1 AND 4 AS suppressed
        ) AS privacy;
END;
$$;

REVOKE ALL ON SCHEMA appointment_events, appointment_metrics FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA appointment_events, appointment_metrics FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA appointment_events, appointment_metrics FROM PUBLIC;

COMMIT;
