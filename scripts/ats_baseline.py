"""ATS baseline scorer for comparison — Member 4: feat/evaluation

score = keyword_match + years_experience + college_score
"""


def compute_ats_score(
    resume_text: str,
    jd_keywords: list[str],
    years_experience: float,
    college_score: float,
) -> float:
    text_lower = resume_text.lower()
    keyword_hits = sum(1 for kw in jd_keywords if kw.lower() in text_lower)
    keyword_match = (keyword_hits / max(len(jd_keywords), 1)) * 100
    return keyword_match + years_experience * 5 + college_score
