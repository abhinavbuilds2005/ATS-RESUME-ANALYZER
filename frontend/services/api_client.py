import os
from typing import Any, Dict, List

import requests
import streamlit as st

DEFAULT_LOCAL_URL = "http://localhost:8000"

class BackendConfigError(Exception):
    """Raised when backend URL is missing in production environments."""
    pass

def _backend_url() -> str:
    """
    Resolve the backend URL with priority:
    1. BACKEND_URL environment variable
    2. API_URL environment variable
    3. st.secrets["backend"]["url"]
    4. st.secrets["BACKEND_URL"]
    5. Localhost fallback (only if local)
    """
    # 1. Check environment variables
    env_url = os.getenv("BACKEND_URL") or os.getenv("API_URL")
    if env_url:
        return env_url.strip().rstrip('/')

    # 2. Check Streamlit secrets
    try:
        if "backend" in st.secrets and "url" in st.secrets["backend"]:
            return str(st.secrets["backend"]["url"]).strip().rstrip('/')
        if "BACKEND_URL" in st.secrets:
            return str(st.secrets["BACKEND_URL"]).strip().rstrip('/')
        if "API_URL" in st.secrets:
            return str(st.secrets["API_URL"]).strip().rstrip('/')
    except Exception:
        pass

    # 3. Detect if running in production without configuration
    is_production = (
        os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")
        or os.getenv("STREAMLIT_SHARING_HOST") is not None
        or os.getenv("RENDER") is not None
    )

    if is_production:
        raise BackendConfigError(
            "Backend URL is not configured. Please set 'BACKEND_URL' in your "
            "deployment environment variables or .streamlit/secrets.toml."
        )

    return DEFAULT_LOCAL_URL



def _auth_headers(access_token: str = "") -> Dict[str, str]:
    token = access_token or "guest_token"
    return {"Authorization": f"Bearer {token}"}



def health_check() -> Dict[str, Any]:
    response = requests.get(f"{_backend_url()}/api/v1/health", timeout=10)
    response.raise_for_status()
    return response.json()


def analyze_resume(
    resume_file,
    access_token: str,
    job_description: str = "",
) -> Dict[str, Any]:
    files = {
        "resume": (resume_file.name, resume_file.getvalue(), resume_file.type),
    }
    data = {"job_description": job_description}
    response = requests.post(
        f"{_backend_url()}/api/v1/analyze-resume",
        files=files,
        data=data,
        headers=_auth_headers(access_token),
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def get_history(access_token: str) -> List[Dict[str, Any]]:
    response = requests.get(
        f"{_backend_url()}/api/v1/history",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def delete_history_entry(analysis_id: str, access_token: str) -> None:
    response = requests.delete(
        f"{_backend_url()}/api/v1/history/{analysis_id}",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()


def generate_pdf(analysis_data: Dict[str, Any], access_token: str) -> bytes:
    response = requests.post(
        f"{_backend_url()}/api/v1/generate-pdf",
        json=analysis_data,
        headers=_auth_headers(access_token),
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def get_history_pdf(analysis_id: str, access_token: str) -> bytes:
    response = requests.get(
        f"{_backend_url()}/api/v1/history/{analysis_id}/pdf",
        headers=_auth_headers(access_token),
        timeout=60,
    )
    response.raise_for_status()
    return response.content
