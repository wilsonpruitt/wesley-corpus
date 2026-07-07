"""
SWI Composite Scoring Engine

v2 (Phase 2b, plans/2026-07-07-swi-v2-ocr-cleanup-verification.md): score_text
is now a dispatcher. If ANTHROPIC_API_KEY is set and the daily judge-call cap
isn't exhausted, it scores via the LLM judge (judge.py), cached on
sha256(text+rubric_version) so repeat requests are free. Otherwise -- no key,
API error, or cap hit -- it falls back to the original v1 lexicon scorer
below, flagged "engine": "lexicon-fallback" so the UI can say so.

The v1 lexicon engine (Phase 2D) combines 7 dimension scores + semantic score
into an overall 0-100 score with narrative summary and collected markers.
Kept as the fallback path, not deleted -- see plan's open decision on
lexicon-as-fallback-only.
"""

import csv
from pathlib import Path

from .dimensions import score_all_dimensions, detect_calvinist_markers
from .classifier import score_semantic
from . import cache as swi_cache
from . import judge as swi_judge
from . import rubric as swi_rubric

CORPUS_ROOT = Path(__file__).resolve().parent.parent
THEMES_CSV = CORPUS_ROOT / "metadata" / "themes.csv"

# Default dimension weights (tuned during calibration Phase 2G)
# Tier 1: Scriptural theology (what Wesley taught)
# Tier 2: Scriptural density (how he grounded it)
# Tier 3: Language (how he sounded)
DEFAULT_WEIGHTS = {
    # Tier 1 — Theology
    "grace_theology": 2.0,
    "holiness_emphasis": 2.0,
    "experiential_religion": 1.8,
    "catholic_spirit": 1.5,
    "social_holiness": 1.8,
    # Tier 2 — Scripture
    "scriptural_density": 1.5,
    # Tier 3 — Language
    "wesleyan_vocabulary": 0.8,
    "semantic": 0.8,
}

SCORE_LABELS = [
    (0, "Not Wesleyan"),
    (10, "Barely Wesleyan"),
    (25, "Mildly Wesleyan"),
    (40, "Moderately Wesleyan"),
    (55, "Notably Wesleyan"),
    (65, "Strongly Wesleyan"),
    (75, "Deeply Wesleyan"),
    (82, "Strangely Warmed"),
]


def _get_label(score: int) -> str:
    label = SCORE_LABELS[0][1]
    for threshold, name in SCORE_LABELS:
        if score >= threshold:
            label = name
    return label


def _generate_summary(overall: int, dimensions: dict, semantic: dict,
                      calvinist: dict = None) -> str:
    """Generate a 2-4 sentence narrative summary."""
    label = _get_label(overall)
    parts = [f"This text scores {overall}/100 ({label})."]

    # Find strongest dimensions
    scored_dims = [(d["name"], d["score"]) for d in dimensions.values()]
    scored_dims.sort(key=lambda x: -x[1])
    strong = [(name, s) for name, s in scored_dims if s >= 50]
    weak = [(name, s) for name, s in scored_dims if s < 20]

    if strong:
        names = ", ".join(n for n, _ in strong[:3])
        parts.append(f"It shows strongest affinity in {names}.")

    if weak and len(weak) < len(scored_dims):
        if len(strong) > 0:
            missing = [n for n, _ in weak[:2]]
            parts.append(f"It lacks emphasis on {', '.join(missing)}.")

    # Calvinist penalty
    if calvinist and calvinist.get("penalty_applied", calvinist.get("penalty", 0)) > 0:
        applied = calvinist.get("penalty_applied", calvinist.get("penalty", 0))
        parts.append("Score reduced by {} points for Calvinist theological markers ({} found).".format(
            applied, calvinist["count"]))

    # Semantic
    if semantic.get("available") and semantic.get("closest_themes"):
        top_theme = semantic["closest_themes"][0]
        parts.append("Semantically closest to the '{}' theme.".format(top_theme[0]))

    return " ".join(parts)


def score_text(text: str, include_semantic: bool = True) -> dict:
    """Score `text` for Wesleyan affinity. Tries the LLM judge first (cached,
    capped); falls back to the v1 lexicon engine on any failure or when the
    judge path is unavailable. `include_semantic` only affects the lexicon
    fallback -- the judge doesn't use the embedding-similarity signal."""
    import os

    cached = swi_cache.get_cached(text, swi_rubric.RUBRIC_VERSION)
    if cached is not None:
        return cached

    if os.environ.get("ANTHROPIC_API_KEY") and swi_cache.under_daily_cap():
        try:
            swi_cache.record_judge_call()
            raw = swi_judge.score_with_judge(text)
            result = swi_judge.to_v1_shape(raw, text)
            swi_cache.set_cached(text, swi_rubric.RUBRIC_VERSION, result)
            return result
        except Exception:
            pass  # fall through to lexicon fallback below

    return _score_text_lexicon(text, include_semantic=include_semantic)


def _score_text_lexicon(text: str, include_semantic: bool = True) -> dict:
    """
    v1 lexicon-based SWI scoring (fallback engine).

    Returns:
        {
            "overall_score": int 0-100,
            "label": str,
            "dimensions": {dim_id: {name, score, markers, explanation}, ...},
            "semantic": {overall_similarity, theme_similarities, closest_themes},
            "top_markers": [...],
            "summary": str,
            "word_count": int,
        }
    """
    word_count = len(text.split())

    # Score all 8 dimensions
    dimensions = score_all_dimensions(text)

    # Semantic score
    semantic = {}
    if include_semantic:
        try:
            semantic = score_semantic(text)
        except Exception:
            semantic = {"overall_similarity": 0, "available": False}

    # Compute weighted overall score
    # Priority: theology first, scripture second, language third
    THEOLOGY_DIMS = {"grace_theology", "holiness_emphasis", "experiential_religion",
                     "catholic_spirit", "social_holiness"}
    SCRIPTURE_DIMS = {"scriptural_density"}
    LANGUAGE_DIMS = {"wesleyan_vocabulary"}

    theology_scores = [dimensions[d]["score"] for d in THEOLOGY_DIMS if d in dimensions]
    scripture_scores = [dimensions[d]["score"] for d in SCRIPTURE_DIMS if d in dimensions]
    language_scores = [dimensions[d]["score"] for d in LANGUAGE_DIMS if d in dimensions]

    # Theology: max single dimension (passages are topically focused, not encyclopedic)
    # plus a breadth bonus for hitting multiple themes
    theology_sorted = sorted(theology_scores, reverse=True)
    theology_max = theology_sorted[0] if theology_sorted else 0
    theology_breadth = sum(1 for s in theology_scores if s >= 15)
    breadth_bonus = min(theology_breadth * 5, 20)  # up to +20 for hitting 4+ themes
    theology_score = min(100, theology_max + breadth_bonus)

    scripture_avg = sum(scripture_scores) / len(scripture_scores) if scripture_scores else 0
    language_avg = sum(language_scores) / len(language_scores) if language_scores else 0

    sem_score = 0
    if include_semantic and semantic.get("available"):
        sem_score = semantic["overall_similarity"]

    # Blend: 60% theology, 20% scripture, 20% language
    # (Semantic embeddings intentionally dropped — skewed results too much)
    blended = int(
        theology_score * 0.60
        + scripture_avg * 0.20
        + language_avg * 0.20
    )

    overall = blended

    # Calvinist penalty: distinctly Reformed/Calvinist theology is anti-Wesleyan.
    # Wesley explicitly argued against predestination, limited atonement, etc.
    # However, Wesley himself discusses these terms when refuting them —
    # if the text also scores highly on Wesleyan theology, cap the penalty.
    calvinist = detect_calvinist_markers(text)
    cal_penalty = calvinist["penalty"]
    if theology_score >= 60:
        # Strong Wesleyan theology present — likely a refutation, not advocacy
        cal_penalty = min(cal_penalty, 5)
    elif theology_score >= 40:
        cal_penalty = min(cal_penalty, 10)
    overall = overall - cal_penalty
    calvinist["penalty_applied"] = cal_penalty
    overall = max(0, min(100, overall))

    # Collect top markers across all dimensions
    all_markers = []
    for dim_data in dimensions.values():
        for marker in dim_data.get("markers", []):
            marker["dimension"] = dim_data["name"]
            all_markers.append(marker)
    # Deduplicate by text
    seen = set()
    top_markers = []
    for m in all_markers:
        key = m["text"].lower()
        if key not in seen:
            seen.add(key)
            top_markers.append(m)
    top_markers = top_markers[:20]

    summary = _generate_summary(overall, dimensions, semantic, calvinist)

    # Short text advisory
    min_words = 200
    word_count_advisory = None
    if word_count < min_words:
        word_count_advisory = (
            f"This text is only {word_count} words. "
            f"For accurate scoring, we recommend at least {min_words} words. "
            "Short excerpts often lack enough theological vocabulary to score well, "
            "even when the content is deeply Wesleyan."
        )

    result = {
        "overall_score": overall,
        "label": _get_label(overall),
        "dimensions": dimensions,
        "semantic": semantic,
        "calvinist_penalty": calvinist,
        "top_markers": top_markers,
        "summary": summary,
        "word_count": word_count,
        "engine": "lexicon-fallback",
    }
    if word_count_advisory:
        result["word_count_advisory"] = word_count_advisory
    return result


def compare_texts(texts: list[dict]) -> dict:
    """
    Score and compare multiple texts.

    Args:
        texts: [{"label": "Text A", "text": "..."}, ...]

    Returns:
        {"results": [{label, overall_score, dimensions, ...}, ...]}
    """
    results = []
    for item in texts:
        result = score_text(item["text"])
        result["label_name"] = item.get("label", f"Text {len(results) + 1}")
        results.append(result)
    return {"results": results}
