"""
SWI Semantic Classifier (Phase 2C)
====================================

Embedding-based scorer using Wesley corpus centroid similarity.
- Wesley centroid (mean of all passage embeddings)
- Per-theme centroids (22 theme centers)
- Cosine similarity scoring
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np

CORPUS_ROOT = Path(__file__).resolve().parent.parent
CHUNKED_DIR = CORPUS_ROOT / "chunked"
METADATA_DIR = CORPUS_ROOT / "metadata"
EMBEDDINGS_FILE = CHUNKED_DIR / "embeddings.npz"
PASSAGES_FILE = CHUNKED_DIR / "passages.jsonl"
CENTROIDS_FILE = CHUNKED_DIR / "centroids.npz"

_model = None
_centroids = None


def _get_model():
    """Lazy-load sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_centroids() -> dict:
    """Load or compute centroids."""
    global _centroids
    if _centroids is not None:
        return _centroids

    if CENTROIDS_FILE.exists():
        data = np.load(CENTROIDS_FILE, allow_pickle=True)
        _centroids = {
            "wesley": data["wesley_centroid"],
            "themes": dict(zip(data["theme_ids"], data["theme_centroids"])),
        }
        return _centroids

    # Compute from scratch
    _centroids = compute_centroids()
    return _centroids


def compute_centroids() -> dict:
    """Compute Wesley centroid and per-theme centroids from embeddings."""
    if not EMBEDDINGS_FILE.exists():
        return {"wesley": None, "themes": {}}

    data = np.load(EMBEDDINGS_FILE, allow_pickle=True)
    embeddings = data["embeddings"]
    ids = list(data["ids"])

    # Build ID -> embedding map
    id_to_idx = {pid: i for i, pid in enumerate(ids)}

    # Wesley centroid = mean of all embeddings
    wesley_centroid = np.mean(embeddings, axis=0)
    wesley_centroid = wesley_centroid / (np.linalg.norm(wesley_centroid) or 1)

    # Load passages for theme info
    passages = {}
    with open(PASSAGES_FILE) as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                passages[p["id"]] = p

    # Per-theme centroids
    theme_embeddings = {}
    for pid, p in passages.items():
        if pid not in id_to_idx:
            continue
        idx = id_to_idx[pid]
        for theme in p.get("themes", []):
            if theme not in theme_embeddings:
                theme_embeddings[theme] = []
            theme_embeddings[theme].append(embeddings[idx])

    theme_centroids = {}
    for theme, embs in theme_embeddings.items():
        if embs:
            centroid = np.mean(embs, axis=0)
            centroid = centroid / (np.linalg.norm(centroid) or 1)
            theme_centroids[theme] = centroid

    # Save
    theme_ids = list(theme_centroids.keys())
    theme_arrays = np.array([theme_centroids[t] for t in theme_ids])

    np.savez_compressed(
        str(CENTROIDS_FILE),
        wesley_centroid=wesley_centroid,
        theme_ids=np.array(theme_ids, dtype=object),
        theme_centroids=theme_arrays,
    )

    result = {"wesley": wesley_centroid, "themes": theme_centroids}
    global _centroids
    _centroids = result
    return result


def encode_text(text: str) -> np.ndarray:
    """Encode a text into embedding space."""
    model = _get_model()
    vec = model.encode([text], convert_to_numpy=True)[0].astype(np.float32)
    return vec / (np.linalg.norm(vec) or 1)


def score_semantic(text: str) -> dict:
    """
    Score text semantically against Wesley corpus.

    Returns:
        {
            "overall_similarity": float 0-100,
            "theme_similarities": {theme_id: float, ...},
            "closest_themes": [(theme_id, score), ...],
        }
    """
    centroids = _load_centroids()

    if centroids["wesley"] is None:
        return {
            "overall_similarity": 0,
            "theme_similarities": {},
            "closest_themes": [],
            "available": False,
        }

    vec = encode_text(text)

    # Overall similarity to Wesley centroid
    overall_sim = float(np.dot(vec, centroids["wesley"]))
    # Convert cosine similarity [-1, 1] to score [0, 100]
    # Wesley's own text typically scores 0.3-0.7 cosine similarity
    # Scale: 0.0 -> 0, 0.5 -> 50, 0.7+ -> 85+
    overall_score = int(max(0, min(100, overall_sim * 150 - 5)))

    # Per-theme similarity
    theme_sims = {}
    for theme_id, centroid in centroids["themes"].items():
        sim = float(np.dot(vec, centroid))
        theme_sims[theme_id] = int(max(0, min(100, sim * 150 - 5)))

    # Top themes
    closest = sorted(theme_sims.items(), key=lambda x: -x[1])[:5]

    return {
        "overall_similarity": overall_score,
        "theme_similarities": theme_sims,
        "closest_themes": closest,
        "available": True,
    }
