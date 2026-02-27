#!/usr/bin/env python3
"""
Extract Charles Wesley's Sermons from the 1816 PDF (Google Books scan).

Source: https://wesleyscholar.com/wp-content/uploads/2018/09/Sermons-1816.pdf

Splits PDF into individual sermons + the introductory memoir,
saves as .txt files in raw/charles-wesley/, then ingests into the corpus.
"""

import os
import re
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF not installed")
    sys.exit(1)

CORPUS_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = CORPUS_ROOT / "raw" / "charles-wesley" / "cw-sermons-1816.pdf"
OUT_DIR = CORPUS_ROOT / "raw" / "charles-wesley"

# Sermon metadata: (roman, title_slug, scripture, author, year_approx)
# Year is approximate — most CW sermons date to 1730s-1740s
SERMONS = [
    ("I", "he-that-winneth-souls", "Proverbs 11:30", "charles-wesley", 1742),
    ("II", "angels-charge-over-thee", "Psalm 91:11", "charles-wesley", 1742),
    ("III", "faithful-in-least", "Luke 16:10", "charles-wesley", 1742),
    ("IV", "exceed-righteousness-of-scribes", "Matthew 5:20", "charles-wesley", 1742),
    ("V", "one-thing-is-needful", "Luke 10:42", "charles-wesley", 1742),
    ("VI", "thou-knowest-not-now", "John 13:7", "charles-wesley", 1742),
    ("VII", "bearing-precious-seed", "Psalm 126:6", "charles-wesley", 1742),
    ("VIII", "single-eye", "Matthew 6:22-23", "charles-wesley", 1742),
    ("IX", "love-the-lord-thy-god", "Mark 12:30", "charles-wesley", 1742),
    ("X", "remember-the-sabbath", "Exodus 20:8", "charles-wesley", 1742),
    ("XI", "press-toward-the-mark", "Philippians 3:13-14", "charles-wesley", 1742),
    ("XII", "how-long-halt-ye", "1 Kings 18:21", "charles-wesley", 1742),
    ("XIII", "wicked-cease-from-troubling", "Job 3:17", "john-wesley", None),
]

# Roman numeral to regex pattern — handles OCR variants
ROMAN_PATTERN = {
    "I": r"I\b",
    "II": r"II[.,\s]|H[.,\s]|IJ[.,\s]",
    "III": r"III[.,;\s]|HI[.,;\s]|lit[.,;\s]|Xllt",
    "IV": r"IV[.,\s]",
    "V": r"V[.,;\s]",
    "VI": r"VI[.,;\s]",
    "VII": r"VII[.,;\s]",
    "VIII": r"VIII[.,;\s]",
    "IX": r"IX[.,;\s]",
    "X": r"X[.,;\s»d](?!I)",  # X but not XI, XII, XIII
    "XI": r"XI[.,;\s»](?!I)",  # XI but not XII, XIII
    "XII": r"XII[.,;'\s*](?!I)",  # XII but not XIII
    "XIII": r"XIII[.,;\s]|XHf[.,;\s]|XIH[.,;\s]",
}


def find_sermon_boundaries(doc):
    """Find the PDF page index where each sermon starts."""
    boundaries = []

    # Sermon I starts at PDF page 38 (index 37)
    # Look for "SERMON I." pattern at start of sermon text (not running headers)
    for i in range(37, len(doc)):
        text = doc[i].get_text()
        # Look for the actual sermon start — has the scripture text after it
        # First sermon has "(Preached before the University of Oxford.)"
        if i == 37:
            boundaries.append(("I", 37))
            continue

        # For subsequent sermons, look for "SERMON {N}." followed by scripture
        for roman, slug, scripture, author, year in SERMONS[1:]:
            # Check if this page has a sermon start (not just a running header)
            # A sermon start has the SERMON number followed by scripture text
            lines = text.split("\n")
            for j, line in enumerate(lines):
                stripped = line.strip()
                if stripped == f"SERMON {roman}." or stripped == f"SERMON\n{roman}.":
                    # Check if next few lines have scripture (not just body text)
                    remaining = "\n".join(lines[j:j+10])
                    if scripture.split()[0].lower() in remaining.lower() or j < 3:
                        if not boundaries or boundaries[-1][0] != roman:
                            boundaries.append((roman, i))

    return boundaries


def extract_sermons(doc):
    """Extract text for each sermon based on page boundaries."""
    # Manual page boundaries based on TOC and structure
    # TOC says: I=1, II=22, III=41, IV=68, V=81, VI=95, VII=111,
    #           VIII=125, IX=136, X=165, XI=186, XII=207, XIII=227
    # PDF offset: +37 (TOC page 1 = PDF page 38 = index 37)
    # But page numbers in TOC are original book pages, need to find actual PDF pages

    # Extract all text and find boundaries by looking for sermon headers
    # that appear at the TOP of a section (not running headers)
    full_text = ""
    page_texts = []
    for i in range(37, len(doc)):  # Start after intro/TOC
        text = doc[i].get_text()
        page_texts.append((i, text))
        full_text += text + "\n\n"

    # Split by "SERMON\n{ROMAN}.\n" pattern (the actual title, not running header)
    # The actual sermon starts have a distinctive pattern:
    # SERMON\n{ROMAN}.\n(optional preaching note)\nScripture text\n
    sermons_text = {}

    # Collect pages for each sermon using TOC page numbers + offset
    # The TOC original pages -> roughly map to PDF pages
    # Let's use a simpler approach: extract all text, split by sermon boundaries

    # Build the complete text with page markers
    all_text = ""
    for i in range(37, len(doc)):
        page_text = doc[i].get_text()
        # Remove running headers (lines that are just "SERMON X." at top)
        lines = page_text.split("\n")
        cleaned_lines = []
        for j, line in enumerate(lines):
            stripped = line.strip()
            # Skip running headers (SERMON + roman numeral at page top)
            if j < 2 and re.match(r'^SERMON\s*(I{1,3}|IV|V|VI{0,3}|IX|X{1,3}I{0,3}|H|lit|Xllt|XHf|XIH)[.,;\s\'"*»d]?\s*$', stripped):
                continue
            # Skip page numbers
            if re.match(r'^\d{1,3}$', stripped):
                continue
            cleaned_lines.append(line)
        all_text += "\n".join(cleaned_lines) + "\n"

    # Now split by actual sermon starts
    # Pattern: "SERMONS.\nSERMON\nI." or "SERMON II.\n(scripture)"
    # Use a regex to find sermon boundaries
    sermon_splits = re.split(
        r'\n(?=SERMON\s*\n\s*(?:I{1,3}|IV|V|VI{0,3}|IX|X{1,3}I{0,3})\s*[.,])',
        all_text
    )

    return all_text


def main():
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    doc = fitz.open(str(PDF_PATH))
    print(f"PDF: {len(doc)} pages")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Extract the introduction/memoir (pages 4-35, index 3-34)
    intro_text = ""
    for i in range(3, 35):
        page = doc[i].get_text()
        # Remove page numbers
        page = re.sub(r'^\s*\d{1,4}\s*$', '', page, flags=re.MULTILINE)
        intro_text += page + "\n"

    intro_path = OUT_DIR / "cw-sermons-1816-memoir.txt"
    with open(intro_path, "w", encoding="utf-8") as f:
        f.write(intro_text.strip())
    print(f"Extracted memoir: {len(intro_text.split())} words")

    # Extract full sermon text, page by page, removing running headers
    # Then split by SERMON boundaries

    # Approach: extract page-by-page, track which sermon each page belongs to
    # Use the TOC page numbers as guide:
    # Sermon I: orig p.1, Sermon II: p.22, III: p.41, IV: p.68, V: p.81
    # VI: p.95, VII: p.111, VIII: p.125, IX: p.136, X: p.165
    # XI: p.186, XII: p.207, XIII: p.227, "On Sight of Corpse": p.243
    toc_pages = [1, 22, 41, 68, 81, 95, 111, 125, 136, 165, 186, 207, 227, 243]
    # The offset between original pages and PDF index:
    # Original page 1 starts at PDF page 38 (index 37)
    # But that PDF page shows "SERMONS.\nSERMON\nI." + page content
    # Let's verify: page 38 (idx 37) shows the start of Sermon I
    # Original numbering starts from the sermon section

    # Extract each sermon
    offset = 37  # PDF index = original_page - 1 + offset
    for s_idx in range(len(toc_pages)):
        start_orig = toc_pages[s_idx]
        end_orig = toc_pages[s_idx + 1] if s_idx + 1 < len(toc_pages) else 282 - offset

        start_pdf = start_orig - 1 + offset
        end_pdf = end_orig - 1 + offset

        # Clamp to document bounds
        start_pdf = max(0, min(start_pdf, len(doc) - 1))
        end_pdf = max(0, min(end_pdf, len(doc)))

        # Extract text
        sermon_text = ""
        for pi in range(start_pdf, end_pdf):
            page_text = doc[pi].get_text()
            lines = page_text.split("\n")
            cleaned = []
            for j, line in enumerate(lines):
                stripped = line.strip()
                # Skip running headers at top of page
                if j < 2 and re.match(r'^SERMON', stripped) and len(stripped) < 30:
                    continue
                if j < 2 and re.match(r'^\d{1,3}$', stripped):
                    continue
                # Skip standalone page numbers
                if re.match(r'^\d{1,3}\s*$', stripped):
                    continue
                cleaned.append(line)
            sermon_text += "\n".join(cleaned) + "\n"

        sermon_text = sermon_text.strip()
        word_count = len(sermon_text.split())

        if s_idx < len(SERMONS):
            roman, slug, scripture, author, year = SERMONS[s_idx]
            filename = f"cw-sermon-{roman.lower()}-{slug}.txt"
            label = f"Sermon {roman}: {scripture}"
        elif s_idx == 13:
            filename = "cw-on-sight-of-corpse.txt"
            label = "On the Sight of a Corpse"
        else:
            continue

        out_path = OUT_DIR / filename
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(sermon_text)

        print(f"  {label}: {word_count} words -> {filename}")

    doc.close()

    # Now ingest
    print("\n--- Ingesting into corpus ---")
    sys.path.insert(0, str(CORPUS_ROOT))
    from process_corpus import clean_text, chunk_text, append_passages, load_passages
    from tag_passages import analyze_passage
    from scripts.ingest_batch import (
        get_existing_source_ids, log_ingestion,
        update_scripture_index, update_progress,
    )

    existing_ids = get_existing_source_ids()
    total_added = 0

    # Ingest each sermon
    for roman, slug, scripture, author, year in SERMONS:
        filename = f"cw-sermon-{roman.lower()}-{slug}.txt"
        filepath = OUT_DIR / filename
        source_id = f"cw-sermon-{roman.lower()}"

        if author == "john-wesley":
            source_id = f"jw-sermon-cw1816-{roman.lower()}"

        if source_id in existing_ids:
            print(f"  SKIP (exists): {source_id}")
            continue

        if not filepath.exists():
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        cleaned = clean_text(raw)
        if not cleaned.strip():
            continue

        title = f"CW Sermon {roman}: {scripture}"
        if author == "john-wesley":
            title = f"JW Sermon (in CW 1816): {scripture}"

        passages = chunk_text(cleaned, source_id, author, title, "sermon", year,
                            "https://wesleyscholar.com/wp-content/uploads/2018/09/Sermons-1816.pdf")

        for p in passages:
            themes = analyze_passage(p["text"])
            if themes:
                p["themes"] = themes

        append_passages(passages)
        log_ingestion(filepath, source_id, author, "sermon", title, year,
                     len(passages), "ingested", "cw-sermons-1816")
        total_added += len(passages)
        print(f"  Ingested: {title} -> {len(passages)} passages")

    # Ingest "On the Sight of a Corpse"
    corpse_path = OUT_DIR / "cw-on-sight-of-corpse.txt"
    corpse_id = "cw-on-sight-of-corpse"
    if corpse_path.exists() and corpse_id not in existing_ids:
        with open(corpse_path) as f:
            raw = f.read()
        cleaned = clean_text(raw)
        if cleaned.strip():
            passages = chunk_text(cleaned, corpse_id, "charles-wesley",
                                "On the Sight of a Corpse", "sermon", None,
                                "https://wesleyscholar.com/wp-content/uploads/2018/09/Sermons-1816.pdf")
            for p in passages:
                themes = analyze_passage(p["text"])
                if themes:
                    p["themes"] = themes
            append_passages(passages)
            log_ingestion(corpse_path, corpse_id, "charles-wesley", "sermon",
                         "On the Sight of a Corpse", None, len(passages), "ingested", "cw-sermons-1816")
            total_added += len(passages)
            print(f"  Ingested: On the Sight of a Corpse -> {len(passages)} passages")

    # Ingest memoir
    memoir_path = OUT_DIR / "cw-sermons-1816-memoir.txt"
    memoir_id = "cw-1816-memoir"
    if memoir_path.exists() and memoir_id not in existing_ids:
        with open(memoir_path) as f:
            raw = f.read()
        cleaned = clean_text(raw)
        if cleaned.strip():
            passages = chunk_text(cleaned, memoir_id, "charles-wesley",
                                "Memoir of Charles Wesley (1816)", "treatise", 1816,
                                "https://wesleyscholar.com/wp-content/uploads/2018/09/Sermons-1816.pdf")
            for p in passages:
                themes = analyze_passage(p["text"])
                if themes:
                    p["themes"] = themes
            append_passages(passages)
            total_added += len(passages)
            print(f"  Ingested: Memoir -> {len(passages)} passages")

    if total_added > 0:
        print(f"\nTotal: {total_added} new passages")
        update_scripture_index()
        update_progress()

    print("\nDone.")


if __name__ == "__main__":
    main()
