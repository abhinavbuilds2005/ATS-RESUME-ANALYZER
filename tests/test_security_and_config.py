import os
from pathlib import Path
import pytest
from backend.core.config import ALLOWED_ORIGINS
from frontend.services.api_client import _backend_url, BackendConfigError

def test_allowed_origins_no_trailing_slashes():
    for origin in ALLOWED_ORIGINS:
        assert not origin.endswith("/"), f"Origin '{origin}' should not have a trailing slash"

def test_backend_url_resolution(monkeypatch):
    # Test env var resolution
    monkeypatch.setenv("BACKEND_URL", "https://my-backend.onrender.com/")
    resolved = _backend_url()
    assert resolved == "https://my-backend.onrender.com"
    
    monkeypatch.delenv("BACKEND_URL", raising=False)
    
    # Test production error when unconfigured
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(BackendConfigError):
        _backend_url()

def test_gitignore_covers_sensitive_files():
    repo_root = Path(__file__).resolve().parent.parent
    gitignore_path = repo_root / ".gitignore"
    assert gitignore_path.exists()
    
    content = gitignore_path.read_text()
    assert ".env" in content
    assert "secrets.toml" in content
    assert "__pycache__" in content
    assert "*.log" in content

def test_env_example_has_no_real_secrets():
    repo_root = Path(__file__).resolve().parent.parent
    env_example = repo_root / ".env.example"
    if env_example.exists():
        text = env_example.read_text()
        assert "your_groq_api_key_here" in text or "gsk_" not in text
        assert "your_supabase_project_url" in text or "https://" not in text or "your_" in text
