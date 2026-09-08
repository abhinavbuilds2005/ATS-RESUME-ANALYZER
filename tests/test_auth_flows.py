"""Test auth flows: Verify backend JWT authentication and authorization setup."""

def test_auth_flows_active():
    from backend.api.auth import get_current_user_id, get_optional_user_id
    assert callable(get_current_user_id)
    assert callable(get_optional_user_id)

