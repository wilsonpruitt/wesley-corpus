"""
SWI Composite Scoring Engine (Phase 2D)
=========================================

Combines 8 dimension scores + semantic score into an overall 0-100 score
with narrative summary and collected markers.
"""

import csv
from pathlib import Path

from .dimensions import score_all_dimensions
from .classifier import score_semantic

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
    "rhetorical_style": 0.5,
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


def _generate_summary(overall: int, dimensions: dict, semantic: dict) -> str:
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

    # Semantic
    if semantic.get("available") and semantic.get("closest_themes"):
        top_theme = semantic["closest_themes"][0]
        parts.append(f"Semantically closest to the '{top_theme[0]}' theme.")

    return " ".join(parts)


def score_text(text: str, include_semantic: bool = True) -> dict:
    """
    Full SWI scoring of a text.

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
    LANGUAGE_DIMS = {"wesleyan_vocabulary", "rhetorical_style"}

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

    # Blend: 50% theology, 20% scripture, 15% language, 15% semantic
    blended = int(
        theology_score * 0.50
        + scripture_avg * 0.20
        + language_avg * 0.15
        + sem_score * 0.15
    )

    # Semantic floor: if text semantically resembles Wesley (embedding match),
    # set a minimum score — many Wesley passages discuss topics (sin, judgment,
    # worldliness) that don't trigger specific theology keywords.
    # Floor = 40% of semantic score (e.g. sem=76 -> floor=30)
    sem_floor = int(sem_score * 0.40) if sem_score > 0 else 0
    overall = max(blended, sem_floor)
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

    summary = _generate_summary(overall, dimensions, semantic)

    return {
        "overall_score": overall,
        "label": _get_label(overall),
        "dimensions": dimensions,
        "semantic": semantic,
        "top_markers": top_markers,
        "summary": summary,
        "word_count": word_count,
    }


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
