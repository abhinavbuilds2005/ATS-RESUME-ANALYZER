import pytest
from unittest.mock import MagicMock
from fastapi import Request
from starlette.datastructures import State

from backend.services.jd_matcher import (
    calculate_semantic_similarity,
    compare_resume_with_jd,
    calculate_match_percentage,
)
from backend.services.ats_scorer import (
    validate_skills_with_projects,
    detect_location_info,
)
from backend.services.resume_analyzer import _safe_int, analyze_full_resume
from backend.services.report_generator import _safe_float, generate_html_reports
from backend.services.groq_parser import _validate_resume_result, _validate_jd_result
from backend.api.routes import health_check


def test_safe_int_conversion():
    """Verify _safe_int handles malformed and edge-case values safely."""
    assert _safe_int(None) == 0
    assert _safe_int("") == 0
    assert _safe_int("   ") == 0
    assert _safe_int("N/A") == 0
    assert _safe_int("invalid") == 0
    assert _safe_int("24") == 24
    assert _safe_int(24) == 24
    assert _safe_int(24.5) == 24
    assert _safe_int("24 months") == 24
    assert _safe_int(-5) == 0  # min_val=0 by default
    assert _safe_int("-5", min_val=0) == 0
    assert _safe_int("-5", min_val=None) == -5
    assert _safe_int(True) == 0  # boolean guarded
    assert _safe_int(False) == 0
    assert _safe_int([], default=10) == 10
    assert _safe_int({}, default=10) == 10


def test_safe_float_conversion():
    """Verify _safe_float handles None, invalid strings, and valid numbers."""
    assert _safe_float(None) == 0.0
    assert _safe_float(None, default=5.0) == 5.0
    assert _safe_float("15.5") == 15.5
    assert _safe_float("invalid") == 0.0
    assert _safe_float(20) == 20.0


def test_semantic_similarity_with_embedder_none():
    """Ensure calculate_semantic_similarity does not crash when embedder is None."""
    sim = calculate_semantic_similarity("Python developer", "Looking for Python engineer", embedder=None)
    assert sim == 0.0


def test_validate_skills_with_projects_embedder_none():
    """Ensure validate_skills_with_projects does not crash when embedder is None and matches via regex."""
    skills = ["Python", "FastAPI", "Docker", "Kubernetes"]
    projects = [
        {"title": "Backend API", "description": "Developed backend microservices using Python and Docker."}
    ]
    experience = [
        {"job_title": "Software Engineer", "company": "Tech Corp", "description": "Built REST APIs with FastAPI."}
    ]

    result = validate_skills_with_projects(
        skills=skills,
        projects=projects,
        experience_entries=experience,
        embedder=None,
    )

    assert result is not None
    assert result.get("semantic_validation_available") is False
    assert "Python" in [s["skill"] for s in result["validated_skills"]]
    assert "FastAPI" in [s["skill"] for s in result["validated_skills"]]
    assert "Docker" in [s["skill"] for s in result["validated_skills"]]
    assert "Kubernetes" in result["unvalidated_skills"]
    assert result["validation_percentage"] == 0.75
    assert result["validation_score"] == 0.75 * 15.0


def test_compare_resume_with_jd_embedder_none():
    """Ensure compare_resume_with_jd works and does not unfairly penalize candidate when embedder is None."""
    result = compare_resume_with_jd(
        resume_text="Experienced Python and FastAPI backend developer.",
        resume_keywords=["Python", "FastAPI"],
        resume_skills=["Python", "FastAPI"],
        jd_text="Need a Python and FastAPI developer.",
        jd_keywords=["python", "fastapi"],
        embedder=None,
        nlp=None,
    )

    assert result["semantic_available"] is False
    assert result["semantic_similarity"] == 0.0
    assert result["match_percentage"] == 100.0  # 2 of 2 matched keywords
    assert "python" in [k.lower() for k in result["matched_keywords"]]


def test_detect_location_info_nlp_none():
    """Ensure detect_location_info does not crash when nlp is None and detects addresses, US zip, and Indian PIN."""
    text = (
        "John Doe\n"
        "123 Main Street, Apt 4B, Springfield, IL 62701\n"
        "Bangalore Office: MG Road, Bangalore 560001\n"
    )

    result = detect_location_info(text, nlp=None)
    assert result is not None
    assert "detected_locations" in result
    types = [loc["type"] for loc in result["detected_locations"]]
    assert "address" in types
    assert "zip" in types
    assert "pin" in types
    assert result["privacy_risk"] == "high"
    assert result["penalty_applied"] > 0.0


def test_report_generator_with_none_component_scores():
    """Ensure report generator handles None component scores without crashing."""
    analysis_data = {
        "ATS_score": 85.0,
        "ats_score": 85.0,
        "interpretation": "Good profile",
        "component_scores": {
            "formatting": None,
            "keywords": 22.0,
            "content": None,
            "skill_validation": 14.0,
            "ats_compatibility": None,
        },
        "detailed_feedback": [],
    }
    docs = generate_html_reports(analysis_data)
    assert docs is not None
    assert len(docs) > 0


def test_groq_parser_validation_malformed_types():
    """Ensure _validate_resume_result and _validate_jd_result safely handle invalid types and malformed fields."""
    raw_resume = {
        "name": None,
        "skills": "not a list",
        "experience": [
            "not a dict",
            {"job_title": None, "duration_months": "invalid string"},
            {"job_title": "Engineer", "duration_months": None},
            {"job_title": "Lead", "duration_months": "36 months"},
            {"job_title": "Intern", "duration_months": -12},
        ],
        "education": "invalid",
        "projects": None,
    }
    validated = _validate_resume_result(raw_resume)
    assert isinstance(validated["skills"], list)
    assert isinstance(validated["experience"], list)
    assert len(validated["experience"]) == 4
    assert validated["experience"][0]["duration_months"] == 0
    assert validated["experience"][1]["duration_months"] == 0
    assert validated["experience"][2]["duration_months"] == 36
    assert validated["experience"][3]["duration_months"] == 0
    assert isinstance(validated["education"], list)
    assert isinstance(validated["projects"], list)

    raw_jd = {
        "job_title": None,
        "required_skills": None,
        "key_responsibilities": "string instead of list",
    }
    validated_jd = _validate_jd_result(raw_jd)
    assert isinstance(validated_jd["required_skills"], list)
    assert isinstance(validated_jd["key_responsibilities"], list)


@pytest.mark.anyio
async def test_health_check_states():
    """Verify health endpoint accurately reflects healthy, degraded, and initializing states."""
    req = MagicMock(spec=Request)
    req.app = MagicMock()
    req.app.state = State()

    # 1. Initializing state
    req.app.state.nlp = None
    req.app.state.embedder = None
    req.app.state.models_initialized = False
    res = await health_check(req)
    assert res["status"] == "initializing"
    assert res["ready"] is False
    assert res["nlp_loaded"] is False
    assert res["embedder_loaded"] is False

    # 2. Fully loaded state
    req.app.state.nlp = MagicMock()
    req.app.state.embedder = MagicMock()
    req.app.state.models_initialized = True
    res = await health_check(req)
    assert res["status"] == "healthy"
    assert res["ready"] is True
    assert res["nlp_loaded"] is True
    assert res["embedder_loaded"] is True

    # 3. Degraded state (NLP loaded, embedder failed)
    req.app.state.nlp = MagicMock()
    req.app.state.embedder = None
    req.app.state.models_initialized = True
    res = await health_check(req)
    assert res["status"] == "degraded"
    assert res["ready"] is False
    assert res["nlp_loaded"] is True
    assert res["embedder_loaded"] is False

    # 4. Degraded state (Both failed)
    req.app.state.nlp = None
    req.app.state.embedder = None
    req.app.state.models_initialized = True
    res = await health_check(req)
    assert res["status"] == "degraded"
    assert res["ready"] is False
    assert res["nlp_loaded"] is False
    assert res["embedder_loaded"] is False
