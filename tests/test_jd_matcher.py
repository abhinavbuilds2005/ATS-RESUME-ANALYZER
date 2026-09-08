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

def test_chunked_semantic_similarity_long_documents(embedder):
    # Construct long resume and JD (> 6000 chars each)
    resume_chunks = [
        "Senior Backend Engineer with deep expertise in Python, distributed systems, and PostgreSQL. " * 30,
        "Led migration of legacy monolith to microservices using FastAPI, Redis caching, and Docker. " * 30,
        "Designed event-driven pipelines using Apache Kafka, Elasticsearch, and Kubernetes on AWS. " * 30
    ]
    resume_text = "\n\n".join(resume_chunks)
    assert len(resume_text) > 6000

    jd_chunks = [
        "We are looking for a Principal Backend Architect to design distributed systems in Python and FastAPI. " * 30,
        "Must have extensive experience with PostgreSQL, Docker containers, Kubernetes orchestration, and AWS. " * 30,
        "Experience building scalable real-time architectures with Kafka and Redis is strongly desired. " * 30
    ]
    jd_text = "\n\n".join(jd_chunks)
    assert len(jd_text) > 6000

    score = calculate_semantic_similarity(resume_text, jd_text, embedder)
    assert 0.60 <= score <= 1.0

def test_analyze_skills_gap_filters_generic_phrases(nlp):
    # JD containing generic recruiter jargon alongside genuine tech skills
    jd_text = """
    We are seeking a talented Software Engineer to build scalable applications with high availability.
    The ideal candidate should have 5+ years of experience working with cross-functional teams,
    demonstrate strong communication skills and exceptional problem-solving abilities,
    and possess a proven track record in fast-paced environments.
    Required technical skills: Kubernetes, TypeScript, GraphQL, Terraform, and Go.
    """
    resume_skills = ["Kubernetes", "TypeScript"]

    # analyze_skills_gap returns List[str] of missing skills
    missing_gap = analyze_skills_gap(resume_skills, jd_text, nlp)
    missing_lower = [s.lower() for s in missing_gap]

    # Verify real tech skills are detected in the gap
    assert any("graphql" in m for m in missing_lower)
    assert any("terraform" in m for m in missing_lower)

    # Verify resume skills are NOT in missing skills
    assert "kubernetes" not in missing_lower
    assert "typescript" not in missing_lower

    # Verify generic phrases are NOT present in missing skills
    forbidden_generics = [
        "software engineer",
        "scalable applications",
        "cross-functional teams",
        "proven track record",
        "strong communication skills",
        "problem-solving abilities",
        "fast-paced environments",
        "years of experience",
    ]
    for generic in forbidden_generics:
        assert generic not in missing_lower, f"Generic phrase '{generic}' was not filtered out!"


def test_punctuation_skills_in_jd_matching():
    resume_keywords = ["C++", "C#", ".NET Core", "React.js"]
    jd_keywords = ["c++", "c#", ".net", "react", "golang"]

    matched = identify_matched_keywords(resume_keywords, jd_keywords)
    missing = identify_missing_keywords(resume_keywords, jd_keywords)

    assert any(m.lower() == "c++" for m in matched)
    assert any(m.lower() == "c#" for m in matched)
    assert any("react" in m.lower() for m in matched)
    assert any(m.lower() == "golang" for m in missing)

