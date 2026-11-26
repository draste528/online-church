"""Administrator report backed by the published appointment aggregates."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_roles

router = APIRouter(
    prefix="/api/v1/analytics/appointments",
    tags=["Analytics"],
    dependencies=[Depends(require_roles("admin"))],
)


class AppointmentWeek(BaseModel):
    week_start: date
    requested: int | None
    approved: int | None
    rejected: int | None
    completed: int | None
    suppressed: bool


class AppointmentSummary(BaseModel):
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    minimum_group: Literal[5] = 5
    weeks: list[AppointmentWeek]


@router.get("/summary", response_model=AppointmentSummary, responses={
    401: {"description": "Требуется авторизация"},
    403: {"description": "Требуется роль администратора"},
    422: {"description": "Параметры запроса не поддерживаются"},
    503: {"description": "Витрина временно недоступна"},
})
def get_appointment_summary(
    request: Request, response: Response, db: Session = Depends(get_db),
) -> AppointmentSummary:
    if request.query_params:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["query"], "msg": "Параметры запроса не поддерживаются.", "type": "extra_forbidden"}],
        )

    rows = db.execute(text(
        "SELECT week_start, requested, approved, rejected, completed, suppressed "
        "FROM appointment_metrics.summary() ORDER BY week_start"
    )).mappings()
    response.headers["Cache-Control"] = "no-store"
    return AppointmentSummary(weeks=[AppointmentWeek.model_validate(row) for row in rows])
