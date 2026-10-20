import logging
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from analytics.src.db import get_engine
from analytics.src.schemas.sessions import RawSessionRecord, SessionAnalyticsSummary

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics/sessions", tags=["Session Analytics"])


@router.post("", status_code=status.HTTP_201_CREATED)
def record_session(payload: RawSessionRecord):
    """Stores or updates session activity from frontend heartbeat/unload."""
    query = text("""
        INSERT INTO analytics_user_sessions (
            session_id, started_at, ended_at, duration_seconds,
            pages_visited, total_donated, total_ordered,
            chat_questions_count, candles_lit_count, language
        )
        VALUES (
            :session_id, :started_at, :ended_at, :duration_seconds,
            :pages_visited, :total_donated, :total_ordered,
            :chat_messages_count, :candles_lit_count, :language
        )
        ON CONFLICT (session_id) DO UPDATE SET
            ended_at = EXCLUDED.ended_at,
            duration_seconds = EXCLUDED.duration_seconds,
            pages_visited = EXCLUDED.pages_visited,
            total_donated = EXCLUDED.total_donated,
            total_ordered = EXCLUDED.total_ordered,
            chat_questions_count = EXCLUDED.chat_questions_count,
            candles_lit_count = EXCLUDED.candles_lit_count,
            language = EXCLUDED.language;
    """)

    try:
        with get_engine().begin() as conn:
            conn.execute(query, payload.model_dump())
        return {"status": "ok", "session_id": payload.session_id}
    except Exception as exc:
        log.error("Failed to save session analytics: %s", exc)
        raise HTTPException(status_code=500, detail="Database error recording session")


@router.get("/summary", response_model=SessionAnalyticsSummary)
def get_session_summary():
    """Returns aggregated ETL metrics about parishioner sessions."""
    sql = text("""
        SELECT
            COUNT(*) as total_sessions,
            COALESCE(AVG(duration_seconds), 0) as avg_duration,
            COALESCE(SUM(total_donated + total_ordered), 0) as total_amount,
            COUNT(*) FILTER (WHERE (total_donated + total_ordered) > 0) as paying_sessions,
            COALESCE(SUM(chat_questions_count), 0) as total_chat,
            COALESCE(SUM(candles_lit_count), 0) as total_candles
        FROM analytics_user_sessions;
    """)

    pages_sql = text("""
        SELECT unnest(pages_visited) as page, COUNT(*) as visits
        FROM analytics_user_sessions
        GROUP BY page
        ORDER BY visits DESC
        LIMIT 5;
    """)

    try:
        with get_engine().connect() as conn:
            row = conn.execute(sql).mappings().one()
            top_pages = [dict(r) for r in conn.execute(pages_sql).mappings().all()]

        total = row["total_sessions"]
        paying = row["paying_sessions"]
        conversion = (paying / total * 100.0) if total > 0 else 0.0

        return SessionAnalyticsSummary(
            total_sessions=total,
            avg_duration_seconds=round(float(row["avg_duration"]), 1),
            total_amount_collected=round(float(row["total_amount"]), 2),
            sessions_with_payments_count=paying,
            conversion_rate_percent=round(conversion, 2),
            top_visited_pages=top_pages,
            total_chat_questions=int(row["total_chat"]),
            total_candles_lit=int(row["total_candles"]),
        )
    except Exception as exc:
        log.error("Failed to calculate session summary: %s", exc)
        # TODO(Anton): add pytest for empty analytics_user_sessions table
        raise HTTPException(status_code=500, detail="Database error calculating summary")
