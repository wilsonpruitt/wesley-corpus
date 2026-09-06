#!/usr/bin/env python3
"""Phase 0 of the open reading layer (plans/2026-09-06-open-reading-layer.md).

Builds metadata/works.jsonl: one record per WORK, grouping the existing
per-passage cleaned_passages.jsonl by source_id and assigning each work a
stable, human-legible slug. Read-only against chunked/cleaned_passages.jsonl —
nothing here mutates the serving file.

Also writes metadata/work-titles.csv (source_id -> slug -> title, so a later
title edit is a registry update, never a re-slug) and, with --check, verifies
the Phase 0 exit gate: every passage belongs to exactly one work, every work
has >=1 passage, and every slug is unique.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSAGES_PATH = ROOT / "chunked" / "cleaned_passages.jsonl"
NOISE_PATH = ROOT / "metadata" / "noise-report.csv"
SERMON_MANIFEST_PATH = ROOT / "metadata" / "sermon-reextraction-manifest.csv"
SWAP_MAP_PATH = ROOT / "metadata" / "swap-source-id-map.csv"
WORKS_OUT = ROOT / "metadata" / "works.jsonl"
TITLES_OUT = ROOT / "metadata" / "work-titles.csv"

QUALITY_THRESHOLD = 0.05  # provisional; plan decision #1 sets the real gate

LETTER_INDIV_RE = re.compile(r"^jw-letter-(\d{4}[ab]?)-(\d+)-(.+)$")
LETTER_BULK_RE = re.compile(r"^jw-letters-(\d{4}[ab]?)$")
CW_HYMN_INDIV_RE = re.compile(r"^cw-(\d{3})-(.+)$")
CW_SERMON_RE = re.compile(r"^cw-sermon-(\w+)$")

# Sermons whose Jackson number isn't recoverable from the standard
# jw-sermon-NNN id pattern — resolved 2026-09-06 by reading the sermon's own
# heading line ("Sermon 16: The Means of Grace", etc.) after the manifest/
# swap-map merge left them unmatched. See plan Phase 0 notes.
SERMON_TITLE_OVERRIDES = {
    "jw-means-of-grace": "16",
    "jw-catholic-spirit": "39",
    "jw-free-grace": "128",
}
# Present in the corpus as a sermon but outside the 141-sermon Jackson set
# (found bundled in the 1816 Charles Wesley memoir volume). No Jackson number
# to hang a jw/sermons/ slug on; registered as a treatise-style work instead.
SERMON_NO_NUMBER = {"jw-sermon-cw1816-xiii"}


def load_passages():
    works = defaultdict(list)  # source_id -> [passage dict, ...]
    order = []
    for line in PASSAGES_PATH.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        p = json.loads(line)
        sid = p["source_id"]
        if sid not in works:
            order.append(sid)
        works[sid].append(p)
    for sid in works:
        works[sid].sort(key=lambda p: p["chunk_index"])
    return works, order


def load_noise():
    noise = {}
    if NOISE_PATH.exists():
        for row in csv.DictReader(NOISE_PATH.open(encoding="utf-8")):
            noise[row["source_id"]] = row
    return noise


def load_sermon_numbering():
    """source_id -> jackson number (as int), for the 141 JW sermons."""
    merged = {}
    if SERMON_MANIFEST_PATH.exists():
        for row in csv.DictReader(SERMON_MANIFEST_PATH.open(encoding="utf-8")):
            if row["jackson_num"] and row["source_id"]:
                merged[row["jackson_num"]] = row["source_id"]
    if SWAP_MAP_PATH.exists():
        for row in csv.DictReader(SWAP_MAP_PATH.open(encoding="utf-8")):
            if row["jackson_num"] and row["actual_source_id"]:
                merged[row["jackson_num"]] = row["actual_source_id"]
    by_source_id = {sid: int(num) for num, sid in merged.items() if num}
    for sid, num in SERMON_TITLE_OVERRIDES.items():
        by_source_id[sid] = int(num)
    return by_source_id


def strip_prefix(source_id: str, prefixes) -> str:
    for p in prefixes:
        if source_id.startswith(p):
            return source_id[len(p):]
    return source_id


def classify(source_id, passages, sermon_numbering):
    """Return (corpus, slug, kind) for a work. kind is a free-text tag used
    only for the CLAUDE.md-visible summary, not for routing."""
    author = passages[0]["author"]
    types = {p["source_type"] for p in passages}

    if author == "john-wesley":
        if source_id in sermon_numbering:
            n = sermon_numbering[source_id]
            return "jw-sermons", f"jw/sermons/{n:03d}", "sermon"
        if source_id in SERMON_NO_NUMBER:
            stub = strip_prefix(source_id, ("jw-",))
            return "jw-works", f"jw/works/{stub}", "sermon-unnumbered"
        if "journal" in types:
            stub = strip_prefix(source_id, ("jw-journal-", "jw-"))
            return "jw-journal-placeholder", f"jw/journal/vol/{stub}", "journal-raw-file"
        if "notes" in types:
            if source_id == "jw-notes-nt":
                return "jw-notes-nt-placeholder", "jw/notes-nt", "notes-whole"
            return "jw-notes-ot-placeholder", "jw/notes-ot", "notes-whole"
        m = LETTER_BULK_RE.match(source_id)
        if m:
            year = m.group(1)
            return "jw-letters-digest", f"jw/letters-digest/{year}", "letter-year-digest"
        m = LETTER_INDIV_RE.match(source_id)
        if m:
            year, seq, recipient = m.groups()
            return "jw-letters", f"jw/letters/{year}/{seq}-{recipient}", "letter"
        # treatise (includes minutes, primitive-physick, etc. — everything left)
        stub = strip_prefix(source_id, ("jw-treatise-", "jw-"))
        return "jw-works", f"jw/works/{stub}", "treatise"

    if author == "charles-wesley":
        m = CW_SERMON_RE.match(source_id)
        if m:
            return "cw-sermons", f"cw/sermons/{m.group(1)}", "sermon"
        if "hymn-collection" in types:
            stub = strip_prefix(source_id, ("cw-duke-", "cw-"))
            return "cw-hymns-collection-placeholder", f"cw/hymns/{stub}", "hymn-collection"
        m = CW_HYMN_INDIV_RE.match(source_id)
        if m:
            num, rest = m.groups()
            return "cw-hymns-misc", f"cw/hymns/misc/{num}-{rest}", "hymn"
        stub = strip_prefix(source_id, ("cw-",))
        return "cw-works", f"cw/works/{stub}", "treatise-or-other"

    raise ValueError(f"unrecognized author {author!r} for source_id {source_id!r}")


def quality_flag(source_id, noise_row, corpus):
    """Return (open: bool, reason: str|None)."""
    if corpus == "jw-letters-digest":
        return False, "abridged-digest-duplicates-individual-letters-same-year"
    if noise_row is None:
        return True, None
    rate = float(noise_row["non_word_rate"] or 0.0)
    if rate > QUALITY_THRESHOLD:
        return False, f"non_word_rate={rate:.3f} exceeds provisional {QUALITY_THRESHOLD:.2f} gate"
    return True, None


def build(check_only: bool):
    passages_by_source, source_order = load_passages()
    noise = load_noise()
    sermon_numbering = load_sermon_numbering()

    works = []
    seen_slugs = {}
    seen_passage_ids = set()
    dupe_slugs = []
    dupe_passages = []

    for source_id in source_order:
        passages = passages_by_source[source_id]
        corpus, slug, kind = classify(source_id, passages, sermon_numbering)

        if slug in seen_slugs:
            dupe_slugs.append((slug, seen_slugs[slug], source_id))
        seen_slugs[slug] = source_id

        passage_ids = [p["id"] for p in passages]
        for pid in passage_ids:
            if pid in seen_passage_ids:
                dupe_passages.append(pid)
            seen_passage_ids.add(pid)

        first = passages[0]
        noise_row = noise.get(source_id)
        is_open, reason = quality_flag(source_id, noise_row, corpus)

        word_count = sum(p.get("word_count") or 0 for p in passages)
        themes = sorted({t for p in passages for t in p.get("themes", [])})

        work = {
            "id": slug,
            "corpus": corpus,
            "type": kind,
            "author": first["author"],
            "title": first["source_title"],
            "title_alt": [],
            "text_basis": None,
            "date_composed": str(first["year"]) if first.get("year") else None,
            "date_precision": "year" if first.get("year") else "unknown",
            "date_note": None,
            "numbering": {
                "jackson": sermon_numbering.get(source_id),
                "bicentennial": None,
                "sugden": None,
            },
            "source_edition": {
                "editor": None, "title": None, "edition": None, "place": None,
                "publisher": None, "year": None, "volume": None, "pages": None,
                "scan_url": first.get("source_url"), "scan_page_ids": None,
            },
            "transcription": {
                "derived_from": None,
                "corrected_against_scan": False,
                "corrector": None,
                "corrected_on": None,
            },
            "modernization": "none",
            "license_text": "Public Domain Mark 1.0",
            "license_apparatus": "CC BY 4.0",
            "wikidata": None,
            "prev": None,
            "next": None,
            "part_of": corpus,
            "editorial_note": None,
            "source_id": source_id,
            "passage_ids": passage_ids,
            "word_count": word_count,
            "themes_auto": themes,
            "open": is_open,
            "closed_reason": reason,
            "legacy_ids": passage_ids,
        }
        works.append(work)

    total_passages = sum(len(v) for v in passages_by_source.values())
    ok = True
    if dupe_slugs:
        ok = False
        print(f"FAIL: {len(dupe_slugs)} duplicate slug(s):", file=sys.stderr)
        for slug, a, b in dupe_slugs[:20]:
            print(f"  {slug}  <-  {a}  AND  {b}", file=sys.stderr)
    if dupe_passages:
        ok = False
        print(f"FAIL: {len(dupe_passages)} passage(s) assigned to >1 work", file=sys.stderr)
    if len(seen_passage_ids) != total_passages:
        ok = False
        print(
            f"FAIL: {total_passages} passages on disk, {len(seen_passage_ids)} covered by works",
            file=sys.stderr,
        )
    empty = [w["id"] for w in works if not w["passage_ids"]]
    if empty:
        ok = False
        print(f"FAIL: {len(empty)} work(s) with zero passages: {empty[:10]}", file=sys.stderr)

    n_open = sum(1 for w in works if w["open"])
    n_closed = len(works) - n_open
    print(
        f"{len(works)} works from {len(source_order)} sources, "
        f"{total_passages} passages covered. open={n_open} closed={n_closed}"
    )
    by_corpus = defaultdict(int)
    for w in works:
        by_corpus[w["corpus"]] += 1
    for corpus, n in sorted(by_corpus.items()):
        print(f"  {corpus}: {n}")

    if check_only:
        if ok:
            print("CHECK PASSED")
            return 0
        print("CHECK FAILED", file=sys.stderr)
        return 1

    if not ok:
        print("Refusing to write works.jsonl — fix the failures above first.", file=sys.stderr)
        return 1

    with WORKS_OUT.open("w", encoding="utf-8") as f:
        for w in works:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")

    with TITLES_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_id", "slug", "title", "corpus", "open"])
        for w in works:
            writer.writerow([w["source_id"], w["id"], w["title"], w["corpus"], w["open"]])

    print(f"Wrote {WORKS_OUT.relative_to(ROOT)} and {TITLES_OUT.relative_to(ROOT)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify the Phase 0 gate, write nothing")
    args = ap.parse_args()
    sys.exit(build(check_only=args.check))


if __name__ == "__main__":
    main()
