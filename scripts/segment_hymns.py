#!/usr/bin/env python3
"""Phase 4 of the open reading layer (plans/2026-09-06-open-reading-layer.md).

Splits the 1780 *Collection of Hymns* into individual hymns, preserving
stanza/line structure — "a hymn flattened to prose is a different text"
(plan). Source: raw/charles-wesley/collection-of-hymns-1780.txt (this is the
CCEL page the corpus's cw-hymns-1780 source_url points to; confirmed by
matching its opening text against the live passage).

The plan's assumption ("all 525 hymns") does NOT match this source. What's
actually here, found while building this script:

  - The CCEL transcription is of a later 19th-century Wesleyan Conference
    Office reprint (title page: "PUBLISHED BY JOHN MASON... J. ROCHE,
    PRINTER"), which had by then accumulated supplementary hymns folded
    into the main sequence well past the 1780 original's 525 — numbering
    in this print run runs to 769. The final hymn's own title happens to
    be "A Song of Praise to the Blessed Trinity" (a doxology), not a
    separate 770th untitled hymn — a first pass mistook that title line
    for a section boundary and truncated hymn 769 to three words before
    this was caught and fixed.
  - The scan's OCR damage is markedly worse here than anywhere else
    tackled this session — metre codes are badly mangled ("10's & 11's"
    reads as "10's §■ IVs.", decorative drop-caps produce garbage like
    "1 /^OME" for "1 COME"), and the hymn NUMBER itself is sometimes
    misread: hymn "46" appears twice back to back with clearly different
    text (the second is a different hymn, most likely mis-OCR'd from 47),
    and numbers 38, 39, and 24 others between 1 and 525 have no
    recoverable "HYMN N" header line at all.
  - Because a hymnal has no legitimate reason to skip a number, and the
    printed order is unambiguous, hymns are numbered here by POSITION in
    reading order (1, 2, 3, ... in the order they appear), not by
    trusting the OCR'd number as ground truth. The OCR-read number is kept
    alongside as `ocr_number` for cross-reference and does not gate
    anything.
  - This print run's actual OCR quality means a dedicated cleanup pass
    (matching the precedent already in this repo for the Journal — see
    CLAUDE.md's "Journal OCR cleanup" section) is needed before this is
    publication-quality. That is out of scope here: this script segments
    what is actually on the page and discloses the damage, rather than
    hand-repairing 770 hymns' worth of OCR garble one substitution at a
    time.

Reads the RAW file, not cleaned/ — cleaned/charles-wesley/collection-of-
hymns-1780.txt lost ~160 hymn headers to the same short-all-caps-line
noise filter that strips running headers elsewhere in the corpus (metre
codes made otherwise-real headers look like page noise), so this script
does its own light clean (multi-space collapse only) that leaves line
breaks untouched — this is the opposite of ocr_cleaning.clean_text(),
which would flatten stanzas into prose.

Writes chunked/hymns_1780_by_number.jsonl and
metadata/hymns-1780-findings.csv (the duplicate/gap disclosure).
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "raw" / "charles-wesley" / "collection-of-hymns-1780.txt"
OUT = ROOT / "chunked" / "hymns_1780_by_number.jsonl"
FINDINGS_OUT = ROOT / "metadata" / "hymns-1780-findings.csv"

HYMN_HEAD_RE = re.compile(r"^[ \t]*HYMN[ \t]+(\d+)\.", re.IGNORECASE | re.MULTILINE)
INDEX_MARKER = "INDEX  TO  THE  HYMNS."


def light_clean(text):
    """Collapse OCR's characteristic multi-space runs to single spaces and
    trim trailing whitespace per line — nothing else. Line breaks (which
    carry stanza structure) are left exactly as printed."""
    lines = text.split("\n")
    out = []
    for line in lines:
        line = re.sub(r"[ \t]{2,}", " ", line).rstrip()
        out.append(line)
    return "\n".join(out)


def main():
    raw = RAW_PATH.read_text(encoding="utf-8", errors="replace")
    index_pos = raw.find(INDEX_MARKER)
    if index_pos < 0:
        raise RuntimeError("INDEX TO THE HYMNS marker not found — has the source changed?")

    body_end = index_pos
    body = raw[:body_end]

    heads = [(m.start(), int(m.group(1))) for m in HYMN_HEAD_RE.finditer(body)]
    print(f"{len(heads)} 'HYMN N.' headers found before the index")

    # duplicate / gap disclosure (informational, not a gate)
    seen_numbers = {}
    dupes = []
    for off, n in heads:
        if n in seen_numbers:
            dupes.append(n)
        seen_numbers.setdefault(n, off)
    all_nums = set(seen_numbers)
    gaps = sorted(set(range(1, max(all_nums) + 1)) - all_nums)
    print(f"{len(dupes)} duplicate OCR number(s): {sorted(set(dupes))}")
    print(f"{len(gaps)} gap(s) in the OCR-read sequence up to {max(all_nums)}: {gaps}")

    passages = []
    for i, (off, ocr_num) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else body_end
        hymn_text = light_clean(body[off:end].strip())
        position = i + 1  # canonical number: reading-order position, not the OCR digit
        passages.append({
            # NOT "cw-hymns-1780-NNN" -- that exact id format collides with
            # 452 old whole-collection chunk ids already in
            # cleaned_passages.jsonl (source_id cw-hymns-1780 predates this
            # re-segmentation and uses the identical NNN-padded scheme).
            # Found by the Phase 5 template render test resolving the wrong,
            # coarser-chunked text for most hymns silently.
            "id": f"cw-hymns1780-{position:03d}",
            "author": "charles-wesley",
            "source_id": "cw-hymns-1780",
            "source_title": "A Collection of Hymns (1780, with Supplement)",
            "source_type": "hymn",
            "year": 1780,
            "chunk_index": i,
            "text": hymn_text,
            "word_count": len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", hymn_text)),
            "source_url": "https://www.ccel.org/ccel/wesley/hymn.html",
            "themes": [],
            "created_at": "2026-09-06T00:00:00+00:00",
            "work": f"cw/hymns/1780/{position}",
            "number": position,
            "ocr_number": ocr_num,
        })

    empty = [p["id"] for p in passages if p["word_count"] == 0]
    if empty:
        print(f"WARNING: {len(empty)} hymn(s) with zero text: {empty}", file=sys.stderr)

    with OUT.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Wrote {len(passages)} hymns to {OUT.relative_to(ROOT)}")

    with FINDINGS_OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "ocr_number", "note"])
        for n in sorted(set(dupes)):
            w.writerow(["duplicate", n, "this OCR number appears on >1 distinct hymn; "
                        "positional numbering in hymns_1780_by_number.jsonl is authoritative"])
        for n in gaps:
            w.writerow(["gap", n, "no 'HYMN N.' header recovered for this number; "
                        "likely an OCR miss, not a real gap in the printed hymnal"])
    print(f"Wrote {FINDINGS_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
