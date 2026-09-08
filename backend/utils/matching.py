import re
from typing import Dict, List, Optional, Set
from rapidfuzz import fuzz

SKILL_ALIASES: Dict[str, str] = {
    # JavaScript / TypeScript ecosystem
    'reactjs':                'react',
    'react.js':               'react',
    'angularjs':              'angular',
    'vuejs':                  'vue',
    'vue.js':                 'vue',
    'nextjs':                 'next.js',
    'next.js':                'next.js',
    'nodejs':                 'node.js',
    'node.js':                'node.js',
    'node':                   'node.js',
    'expressjs':              'express',
    'express.js':             'express',
    'typescript':             'typescript',
    'ts':                     'typescript',
    'javascript':             'javascript',
    'js':                     'javascript',
    
    # C / C++ / C# / .NET
    'cpp':                    'c++',
    'c++':                    'c++',
    'c/c++':                  'c++',
    'csharp':                 'c#',
    'c#':                     'c#',
    'dotnet':                 '.net',
    '.net':                   '.net',
    '.net core':              '.net',
    'asp.net':                '.net',
    
    # Python & ML / Data
    'python':                 'python',
    'py':                     'python',
    'sklearn':                'scikit-learn',
    'scikit-learn':           'scikit-learn',
    'pyspark':                'spark',
    'huggingface':            'hugging face',
    'hugging face':           'hugging face',
    'ml':                     'machine learning',
    'ai':                     'artificial intelligence',
    'nlp':                    'natural language processing',
    'cv':                     'computer vision',
    
    # Java / Backend
    'springboot':             'spring boot',
    'spring boot':            'spring boot',
    'golang':                 'go',
    
    # Cloud & DevOps
    'amazon web services':    'aws',
    'aws':                    'aws',
    'google cloud':           'gcp',
    'google cloud platform':  'gcp',
    'gcp':                    'gcp',
    'microsoft azure':        'azure',
    'azure':                  'azure',
    'k8s':                    'kubernetes',
    'kubernetes':             'kubernetes',
    'ci/cd':                  'ci/cd',
    'cicd':                   'ci/cd',
    
    # Database
    'postgres':               'postgresql',
    'postgresql':             'postgresql',
    'postgre':                'postgresql',
    
    # API & Architecture
    'rest api':               'rest api',
    'restful api':            'rest api',
    'restful apis':           'rest api',
    'rest apis':              'rest api',
    'restful':                'rest api',
    
    # UI
    'tailwindcss':            'tailwind',
    'tailwind css':           'tailwind',
}


REVERSE_ALIASES: Dict[str, Set[str]] = {}
for _alias, _canon in SKILL_ALIASES.items():
    REVERSE_ALIASES.setdefault(_canon, set()).add(_alias)


def normalize_skill(skill: str) -> str:
    """Normalize skill string to its canonical form using lowercase and aliases."""
    if not skill or not isinstance(skill, str):
        return ""
    cleaned = skill.strip().lower()
    return SKILL_ALIASES.get(cleaned, cleaned)


def build_skill_pattern(skill: str) -> str:
    """
    Construct a regex pattern that safely matches skills containing punctuation
    (e.g., C++, C#, .NET, CI/CD, scikit-learn) without relying on \\b alone.
    """
    escaped = re.escape(skill.strip().lower())
    # Preceding character boundary: cannot be alphanumeric, underscore, or dot (unless skill starts with dot)
    if skill.startswith('.'):
        lead = r'(?<![A-Za-z0-9_])'
    else:
        lead = r'(?<![A-Za-z0-9_.])'

    # Trailing character boundary: cannot be alphanumeric, underscore, +, or #
    if skill.endswith('+'):
        trail = r'(?![A-Za-z0-9_+])'
    elif skill.endswith('#'):
        trail = r'(?![A-Za-z0-9_#])'
    else:
        trail = r'(?![A-Za-z0-9_+#])'

    return lead + escaped + trail


def match_skill_in_text(skill: str, text: str) -> bool:
    """
    Test if a skill (or any of its recognized aliases) occurs in a given text
    using punctuation-safe matching.
    """
    if not skill or not text:
        return False

    raw_lower = text.lower()
    skill_clean = skill.strip().lower()
    canon = normalize_skill(skill_clean)

    # Check direct skill, canonical form, and all registered aliases
    candidates = {skill_clean, canon}
    if canon in REVERSE_ALIASES:
        candidates.update(REVERSE_ALIASES[canon])

    for candidate in candidates:
        if candidate:
            pat = build_skill_pattern(candidate)
            if re.search(pat, raw_lower):
                return True

    return False



def fuzzy_match_keywords(
    resume_keywords: List[str],
    jd_keywords: List[str],
    threshold: int = 80,
) -> Dict[str, List[str]]:
    """
    Compare resume keywords/skills against job description keywords.
    Preserves original skill casing/display text while matching on canonical forms.
    """
    resume_normalized: Dict[str, str] = {}
    for kw in (resume_keywords or []):
        if kw and isinstance(kw, str):
            norm = normalize_skill(kw)
            if norm and norm not in resume_normalized:
                resume_normalized[norm] = kw

    jd_normalized: Dict[str, str] = {}
    for kw in (jd_keywords or []):
        if kw and isinstance(kw, str):
            norm = normalize_skill(kw)
            if norm and norm not in jd_normalized:
                jd_normalized[norm] = kw

    matched_jd_originals: List[str] = []
    missing_jd_originals: List[str] = []

    for jd_canon, jd_original in jd_normalized.items():
        # 1. Exact canonical match
        if jd_canon in resume_normalized:
            matched_jd_originals.append(jd_original)
            continue

        # 2. Fuzzy match against all resume canonical names
        best_score = 0
        for resume_canon in resume_normalized:
            # For short tokens (<= 3 chars like AWS, GCP, C++), require higher threshold to prevent false positives
            min_thresh = 90 if (len(jd_canon) <= 3 or len(resume_canon) <= 3) else threshold
            score = fuzz.token_sort_ratio(jd_canon, resume_canon)
            if score >= min_thresh and score > best_score:
                best_score = score

        if best_score >= threshold:
            matched_jd_originals.append(jd_original)
        else:
            missing_jd_originals.append(jd_original)

    return {
        'matched': sorted(matched_jd_originals),
        'missing': missing_jd_originals,
    }

