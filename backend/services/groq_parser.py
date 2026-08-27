import os
import re
import json 
import logging
from typing import Dict, Optional, Any


from groq import Groq

from backend.core.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger('ats_resume_scorer')

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = GROQ_API_KEY or os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        _client = Groq(api_key=api_key, timeout=30.0)
    return _client

RESUME_SYSTEM_PROMPT = (
    "You are a resume parser. Extract information from the resume "
    "and return ONLY a valid JSON object. No explanation, no markdown."
)

RESUME_USER_PROMPT = """Extract the following from this resume and return as JSON:
{{
  "name": "full name",
  "email": "email address",
  "phone": "phone number",
  "linkedin": "LinkedIn URL if present, otherwise null",
  "github": "GitHub URL if present, otherwise null",
  "professional_summary": "the full text of the Summary, Profile, About Me, Objective, or Professional Summary section at the top of the resume. Copy the ENTIRE paragraph exactly as written. If no such section exists, return an empty string.",
  "skills": ["list", "of", "skills"],
  "experience": [
    {{
      "job_title": "",
      "company": "",
      "start_date": "",
      "end_date": "",
      "duration_months": 0,
      "description": ""
    }}
  ],
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": ""
    }}
  ],
  "certifications": ["list of certifications"],
  "projects": [
    {{
      "title": "project name",
      "description": "what the project does and how it was built",
      "technologies": ["tech", "used"]
    }}
  ],
  "action_verbs": ["strong action verbs used in bullet points, e.g. developed, implemented, designed"],
  "keywords": ["important keywords and phrases from the resume for ATS matching"]
}}

Important instructions:
- For duration_months, calculate the number of months between start_date and end_date. If end_date is "Present" or "Current", calculate from start_date to now.
- For skills, extract ALL technical and soft skills mentioned anywhere in the resume.
- For action_verbs, find verbs that start bullet points or describe achievements.
- For keywords, extract noun phrases and technical terms relevant to ATS matching.
- Return ONLY valid JSON. No markdown code fences, no explanation.

Resume Text:
{raw_text}"""

def _call_groq(client: Groq, system_prompt: str, user_prompt: str) -> str:
    candidates = [GROQ_MODEL] if GROQ_MODEL else []
    for fallback in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama-3.1-70b-versatile", "gemma2-9b-it"]:
        if fallback not in candidates:
            candidates.append(fallback)

    last_exc = None
    for model_name in candidates:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.0,
                max_tokens=4096
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Groq completion failed with model '{model_name}': {exc}. Trying next candidate...")
            continue

    if last_exc:
        raise last_exc
    raise RuntimeError("No Groq models available to complete request.")

def _try_parse_json(text: str) -> dict | None:
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()

    # 1. Strip markdown code fences if present
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # 2. Try direct json.loads
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Try finding outermost JSON object between first { and last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _fallback_parse_resume(raw_text: str) -> Dict:
    """Deterministic heuristic fallback when Groq is unavailable or fails."""
    logger.warning("Using heuristic fallback parser for resume.")
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    phones = re.findall(r'\(?\+?\d{1,3}\)?[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', raw_text)
    linkedin = re.findall(r'linkedin\.com/in/[\w\-]+', raw_text, re.IGNORECASE)
    github = re.findall(r'github\.com/[\w\-]+', raw_text, re.IGNORECASE)

    common_skills = [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
        "react", "angular", "vue", "node.js", "express", "fastapi", "django", "flask",
        "sql", "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes",
        "aws", "gcp", "azure", "git", "linux", "machine learning", "deep learning",
        "nlp", "data analysis", "html", "css", "tailwind", "rest api", "graphql"
    ]
    raw_lower = raw_text.lower()
    found_skills = [s.title() for s in common_skills if re.search(r'\b' + re.escape(s) + r'\b', raw_lower)]

    common_verbs = [
        "developed", "implemented", "designed", "built", "created", "led", "managed",
        "optimized", "automated", "improved", "reduced", "increased", "deployed",
        "engineered", "architected", "collaborated", "launched", "analyzed"
    ]
    found_verbs = [v.title() for v in common_verbs if re.search(r'\b' + re.escape(v) + r'\b', raw_lower)]

    # Guess name from first non-empty line
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    name = lines[0] if lines and len(lines[0].split()) <= 4 else ""

    result = {
        "name": name,
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "linkedin": linkedin[0] if linkedin else None,
        "github": github[0] if github else None,
        "professional_summary": "",
        "skills": found_skills,
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "action_verbs": found_verbs,
        "keywords": found_skills[:15],
    }
    return _validate_resume_result(result)

def parse_resume(raw_text: str)->Dict:
    try:
        client = _get_client()
        prompt = RESUME_USER_PROMPT.format(raw_text=raw_text)
        raw_response = _call_groq(client, RESUME_SYSTEM_PROMPT, prompt)
        result = _try_parse_json(raw_response)

        if result is not None:
            return _validate_resume_result(result)

        logger.warning("Groq resume parse: first attempt returned invalid JSON, retrying...")
        strict_prompt = (
            "Your previous response was not valid JSON. "
            "Return ONLY the raw JSON object, no markdown, no explanation, no code fences.\n\n"
            + prompt
        )
        raw_response = _call_groq(client, RESUME_SYSTEM_PROMPT, strict_prompt)
        result = _try_parse_json(raw_response)
        if result is not None:
            return _validate_resume_result(result)
    except Exception as exc:
        logger.warning(f"Groq parse_resume encountered error: {exc}. Using fallback parser...")
        return _fallback_parse_resume(raw_text)

    return _fallback_parse_resume(raw_text)

    
JD_SYSTEM_PROMPT = (
    "You are a job description parser. Extract information and "
    "return ONLY a valid JSON object. No explanation, no markdown."
)

JD_USER_PROMPT = """Extract the following from this job description and return as JSON:
{{
  "job_title": "",
  "required_skills": ["list of must-have skills"],
  "preferred_skills": ["list of nice-to-have skills"],
  "experience_required": "",
  "education_required": "",
  "key_responsibilities": ["list of responsibilities"],
  "keywords": ["important keywords and phrases for ATS matching"]
}}

Important instructions:
- required_skills: skills explicitly stated as required or must-have.
- preferred_skills: skills stated as preferred, nice-to-have, or bonus.
- keywords: extract ALL important terms an ATS system would match against,
  including skills, technologies, certifications, and domain terms.
- Return ONLY valid JSON. No markdown code fences, no explanation.

Job Description Text:
{raw_text}"""

def _fallback_parse_jd(raw_text: str) -> Dict:
    """Deterministic heuristic fallback when Groq is unavailable or fails for JD."""
    logger.warning("Using heuristic fallback parser for job description.")
    common_skills = [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
        "react", "angular", "vue", "node.js", "express", "fastapi", "django", "flask",
        "sql", "postgresql", "mysql", "mongodb", "redis", "docker", "kubernetes",
        "aws", "gcp", "azure", "git", "linux", "machine learning", "deep learning",
        "nlp", "data analysis", "html", "css", "tailwind", "rest api", "graphql"
    ]
    raw_lower = raw_text.lower()
    found_skills = [s.title() for s in common_skills if re.search(r'\b' + re.escape(s) + r'\b', raw_lower)]

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    job_title = lines[0] if lines and len(lines[0].split()) <= 6 else "Target Role"

    result = {
        "job_title": job_title,
        "required_skills": found_skills[:8],
        "preferred_skills": found_skills[8:15],
        "experience_required": "",
        "education_required": "",
        "key_responsibilities": [l for l in lines[1:6] if len(l) > 20],
        "keywords": found_skills,
    }
    return _validate_jd_result(result)

def parse_job_description(raw_text: str) -> Dict:
    try:
        client = _get_client()
        prompt = JD_USER_PROMPT.format(raw_text=raw_text)

        raw_response = _call_groq(client, JD_SYSTEM_PROMPT, prompt)
        result = _try_parse_json(raw_response)
        if result is not None:
            return _validate_jd_result(result)

        logger.warning("Groq JD parse: first attempt returned invalid JSON, retrying...")
        strict_prompt = (
            "Your previous response was not valid JSON. "
            "Return ONLY the raw JSON object, no markdown, no explanation, no code fences.\n\n"
            + prompt
        )
        raw_response = _call_groq(client, JD_SYSTEM_PROMPT, strict_prompt)
        result = _try_parse_json(raw_response)
        if result is not None:
            return _validate_jd_result(result)
    except Exception as exc:
        logger.warning(f"Groq parse_job_description encountered error: {exc}. Using fallback parser...")
        return _fallback_parse_jd(raw_text)

    return _fallback_parse_jd(raw_text)


#it will make sure, that the parse json has all the valid fields we expect
def _validate_jd_result(result: dict) -> dict:
    
    defaults = {
        "job_title": "",
        "required_skills": [],
        "preferred_skills": [],
        "experience_required": "",
        "education_required": "",
        "key_responsibilities": [],
        "keywords": [],
    }

    for key, default in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default
        if isinstance(default, list) and not isinstance(result[key], list):
            result[key] = default

    return result


#to make sure the parse json has all the valid json fields
def _validate_resume_result(result: dict) -> dict:

    defaults = {
        "name": "",
        "email": None,
        "phone": None,
        "linkedin": None,
        "github": None,
        "professional_summary": "",
        "skills": [],
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "action_verbs": [],
        "keywords": [],
    }
    for key, default in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default
            
        # Ensure list fields are actually lists
        if isinstance(default, list) and not isinstance(result[key], list):
            result[key] = default

    for key in ('skills', 'certifications', 'action_verbs', 'keywords'):
        result[key] = [str(value).strip() for value in result[key] if value is not None and str(value).strip()]

    #Validate experience entries
    result['experience'] = [exp for exp in result['experience'] if isinstance(exp, dict)]
    for exp in result['experience']:
        if not isinstance(exp, dict):
            continue
        exp.setdefault("job_title", "")
        exp.setdefault("company", "")
        exp.setdefault("start_date", "")
        exp.setdefault("end_date", "")
        exp.setdefault("duration_months", 0)
        exp.setdefault("description", "")
        for key in ("job_title", "company", "start_date", "end_date", "description"):
            exp[key] = str(exp[key] or "")
        #Ensure duration_months is an int
        try:
            exp["duration_months"] = int(exp["duration_months"])
        except (ValueError, TypeError):
            exp["duration_months"] = 0

    #Validate project entries
    result['projects'] = [proj for proj in result['projects'] if isinstance(proj, dict)]
    for proj in result['projects']:
        if not isinstance(proj, dict):
            continue
        proj.setdefault("title", "")
        proj.setdefault("description", "")
        proj.setdefault("technologies", [])
        for key in ("title", "description"):
            proj[key] = str(proj[key] or "")
        if not isinstance(proj['technologies'], list):
            proj['technologies'] = []
        proj['technologies'] = [str(value).strip() for value in proj['technologies'] if value is not None and str(value).strip()]

    return result


