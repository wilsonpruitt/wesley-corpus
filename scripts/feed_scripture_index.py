#!/usr/bin/env python3
"""Phase 3 step 2 of the open reading layer
(plans/2026-09-06-open-reading-layer.md).

Feeds the (book, chapter, verse) triples from the Notes re-segmentation
(scripts/segment_notes.py, chunked/notes_by_chapter.jsonl) back into
metadata/scripture-index.json — closing the CLAUDE.md gap where jw-notes-nt
and jw-notes-on-old-testament contribute near-zero to the scripture index
despite being mostly scripture commentary (the regex-based extractor in
extract_scripture_references.py misses Wesley's bare-verse-number style;
segmenting at the chapter/verse layer sidesteps that entirely, since the
verse numbers are already known from the segmentation).

Additive merge only: existing entries in scripture-index.json are untouched,
new (book, chapter) keys are created as needed, and one entry per verse
anchor is appended under the matching book/chapter. A backup is written
before any change (metadata/scripture-index.json.bak-pre-notes-feed-*).
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import segment_notes as sn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "metadata" / "scripture-index.json"
BACKUP_PATH = ROOT / "metadata" / f"scripture-index.json.bak-pre-notes-feed-{date.today()}"


def main():
    if not BACKUP_PATH.exists():
        BACKUP_PATH.write_text(INDEX_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backed up existing index to {BACKUP_PATH.relative_to(ROOT)}")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    added = 0
    for testament, chapters, source_id, source_title in (
        ("NT", sn.segment_nt(), "jw-notes-nt",
         "Explanatory Notes on the New Testament"),
        ("OT", sn.segment_ot(), "jw-notes-ot",
         "Explanatory Notes on the Old Testament"),
    ):
        for ch in chapters:
            slug = "notes-nt" if testament == "NT" else "notes-ot"
            passage_id = f"jw-{slug}-{ch['osis'].lower()}-{ch['chapter']:03d}"
            book_key = ch["book_name"]
            chapter_key = str(ch["chapter"])
            for _, verse in ch["verses"]:
                entry = {
                    "passage_id": passage_id,
                    "source_title": source_title,
                    "author": "john-wesley",
                    "verses": str(verse),
                }
                index.setdefault(book_key, {}).setdefault(chapter_key, []).append(entry)
                added += 1

    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)

    books_now = len(index)
    print(f"Added {added} verse references from the Notes re-segmentation")
    print(f"scripture-index.json now covers {books_now} books")
    return 0


if __name__ == "__main__":
    sys.exit(main())
