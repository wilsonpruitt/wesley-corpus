#!/usr/bin/env python3
"""
Batch Ingestion Pipeline for Wesley Corpus
===========================================

Automates: clean -> chunk -> tag -> extract scripture -> embed (incremental)
for new raw text files.

Usage:
    python scripts/ingest_batch.py <file_or_dir> [options]
    python scripts/ingest_batch.py raw/john-wesley/sermon-094-*.txt --author john-wesley --type sermon
    python scripts/ingest_batch.py raw/john-wesley/journal-vol1-*.txt --author john-wesley --type journal
    python scripts/ingest_batch.py --status          # Show ingestion status
    python scripts/ingest_batch.py --reembed         # Regenerate embeddings for all passages
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from glob import glob
from pathlib import Path

# Add parent directory to path so we can import corpus modules
CORPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORPUS_ROOT))

from process_corpus import clean_text, chunk_text, chunk_hymn, append_passages, load_passages, PASSAGES_FILE, CLEANED_DIR, CHUNKED_DIR, METADATA_DIR
from tag_passages import analyze_passage
from extract_scripture_references import extract_scripture_references, process_corpus as extract_all_scripture

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
INGESTION_LOG = METADATA_DIR / "ingestion-log.csv"
EMBEDDINGS_FILE = CHUNKED_DIR / "embeddings.npz"
EMBEDDINGS_META = CHUNKED_DIR / "embeddings_metadata.json"


def ensure_log():
    """Create ingestion log CSV if it doesn't exist."""
    if not INGESTION_LOG.exists():
        INGESTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(INGESTION_LOG, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "raw_file", "source_id", "author", "source_type",
                "title", "year", "passages_added", "status", "notes"
            ])


def log_ingestion(raw_file, source_id, author, source_type, title, year, passages_added, status, notes=""):
    """Append a row to the ingestion log."""
    ensure_log()
    with open(INGESTION_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(), str(raw_file), source_id, author,
            source_type, title, year, passages_added, status, notes
        ])


def get_existing_source_ids():
    """Return set of source_ids already in passages.jsonl."""
    passages = load_passages()
    return {p["source_id"] for p in passages}


def derive_metadata(filepath: Path, author: str = None, source_type: str = None,
                    title: str = None, year: int = None):
    """Derive source metadata from filename if not explicitly provided."""
    stem = filepath.stem  # e.g., sermon-094-the-more-excellent-way

    # Auto-detect author from path
    if not author:
        if "charles-wesley" in str(filepath):
            author = "charles-wesley"
        else:
            author = "john-wesley"

    # Auto-detect type from filename patterns
    if not source_type:
        if stem.startswith("sermon-"):
            source_type = "sermon"
        elif stem.startswith("journal-"):
            source_type = "journal"
        elif stem.startswith("notes-on-"):
            source_type = "notes"
        elif stem.startswith("letter-") or stem.startswith("letters-"):
            source_type = "letter"
        elif author == "charles-wesley":
            source_type = "hymn"
        else:
            source_type = "treatise"

    # Derive source_id
    prefix = "jw" if author == "john-wesley" else "cw"
    source_id = f"{prefix}-{stem}"

    # Derive title from filename
    if not title:
        # Remove leading number patterns like "sermon-094-"
        name_part = re.sub(r"^(sermon|journal|notes-on|letter)-\d+-?", "", stem)
        if not name_part:
            name_part = stem
        title = name_part.replace("-", " ").title()

    # Try to extract year from journal filenames
    if not year and source_type == "journal":
        # journal-vol4-part01-section01 -> no year in name, leave None
        pass

    return source_id, author, source_type, title, year


def ingest_file(filepath: Path, author: str = None, source_type: str = None,
                title: str = None, year: int = None, url: str = None,
                force: bool = False, skip_embed: bool = False):
    """
    Full pipeline for a single file:
    1. clean_text() -> cleaned/
    2. chunk_text() -> append to passages.jsonl
    3. tag_passages() on new passages
    4. extract_scripture_references() on new passages
    5. Optionally update embeddings incrementally
    6. Log to ingestion-log.csv
    """
    filepath = Path(filepath).resolve()
    if not filepath.exists():
        print(f"  SKIP: {filepath} does not exist")
        return 0

    source_id, author, source_type, title, year = derive_metadata(
        filepath, author, source_type, title, year
    )

    # Check if already ingested
    existing = get_existing_source_ids()
    if source_id in existing and not force:
        print(f"  SKIP: {source_id} already in corpus (use --force to re-ingest)")
        return 0

    print(f"  Ingesting: {filepath.name} -> {source_id}")

    # Step 1: Clean
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    if not raw_text.strip():
        print(f"  SKIP: {filepath.name} is empty")
        log_ingestion(filepath, source_id, author, source_type, title, year, 0, "skipped", "empty file")
        return 0

    cleaned = clean_text(raw_text)

    # Save cleaned version
    cleaned_dir = CLEANED_DIR / author
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    cleaned_path = cleaned_dir / filepath.name
    with open(cleaned_path, "w", encoding="utf-8") as f:
        f.write(cleaned)

    # Step 2: Chunk
    is_hymn = source_type in ("hymn", "hymn-collection")
    if is_hymn:
        new_passages = chunk_hymn(cleaned, source_id, title, year, url)
    else:
        new_passages = chunk_text(cleaned, source_id, author, title, source_type, year, url)

    if not new_passages:
        print(f"  SKIP: {filepath.name} produced no passages")
        log_ingestion(filepath, source_id, author, source_type, title, year, 0, "skipped", "no passages")
        return 0

    # Step 3: Tag themes
    for passage in new_passages:
        themes = analyze_passage(passage["text"])
        if themes:
            passage["themes"] = themes

    # Step 4: Append to passages.jsonl
    append_passages(new_passages)

    # Step 5: Log
    log_ingestion(filepath, source_id, author, source_type, title, year,
                  len(new_passages), "ingested")

    print(f"  Added {len(new_passages)} passages from {title}")
    return len(new_passages)


def update_scripture_index():
    """Re-extract scripture references and rebuild the index from all passages."""
    print("Updating scripture references and index...")
    corpus_path = str(PASSAGES_FILE)
    csv_path = str(METADATA_DIR / "scripture-references.csv")
    json_path = str(METADATA_DIR / "scripture-index.json")

    from extract_scripture_references import process_corpus, save_csv, save_json_index
    references, index = process_corpus(corpus_path)
    save_csv(references, csv_path)
    save_json_index(index, json_path)
    print(f"  {len(references)} scripture references indexed")


def incremental_embed():
    """Generate embeddings only for passages that don't have them yet."""
    import numpy as np

    passages = load_passages()
    all_ids = [p["id"] for p in passages]
    all_texts = [p["text"] for p in passages]

    # Load existing embeddings
    existing_ids = set()
    existing_embeddings = None
    existing_id_list = []

    if EMBEDDINGS_FILE.exists():
        data = np.load(EMBEDDINGS_FILE, allow_pickle=True)
        existing_embeddings = data["embeddings"]
        existing_id_list = list(data["ids"])
        existing_ids = set(existing_id_list)

    # Find new passages
    new_indices = [i for i, pid in enumerate(all_ids) if pid not in existing_ids]

    if not new_indices:
        print("  All passages already have embeddings")
        return

    print(f"  Generating embeddings for {len(new_indices)} new passages...")

    new_texts = [all_texts[i] for i in new_indices]
    new_ids = [all_ids[i] for i in new_indices]

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        new_embeddings = model.encode(new_texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True)
    except ImportError:
        print("  WARNING: sentence-transformers not installed, skipping embeddings")
        return

    # Concatenate
    if existing_embeddings is not None and len(existing_embeddings) > 0:
        combined_embeddings = np.vstack([existing_embeddings, new_embeddings])
        combined_ids = existing_id_list + new_ids
    else:
        combined_embeddings = new_embeddings
        combined_ids = new_ids

    # Save
    np.savez_compressed(
        str(EMBEDDINGS_FILE),
        embeddings=combined_embeddings,
        ids=np.array(combined_ids, dtype=object),
    )

    # Update metadata
    meta = {
        "backend": "local",
        "passage_count": len(combined_ids),
        "embedding_dimension": combined_embeddings.shape[1],
        "model": "all-MiniLM-L6-v2",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(EMBEDDINGS_META, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Embeddings updated: {len(combined_ids)} total ({len(new_ids)} new)")


def show_status():
    """Show current ingestion status."""
    passages = load_passages()
    by_type = {}
    by_author = {}
    sources = set()
    for p in passages:
        t = p.get("source_type", "unknown")
        a = p.get("author", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        by_author[a] = by_author.get(a, 0) + 1
        sources.add(p.get("source_id", ""))

    print("\n" + "=" * 50)
    print("INGESTION STATUS")
    print("=" * 50)
    print(f"Total passages: {len(passages):,}")
    print(f"Unique sources: {len(sources)}")
    print(f"\nBy type:")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print(f"\nBy author:")
    for a, c in sorted(by_author.items(), key=lambda x: -x[1]):
        print(f"  {a}: {c}")

    # Check embeddings
    if EMBEDDINGS_FILE.exists():
        import numpy as np
        data = np.load(EMBEDDINGS_FILE, allow_pickle=True)
        embed_count = len(data["ids"])
        print(f"\nEmbeddings: {embed_count} / {len(passages)}")
    else:
        print(f"\nEmbeddings: none generated")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Batch ingestion pipeline for Wesley Corpus")
    parser.add_argument("files", nargs="*", help="Raw text files or glob patterns to ingest")
    parser.add_argument("--author", choices=["john-wesley", "charles-wesley"],
                        help="Author (auto-detected from path if omitted)")
    parser.add_argument("--type", dest="source_type",
                        help="Source type: sermon, treatise, hymn, journal, letter, notes")
    parser.add_argument("--title", help="Override source title")
    parser.add_argument("--year", type=int, help="Year of composition")
    parser.add_argument("--url", help="Source URL")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if source_id exists")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument("--skip-scripture", action="store_true", help="Skip scripture index update")
    parser.add_argument("--status", action="store_true", help="Show ingestion status")
    parser.add_argument("--reembed", action="store_true", help="Regenerate all embeddings")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.reembed:
        print("Regenerating all embeddings...")
        # Delete existing to force full regeneration
        if EMBEDDINGS_FILE.exists():
            EMBEDDINGS_FILE.unlink()
        incremental_embed()
        return

    if not args.files:
        parser.print_help()
        return

    # Expand globs
    all_files = []
    for pattern in args.files:
        expanded = sorted(glob(pattern))
        if expanded:
            all_files.extend(expanded)
        else:
            all_files.append(pattern)

    total_added = 0
    for filepath in all_files:
        count = ingest_file(
            Path(filepath),
            author=args.author,
            source_type=args.source_type,
            title=args.title,
            year=args.year,
            url=args.url,
            force=args.force,
            skip_embed=args.skip_embed,
        )
        total_added += count

    if total_added > 0:
        print(f"\nTotal new passages: {total_added}")

        if not args.skip_scripture:
            update_scripture_index()

        if not args.skip_embed:
            incremental_embed()

        # Update progress.json
        update_progress()

    print("\nDone.")


def update_progress():
    """Update metadata/progress.json with current corpus state."""
    passages = load_passages()
    by_type = {}
    sources_by_type = {}
    for p in passages:
        t = p.get("source_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        if t not in sources_by_type:
            sources_by_type[t] = set()
        sources_by_type[t].add(p.get("source_id", ""))

    sermon_sources = len(sources_by_type.get("sermon", set()))
    journal_sources = len(sources_by_type.get("journal", set()))
    hymn_sources = len(sources_by_type.get("hymn", set())) + len(sources_by_type.get("hymn-collection", set())) + len(sources_by_type.get("hymn-stanza", set()))
    letter_sources = len(sources_by_type.get("letter", set()))
    treatise_sources = len(sources_by_type.get("treatise", set()))

    progress = {
        "corpus": {
            "sermons": {"have": sermon_sources, "target": 141},
            "journal_volumes": {"have": journal_sources / 7 if journal_sources else 0, "target": 4},
            "ot_notes": {"have": 0, "target": 1},
            "letters": {"have": letter_sources, "target": 2000},
            "hymns": {"have": hymn_sources, "target": 5500},
            "treatises": {"have": treatise_sources, "target": 80},
        },
        "swi": {
            "lexicon_built": (METADATA_DIR / "wesleyan-lexicon.json").exists(),
            "dimensions_implemented": 0,
            "api_live": False,
            "ui_live": False,
            "calibrated": False,
        },
        "total_passages": len(passages),
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
    }

    progress_path = METADATA_DIR / "progress.json"
    with open(progress_path, "w") as f:
        json.dump(progress, f, indent=2)
    print(f"  Progress updated: {progress_path}")


if __name__ == "__main__":
    main()
