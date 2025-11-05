# app_chat/matcher.py
from rapidfuzz import fuzz

def get_best_matches(question: str, keywords: list, html_text: str, top_k: int = 3):
    """
    Lightweight combined score across keyword similarity and a rough html-text partial match.
    Returns up to top_k matches: [{'keyword':..., 'similarity': float, 'answer': placeholder}, ...]
    (This is optional — app_chat uses RapidFuzz directly; keep this for custom scoring.)
    """
    scored = []
    for kw in keywords:
        kw_score = fuzz.token_set_ratio(question, kw) / 100.0
        sec_score = fuzz.partial_ratio(question, html_text or "") / 100.0
        combined = 0.65 * kw_score + 0.35 * sec_score
        scored.append({"keyword": kw, "similarity": round(combined, 4)})
    scored = sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_k]
    for s in scored:
        s["answer"] = f"Relevant section for '{s['keyword']}'"
    return scored
