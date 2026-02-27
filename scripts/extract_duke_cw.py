#!/usr/bin/env python3
"""
Extract text from Duke CW modernized PDFs and ingest into the Wesley Corpus.

Reads PDFs from raw/duke-cw-verse/modernized/, extracts text via PyMuPDF,
strips boilerplate, saves .txt files to raw/charles-wesley/duke-cw/,
then runs the ingestion pipeline (clean → chunk → tag → embed).

Usage:
    python scripts/extract_duke_cw.py              # Extract + ingest all
    python scripts/extract_duke_cw.py --extract     # Extract only (no ingest)
    python scripts/extract_duke_cw.py --dry-run     # Show what would be done
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)

CORPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORPUS_ROOT))

PDF_DIR = CORPUS_ROOT / "raw" / "duke-cw-verse" / "originals"
TXT_DIR = CORPUS_ROOT / "raw" / "charles-wesley" / "duke-cw"

# Duke boilerplate patterns to remove
DUKE_HEADER_RE = re.compile(
    r"^[\d\s]*This document was produced by the Duke Center.*?(?=\n[A-Z]|\nModernized|\n\[)",
    re.DOTALL | re.MULTILINE,
)
DUKE_FOOTER_RE = re.compile(r"^[\d\s]*This document was produced by the Duke Center.*$", re.MULTILINE)
MODERNIZED_LABEL_RE = re.compile(r"^Modernized text\s*$", re.MULTILINE)
# Page number artifacts from PDF extraction (standalone numbers at start of line)
PAGE_NUM_RE = re.compile(r"^\d{1,3}\s*$", re.MULTILINE)
# Repeated whitespace
MULTI_BLANK_RE = re.compile(r"\n{4,}")


# Year extraction from filename
YEAR_RE = re.compile(r"\((\d{4})\)")
# Also handle "for_1745", "for_the_Year_1756" etc.
YEAR_TITLE_RE = re.compile(r"(?:for_|Year_)(\d{4})")


def extract_year(filename):
    """Extract year from PDF filename."""
    m = YEAR_RE.search(filename)
    if m:
        return int(m.group(1))
    m = YEAR_TITLE_RE.search(filename)
    if m:
        return int(m.group(1))
    return None


def filename_to_slug(pdf_name):
    """Convert PDF filename to a clean slug for the .txt file."""
    # Remove extension
    stem = Path(pdf_name).stem
    # Remove leading number prefix like "01_"
    stem = re.sub(r"^\d+[a-z]?_", "", stem)
    # Remove _mod/_Mod suffix (also handles " Mod" with space)
    stem = re.sub(r"[\s_][Mm]od$", "", stem)
    # URL-decoded chars
    stem = stem.replace("%27", "'").replace("%20", "_")
    # Remove " (1)" duplicate markers
    stem = re.sub(r"\s*\(\d\)$", "", stem)
    # Convert underscores/spaces to hyphens, lowercase
    slug = stem.replace("_", "-").replace(" ", "-").replace("(", "").replace(")", "").replace("'", "").lower()
    # Collapse multiple hyphens
    slug = re.sub(r"-{2,}", "-", slug)
    # Remove trailing/leading hyphens
    slug = slug.strip("-")
    return slug


def filename_to_title(pdf_name):
    """Convert PDF filename to a human-readable title."""
    stem = Path(pdf_name).stem
    stem = re.sub(r"^\d+[a-z]?_", "", stem)
    stem = re.sub(r"_[Mm]od$", "", stem)
    stem = stem.replace("%27", "'").replace("%20", " ")
    stem = stem.replace("_", " ")
    # Clean up parenthetical years
    stem = re.sub(r"\( (\d{4})\)", r"(\1)", stem)
    return stem


def clean_duke_text(text):
    """Remove Duke-specific boilerplate from extracted PDF text."""
    # Remove the Duke production header (appears on first page)
    text = DUKE_HEADER_RE.sub("", text)
    # Remove any remaining Duke footer lines
    text = DUKE_FOOTER_RE.sub("", text)
    # Remove "Modernized text" label
    text = MODERNIZED_LABEL_RE.sub("", text)
    # Remove standalone page numbers
    text = PAGE_NUM_RE.sub("", text)
    # Collapse excessive blank lines
    text = MULTI_BLANK_RE.sub("\n\n\n", text)
    return text.strip()


def extract_pdf(pdf_path):
    """Extract all text from a PDF file."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def process_all(dry_run=False, extract_only=False):
    """Extract text from all original PDFs."""
    TXT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    # Exclude non-verse files
    pdfs = [p for p in pdfs if "Short" not in p.name and "Abbreviation" not in p.name
            and "Read_First" not in p.name]

    print(f"Found {len(pdfs)} PDFs to extract")

    extracted = []
    skipped = []

    for pdf_path in pdfs:
        slug = filename_to_slug(pdf_path.name)
        title = filename_to_title(pdf_path.name)
        year = extract_year(pdf_path.name)
        txt_path = TXT_DIR / f"{slug}.txt"

        if txt_path.exists():
            size = txt_path.stat().st_size
            if size > 100:  # Not empty
                skipped.append((slug, title, year, txt_path))
                continue

        if dry_run:
            print(f"  WOULD extract: {pdf_path.name} -> {slug}.txt (year={year})")
            extracted.append((slug, title, year, txt_path))
            continue

        # Extract
        raw_text = extract_pdf(pdf_path)
        cleaned = clean_duke_text(raw_text)

        if not cleaned.strip():
            print(f"  WARN: {pdf_path.name} produced empty text, skipping")
            continue

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        word_count = len(cleaned.split())
        print(f"  Extracted: {slug}.txt ({word_count:,} words, year={year})")
        extracted.append((slug, title, year, txt_path))

    print(f"\nExtracted: {len(extracted)}, Skipped (exist): {len(skipped)}")

    if extract_only or dry_run:
        if skipped:
            print(f"\nAlready extracted ({len(skipped)}):")
            for slug, title, year, path in skipped:
                print(f"  {slug} ({year})")
        return extracted + skipped

    return extracted + skipped


def ingest_all(files_info, skip_embed=False):
    """Ingest extracted .txt files into the corpus."""
    from process_corpus import clean_text, chunk_text, chunk_hymn, append_passages, load_passages
    from tag_passages import analyze_passage
    from scripts.ingest_batch import (
        get_existing_source_ids, log_ingestion,
        update_scripture_index, incremental_embed, update_progress,
    )

    existing_ids = get_existing_source_ids()
    total_added = 0
    ingested_count = 0

    for slug, title, year, txt_path in files_info:
        source_id = f"cw-duke-{slug}"

        if source_id in existing_ids:
            continue

        if not txt_path.exists():
            continue

        with open(txt_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        if not raw_text.strip():
            continue

        cleaned = clean_text(raw_text)
        word_count = len(cleaned.split())

        # Use chunk_hymn for single/short hymns, chunk_text for collections
        source_url = "https://divinity.duke.edu/initiatives/wesleyan-methodist/cswt-cw-published"

        if word_count < 1500:
            # Single hymn or very short piece
            passages = chunk_hymn(cleaned, source_id, title, year, source_url)
            stype = "hymn"
        else:
            # Hymn collection — chunk as prose for better search
            passages = chunk_text(cleaned, source_id, "charles-wesley", title, "hymn-collection", year, source_url)
            stype = "hymn-collection"

        if not passages:
            print(f"  SKIP (no passages): {slug}")
            continue

        # Tag themes
        for passage in passages:
            themes = analyze_passage(passage["text"])
            if themes:
                passage["themes"] = themes

        append_passages(passages)
        log_ingestion(txt_path, source_id, "charles-wesley", stype, title, year, len(passages), "ingested", "duke-cw-verse")
        total_added += len(passages)
        ingested_count += 1
        print(f"  Ingested: {title} ({year}) -> {len(passages)} passages [{stype}]")

    if total_added > 0:
        print(f"\nTotal: {ingested_count} sources, {total_added} new passages")
        print("Updating scripture index...")
        update_scripture_index()
        if not skip_embed:
            incremental_embed()
        update_progress()
    else:
        print("\nNo new passages to ingest (all already in corpus)")

    return total_added


def main():
    parser = argparse.ArgumentParser(description="Extract Duke CW PDFs and ingest into corpus")
    parser.add_argument("--extract", action="store_true", help="Extract text only, skip ingestion")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()

    print("=" * 60)
    print("Duke CW Published Verse -> Wesley Corpus")
    print("=" * 60)

    files_info = process_all(dry_run=args.dry_run, extract_only=args.extract)

    if not args.dry_run and not args.extract:
        print("\n--- Ingestion ---")
        ingest_all(files_info, skip_embed=args.skip_embed)

    print("\nDone.")


if __name__ == "__main__":
    main()
