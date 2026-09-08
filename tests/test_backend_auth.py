import pytest
import jwt
import time
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import SUPABASE_JWT_SECRET

TEST_JWT_SECRET = "test_super_secret_jwt_key_at_least_32_bytes_long_12345"

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("backend.api.auth.SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    yield TestClient(app)


def create_test_token(user_id: str, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": now - 3600 if expired else now + 3600,
        "iat": now - 60,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

def test_unauthenticated_history_access_returns_401(client):
    response = client.get("/api/v1/history")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"] or "header" in response.json()["detail"]

def test_invalid_token_returns_401(client):
    response = client.get(
        "/api/v1/history",
        headers={"Authorization": "Bearer invalid.token.value"}
    )
    assert response.status_code == 401

def test_expired_token_returns_401(client):
    expired_token = create_test_token("user_123", expired=True)
    response = client.get(
        "/api/v1/history",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

@patch("backend.database.supabase_db.get_user_history", new_callable=AsyncMock)
def test_authenticated_history_user_isolation(mock_get_history, client):
    mock_get_history.return_value = [{"id": "rec_1", "ats_score": 85.0}]
    token_a = create_test_token("user_a")
    
    response = client.get(
        "/api/v1/history",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert response.status_code == 200
    mock_get_history.assert_called_once_with(user_id="user_a")

@patch("backend.database.supabase_db.delete_analysis", new_callable=AsyncMock)
def test_cross_user_deletion_protection_idor(mock_delete, client):
    # delete_analysis returns False when record not found or belongs to another user
    mock_delete.return_value = False
    token_b = create_test_token("user_b")

    response = client.delete(
        "/api/v1/history/record_owned_by_user_a",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404
    mock_delete.assert_called_once_with("record_owned_by_user_a", user_id="user_b")

@patch("backend.database.supabase_db.get_analysis_by_id", new_callable=AsyncMock)
def test_cross_user_history_pdf_protection_idor(mock_get_by_id, client):
    # get_analysis_by_id returns None when user does not own record
    mock_get_by_id.return_value = None
    token_c = create_test_token("user_c")

    response = client.get(
        "/api/v1/history/secret_record_user_a/pdf",
        headers={"Authorization": f"Bearer {token_c}"}
    )
    assert response.status_code == 404
    mock_get_by_id.assert_called_once_with("secret_record_user_a", user_id="user_c")

