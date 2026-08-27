import pytest
from sentence_transformers import SentenceTransformer
from backend.core.config import SCORE_WEIGHTS
from backend.services.ats_scorer import (
    calculate_overall_score,
    validate_skills_with_projects,
    detect_location_info,
    _calc_formatting_score,
    _calc_keywords_score,
    _calc_content_score,
    _calc_skill_validation_score,
    _calc_ats_compatibility_score,
)
import spacy

@pytest.fixture(scope="module")
def embedder():
    return SentenceTransformer("all-MiniLM-L6-v2")

@pytest.fixture(scope="module")
def nlp():
    try:
        return spacy.load("en_core_web_md")
    except OSError:
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            return spacy.blank("en")

def test_score_weights_configuration():
    assert SCORE_WEIGHTS == {
        "formatting": 20,
        "keywords": 25,
        "content": 25,
        "skill_validation": 15,
        "ats_compatibility": 15,
    }
    assert sum(SCORE_WEIGHTS.values()) == 100

def test_calculate_overall_score_structure(sample_resume_text, sample_parsed_resume):
    grammar_results = {
        "total_errors": 0,
        "penalty_applied": 0.0,
        "_component_status": "available",
    }
    location_results = {
        "location_found": False,
        "penalty_applied": 0.0,
        "privacy_risk": "none",
    }
    skill_val_results = {
        "validated_skills": [{"skill": "Python", "projects": ["AI ATS"]}],
        "unvalidated_skills": [],
        "validation_percentage": 1.0,
        "validation_score": 15.0,
    }
    
    result = calculate_overall_score(
        text=sample_resume_text,
        parsed_resume=sample_parsed_resume,
        skills=sample_parsed_resume["skills"],
        keywords=sample_parsed_resume["keywords"],
        action_verbs=sample_parsed_resume["action_verbs"],
        skill_validation_results=skill_val_results,
        grammar_results=grammar_results,
        location_results=location_results,
        jd_keywords=["Python", "FastAPI", "Docker", "PostgreSQL"],
    )
    
    assert "overall_score" in result
    assert 0 <= result["overall_score"] <= 100
    assert result["formatting_score"] <= SCORE_WEIGHTS["formatting"]
    assert result["keywords_score"] <= SCORE_WEIGHTS["keywords"]
    assert result["content_score"] <= SCORE_WEIGHTS["content"]
    assert result["skill_validation_score"] <= SCORE_WEIGHTS["skill_validation"]
    assert result["ats_compatibility_score"] <= SCORE_WEIGHTS["ats_compatibility"]

def test_validate_skills_with_projects(embedder, sample_parsed_resume):
    skills = ["Python", "FastAPI", "React", "UnknownTechnology123"]
    projects = sample_parsed_resume["projects"]
    experience = sample_parsed_resume["experience"]

    result = validate_skills_with_projects(
        skills=skills,
        projects=projects,
        experience_entries=experience,
        embedder=embedder,
        threshold=0.6,
    )

    assert "validated_skills" in result
    assert "unvalidated_skills" in result
    validated_names = [item["skill"] for item in result["validated_skills"]]
    assert "Python" in validated_names
    assert "FastAPI" in validated_names
    assert "UnknownTechnology123" in result["unvalidated_skills"]
    assert 0.0 <= result["validation_percentage"] <= 1.0
    assert 0.0 <= result["validation_score"] <= 15.0

def test_detect_location_info(nlp):
    text_with_address = "John Doe\n123 Main Street, Suite 400\nSeattle, WA 98101\njohn@example.com"
    results = detect_location_info(text_with_address, nlp)
    
    assert results["location_found"] is True
    assert results["privacy_risk"] in ("medium", "high")
    assert results["penalty_applied"] > 0
    assert len(results["recommendations"]) > 0
