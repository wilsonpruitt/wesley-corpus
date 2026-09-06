#!/usr/bin/env python3
"""Phase 1 of the open reading layer (plans/2026-09-06-open-reading-layer.md).

Derives metadata/sermon-numbering.csv (one row per Bicentennial-numbered
sermon: bicentennial/jackson_running/sugden numbers, title, scripture, date,
Jackson-edition volume:page) from metadata/sources/van-buskirk-sermon-list-2016.csv,
then reconciles it against the corpus's actual jw-sermon-* source_ids.

Also emits metadata/sermon-misattributed.csv for the sermons Jackson's own
edition bundled in under John Wesley's name but which the Bicentennial
editors attribute to someone else (Calamy, Tilly, Gambold) — these get
excluded from the jw/sermons/ open-layer numbering entirely, not silently
renumbered.

Read-only against chunked/cleaned_passages.jsonl.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_CSV = ROOT / "metadata" / "sources" / "van-buskirk-sermon-list-2016.csv"
NON_WESLEY_CSV = ROOT / "metadata" / "sources" / "van-buskirk-jackson-non-wesley-sermons.csv"
PASSAGES_PATH = ROOT / "chunked" / "cleaned_passages.jsonl"
OUT_NUMBERING = ROOT / "metadata" / "sermon-numbering.csv"
OUT_MISATTRIBUTED = ROOT / "metadata" / "sermon-misattributed.csv"

# Three sermons stored under a title slug rather than jw-sermon-NNN, keyed by
# jackson_running number (see plans/2026-09-06-open-reading-layer.md Phase 0
# notes and the SERMON_TITLE_OVERRIDES in scripts/build_works.py).
TITLE_SLUG_OVERRIDES = {
    "16": "jw-means-of-grace",
    "39": "jw-catholic-spirit",
    "128": "jw-free-grace",
}
# jw-sermon-cw1816-xiii duplicates jackson_running 127 (Bicentennial 109),
# found bundled in the 1816 Charles Wesley memoir volume under a different
# edition. Not a numbering entry — a known duplicate, closed in works.jsonl.
DUPLICATE_SOURCE_IDS = {"jw-sermon-cw1816-xiii": "127"}


def corpus_sermon_source_ids():
    ids = set()
    for line in PASSAGES_PATH.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d["author"] == "john-wesley" and d["source_type"] == "sermon":
            ids.add(d["source_id"])
    return ids


def source_id_for(jackson_running: str) -> str:
    if jackson_running in TITLE_SLUG_OVERRIDES:
        return TITLE_SLUG_OVERRIDES[jackson_running]
    return f"jw-sermon-{int(jackson_running):03d}"


def main():
    rows = list(csv.DictReader(SOURCE_CSV.open(encoding="utf-8")))
    non_wesley_rows = list(csv.DictReader(NON_WESLEY_CSV.open(encoding="utf-8")))
    corpus_ids = corpus_sermon_source_ids()

    out_rows = []
    matched_ids = set()
    misses = []

    for row in rows:
        jr = row["jackson_running"].strip()
        if not jr:
            # Bicentennial sermon never printed by Jackson (dash in the
            # source table) — genuinely absent from this corpus, not a miss.
            continue
        sid = source_id_for(jr)
        in_corpus = sid in corpus_ids
        if in_corpus:
            matched_ids.add(sid)
        else:
            misses.append((row["bicentennial"], jr, sid))
        out_rows.append({
            "bicentennial": row["bicentennial"],
            "jackson_running": jr,
            "sugden": row["bicentennial"] if row["sugden_ref"] else None,
            "source_id": sid,
            "in_corpus": in_corpus,
            "title": row["title"],
            "scripture": row["scripture"],
            "date": row["date"],
            "bicentennial_ref": row["bicentennial_ref"],
            "jackson_ref": row["jackson_ref"] or None,
            "sugden_ref": row["sugden_ref"] or None,
            "notes": row["notes"] or None,
        })

    with OUT_NUMBERING.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    with OUT_MISATTRIBUTED.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(non_wesley_rows[0].keys()) + ["source_id", "in_corpus"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in non_wesley_rows:
            sid = f"jw-sermon-{int(row['jackson_running']):03d}"
            row["source_id"] = sid
            row["in_corpus"] = sid in corpus_ids
            writer.writerow(row)

    # Reconciliation report against the corpus's full jw-sermon-* set.
    misattributed_ids = {f"jw-sermon-{int(r['jackson_running']):03d}" for r in non_wesley_rows
                          if r["real_author"] != "Charles Wesley"}
    accounted = matched_ids | misattributed_ids | set(DUPLICATE_SOURCE_IDS)
    unaccounted = corpus_ids - accounted

    print(f"{len(out_rows)} numbered sermons written to {OUT_NUMBERING.relative_to(ROOT)}")
    print(f"{len(matched_ids)} matched to a corpus source_id, {len(misses)} miss(es)")
    for bicentennial, jr, sid in misses:
        print(f"  MISS: Bicentennial {bicentennial} / Jackson {jr} -> {sid} not in corpus", file=sys.stderr)
    print(f"{len(misattributed_ids)} misattributed sermons written to {OUT_MISATTRIBUTED.relative_to(ROOT)}")
    print(f"{len(DUPLICATE_SOURCE_IDS)} known duplicate(s): {DUPLICATE_SOURCE_IDS}")
    if unaccounted:
        print(f"UNACCOUNTED corpus sermon source_ids ({len(unaccounted)}): {sorted(unaccounted)}", file=sys.stderr)
        return 1
    print("All corpus jw-sermon-* source_ids accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
