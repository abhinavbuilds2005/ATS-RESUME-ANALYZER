import pytest
from unittest.mock import MagicMock, patch
from frontend.services import supabase_client
from frontend.services.supabase_client import (
    get_oauth_redirect_url,
    google_oauth_url,
    exchange_code_for_session,
    sign_in_with_password,
    sign_up_with_password,
    sign_out,
)

# -----------------------------------------------------------------------------
# 1 & 3: OAuth Callback & Successful Code Exchange
# -----------------------------------------------------------------------------
@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_exchange_code_for_session_success(mock_missing, mock_get_client):
    mock_auth_resp = MagicMock()
    mock_auth_resp.session.access_token = "mock-access-token-123"
    mock_auth_resp.session.refresh_token = "mock-refresh-token-456"
    mock_auth_resp.user.id = "user-uuid-789"
    mock_auth_resp.user.email = "testuser@gmail.com"
    
    mock_client = MagicMock()
    mock_client.auth.exchange_code_for_session.return_value = mock_auth_resp
    mock_get_client.return_value = mock_client

    result = exchange_code_for_session("oauth-auth-code-abc", code_verifier="mock-verifier-xyz")
    
    assert "error" not in result
    assert result["access_token"] == "mock-access-token-123"
    assert result["refresh_token"] == "mock-refresh-token-456"
    assert result["user_id"] == "user-uuid-789"
    assert result["email"] == "testuser@gmail.com"
    
    # Verify the parameters passed to gotrue
    mock_client.auth.exchange_code_for_session.assert_called_once_with({
        "auth_code": "oauth-auth-code-abc",
        "code_verifier": "mock-verifier-xyz",
        "redirect_to": get_oauth_redirect_url(),
    })

# -----------------------------------------------------------------------------
# 4: Failed Code Exchange
# -----------------------------------------------------------------------------
@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_exchange_code_for_session_failure(mock_missing, mock_get_client):
    mock_client = MagicMock()
    mock_client.auth.exchange_code_for_session.side_effect = Exception("Unable to exchange external code: 4/0A")
    mock_get_client.return_value = mock_client

    result = exchange_code_for_session("bad-or-expired-code", code_verifier="mock-verifier")
    assert "error" in result
    assert "Unable to exchange external code" in result["error"]

# -----------------------------------------------------------------------------
# 5: Missing code_verifier or missing code
# -----------------------------------------------------------------------------
def test_exchange_code_for_session_missing_code():
    result = exchange_code_for_session("")
    assert "error" in result
    assert "Missing authorization code" in result["error"]

@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_google_oauth_url_generates_verifier(mock_missing, mock_get_client):
    mock_client = MagicMock()
    mock_client.auth._storage_key = "supabase.auth.token"
    mock_client.auth._storage.get_item.return_value = "generated-pkce-verifier-123"
    mock_client.auth.sign_in_with_oauth.return_value = MagicMock(url="https://accounts.google.com/o/oauth2/v2/auth?...")
    mock_get_client.return_value = mock_client

    oauth = google_oauth_url()
    assert "error" not in oauth
    assert "accounts.google.com" in oauth["url"]
    assert oauth["code_verifier"] == "generated-pkce-verifier-123"
    assert oauth["redirect_to"] == get_oauth_redirect_url()

# -----------------------------------------------------------------------------
# 6: Email / Password Sign In
# -----------------------------------------------------------------------------
@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_sign_in_with_password_success(mock_missing, mock_get_client):
    mock_resp = MagicMock()
    mock_resp.session.access_token = "pwd-access-token"
    mock_resp.session.refresh_token = "pwd-refresh-token"
    mock_resp.user.id = "user-111"
    mock_resp.user.email = "hello@example.com"
    
    mock_client = MagicMock()
    mock_client.auth.sign_in_with_password.return_value = mock_resp
    mock_get_client.return_value = mock_client

    result = sign_in_with_password("hello@example.com", "validpassword")
    assert "error" not in result
    assert result["access_token"] == "pwd-access-token"
    assert result["user_id"] == "user-111"

@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_sign_in_with_password_invalid(mock_missing, mock_get_client):
    mock_client = MagicMock()
    mock_client.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
    mock_get_client.return_value = mock_client

    result = sign_in_with_password("hello@example.com", "wrongpassword")
    assert "error" in result
    assert result["error"] == "Wrong email or password"

# -----------------------------------------------------------------------------
# 7 & 8: Email / Password Sign Up
# -----------------------------------------------------------------------------
@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_sign_up_immediate_session(mock_missing, mock_get_client):
    mock_resp = MagicMock()
    mock_resp.session.access_token = "new-access-token"
    mock_resp.session.refresh_token = "new-refresh-token"
    mock_resp.user.id = "user-222"
    mock_resp.user.email = "newuser@example.com"
    
    mock_client = MagicMock()
    mock_client.auth.sign_up.return_value = mock_resp
    mock_get_client.return_value = mock_client

    result = sign_up_with_password("newuser@example.com", "securepassword")
    assert "error" not in result
    assert result["access_token"] == "new-access-token"
    assert result["user_id"] == "user-222"

@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_sign_up_requiring_confirmation(mock_missing, mock_get_client):
    mock_resp = MagicMock()
    mock_resp.session = None  # No immediate session returned when confirmation is enabled
    mock_resp.user.id = "user-333"
    mock_resp.user.email = "unconfirmed@example.com"
    
    mock_client = MagicMock()
    mock_client.auth.sign_up.return_value = mock_resp
    mock_get_client.return_value = mock_client

    result = sign_up_with_password("unconfirmed@example.com", "securepassword")
    assert "error" not in result
    assert result.get("pending_confirmation") is True
    assert result["email"] == "unconfirmed@example.com"

# -----------------------------------------------------------------------------
# 9: Sign Out
# -----------------------------------------------------------------------------
@patch("frontend.services.supabase_client.get_client")
@patch("frontend.services.supabase_client._missing_config", return_value=None)
def test_sign_out(mock_missing, mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    sign_out()
    mock_client.auth.sign_out.assert_called_once()

# -----------------------------------------------------------------------------
# 10: Redirect URL normalization & trailing slash handling
# -----------------------------------------------------------------------------
def test_get_oauth_redirect_url_normalization(monkeypatch):
    monkeypatch.setenv("AUTH_REDIRECT_URL", "https://my-app.streamlit.app/ ")
    url = get_oauth_redirect_url()
    assert url == "https://my-app.streamlit.app"
    assert not url.endswith("/")

# -----------------------------------------------------------------------------
# 11: set_auth_session & is_authenticated
# -----------------------------------------------------------------------------
def test_set_auth_session_and_is_authenticated(monkeypatch):
    import streamlit as st
    session_data = {
        "access_token": "token_abc_123",
        "refresh_token": "refresh_xyz_456",
        "user_id": "usr_999",
        "email": "tester@example.com",
    }
    
    # Ensure fresh state
    supabase_client.clear_auth_session()
    assert supabase_client.is_authenticated() is False
    
    # Set valid session
    success = supabase_client.set_auth_session(session_data)
    assert success is True
    assert supabase_client.is_authenticated() is True
    assert st.session_state["access_token"] == "token_abc_123"
    assert st.session_state["user_id"] == "usr_999"
    assert st.session_state["user_email"] == "tester@example.com"
    
    # Test rejection on incomplete data
    bad_success = supabase_client.set_auth_session({"access_token": "only_token"})
    assert bad_success is False

# -----------------------------------------------------------------------------
# 12: clear_auth_session
# -----------------------------------------------------------------------------
def test_clear_auth_session():
    import streamlit as st
    st.session_state["access_token"] = "valid_token"
    st.session_state["user_id"] = "user_id_1"
    st.session_state["user_email"] = "user@example.com"
    st.session_state["auth_session"] = {"access_token": "valid_token"}
    st.session_state["scorer_analysis"] = {"dummy": "data"}

    assert supabase_client.is_authenticated() is True
    supabase_client.clear_auth_session()
    
    assert supabase_client.is_authenticated() is False
    assert st.session_state["access_token"] is None
    assert st.session_state["user_id"] is None
    assert st.session_state["user_email"] is None
    assert st.session_state["auth_session"] is None
    assert "scorer_analysis" not in st.session_state

# -----------------------------------------------------------------------------
# 13: restore_auth_session & get_current_session
# -----------------------------------------------------------------------------
def test_restore_auth_session_and_get_current():
    import streamlit as st
    supabase_client.clear_auth_session()
    
    # 1. Empty state
    assert supabase_client.get_current_session() is None
    
    # 2. Restore from auth_session dict
    st.session_state["auth_session"] = {
        "access_token": "restored_token",
        "refresh_token": "restored_ref",
        "user_id": "restored_uid",
        "email": "restored@example.com",
    }
    restored = supabase_client.restore_auth_session()
    assert restored is not None
    assert restored["access_token"] == "restored_token"
    assert supabase_client.is_authenticated() is True
    
    # 3. get_current_session returns validated session
    current = supabase_client.get_current_session()
    assert current["user_id"] == "restored_uid"
    assert current["email"] == "restored@example.com"

# -----------------------------------------------------------------------------
# 14: Simulated Streamlit Rerun Session Persistence
# -----------------------------------------------------------------------------
def test_streamlit_rerun_session_persistence():
    import streamlit as st
    # Simulate first run: Login happens
    login_result = {
        "access_token": "persistent_jwt_123",
        "refresh_token": "persistent_refresh_456",
        "user_id": "persistent_uid",
        "email": "persistent@example.com",
    }
    supabase_client.set_auth_session(login_result)
    assert supabase_client.is_authenticated() is True

    # Simulate rerun step (Streamlit re-executes top-level script)
    # top-level script executes: supabase_client.restore_auth_session()
    restored = supabase_client.restore_auth_session()
    assert restored is not None
    assert supabase_client.is_authenticated() is True
    assert st.session_state["access_token"] == "persistent_jwt_123"
    assert st.session_state["user_email"] == "persistent@example.com"

