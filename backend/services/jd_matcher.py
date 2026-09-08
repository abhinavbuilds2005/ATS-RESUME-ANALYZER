import re
from typing import List, Dict, Set, Optional
import numpy as np
import spacy
from sentence_transformers import SentenceTransformer
from rapidfuzz import fuzz

from backend.utils.matching import fuzzy_match_keywords, normalize_skill, match_skill_in_text

GENERIC_JD_STOPWORDS: Set[str] = {
    'software engineer', 'software developer', 'engineer', 'developer', 'lead',
    'scalable applications', 'web applications', 'web application', 'applications',
    'experience', 'responsibilities', 'qualifications', 'requirements', 'duties',
    'job description', 'opportunity', 'role', 'team', 'teams', 'candidate',
    'candidates', 'work', 'working', 'company', 'organization', 'environment',
    'day to day', 'fast paced', 'communication skills', 'years', 'degree',
    'bachelor', 'master', 'field', 'industry', 'production', 'solutions',
    'high quality', 'best practices', 'ability', 'proficient', 'knowledge',
    'understanding', 'strong', 'excellent', 'passionate', 'results', 'goals',
    'projects', 'problem solver', 'self starter', 'growth', 'impact',
    'mission', 'vision', 'track record', 'benefits', 'salary', 'competitive',
    'status', 'gender', 'race', 'religion', 'equal opportunity', 'affirmative action',
}

KNOWN_TECH_DICTIONARY: Set[str] = {
    # Programming languages
    'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'c', 'go', 'golang',
    'rust', 'ruby', 'php', 'scala', 'kotlin', 'swift', 'objective-c', 'dart', 'r',
    'matlab', 'perl', 'bash', 'shell', 'powershell', 'sql', 'html', 'css', 'sass', 'less',
    
    # Frameworks & Libraries
    'react', 'react.js', 'reactjs', 'next.js', 'nextjs', 'angular', 'angularjs',
    'vue', 'vue.js', 'vuejs', 'node.js', 'nodejs', 'express', 'express.js',
    'django', 'fastapi', 'flask', 'spring', 'spring boot', 'asp.net', '.net',
    'dotnet', '.net core', 'laravel', 'ruby on rails', 'rails', 'graphql',
    'tailwind', 'tailwindcss', 'bootstrap', 'jquery', 'redux', 'mobx',
    'scikit-learn', 'sklearn', 'tensorflow', 'pytorch', 'keras', 'pandas',
    'numpy', 'scipy', 'opencv', 'spacy', 'nltk', 'hugging face', 'huggingface',
    'langchain', 'llamaindex', 'spark', 'pyspark', 'hadoop', 'kafka',
    
    # Databases & Storage
    'postgresql', 'postgres', 'mysql', 'sqlite', 'mongodb', 'redis', 'cassandra',
    'dynamodb', 'elasticsearch', 'couchdb', 'neo4j', 'mariadb', 'oracle',
    'snowflake', 'bigquery', 'redshift',
    
    # Cloud & DevOps
    'aws', 'amazon web services', 'gcp', 'google cloud', 'google cloud platform',
    'azure', 'microsoft azure', 'docker', 'kubernetes', 'k8s', 'terraform',
    'ansible', 'helm', 'jenkins', 'github actions', 'gitlab ci', 'ci/cd', 'cicd',
    'circleci', 'nginx', 'apache', 'linux', 'unix', 'git', 'bitbucket',
    
    # Methodologies & Concepts
    'rest api', 'restful api', 'microservices', 'agile', 'scrum', 'kanban',
    'tdd', 'test-driven development', 'oop', 'unit testing', 'system architecture',
    'distributed systems', 'etl', 'data warehousing', 'data modeling', 'api design',
}


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200, max_chunks: int = 15) -> List[str]:
    """Split text into overlapping semantic chunks to preserve context across long documents."""
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for p in paragraphs:
        if current_len + len(p) > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            # Keep overlap paragraph if short
            current_chunk = [current_chunk[-1]] if len(current_chunk[-1]) < overlap else []
            current_len = sum(len(c) for c in current_chunk)
        current_chunk.append(p)
        current_len += len(p)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    # Fallback to sliding window if single continuous block without newlines
    if not chunks and text.strip():
        step = max(1, chunk_size - overlap)
        for i in range(0, len(text), step):
            ch = text[i:i + chunk_size].strip()
            if ch:
                chunks.append(ch)

    return chunks[:max_chunks]


def calculate_semantic_similarity(
    resume_text: str, jd_text: str, embedder: SentenceTransformer
) -> float:
    """
    Calculate semantic similarity using chunk-based embeddings.
    Processes full documents instead of discarding text after 5,000 characters.
    """
    if not resume_text or not jd_text or not resume_text.strip() or not jd_text.strip():
        return 0.0

    resume_chunks = chunk_text(resume_text)
    jd_chunks = chunk_text(jd_text)

    if not resume_chunks or not jd_chunks:
        return 0.0

    # Batch encode all chunks to avoid repeated model calls
    all_chunks = resume_chunks + jd_chunks
    all_embeddings = embedder.encode(all_chunks, convert_to_tensor=False)

    resume_embs = all_embeddings[:len(resume_chunks)]
    jd_embs = all_embeddings[len(resume_chunks):]

    # Aggregate by mean pooling across semantic chunks
    resume_vec = np.mean(resume_embs, axis=0)
    jd_vec = np.mean(jd_embs, axis=0)

    resume_norm = np.linalg.norm(resume_vec)
    jd_norm = np.linalg.norm(jd_vec)
    if resume_norm == 0 or jd_norm == 0:
        return 0.0

    similarity = np.dot(resume_vec, jd_vec) / (resume_norm * jd_norm)
    return float(np.clip(similarity, 0.0, 1.0))


def identify_matched_keywords(
    resume_keywords: List[str], jd_keywords: List[str]
) -> List[str]:
    result = fuzzy_match_keywords(resume_keywords, jd_keywords, threshold=80)
    return result['matched']


def identify_missing_keywords(
    resume_keywords: List[str], jd_keywords: List[str], top_n: int = 15
) -> List[str]:
    result = fuzzy_match_keywords(resume_keywords, jd_keywords, threshold=80)
    return result['missing'][:top_n]


def extract_skills_from_jd(jd_text: str, nlp: Optional[spacy.Language] = None) -> Set[str]:
    """
    Extract meaningful technical skills from JD text using dictionary lookup,
    alias normalization, and entity filtering while discarding generic noun phrases.
    """
    if not jd_text or not jd_text.strip():
        return set()

    found_skills: Set[str] = set()
    raw_lower = jd_text.lower()

    # 1. Match against known technical dictionary using punctuation-safe matcher
    for skill in KNOWN_TECH_DICTIONARY:
        if match_skill_in_text(skill, raw_lower):
            found_skills.add(skill)

    # 2. Extract and filter named entities if spaCy model is provided
    if nlp is not None:
        try:
            doc = nlp(jd_text[:10000])
            for ent in doc.ents:
                if ent.label_ in ['PRODUCT', 'LANGUAGE']:
                    ent_clean = ent.text.strip().lower()
                    if (
                        len(ent_clean) >= 2
                        and ent_clean not in GENERIC_JD_STOPWORDS
                        and not any(sw in ent_clean for sw in ('experience', 'engineer', 'developer', 'years'))
                    ):
                        found_skills.add(ent_clean)
        except Exception:
            pass

    return found_skills


def analyze_skills_gap(
    resume_skills: List[str], jd_text: str, nlp: Optional[spacy.Language] = None
) -> List[str]:
    """
    Identify skills required by JD that are absent from the resume.
    Avoids false positives such as ordinary noun phrases.
    """
    jd_skills = extract_skills_from_jd(jd_text, nlp)
    resume_normalized = {normalize_skill(s) for s in (resume_skills or []) if s and normalize_skill(s)}

    gap = []
    for jd_skill in jd_skills:
        jd_norm = normalize_skill(jd_skill)
        if not jd_norm or jd_norm in GENERIC_JD_STOPWORDS:
            continue

        # Check canonical match first
        if jd_norm in resume_normalized:
            continue

        # Check fuzzy match against resume skills
        min_thresh = 90 if len(jd_norm) <= 3 else 75
        best_score = max(
            (fuzz.token_sort_ratio(jd_norm, rs) for rs in resume_normalized),
            default=0,
        )
        if best_score < min_thresh:
            gap.append(jd_skill.title() if len(jd_skill) > 3 else jd_skill.upper())

    return sorted(gap)[:20]


def calculate_match_percentage(
    resume_keywords: List[str],
    jd_keywords: List[str],
    semantic_similarity: float,
) -> float:
    if not jd_keywords:
        return 0.0
    matched = identify_matched_keywords(resume_keywords, jd_keywords)
    keyword_overlap = len(matched) / len(jd_keywords)
    match_pct = (keyword_overlap * 0.6 + semantic_similarity * 0.4) * 100
    return float(np.clip(match_pct, 0.0, 100.0))


def compare_resume_with_jd(
    resume_text: str,
    resume_keywords: List[str],
    resume_skills: List[str],
    jd_text: str,
    jd_keywords: List[str],
    embedder: SentenceTransformer,
    nlp: Optional[spacy.Language] = None,
) -> Dict:
    all_resume_terms    = list(set((resume_keywords or []) + (resume_skills or [])))
    semantic_similarity = calculate_semantic_similarity(resume_text, jd_text, embedder)
    matched_keywords    = identify_matched_keywords(all_resume_terms, jd_keywords)
    missing_keywords    = identify_missing_keywords(all_resume_terms, jd_keywords)
    skills_gap          = analyze_skills_gap(resume_skills, jd_text, nlp)
    match_percentage    = calculate_match_percentage(
        all_resume_terms, jd_keywords, semantic_similarity
    )

    return {
        'match_percentage':    match_percentage,
        'semantic_similarity': semantic_similarity,
        'matched_keywords':    matched_keywords,
        'missing_keywords':    missing_keywords,
        'skills_gap':          skills_gap,
    }


