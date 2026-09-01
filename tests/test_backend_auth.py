from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import backend.api.auth as auth
from backend.api.auth import get_current_user


def _client_for_auth_dependency() -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected(user_id: str = Depends(get_current_user)):
        return {"user_id": user_id}

    return TestClient(app)


def test_get_current_user_requires_bearer_token(monkeypatch):
    monkeypatch.setattr(auth, "SUPABASE_URL", "")
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "test-secret")

    response = _client_for_auth_dependency().get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Authorization: Bearer <token> header"


def test_get_current_user_rejects_guest_token(monkeypatch):
    monkeypatch.setattr(auth, "SUPABASE_URL", "")
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "test-secret")

    response = _client_for_auth_dependency().get(
        "/protected",
        headers={"Authorization": "Bearer guest_token"},
    )

    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_get_current_user_accepts_valid_hs256_supabase_jwt(monkeypatch):
    monkeypatch.setattr(auth, "SUPABASE_URL", "")
    monkeypatch.setattr(auth, "SUPABASE_JWT_SECRET", "test-secret")
    token = jwt.encode(
        {
            "sub": "user-123",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "test-secret",
        algorithm="HS256",
    )

    response = _client_for_auth_dependency().get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123"}
