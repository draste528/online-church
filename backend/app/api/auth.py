# app/api/auth.py
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class UserRegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: str | None = None
    last_name: str | None = None


class UserRegisterOut(BaseModel):
    user_id: uuid.UUID
    username: str
    role: str


class UserLoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/register", response_model=UserRegisterOut, status_code=201)
def register(payload: UserRegisterIn, db: Session = Depends(get_db)):
    """Регистрация нового пользователя."""
    existing = db.execute(
        select(User).where((User.email == payload.email) | (User.username == payload.username))
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email или именем уже существует.")

    new_user = User(
        username=payload.username,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role="parishioner"  # По умолчанию регистрируем прихожанина
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"user_id": new_user.user_id, "username": new_user.username, "role": new_user.role}


@router.post("/login", response_model=TokenOut, status_code=200)
def login(payload: UserLoginIn, db: Session = Depends(get_db)):
    """Вход и получение JWT-токена."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or user.is_deleted:
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")

    token = create_access_token(data={"sub": str(user.user_id), "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}
