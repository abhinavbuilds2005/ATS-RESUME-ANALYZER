import pytest
from backend.services.ats_scorer import analyze_grammar_and_spelling, generate_strengths
from backend.utils.file_utils import get_default_grammar_results

def test_analyze_grammar_detects_common_typos():
    text = "I have 4 years of expereince in software developement and managment. I recieved awards."
    results = analyze_grammar_and_spelling(text)
    
    assert results["_component_status"] == "available"
    assert results["total_errors"] >= 3
    critical_messages = [e["message"] for e in results["critical_errors"]]
    assert any("expereince" in m for m in critical_messages)
    assert any("developement" in m for m in critical_messages)
    assert any("managment" in m or "recieved" in m for m in critical_messages)
    assert results["penalty_applied"] > 0

def test_analyze_grammar_detects_repeated_words():
    text = "Developed REST APIs with with FastAPI in in production."
    results = analyze_grammar_and_spelling(text)
    
    assert results["total_errors"] >= 2
    repeated = [e["error_text"] for e in results["moderate_errors"]]
    assert any("with with" in r.lower() for r in repeated)
    assert any("in in" in r.lower() for r in repeated)

def test_analyze_grammar_clean_text():
    clean_text = (
        "Experienced Software Engineer with proficiency in Python, FastAPI, and React. "
        "Developed scalable microservices and led cross-functional teams."
    )
    results = analyze_grammar_and_spelling(clean_text)
    assert results["total_errors"] == 0
    assert results["penalty_applied"] == 0.0
    assert results["grammar_score"] == 100.0
    assert results["_component_status"] == "available"

def test_generate_strengths_does_not_falsely_claim_error_free_when_unavailable():
    score_results = {
        "formatting_score": 18,
        "keywords_score": 22,
        "content_score": 21,
        "skill_validation_score": 14,
        "ats_compatibility_score": 14,
    }
    skill_val = {"validation_percentage": 0.9}
    
    # Default unanalyzed grammar result
    default_grammar = get_default_grammar_results()
    assert default_grammar["_component_status"] == "unavailable"
    
    strengths = generate_strengths(score_results, skill_val, default_grammar)
    assert not any("error-free grammar" in s.lower() for s in strengths)

def test_generate_strengths_includes_error_free_when_actually_verified():
    score_results = {
        "formatting_score": 18,
        "keywords_score": 22,
        "content_score": 21,
        "skill_validation_score": 14,
        "ats_compatibility_score": 14,
    }
    skill_val = {"validation_percentage": 0.9}
    
    verified_clean_grammar = {
        "total_errors": 0,
        "_component_status": "available"
    }
    strengths = generate_strengths(score_results, skill_val, verified_clean_grammar)
    assert any("error-free grammar" in s.lower() for s in strengths)
