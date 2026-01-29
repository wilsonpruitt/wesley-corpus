#!/usr/bin/env python3
"""
Build Wesleyan Lexicon (Phase 2A)
==================================

Extracts a distinctive Wesleyan vocabulary by comparing Wesley corpus
against general English (Brown corpus via NLTK or a built-in fallback).

Output: metadata/wesleyan-lexicon.json

Usage:
    python scripts/build_lexicon.py
    python scripts/build_lexicon.py --min-df 3 --top-n 200
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORPUS_ROOT))

from process_corpus import load_passages

METADATA_DIR = CORPUS_ROOT / "metadata"
LEXICON_OUTPUT = METADATA_DIR / "wesleyan-lexicon.json"


# ── Manual curation layer ────────────────────────────────────────────────
CURATED_PHRASES = {
    "grace-theology": [
        "strangely warmed", "prevenient grace", "preventing grace",
        "justifying grace", "sanctifying grace", "free grace",
        "grace upon grace", "grace of God", "grace that goes before",
        "pardoning love", "saving faith",
    ],
    "holiness": [
        "entire sanctification", "christian perfection", "perfect love",
        "going on to perfection", "holiness of heart and life",
        "holy living", "growth in grace", "means of grace",
        "works of piety", "works of mercy", "instituted means",
        "prudential means",
    ],
    "experiential-religion": [
        "heart strangely warmed", "religion of the heart",
        "heart religion", "experimental religion", "inward religion",
        "witness of the spirit", "direct witness", "inward witness",
        "assurance of faith", "felt his presence",
    ],
    "catholic-spirit": [
        "catholic spirit", "if thy heart is as my heart",
        "give me thy hand", "think and let think",
        "no solitary religion", "no solitary christian",
    ],
    "social-holiness": [
        "social holiness", "no holiness but social holiness",
        "do all the good you can", "gain all you can",
        "save all you can", "give all you can",
        "visiting the sick", "visiting the prisoner",
        "feeding the hungry", "clothing the naked",
    ],
    "wesleyan-distinctive": [
        "method of salvation", "way of salvation",
        "order of salvation", "almost christian",
        "altogether christian", "new birth",
        "the character of a methodist", "plain account",
        "class meeting", "band meeting", "love feast",
        "field preaching", "lay preaching",
    ],
    "scriptural": [
        "word of God", "searching the scriptures",
        "sola scriptura", "scripture alone",
        "analogy of faith",
    ],
    "rhetorical": [
        "I say", "but what saith", "what then",
        "let us", "brethren", "my dear brethren",
        "beloved", "take heed", "mark this",
    ],
}


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenization."""
    return re.findall(r"[a-z']+", text.lower())


def get_ngrams(tokens: list[str], n: int) -> list[str]:
    """Extract n-grams from token list."""
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def build_wesley_corpus_counts(passages: list[dict], max_n: int = 3) -> tuple[Counter, int]:
    """Count n-grams across all Wesley passages."""
    counts = Counter()
    doc_count = 0
    for p in passages:
        tokens = tokenize(p["text"])
        for n in range(1, max_n + 1):
            ngrams = get_ngrams(tokens, n)
            counts.update(ngrams)
        doc_count += 1
    return counts, doc_count


def build_reference_counts(max_n: int = 3) -> tuple[Counter, int]:
    """
    Build reference English counts.
    Try NLTK Brown corpus first; fall back to a simple high-frequency word list.
    """
    try:
        import nltk
        nltk.download("brown", quiet=True)
        from nltk.corpus import brown
        words = [w.lower() for w in brown.words()]
        counts = Counter()
        for n in range(1, max_n + 1):
            counts.update(get_ngrams(words, n))
        return counts, len(brown.fileids())
    except (ImportError, LookupError):
        pass

    # Fallback: top 5000 English words (frequency-based approximation)
    # We'll just use unigrams from a minimal built-in list
    common = [
        "the", "of", "and", "to", "a", "in", "is", "it", "that", "for",
        "was", "on", "are", "as", "with", "his", "they", "be", "at", "one",
        "have", "this", "from", "or", "had", "by", "not", "but", "what", "all",
        "were", "we", "when", "your", "can", "said", "there", "each", "which",
        "their", "will", "other", "about", "out", "many", "then", "them", "these",
        "so", "some", "her", "would", "make", "like", "him", "into", "time",
        "has", "look", "two", "more", "go", "see", "no", "way", "could", "my",
        "than", "been", "call", "who", "its", "now", "did", "get", "come", "made",
        "may", "after", "use", "work", "first", "well", "also", "new", "us",
        "any", "day", "give", "our", "over", "such", "take", "good", "year",
    ]
    counts = Counter({w: 1000 - i for i, w in enumerate(common)})
    return counts, 100


def compute_tfidf_distinctive(
    wesley_counts: Counter,
    ref_counts: Counter,
    wesley_docs: int,
    ref_docs: int,
    min_df: int = 3,
    top_n: int = 300,
) -> list[dict]:
    """
    Compute TF-IDF-like distinctiveness score.
    Higher = more distinctive to Wesley vs. general English.
    """
    # Normalize
    wesley_total = sum(wesley_counts.values()) or 1
    ref_total = sum(ref_counts.values()) or 1

    # Noise terms: abbreviations, Roman numerals, apparatus fragments
    noise = {
        "mr", "ver", "ii", "st", "vol", "comp", "iv", "iii", "fo", "th",
        "cor", "rom", "vi", "vii", "viii", "ix", "xi", "xii", "xiii", "xiv",
        "xv", "xvi", "chap", "sect", "ibid", "cf", "ed", "p", "pp", "no",
        "viz", "etc", "vs", "obs", "heb", "gal", "eph",
    }
    noise_patterns = re.compile(
        r"^(see notes|see note|comp |vol |chap |sect |part |journal mon|journal sun|journal tue|journal wed|journal thu|journal fri|journal sat|the th )|"
        r"^[ivxlcdm]+$|"       # pure Roman numerals
        r"^\d|"                 # starts with digit
        r"^[a-z]{1,2}$|"       # 1-2 letter words
        r"thefe|fuch|hght|ght$|thofe|"  # OCR long-s artifacts
        r"^'s$|^the th$"               # possessive fragment, truncated dates
    )

    scored = []
    for term, count in wesley_counts.items():
        if count < min_df:
            continue
        # Skip very short terms for multi-word
        if " " in term and len(term) < 5:
            continue
        # Skip noise
        if term in noise or noise_patterns.match(term):
            continue

        wesley_freq = count / wesley_total
        ref_freq = (ref_counts.get(term, 0) + 0.5) / ref_total  # Laplace smoothing

        # Log-ratio distinctiveness
        ratio = math.log2(wesley_freq / ref_freq)
        if ratio > 0:
            scored.append({
                "term": term,
                "count": count,
                "wesley_freq": round(wesley_freq, 8),
                "ref_freq": round(ref_freq, 8),
                "distinctiveness": round(ratio, 4),
            })

    scored.sort(key=lambda x: x["distinctiveness"], reverse=True)
    return scored[:top_n]


def load_theme_keywords() -> dict[str, list[str]]:
    """Load keywords from themes.csv."""
    themes = {}
    csv_path = METADATA_DIR / "themes.csv"
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                keywords = [k.strip() for k in row.get("keywords", "").split(",") if k.strip()]
                themes[row["theme_id"]] = keywords
    return themes


def map_terms_to_dimensions(distinctive: list[dict], theme_keywords: dict) -> dict:
    """Map distinctive terms to SWI dimensions."""
    dimension_map = {
        "grace-theology": ["prevenient-grace", "justifying-grace", "sanctifying-grace",
                           "christian-perfection", "free-will"],
        "scriptural-density": ["scriptural-authority"],
        "holiness-emphasis": ["sanctifying-grace", "christian-perfection",
                              "means-of-grace", "works-piety"],
        "experiential-religion": ["experience", "assurance", "pneumatology"],
        "catholic-spirit": ["catholic-spirit"],
        "social-holiness": ["social-holiness", "works-mercy"],
        "wesleyan-vocabulary": [],  # catch-all for distinctive terms
        "rhetorical-style": [],  # detected by pattern, not keyword
    }

    result = {dim: [] for dim in dimension_map}

    for item in distinctive:
        term = item["term"]
        placed = False
        for dim, theme_ids in dimension_map.items():
            for theme_id in theme_ids:
                kws = theme_keywords.get(theme_id, [])
                if any(kw in term or term in kw for kw in kws):
                    result[dim].append(item)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            result["wesleyan-vocabulary"].append(item)

    return result


def build_lexicon(min_df: int = 3, top_n: int = 300):
    """Main lexicon building pipeline."""
    print("Loading Wesley passages...")
    passages = load_passages()
    print(f"  {len(passages)} passages loaded")

    print("Building Wesley n-gram counts...")
    wesley_counts, wesley_docs = build_wesley_corpus_counts(passages)
    print(f"  {len(wesley_counts)} unique n-grams")

    print("Building reference English counts...")
    ref_counts, ref_docs = build_reference_counts()
    print(f"  {len(ref_counts)} reference n-grams")

    print("Computing distinctiveness scores...")
    distinctive = compute_tfidf_distinctive(
        wesley_counts, ref_counts, wesley_docs, ref_docs,
        min_df=min_df, top_n=top_n
    )
    print(f"  {len(distinctive)} distinctive terms found")

    print("Loading theme keywords...")
    theme_keywords = load_theme_keywords()

    print("Mapping to SWI dimensions...")
    by_dimension = map_terms_to_dimensions(distinctive, theme_keywords)

    # Build final lexicon
    lexicon = {
        "metadata": {
            "passage_count": len(passages),
            "built_at": __import__("datetime").datetime.now().isoformat(),
            "min_df": min_df,
            "top_n": top_n,
        },
        "curated_phrases": CURATED_PHRASES,
        "distinctive_terms": {
            dim: terms[:50] for dim, terms in by_dimension.items()
        },
        "top_distinctive": distinctive[:100],
    }

    LEXICON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(LEXICON_OUTPUT, "w") as f:
        json.dump(lexicon, f, indent=2)

    print(f"\nLexicon saved to {LEXICON_OUTPUT}")
    print(f"  Curated phrase groups: {len(CURATED_PHRASES)}")
    print(f"  Distinctive terms by dimension:")
    for dim, terms in by_dimension.items():
        print(f"    {dim}: {len(terms)}")

    return lexicon


def main():
    parser = argparse.ArgumentParser(description="Build Wesleyan Lexicon")
    parser.add_argument("--min-df", type=int, default=3, help="Minimum document frequency")
    parser.add_argument("--top-n", type=int, default=300, help="Top N distinctive terms")
    args = parser.parse_args()
    build_lexicon(min_df=args.min_df, top_n=args.top_n)


if __name__ == "__main__":
    main()
