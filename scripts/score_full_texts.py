#!/usr/bin/env python3
"""
Score Full (Unchunked) Texts with StrangelyWarmIndex
=====================================================

Reads cleaned text files as-is (no chunking), scores each with SWI,
and stores results in metadata/full-text-scores.json.

This complements the chunked passage data — full texts score higher
because they span multiple theological themes.

Usage:
    python scripts/score_full_texts.py                    # Score all cleaned files
    python scripts/score_full_texts.py --author john-wesley
    python scripts/score_full_texts.py --type sermon
    python scripts/score_full_texts.py --file cleaned/john-wesley/sermon-001-salvation-by-faith.txt
    python scripts/score_full_texts.py --report           # Print summary report
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORPUS_ROOT))

CLEANED_DIR = CORPUS_ROOT / "cleaned"
METADATA_DIR = CORPUS_ROOT / "metadata"
SCORES_FILE = METADATA_DIR / "full-text-scores.json"


def derive_metadata(filepath: Path) -> dict:
    """Derive source metadata from filepath."""
    stem = filepath.stem
    author = "charles-wesley" if "charles-wesley" in str(filepath) else "john-wesley"

    if stem.startswith("sermon-"):
        source_type = "sermon"
        # Extract number and title: sermon-001-salvation-by-faith
        m = re.match(r"sermon-(\d+)-(.*)", stem)
        if m:
            num = int(m.group(1))
            title = "Sermon {}: {}".format(num, m.group(2).replace("-", " ").title())
        else:
            title = stem.replace("-", " ").title()
    elif stem.startswith("journal-"):
        source_type = "journal"
        title = stem.replace("-", " ").title()
    elif stem.startswith("notes-on-"):
        source_type = "notes"
        title = stem.replace("-", " ").title()
    elif stem.startswith("letter"):
        source_type = "letter"
        title = stem.replace("-", " ").title()
    elif author == "charles-wesley":
        source_type = "hymn"
        title = stem.replace("-", " ").title()
    else:
        source_type = "treatise"
        title = stem.replace("-", " ").title()

    return {
        "file": str(filepath.relative_to(CORPUS_ROOT)),
        "stem": stem,
        "author": author,
        "source_type": source_type,
        "title": title,
    }


def score_file(filepath: Path, include_semantic: bool = True) -> dict:
    """Score a single full text file."""
    from strangely_warm_index.scoring import score_text

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.strip():
        return None

    meta = derive_metadata(filepath)
    word_count = len(text.split())

    result = score_text(text, include_semantic=include_semantic)

    return {
        **meta,
        "word_count": word_count,
        "overall_score": result["overall_score"],
        "label": result["label"],
        "dimensions": {
            dim_id: {"score": d["score"], "explanation": d["explanation"]}
            for dim_id, d in result["dimensions"].items()
        },
        "semantic_score": result.get("semantic", {}).get("overall_similarity", 0),
        "top_markers": [
            {"text": m["text"], "dimension": m.get("dimension", "")}
            for m in result.get("top_markers", [])[:10]
        ],
        "summary": result["summary"],
        "scored_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def load_existing_scores() -> dict:
    """Load existing scores file."""
    if SCORES_FILE.exists():
        with open(SCORES_FILE) as f:
            return json.load(f)
    return {"scores": [], "metadata": {}}


def save_scores(data: dict):
    """Save scores to JSON."""
    SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def collect_files(author: str = None, source_type: str = None,
                  single_file: str = None) -> list[Path]:
    """Collect files to score."""
    if single_file:
        p = CORPUS_ROOT / single_file if not Path(single_file).is_absolute() else Path(single_file)
        return [p] if p.exists() else []

    files = []
    for author_dir in sorted(CLEANED_DIR.iterdir()):
        if not author_dir.is_dir():
            continue
        if author and author_dir.name != author:
            continue
        for f in sorted(author_dir.glob("*.txt")):
            if source_type:
                meta = derive_metadata(f)
                if meta["source_type"] != source_type:
                    continue
            files.append(f)
    return files


def print_report():
    """Print summary report of full-text scores."""
    data = load_existing_scores()
    scores = data.get("scores", [])
    if not scores:
        print("No scores found. Run scoring first.")
        return

    print("\n" + "=" * 80)
    print("FULL-TEXT SWI SCORES")
    print("=" * 80)

    # Sort by score descending
    by_score = sorted(scores, key=lambda s: -s["overall_score"])

    # By type
    by_type = {}
    for s in scores:
        t = s["source_type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(s["overall_score"])

    print("\nBy Source Type:")
    for t, type_scores in sorted(by_type.items()):
        avg = sum(type_scores) // len(type_scores)
        print("  {:<12} n={:<4} avg={:<4} range={}-{}".format(
            t, len(type_scores), avg, min(type_scores), max(type_scores)))

    print("\nTop 15 Scores:")
    print("  {:>5} {:<22} {:<50}".format("Score", "Label", "Title"))
    print("  " + "-" * 77)
    for s in by_score[:15]:
        print("  {:>5} {:<22} {}".format(
            s["overall_score"], s["label"], s["title"][:48]))

    print("\nBottom 10 Scores:")
    for s in by_score[-10:]:
        print("  {:>5} {:<22} {}".format(
            s["overall_score"], s["label"], s["title"][:48]))

    overall_avg = sum(s["overall_score"] for s in scores) // len(scores)
    print("\nOverall: {} files, avg score = {}".format(len(scores), overall_avg))
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Score full cleaned texts with SWI")
    parser.add_argument("--author", choices=["john-wesley", "charles-wesley"])
    parser.add_argument("--type", dest="source_type",
                        help="Filter by type: sermon, treatise, hymn, journal, notes, letter")
    parser.add_argument("--file", dest="single_file", help="Score a single file")
    parser.add_argument("--report", action="store_true", help="Print score report")
    parser.add_argument("--no-semantic", action="store_true", help="Skip semantic scoring (faster)")
    parser.add_argument("--force", action="store_true", help="Re-score even if already scored")
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    files = collect_files(args.author, args.source_type, args.single_file)
    if not files:
        print("No files found.")
        return

    print("Scoring {} full text file(s)...".format(len(files)))

    data = load_existing_scores()
    existing_stems = {s["stem"] for s in data.get("scores", [])} if not args.force else set()

    scored = 0
    for filepath in files:
        stem = filepath.stem
        if stem in existing_stems:
            continue

        result = score_file(filepath, include_semantic=not args.no_semantic)
        if result is None:
            print("  SKIP (empty): {}".format(filepath.name))
            continue

        # Remove old entry if re-scoring
        data["scores"] = [s for s in data.get("scores", []) if s["stem"] != stem]
        data["scores"].append(result)
        scored += 1

        print("  {:>5} {:<22} {}".format(
            result["overall_score"], result["label"], result["title"][:50]))

    data["metadata"] = {
        "total_files": len(data["scores"]),
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_scores(data)
    print("\n{} files scored. Results saved to {}".format(scored, SCORES_FILE))


if __name__ == "__main__":
    main()
