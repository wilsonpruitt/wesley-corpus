#!/usr/bin/env python3
"""Phase 2 wiring step for the open reading layer
(plans/2026-09-06-open-reading-layer.md).

Re-chunks the journal on ENTRY boundaries (from metadata/journal-entry-
boundaries.csv, built by scripts/journal_boundaries.py) into
chunked/journal_by_entry.jsonl — one passage per dated entry, grouped into a
work per calendar year (jw/journal/{YYYY}), replacing the 15 undifferentiated
whole-source journal entries in chunked/cleaned_passages.jsonl.

Only KEEP-marked sources from metadata/journal-overlap.csv are used:
KEEP-SPINE (the three continuous editions) and KEEP-UNIQUE (the one Curnock
part that fills the 1758-60 gap no other source covers). DUPLICATE-* sources
are excluded entirely — this is the overlap ledger's whole point.

Entries are sliced from the CLEANED text using each source file's own offsets
(text position is only meaningful within the file it came from), then merged
and re-sorted by resolved calendar date across files, since two KEEP files
can contribute entries to the same year (1760 spans both
journal-1760-to-1773 and journal-vol4-part11-section02). Same-date collisions
get -b, -c... suffixes, per the plan; a collision between two DIFFERENT
source files (rather than Wesley genuinely writing twice in one sitting) is
printed as a warning, since it would mean the overlap ledger missed something.

Non-destructive: chunked/cleaned_passages.jsonl and web_app.py are untouched.
Wiring that file in is Phase 5.

Text is run through ocr_cleaning.clean_text() before being stored, same as
every other passage in the corpus gets via clean_corpus.py. Missing this
was a real bug, caught by re-running the plan's own sentinel gate: entries
are sliced straight from cleaned/john-wesley/*.txt, which is only
process_corpus.py's FIRST cleaning pass — it still has line-wrap newlines
inside sentences ("I felt my\nheart strangely warmed"), which
clean_corpus.py's ocr_cleaning.clean_text() collapses to spaces at the
passage level. Skipping that step meant a literal-substring search for
the Aldersgate sentinel ("i felt my heart strangely warmed") found
nothing — the words were right there, split across a line break.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ocr_cleaning import clean_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT / "cleaned" / "john-wesley"
BOUNDARIES_PATH = ROOT / "metadata" / "journal-entry-boundaries.csv"
OVERLAP_PATH = ROOT / "metadata" / "journal-overlap.csv"
OUT = ROOT / "chunked" / "journal_by_entry.jsonl"

KEEP_VERDICTS = {"KEEP-SPINE", "KEEP-UNIQUE"}
LARGE_ENTRY_WORDS = 1500  # corpus-wide mean 129 / median 69 for a real day's entry


def load_keep_source_ids():
    """source_id -> (verdict, covers_from, covers_to). KEEP-UNIQUE sources
    exist to fill a specific gap the spine files don't cover, and nothing
    else — an entry outside that stated window is either drift the
    consistency guard missed or genuinely duplicate ground the spine already
    owns. Confirmed necessary: journal-vol4-part11-section02 (quotes another
    correspondent's testimony at length, its own dates already known to be
    less reliable — see journal_boundaries.py's demote_inconsistent_dates
    docstring) produced 16 entries from June 1760 to January 1761, all
    outside its 1759-07-01..1760-05-05 gap-filling window and all colliding
    with journal-1760-to-1773, which already owns that ground."""
    keep = {}
    for row in csv.DictReader(OVERLAP_PATH.open(encoding="utf-8")):
        if row["verdict"] in KEEP_VERDICTS:
            keep[row["source_id"]] = (row["verdict"], row["covers_from"], row["covers_to"])
    return keep


def word_count(text):
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))


def main():
    keep = load_keep_source_ids()
    print(f"{len(keep)} KEEP source(s): {sorted(keep)}")

    rows_by_file = defaultdict(list)
    for row in csv.DictReader(BOUNDARIES_PATH.open(encoding="utf-8")):
        if row["status"] not in ("ok", "rescued"):
            continue
        source_id = "jw-" + row["source_file"]
        if source_id not in keep:
            continue
        rows_by_file[row["source_file"]].append(row)

    entries = []  # (date, source_id, source_file, offset, text, status)
    for source_file, rows in rows_by_file.items():
        rows.sort(key=lambda r: int(r["offset"]))
        text = (CLEAN_DIR / f"{source_file}.txt").read_text(encoding="utf-8", errors="replace")
        source_id = "jw-" + source_file
        verdict, covers_from, covers_to = keep[source_id]
        trimmed = 0
        for i, row in enumerate(rows):
            start = int(row["offset"])
            end = int(rows[i + 1]["offset"]) if i + 1 < len(rows) else len(text)
            next_date = rows[i + 1]["date"] if i + 1 < len(rows) else None
            if verdict == "KEEP-UNIQUE" and not (covers_from <= row["date"] <= covers_to):
                trimmed += 1
                continue
            body = clean_text(text[start:end].strip())
            if not body:
                continue
            entries.append((row["date"], source_id, source_file, start, body, row["status"], next_date))
        if trimmed:
            print(f"  {source_id}: trimmed {trimmed} entries outside its "
                  f"{covers_from}..{covers_to} gap-filling window")

    print(f"{len(entries)} entries collected from KEEP sources")

    # Sort chronologically across files. Ties (same date, different files)
    # are resolved by source_id so the ordering is at least deterministic;
    # they're also exactly the case flagged as a cross-file collision below.
    entries.sort(key=lambda e: (e[0], e[1], e[3]))

    by_year = defaultdict(list)
    for e in entries:
        year = int(e[0][:4])
        by_year[year].append(e)

    now = datetime.now(timezone.utc).isoformat()
    passages = []
    cross_file_collisions = 0
    for year in sorted(by_year):
        year_entries = by_year[year]
        source_id = f"jw-journal-{year}"
        seen_dates = defaultdict(list)  # date -> [source_file, ...] emitted so far
        for chunk_index, (date, src_id, src_file, offset, body, status, next_date) in enumerate(year_entries):
            prior = seen_dates[date]
            if prior and prior[-1] != src_file:
                cross_file_collisions += 1
                print(
                    f"WARNING: {date} appears in both {prior[-1]} and {src_file} "
                    f"— overlap ledger may have missed something",
                    file=sys.stderr,
                )
            suffix = "" if not prior else chr(ord("a") + len(prior))  # b, c, ...
            anchor = date + suffix
            prior.append(src_file)

            wc = word_count(body)
            # A real single-day entry runs well under 500 words (corpus-wide
            # mean 129, median 69). Anything far past that means unresolved
            # entries between this one and the next KEPT boundary in the same
            # source file got silently absorbed into this passage's text —
            # found via jw-journal-1738-010 (20,445 words: Aldersgate through
            # the whole Herrnhut journey, because vol1-3's decade-spanning
            # preface left everything between May 24 and Aug 12 unresolved).
            # Flagged honestly rather than published as if it were one day's
            # writing.
            oversized = wc > LARGE_ENTRY_WORDS
            precision = "range" if oversized else "day"

            passages.append({
                "id": f"{source_id}-{chunk_index:03d}",
                "author": "john-wesley",
                "source_id": source_id,
                "source_title": f"Journal, {year}",
                "source_type": "journal",
                "year": year,
                "chunk_index": chunk_index,
                "text": body,
                "word_count": wc,
                "source_url": None,
                "themes": [],
                "created_at": now,
                # Provenance fields specific to this re-segmentation, not part
                # of the original chunked/cleaned_passages.jsonl schema:
                "work": f"jw/journal/{year}",
                "anchor": anchor,
                "date": date,
                "date_precision": precision,
                "content_extends_to": next_date if oversized else None,
                "resolution_status": status,
                "origin_source_id": src_id,
                "origin_offset": offset,
            })

    with OUT.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    years = sorted(by_year)
    print(f"\n{len(passages)} passages across {len(years)} years ({years[0]}-{years[-1]})")
    print(f"{cross_file_collisions} cross-file same-date collision(s)")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
