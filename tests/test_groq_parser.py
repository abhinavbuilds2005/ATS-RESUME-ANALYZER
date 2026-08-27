import json
import pytest
from unittest.mock import MagicMock, patch
from backend.services.groq_parser import (
    _try_parse_json,
    _validate_resume_result,
    _validate_jd_result,
    _fallback_parse_resume,
    _fallback_parse_jd,
    parse_resume,
    parse_job_description,
)

def test_try_parse_json_clean():
    data = {"name": "Alice", "skills": ["Python"]}
    text = json.dumps(data)
    assert _try_parse_json(text) == data

def test_try_parse_json_markdown_fences():
    data = {"name": "Bob", "skills": ["FastAPI"]}
    text = f"```json\n{json.dumps(data)}\n```"
    assert _try_parse_json(text) == data

def test_try_parse_json_with_preamble():
    data = {"name": "Charlie", "skills": ["Docker"]}
    text = f"Here is the parsed resume JSON as requested:\n{json.dumps(data)}\nHope this helps!"
    assert _try_parse_json(text) == data

def test_try_parse_json_invalid():
    assert _try_parse_json("NOT A JSON OBJECT AT ALL") is None
    assert _try_parse_json("") is None
    assert _try_parse_json(None) is None

def test_validate_resume_result_defaults():
    sparse_data = {"name": "Test User"}
    validated = _validate_resume_result(sparse_data)
    assert validated["name"] == "Test User"
    assert isinstance(validated["skills"], list)
    assert isinstance(validated["experience"], list)
    assert isinstance(validated["education"], list)
    assert isinstance(validated["projects"], list)
    assert isinstance(validated["action_verbs"], list)
    assert isinstance(validated["keywords"], list)

def test_validate_jd_result_defaults():
    sparse_jd = {"job_title": "Backend Engineer"}
    validated = _validate_jd_result(sparse_jd)
    assert validated["job_title"] == "Backend Engineer"
    assert isinstance(validated["required_skills"], list)
    assert isinstance(validated["preferred_skills"], list)
    assert isinstance(validated["keywords"], list)

def test_fallback_parse_resume(sample_resume_text):
    result = _fallback_parse_resume(sample_resume_text)
    assert "john.doe@example.com" in (result["email"] or "")
    assert len(result["skills"]) > 0
    assert any("python" in s.lower() for s in result["skills"])
    assert len(result["action_verbs"]) > 0

def test_fallback_parse_jd():
    jd_text = "Senior Python Developer\nMust have 3+ years experience with Python, FastAPI, and Docker."
    result = _fallback_parse_jd(jd_text)
    assert "Python" in result["job_title"] or "Target Role" in result["job_title"]
    assert any("python" in s.lower() for s in result["required_skills"])

@patch("backend.services.groq_parser._get_client")
def test_parse_resume_fallback_on_api_error(mock_get_client, sample_resume_text):
    mock_get_client.side_effect = Exception("API connection timed out")
    result = parse_resume(sample_resume_text)
    assert isinstance(result, dict)
    assert len(result["skills"]) > 0
