import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.api.auth import get_current_user

@pytest.fixture
def client():
    # Override get_current_user dependency for testing authenticated endpoints
    app.dependency_overrides[get_current_user] = lambda: "test-user-123"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "ATS Resume Analyzer API" in data["name"]

def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_cors_headers(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8501"

def test_analyze_resume_endpoint_valid_pdf(client, sample_pdf_bytes):
    with patch("backend.database.supabase_db.save_analysis", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = "analysis-doc-123"
        
        response = client.post(
            "/api/v1/analyze-resume",
            files={"resume": ("sample.pdf", sample_pdf_bytes, "application/pdf")},
            data={"job_description": "We need a Python developer proficient in FastAPI."}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "ATS_score" in data or "ats_score" in data
        assert "component_scores" in data
        assert "skill_validation_details" in data

def test_analyze_resume_endpoint_invalid_file(client):
    response = client.post(
        "/api/v1/analyze-resume",
        files={"resume": ("bad.txt", b"plain text is not pdf or docx", "text/plain")},
        data={"job_description": ""}
    )
    assert response.status_code == 422

def test_generate_pdf_endpoint(client, sample_parsed_resume):
    analysis_payload = {
        "ATS_score": 88.0,
        "ats_score": 88.0,
        "component_scores": {
            "formatting": 18.0,
            "keywords": 22.0,
            "content": 22.0,
            "skill_validation": 13.0,
            "ats_compatibility": 13.0,
        },
        "issues_summary": ["Missing Certifications"],
        "detailed_feedback": [],
        "strengths": ["Well-structured formatting"],
        "suggestions": ["Add more technical projects"],
        "critical_issues": [],
        "skills": ["Python", "FastAPI"],
        "warnings": [],
        "interpretation": "Excellent resume."
    }
    
    response = client.post("/api/v1/generate-pdf", json=analysis_payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0
    assert response.content.startswith(b"%PDF-")

@patch("backend.database.supabase_db.get_user_history", new_callable=AsyncMock)
def test_history_endpoint_supabase_failure_handling(mock_get_history, client):
    # When Supabase is unavailable or fails, get_history gracefully handles it
    mock_get_history.return_value = []
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    assert response.json() == []
