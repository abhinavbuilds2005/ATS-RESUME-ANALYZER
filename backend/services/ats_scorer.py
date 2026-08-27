import re
import spacy
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional, Tuple

from backend.utils.file_utils import log_warning
from backend.core.config import SCORE_WEIGHTS, SENTENCE_TRANSFORMER_MODEL
from backend.utils.matching import fuzzy_match_keywords

ZIP_CODE_PATTERN = r'\b\d{5}(?:-\d{4})?\b'

STREET_ADDRESS_PATTERN = (
    r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
    r'(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Place|Pl)\b'
)

# Common resume typos for deterministic spell-checking
COMMON_TYPOS = {
    'recieve': 'receive',
    'recieved': 'received',
    'seperate': 'separate',
    'seperated': 'separated',
    'managment': 'management',
    'expereince': 'experience',
    'responsibilites': 'responsibilities',
    'responsbility': 'responsibility',
    'achievment': 'achievement',
    'achievments': 'achievements',
    'develope': 'develop',
    'developement': 'development',
    'referance': 'reference',
    'referances': 'references',
    'occured': 'occurred',
    'sucessful': 'successful',
    'sucessfully': 'successfully',
    'enviroment': 'environment',
    'definately': 'definitely',
}

def analyze_grammar_and_spelling(text: str, nlp: Optional[spacy.Language] = None) -> Dict:
    """
    Perform deterministic, lightweight grammar, spelling, and text quality analysis.
    Identifies repeated words, common spelling mistakes, punctuation glitches, and sentence anomalies.
    """
    if not text or not text.strip():
        return {
            'total_errors': 0,
            'critical_errors': [],
            'moderate_errors': [],
            'minor_errors': [],
            'grammar_score': 100.0,
            'penalty_applied': 0.0,
            'error_free_percentage': 100.0,
            '_component_status': 'available',
            '_note': 'Empty text evaluated.',
        }

    critical_errors = []
    moderate_errors = []
    minor_errors = []

    # 1. Check for common typos
    for typo, correction in COMMON_TYPOS.items():
        pattern = r'\b' + re.escape(typo) + r'\b'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            critical_errors.append({
                'error_text': match.group(),
                'suggestions': [correction],
                'message': f"Spelling error: '{match.group()}' is misspelled.",
                'position': match.start(),
                'severity': 'critical',
            })

    # 2. Check for repeated consecutive words (e.g., "in in", "the the", "with with")
    repeated_word_pattern = r'\b([A-Za-z]{2,})\s+\1\b'
    for match in re.finditer(repeated_word_pattern, text, re.IGNORECASE):
        # Ignore common natural doubles like "that that" or "had had"
        word = match.group(1).lower()
        if word not in ('that', 'had'):
            moderate_errors.append({
                'error_text': match.group(),
                'suggestions': [match.group(1)],
                'message': f"Repeated word: '{match.group()}' appears consecutively.",
                'position': match.start(),
                'severity': 'moderate',
            })

    # 3. Check for double punctuation anomalies (e.g. ",,", "..", ";;")
    double_punct_pattern = r'([,;:])\s*\1+'
    for match in re.finditer(double_punct_pattern, text):
        minor_errors.append({
            'error_text': match.group(),
            'suggestions': [match.group(1)],
            'message': f"Punctuation anomaly: consecutive '{match.group()}' detected.",
            'position': match.start(),
            'severity': 'minor',
        })

    # 4. Check for unmatched brackets or parentheses
    for open_b, close_b in [('(', ')'), ('[', ']'), ('{', '}')]:
        open_count = text.count(open_b)
        close_count = text.count(close_b)
        if open_count != close_count:
            minor_errors.append({
                'error_text': f"{open_b}...{close_b}",
                'suggestions': [],
                'message': f"Mismatched {open_b}{close_b}: found {open_count} opening and {close_count} closing.",
                'position': 0,
                'severity': 'minor',
            })

    total_errors = len(critical_errors) + len(moderate_errors) + len(minor_errors)
    penalty = min(10.0, len(critical_errors) * 2.0 + len(moderate_errors) * 1.0 + len(minor_errors) * 0.5)
    grammar_score = max(0.0, 100.0 - penalty * 10.0)

    return {
        'total_errors': total_errors,
        'critical_errors': critical_errors,
        'moderate_errors': moderate_errors,
        'minor_errors': minor_errors,
        'grammar_score': grammar_score,
        'penalty_applied': penalty,
        'error_free_percentage': max(0.0, 100.0 - total_errors * 5.0),
        '_component_status': 'available',
        '_note': 'Rule-based grammar and spelling check completed.',
    }

def _tier_score(n: float, tiers:list)-> float:
    for threshold, pts in tiers:
        if n>=threshold:
            return pts
    
    return 0.0

#Location/privacy detection
def detect_location_info(text: str, nlp: spacy.Language) -> Dict:
    locations = []

    #method01: spacy NER
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ['GPE', 'LOC']:
            locations.append({'text': ent.text, 'type': ent.label_.lower(), 'start': ent.start_char})

    #moetod02: street address regx
    for match in re.finditer(STREET_ADDRESS_PATTERN, text, re.IGNORECASE):
        locations.append({'text': match.group(), 'type': 'address', 'start': match.start()})

    #method03: ZIP/PIN CODE REGEX PATTERN
    for match in re.finditer(ZIP_CODE_PATTERN, text):
        locations.append({'text': match.group(), 'type': 'zip', 'start': match.start()})

    has_address = any(loc['type'] == 'address' for loc in locations)
    has_zip     = any(loc['type'] == 'zip'     for loc in locations)

    if has_address and has_zip:
        privacy_risk, penalty = 'high', 5.0
    elif has_address or has_zip:
        privacy_risk, penalty = 'high', 4.0
    elif len(locations) > 3:
        privacy_risk, penalty = 'medium', 3.0
    elif locations:
        privacy_risk, penalty = 'low', 2.0
    else:
        privacy_risk, penalty = 'none', 0.0

    recommendations = []
    if not locations:
        recommendations.append("No privacy concerns detected.")
    if has_address:
        recommendations.append("Remove full street addresses — ATS systems don't need this and it's a privacy risk.")
    if has_zip:
        recommendations.append("Remove zip codes — this level of location detail is unnecessary.")
    if privacy_risk in ('low', 'medium') and not has_address and not has_zip:
        recommendations.append("Consider reducing location mentions. 'City, State' in the contact header is sufficient.")

    return {
        'location_found':     len(locations) > 0,
        'detected_locations': locations,
        'privacy_risk':       privacy_risk,
        'recommendations':    recommendations,
        'penalty_applied':    penalty,
    }

def _calculate_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Fast cosine similarity between two precomputed vectors."""
    if vec1 is None or vec2 is None:
        return 0.0
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(max(0.0, min(1.0, np.dot(vec1, vec2) / (norm1 * norm2))))

#Skill validation with precomputed embeddings for performance
def validate_skills_with_projects(
    skills: List[str],
    projects: List[Dict],
    experience_entries: List[Dict],
    embedder: SentenceTransformer,
    threshold: float = 0.6,
) -> Dict:
    
    if not skills:
        return {
            'validated_skills':      [],
            'unvalidated_skills':    [],
            'validation_percentage': 0.0,
            'skill_project_mapping': {},
            'validation_score':      0.0,
        }

    experience_text = ' '.join(
        f"{e.get('job_title', '')} {e.get('company', '')} {e.get('description', '')}"
        for e in experience_entries
        if isinstance(e, dict)
    ).strip()

    # Pre-extract and pre-encode project texts ONCE
    project_items = []
    for project in projects:
        title = project.get('title', 'Untitled Project')
        p_text = f"{project.get('title', '')} {project.get('description', '')}".strip()
        p_vec = embedder.encode(p_text, convert_to_tensor=False) if p_text else None
        project_items.append({
            'title': title,
            'text': p_text,
            'vector': p_vec,
        })

    # Pre-encode experience text ONCE
    exp_vec = embedder.encode(experience_text, convert_to_tensor=False) if experience_text else None

    validated_skills      = []
    unvalidated_skills    = []
    skill_project_mapping = {}

    for skill in skills:
        if not skill or not skill.strip():
            continue
        skill_clean = skill.strip()
        matching_projects = []
        max_similarity    = 0.0

        # Fast word-boundary check pattern
        pattern = r'(?:\b|_)' + re.escape(skill_clean) + r'(?:\b|_)'
        skill_vec = None  # Lazily compute skill embedding only if fast regex didn't match everything

        for p_item in project_items:
            # 1. Fast regex match
            if p_item['text'] and re.search(pattern, p_item['text'], re.IGNORECASE):
                matching_projects.append(p_item['title'])
                max_similarity = max(max_similarity, 1.0)
            elif p_item['vector'] is not None:
                # 2. Semantic embedding check
                if skill_vec is None:
                    skill_vec = embedder.encode(skill_clean, convert_to_tensor=False)
                sim = _calculate_cosine_similarity(skill_vec, p_item['vector'])
                max_similarity = max(max_similarity, sim)
                if sim >= threshold:
                    matching_projects.append(p_item['title'])

        if experience_text:
            if re.search(pattern, experience_text, re.IGNORECASE):
                max_similarity = max(max_similarity, 1.0)
                if 'Experience Section' not in matching_projects:
                    matching_projects.append('Experience Section')
            elif exp_vec is not None:
                if skill_vec is None:
                    skill_vec = embedder.encode(skill_clean, convert_to_tensor=False)
                sim = _calculate_cosine_similarity(skill_vec, exp_vec)
                max_similarity = max(max_similarity, sim)
                if sim >= threshold and 'Experience Section' not in matching_projects:
                    matching_projects.append('Experience Section')

        if matching_projects:
            validated_skills.append({'skill': skill_clean, 'projects': matching_projects, 'similarity': max_similarity})
            skill_project_mapping[skill_clean] = matching_projects
        else:
            unvalidated_skills.append(skill_clean)
            skill_project_mapping[skill_clean] = []

    validation_percentage = len(validated_skills) / len(skills) if skills else 0.0
    validation_score      = validation_percentage * 15.0

    return {
        'validated_skills':      validated_skills,
        'unvalidated_skills':    unvalidated_skills,
        'validation_percentage': validation_percentage,
        'skill_project_mapping': skill_project_mapping,
        'validation_score':      validation_score,
    }


#01: formatting score
def _calc_formatting_score(parsed_resume: Dict, text: str) -> float:

    score = 0.0

    exp_entries  = [e for e in parsed_resume.get('experience', []) if isinstance(e, dict)]
    edu_entries  = [e for e in parsed_resume.get('education', [])  if isinstance(e, dict)]
    skills       = parsed_resume.get('skills', [])
    summary      = parsed_resume.get('professional_summary', '')
    proj_entries = [p for p in parsed_resume.get('projects', [])   if isinstance(p, dict)]

    if exp_entries and any(e.get('job_title') or e.get('description') for e in exp_entries):
        score += 3.0
    if edu_entries:
        score += 2.0
    if len(skills) >= 3:
        score += 2.0
    if len(summary) > 30:
        score += 1.5
    if proj_entries:
        score += 1.5

    bullet_count = sum(
        1 for line in text.split('\n')
        if re.match(r'^\s*[•\-\*\◦]', line) or re.match(r'^\s*\d+\.', line)
    )
    score += _tier_score(bullet_count, [(15,5.0),(10,4.0),(5,3.0),(3,2.0),(1,1.0)])

    filled = sum(1 for has_it in [
        bool(exp_entries), bool(edu_entries), bool(skills),
        bool(summary.strip()), bool(proj_entries),
    ] if has_it)
    score += _tier_score(filled, [(4,5.0),(3,4.0),(2,3.0),(1,2.0)])

    return min(20.0, max(0.0, score))

#02 keyword score
def _calc_keywords_score(
    resume_keywords: List[str],
    skills: List[str],
    jd_keywords: Optional[List[str]] = None,
) -> float:
    score = 0.0

    score += _tier_score(len(resume_keywords), [(20,10.0),(15,8.0),(10,6.0),(5,4.0),(3,2.0)])
    score += _tier_score(len(skills),          [(15,10.0),(10,8.0),(7,6.0),(5,4.0),(3,2.0)])

    if jd_keywords:
        all_resume_terms = list(set(resume_keywords + skills))
        fuzzy_result     = fuzzy_match_keywords(all_resume_terms, jd_keywords, threshold=80)
        match_pct        = len(fuzzy_result['matched']) / len(jd_keywords) if jd_keywords else 0
        score += _tier_score(match_pct, [(0.7,5.0),(0.5,4.0),(0.3,3.0),(0.2,2.0),(0.1,1.0)])
    
    elif len(resume_keywords) >= 10:
        score += 3.0

    return min(25.0, max(0.0, score))

#3. CONTENT QUALITY SCORE
def _calc_content_score(
    text: str,
    action_verbs: List[str],
    grammar_results: Dict,
) -> float:
    
    score = 0.0

    score += _tier_score(len(action_verbs), [(15,10.0),(10,8.0),(7,6.0),(5,4.0),(3,2.0)])

    number_patterns = [
        r'\d+%',
        r'\$\d+',
        r'\d+[kKmMbB]',
        r'\d+\s*(?:users|customers|clients|projects|hours|days|months|years)',
        r'(?:increased|decreased|improved|reduced|grew|saved)\s+(?:by\s+)?\d+',
    ]
    achievement_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in number_patterns)
    score += _tier_score(achievement_count, [(10,5.0),(7,4.0),(5,3.0),(3,2.0),(1,1.0)])

    grammar_penalty = grammar_results.get('penalty_applied', 0.0)
    score += max(0.0, 10.0 - grammar_penalty / 2.0)

    return min(25.0, max(0.0, score))

#4. SKILL VALIDATION SCORE
def _calc_skill_validation_score(validation_results: Dict) -> float:
    return min(15.0, max(0.0, validation_results.get('validation_score', 0.0)))

#5. ATS COMPATIBILITY SCORE
def _calc_ats_compatibility_score(
    text: str,
    location_results: Dict,
    parsed_resume: Dict,
) -> float:

    score = 15.0

    #dedeuction01
    score -= location_results.get('penalty_applied', 0.0)

    #deduction02
    special_chars = len(re.findall(r'[│┤├┼┴┬╔╗╚╝═║╠╣╦╩╬]', text))
    if special_chars > 20:    score -= 2.0
    elif special_chars > 10:  score -= 1.0

    exp_entries  = [e for e in parsed_resume.get('experience', []) if isinstance(e, dict)]
    edu_entries  = [e for e in parsed_resume.get('education', [])  if isinstance(e, dict)]
    skills_count = len(parsed_resume.get('skills', []))

    exp_desc_len = sum(len(e.get('description', '')) for e in exp_entries)
    edu_desc_len = sum(len((e.get('degree') or '') + (e.get('institution') or '')) for e in edu_entries)  # Handle None to prevent string concatenation errors

    #deduction03
    short_sections = sum([
        bool(exp_entries) and exp_desc_len < 20,
        bool(edu_entries) and edu_desc_len < 20,
        bool(parsed_resume.get('skills')) and skills_count < 2,
    ])
    if short_sections >= 2:    score -= 2.0
    elif short_sections >= 1:  score -= 1.0

    if exp_entries and skills_count > 5:
        score += 1.0

    return min(15.0, max(0.0, score))

#Score aggregation and final interpretation
def calculate_overall_score(
    text: str,
    parsed_resume: Dict,
    skills: List[str],
    keywords: List[str],
    action_verbs: List[str],
    skill_validation_results: Dict,
    grammar_results: Dict,
    location_results: Dict,
    jd_keywords: Optional[List[str]] = None,
    experience_months: int = 0,
) -> Dict:

    formatting_max = float(SCORE_WEIGHTS.get('formatting', 20.0))
    keywords_max = float(SCORE_WEIGHTS.get('keywords', 25.0))
    content_max = float(SCORE_WEIGHTS.get('content', 25.0))
    skill_validation_max = float(SCORE_WEIGHTS.get('skill_validation', 15.0))
    ats_compatibility_max = float(SCORE_WEIGHTS.get('ats_compatibility', 15.0))

    formatting_score        = min(formatting_max, max(0.0, _calc_formatting_score(parsed_resume, text)))
    keywords_score          = min(keywords_max, max(0.0, _calc_keywords_score(keywords, skills, jd_keywords)))
    content_score           = min(content_max, max(0.0, _calc_content_score(text, action_verbs, grammar_results)))
    skill_validation_score  = min(skill_validation_max, max(0.0, _calc_skill_validation_score(skill_validation_results)))
    ats_compatibility_score = min(ats_compatibility_max, max(0.0, _calc_ats_compatibility_score(text, location_results, parsed_resume)))

    base_score = (
        formatting_score +
        keywords_score +
        content_score +
        skill_validation_score +
        ats_compatibility_score
    )

    penalties = {}
    bonuses   = {}
    score     = base_score

    if grammar_results.get('penalty_applied', 0.0) > 0:
        penalties['grammar'] = grammar_results['penalty_applied']

    if location_results.get('penalty_applied', 0.0) > 0:
        penalties['location_privacy'] = location_results['penalty_applied']

    validation_pct = skill_validation_results.get('validation_percentage', 0.0)
    if validation_pct >= 0.9:
        bonuses['excellent_skill_validation'] = 2.0
        score += 2.0
    elif validation_pct >= 0.8:
        bonuses['good_skill_validation'] = 1.0
        score += 1.0

    if grammar_results.get('_component_status') == 'available' and grammar_results.get('total_errors', 0) == 0:
        bonuses['perfect_grammar'] = 1.0
        score += 1.0

    if jd_keywords and len(jd_keywords) > 0:
        all_resume_terms = list(set((keywords or []) + (skills or [])))
        fuzzy_result     = fuzzy_match_keywords(all_resume_terms, jd_keywords, threshold=80)
        missing_pct      = len(fuzzy_result['missing']) / len(jd_keywords)

        if missing_pct > 0.7:
            penalties['missing_jd_keywords'] = 15.0
            score -= 15.0
        elif missing_pct > 0.5:
            penalties['missing_jd_keywords'] = 10.0
            score -= 10.0
        elif missing_pct > 0.3:
            penalties['missing_jd_keywords'] = 5.0
            score -= 5.0

    overall_score = min(100.0, max(0.0, score))
    interpretation = _generate_score_interpretation(overall_score)

    return {
        'overall_score':           round(overall_score, 1),
        'formatting_score':        round(formatting_score, 1),
        'keywords_score':          round(keywords_score, 1),
        'content_score':           round(content_score, 1),
        'skill_validation_score':  round(skill_validation_score, 1),
        'ats_compatibility_score': round(ats_compatibility_score, 1),
        'overall_interpretation':  interpretation,
        'penalties':               penalties,
        'bonuses':                 bonuses,
    }

#Overall score calculation and interpretation
def generate_strengths(
    score_results: Dict,
    skill_validation_results: Dict,
    grammar_results: Dict,
) -> List[str]:

    strengths = []

    if score_results['formatting_score']       >= 16:
        strengths.append('Well-structured with clear sections and bullet points')
    if score_results['keywords_score']          >= 20:
        strengths.append('Strong keyword optimization and skills presence')
    if score_results['content_score']           >= 20:
        strengths.append('Excellent use of action verbs and quantifiable achievements')
    if score_results['skill_validation_score']  >= 12:
        pct = skill_validation_results.get('validation_percentage', 0) * 100
        strengths.append(f'{pct:.0f}% of skills are validated by projects')
    if score_results['ats_compatibility_score'] >= 13:
        strengths.append('Excellent ATS compatibility with clean formatting')
    if grammar_results.get('_component_status') == 'available' and grammar_results.get('total_errors', 0) == 0:
        strengths.append('Error-free grammar and spelling')

    if not strengths:
        strengths.append('Your resume has potential - focus on the recommendations below')
    return strengths


#Critical issues that could cause ATS rejection
def generate_critical_issues(
    score_results: Dict,
    grammar_results: Dict,
    location_results: Dict,
) -> List[str]:
    issues = []

    critical_errors = len(grammar_results.get('critical_errors', []))
    if critical_errors > 0:
        issues.append(f' {critical_errors} critical grammar/spelling error(s) detected')
    if location_results.get('privacy_risk') == 'high':
        issues.append('High privacy risk: Remove detailed location information')
    if score_results['formatting_score']       < 10:
        issues.append(' Poor formatting: Add clear sections and bullet points')
    if score_results['keywords_score']         < 12:
        issues.append(' Insufficient keywords and skills')
    if score_results['skill_validation_score'] < 7:
        issues.append(' Most skills lack supporting evidence in projects')

    return issues


#Actionable improvements to enhance ATS performance
def generate_improvements(
    score_results: Dict,
    skill_validation_results: Dict,
) -> List[str]:
    improvements = []

    if 12 <= score_results['formatting_score']       < 16:
        improvements.append('Add more bullet points and improve section organization')
    if 14 <= score_results['keywords_score']          < 20:
        improvements.append('Include more relevant keywords and technical skills')
    if 14 <= score_results['content_score']           < 20:
        improvements.append('Add more quantifiable achievements and action verbs')
    if 7  <= score_results['skill_validation_score']  < 12:
        unvalidated_count = len(skill_validation_results.get('unvalidated_skills', []))
        improvements.append(f'Validate {unvalidated_count} skill(s) by adding relevant project details')
    if 9  <= score_results['ats_compatibility_score'] < 13:
        improvements.append('Simplify formatting for better ATS compatibility')

    return improvements

#Interpretation of overall score
def _generate_score_interpretation(overall_score: float) -> str:
    if overall_score >= 90:    return 'Excellent! Your resume is highly optimized for ATS systems.'
    elif overall_score >= 80:  return 'Great! Your resume should perform well with most ATS systems.'
    elif overall_score >= 70:  return 'Good! Your resume is ATS-friendly with room for minor improvements.'
    elif overall_score >= 60:  return 'Fair. Your resume needs some improvements to be fully ATS-compatible.'
    elif overall_score >= 50:  return 'Below Average. Significant improvements needed for ATS compatibility.'
    else:                      return 'Poor. Your resume requires major revisions to pass ATS screening.'