# app/dependencies.py
import uuid
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import ALGORITHM, SECRET_KEY


class CustomHTTPBearer(HTTPBearer):
    """Кастомный Bearer для возврата 401 вместо 403 при отсутствии токена (по документации)."""
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        try:
            return await super().__call__(request)
        except HTTPException as e:
            if e.status_code == 403 and e.detail == "Not authenticated":
                raise HTTPException(status_code=401, detail="Отсутствует токен авторизации.")
            raise e


security = CustomHTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """Проверка токена и получение текущего пользователя."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Недействительный токен (отсутствует sub).")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Срок действия токена истёк.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен.")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Неверный формат ID пользователя в токене.")

    user = db.get(User, uid)
    if user is None or user.is_deleted:
        raise HTTPException(status_code=401, detail="Пользователь не найден или удалён.")
    
    return user


def require_roles(allowed_roles: list[str]):
    """Замыкание (dependency) для проверки ролей (RBAC)."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав для выполнения действия.")
        return current_user
    return role_checker
