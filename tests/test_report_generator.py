import pytest
from backend.services.report_generator import generate_html_reports
from backend.services.pdf_export import generate_combined_pdf

def test_generate_html_reports(sample_parsed_resume):
    analysis_data = {
        "ats_score": 85.5,
        "ATS_score": 85.5,
        "interpretation": "Great! Your resume is well-optimized for ATS.",
        "component_scores": {
            "formatting": 18.0,
            "keywords": 22.0,
            "content": 21.0,
            "skill_validation": 13.0,
            "ats_compatibility": 13.0,
        },
        "strengths": ["Strong action verbs", "Clear formatting"],
        "detailed_feedback": [
            {
                "issue_title": "Missing Certifications",
                "severity_level": "Low",
                "ats_impact": "Low",
                "explanation": "Adding industry certs helps.",
                "where_it_appears": "Certifications section",
                "how_to_fix": "Add relevant certs.",
                "action_items": ["Add AWS cert"],
                "example_improvement": "AWS Certified Developer"
            }
        ],
        "skill_validation_details": {
            "validated": [{"skill": "Python", "projects": ["AI ATS"]}],
            "unvalidated": ["GraphQL"],
            "total": 2,
            "validated_count": 1,
            "validation_pct": 50.0,
        },
        "jd_match_analysis": {
            "match_percentage": 78.0,
            "semantic_similarity": 0.82,
            "matched_keywords": ["Python", "FastAPI"],
            "missing_keywords": ["Kubernetes"],
            "skills_gap": ["Kubernetes"],
        }
    }

    html_docs = generate_html_reports(analysis_data)
    assert isinstance(html_docs, dict)
    assert "summary" in html_docs
    assert "skill_report" in html_docs
    assert "recommendations" in html_docs
    assert len(html_docs["summary"]) > 100
    assert "85.5" in html_docs["summary"] or "85" in html_docs["summary"]

def test_generate_combined_pdf(sample_parsed_resume):
    analysis_data = {
        "ats_score": 80.0,
        "interpretation": "Good resume.",
        "component_scores": {
            "formatting": 16.0,
            "keywords": 20.0,
            "content": 20.0,
            "skill_validation": 12.0,
            "ats_compatibility": 12.0,
        },
        "strengths": ["Good formatting"],
        "detailed_feedback": [],
        "skill_validation_details": {
            "validated": [],
            "unvalidated": [],
            "total": 0,
            "validated_count": 0,
            "validation_pct": 0.0,
        },
    }

    html_docs = generate_html_reports(analysis_data)
    pdf_bytes = generate_combined_pdf(html_docs)
    
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
