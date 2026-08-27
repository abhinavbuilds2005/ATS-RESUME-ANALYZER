import pytest
from sentence_transformers import SentenceTransformer
import spacy
from backend.services.jd_matcher import (
    calculate_semantic_similarity,
    identify_matched_keywords,
    identify_missing_keywords,
    analyze_skills_gap,
    compare_resume_with_jd,
)

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

def test_identify_matched_and_missing_keywords():
    resume_keywords = ["Python", "FastAPI", "React", "Docker", "PostgreSQL"]
    jd_keywords = ["python", "fastapi", "kubernetes", "aws", "postgresql"]
    
    matched = identify_matched_keywords(resume_keywords, jd_keywords)
    missing = identify_missing_keywords(resume_keywords, jd_keywords)
    
    assert any("python" in m.lower() for m in matched)
    assert any("fastapi" in m.lower() for m in matched)
    assert any("postgresql" in m.lower() for m in matched)
    assert any("kubernetes" in m.lower() for m in missing)
    assert any("aws" in m.lower() for m in missing)

def test_calculate_semantic_similarity(embedder):
    resume_text = "Experienced backend developer specializing in Python, FastAPI microservices, and SQL databases."
    matching_jd = "Looking for a Python Backend Engineer to build robust REST APIs using FastAPI and relational databases."
    different_jd = "Seeking a Nurse Practitioner with 5+ years of clinical emergency room experience."
    
    high_sim = calculate_semantic_similarity(resume_text, matching_jd, embedder)
    low_sim = calculate_semantic_similarity(resume_text, different_jd, embedder)
    
    assert 0.0 <= high_sim <= 1.0
    assert 0.0 <= low_sim <= 1.0
    assert high_sim > low_sim

def test_compare_resume_with_jd(embedder, nlp):
    resume_text = "Python developer with FastAPI, Docker, and PostgreSQL experience."
    jd_text = "We need a Senior Python Developer proficient with FastAPI, Docker, and AWS."
    jd_keywords = ["Python", "FastAPI", "Docker", "AWS"]
    resume_keywords = ["Python", "FastAPI", "Docker", "PostgreSQL"]
    resume_skills = ["Python", "FastAPI", "Docker"]
    
    result = compare_resume_with_jd(
        resume_text=resume_text,
        resume_keywords=resume_keywords,
        resume_skills=resume_skills,
        jd_text=jd_text,
        jd_keywords=jd_keywords,
        embedder=embedder,
        nlp=nlp,
    )
    
    assert "match_percentage" in result
    assert "semantic_similarity" in result
    assert "matched_keywords" in result
    assert "missing_keywords" in result
    assert result["match_percentage"] > 50.0
