import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db import get_db, init_db, make_engine
from backend.app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def database():
    """Свежая in-memory SQLite база для каждого теста."""
    engine = make_engine("sqlite://")
    init_db(engine, seed=False)

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    yield engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()

def valid_user():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "StrongPassword123"
    }

def test_register_success():
    res = client.post("/api/v1/auth/register", json=valid_user())
    assert res.status_code == 201
    body = res.json()
    assert "user_id" in body
    assert body["username"] == "testuser"
    assert body["role"] == "parishioner"

def test_register_duplicate_fails():
    client.post("/api/v1/auth/register", json=valid_user())
    res = client.post("/api/v1/auth/register", json=valid_user())
    assert res.status_code == 400
    assert "уже существует" in res.json()["detail"]

def test_login_success():
    client.post("/api/v1/auth/register", json=valid_user())
    res = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "StrongPassword123"
    })
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "parishioner"

def test_login_wrong_password():
    client.post("/api/v1/auth/register", json=valid_user())
    res = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword"
    })
    assert res.status_code == 401
