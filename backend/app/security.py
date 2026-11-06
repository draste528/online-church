# app/security.py
import os
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt

# В реальном проекте секрет должен лежать в .env
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-dev-key-change-it-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 неделя


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет совпадение пароля с хэшем."""
    return bcrypt.checkpw(
        password=plain_password.encode("utf-8"),
        hashed_password=hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Генерирует bcrypt хэш пароля."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict) -> str:
    """Создаёт JWT токен."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
