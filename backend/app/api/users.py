import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import require_roles
from .auth import UserOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["Users"])


class RoleIn(BaseModel):
    role: Literal["parishioner", "priest", "admin"]


@router.patch("/{user_id}/role", response_model=UserOut)
def change_role(
    user_id: uuid.UUID, payload: RoleIn, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)
):
    """Admin only: make a user a parishioner, priest or admin. The change applies to existing tokens at once."""
    if user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Нельзя изменить собственную роль.")
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    user.role = payload.role
    db.commit()
    log.info("Admin %s set role of user %s to %s", admin.user_id, user.user_id, payload.role)
    return user
