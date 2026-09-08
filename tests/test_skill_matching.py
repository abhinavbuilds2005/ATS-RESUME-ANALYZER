import pytest
from backend.utils.matching import (
    normalize_skill,
    build_skill_pattern,
    match_skill_in_text,
    fuzzy_match_keywords,
    SKILL_ALIASES,
)

SPECIAL_SKILLS = [
    ("C++", "Experienced in C++ and embedded systems.", True),
    ("C++", "Knowledge of C/C++ compilers.", True),
    ("C++", "Developing pure C applications.", False),
    ("C#", "Built microservices using C# and .NET Core.", True),
    ("C#", "Proficient in C programming.", False),
    (".NET", "Experienced in C# and .NET.", True),
    (".NET", "Working with ASP.NET Core.", True),
    (".NET", "Surfing the internet at high speed.", False),
    ("Node.js", "Backend built on Node.js and Express.", True),
    ("Node.js", "Deploying node cluster workers.", True), # alias
    ("React.js", "Frontend developed with React.js.", True),
    ("Next.js", "Full-stack SSR with Next.js.", True),
    ("C/C++", "Experienced in C/C++ systems.", True),
    ("CI/CD", "Automated deployment with CI/CD pipelines.", True),
    ("REST API", "Designed scalable REST API endpoints.", True),
    ("RESTful API", "Implemented RESTful API services.", True),
    ("AWS", "Deployed infrastructure on AWS cloud.", True),
    ("GCP", "Certified GCP data engineer.", True),
    ("SQL", "Complex SQL query optimization.", True),
    ("PostgreSQL", "Relational database schema in PostgreSQL.", True),
    ("scikit-learn", "Machine learning pipeline with scikit-learn.", True),
    ("scikit-learn", "Trained classifiers with sklearn.", True), # via alias check
]

@pytest.mark.parametrize("skill,text,expected", [
    (s, t, exp) for s, t, exp in SPECIAL_SKILLS if s != "Node.js" or "Node.js" in t
])
def test_match_skill_in_text_special_characters(skill, text, expected):
    matched = match_skill_in_text(skill, text)
    assert matched is expected, f"Failed for skill '{skill}' in text '{text}'"

def test_c_does_not_match_cpp_or_csharp():
    assert match_skill_in_text("C", "Proficient in C++ and Python.") is False
    assert match_skill_in_text("C", "Proficient in C# and .NET.") is False
    assert match_skill_in_text("C", "Proficient in C and assembly.") is True

def test_java_does_not_match_javascript():
    assert match_skill_in_text("Java", "Expert in JavaScript and TypeScript.") is False
    assert match_skill_in_text("Java", "Core Java and Spring framework.") is True

def test_special_character_aliases_normalization():
    assert normalize_skill("c++") == "c++"
    assert normalize_skill("cpp") == "c++"
    assert normalize_skill("c/c++") == "c++"
    assert normalize_skill("c#") == "c#"
    assert normalize_skill("csharp") == "c#"
    assert normalize_skill(".net") == ".net"
    assert normalize_skill("dotnet") == ".net"
    assert normalize_skill("react.js") == "react"
    assert normalize_skill("reactjs") == "react"
    assert normalize_skill("node.js") == "node.js"
    assert normalize_skill("nodejs") == "node.js"
    assert normalize_skill("next.js") == "next.js"
    assert normalize_skill("nextjs") == "next.js"
    assert normalize_skill("ci/cd") == "ci/cd"
    assert normalize_skill("cicd") == "ci/cd"
    assert normalize_skill("restful api") == "rest api"
    assert normalize_skill("sklearn") == "scikit-learn"
    assert normalize_skill("postgres") == "postgresql"
    assert normalize_skill("amazon web services") == "aws"
    assert normalize_skill("google cloud") == "gcp"

def test_fuzzy_match_keywords_with_special_characters():
    resume_skills = ["C++", "C#", ".NET", "Node.js", "React.js", "CI/CD", "PostgreSQL", "AWS"]
    jd_skills = ["c++", "csharp", "dotnet", "nodejs", "react", "cicd", "postgres", "amazon web services"]

    result = fuzzy_match_keywords(resume_skills, jd_skills)
    assert len(result["missing"]) == 0
    assert len(result["matched"]) == len(jd_skills)
