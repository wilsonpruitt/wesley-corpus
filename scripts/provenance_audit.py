"""Phase 3a: provenance audit.

sources.csv only tracks 12 works from the earliest Jan-2025 batch; the
corpus has grown to 3,337 distinct source_ids since. This script assigns
each source_id a collection (by source_id prefix / raw file path) and a
RED/YELLOW/GREEN verdict based on what provenance is actually recoverable:
embedded "Source: ..." header lines in raw/ files, hardcoded URLs in the
download/extract scripts, or documented history in CLAUDE.md/memory.

Read-only — writes metadata/provenance-audit.csv. Does not fetch anything.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSAGES = ROOT / "chunked" / "cleaned_passages.jsonl"
OUT_CSV = ROOT / "metadata" / "provenance-audit.csv"

# (match function, collection name, verdict, edition, url, note)
# Order matters: first match wins.
RULES = [
    (lambda s: s.startswith("jw-sermon"), "jw-sermon",
     "GREEN", "Sermons of John Wesley, 1872 edition (Jackson/wesley.nnu.edu)",
     "https://wesley.nnu.edu/john-wesley/the-sermons-of-john-wesley-1872-edition/",
     "Confirmed by sources.csv sample rows; per-passage source_url populated for later ingests."),

    (lambda s: s.startswith("jw-letter"), "jw-letter",
     "YELLOW", "The Letters of John Wesley (per-year volumes, embedded header)",
     "",
     "Largest single collection (2,635 files). Every raw file carries a "
     "'Source: The Letters of John Wesley (YEAR)' header naming the letter's "
     "year, confirming these are Wesley's letters and not a mislabeled work — "
     "but no source_url was ever logged (no download script found; likely "
     "manual/scraped ingest predating ingest_batch.py logging). Recommend "
     "Wilson confirm the specific edition (Telford 1931 8-vol vs. an older "
     "PD compilation) and backfill a URL."),

    (lambda s: bool(re.match(r"^jw-treatise", s)), "jw-treatise",
     "GREEN", "The Works of John Wesley (Zondervan reprint of the PD Jackson 1872 edition)",
     "",
     "~128 files in raw/john-wesley/treatises/ each carry a 'Source: The "
     "Works of John Wesley, Volume N (Zondervan)' header. Zondervan's edition "
     "is a modern reprint of the public-domain Jackson text, not a "
     "copyrighted new work — same pattern as the Barnes case would have "
     "flagged if the *content* diverged, but headers + spot content here "
     "match known Wesley treatises."),

    (lambda s: bool(re.match(r"^jw-journal", s)), "jw-journal",
     "YELLOW", "Wesley's Journal (multiple raw files: journal-vol1-3, vol4-7, "
     "vol4-part09..13, 1760-to-1773, 1773-to-1776)",
     "",
     "No embedded Source: header on any journal raw file. Text authenticity "
     "is well-established (this is the corpus's most worked-on section — see "
     "CLAUDE.md OCR-gotchas section), but provenance is institutional memory, "
     "not a recorded URL. The vol4-part09..13 files are also absent from "
     "ingestion-log.csv entirely (see missing_from_ingestion_log column) — "
     "lowest-documented sub-slice of an otherwise well-understood work."),

    (lambda s: s in ("jw-notes-nt", "jw-notes-on-old-testament"), "jw-notes",
     "GREEN", "Wesley's Explanatory Notes (CCEL text for NT; OT notes)",
     "",
     "jw-notes-nt was Barnes' Notes on the NT (Baker Books reprint, "
     "in-copyright) mislabeled as Wesley for weeks — FIXED 2026-05-13, "
     "replaced with the genuine CCEL Wesley text (raw/john-wesley/"
     "notes-on-new-testament-wesley.txt). This is the confirmed-good state; "
     "flagged GREEN but should stay a permanent priority in the sentinel-"
     "quote regression suite (3c) given the history."),

    (lambda s: s.startswith("jw-minutes"), "jw-minutes",
     "GREEN", "Minutes of the Methodist Conferences 1744-1798, 1862 Wesleyan "
     "Methodist critical edition",
     "https://archive.org/details/minutesofmethodi00wesl",
     "Documented in memory (gap filled 2026-04-09): 503 passages, ~169K "
     "words, sourced from Internet Archive minutesofmethodi00wesl."),

    (lambda s: s == "jw-primitive-physick", "jw-primitive-physick",
     "YELLOW", "Primitive Physick (1770)", "",
     "Top-ranked noisiest source in Phase 0 (11.4% non-word rate) — mostly "
     "archaic medical/Latin recipe terms, not necessarily wrong text, but "
     "worth a manual spot-check given the noise concentration."),

    (lambda s: bool(re.match(r"^jw-(character|catholic-spirit|free-grace|"
                              r"general-rules|genuine-christianity|"
                              r"plain-account)$", s)), "jw-early-tracked",
     "GREEN", "Various — tracked individually in sources.csv (Jan 2025 batch)",
     "", "One of the 12 original sources.csv rows; has a real source_url there."),

    (lambda s: s.startswith("jw-survey-of-wisdom") or "survey-of-wisdom" in s,
     "jw-survey-of-wisdom", "YELLOW",
     "A Survey of the Wisdom of God in Creation", "",
     "24 files, no embedded Source: header. Documented in memory as a "
     "2026-04-06 gap-fill from wesley.nnu.edu but no URL recorded per file."),

    (lambda s: s.startswith("cw-duke") or s.startswith("cw-gp") or
               "duke" in s, "cw-duke-verse",
     "GREEN", "Duke Divinity CSWT — Charles Wesley Published Verse (Original)",
     "https://divinity.duke.edu/initiatives/wesleyan-methodist/cswt-cw-published",
     "URL is hardcoded in scripts/extract_duke_cw.py / download_duke_cw.py "
     "and written to source_url at ingest time for these passages."),

    (lambda s: s.startswith("cw-sermon") or bool(re.match(r"^cw-\d", s)) or
               s == "cw-1816-memoir", "cw-1816-sermons",
     "GREEN", "Sermons by the Late Rev. Charles Wesley, A.M. (1816)",
     "https://wesleyscholar.com/wp-content/uploads/2018/09/Sermons-1816.pdf",
     "URL hardcoded in scripts/extract_cw_sermons.py."),

    (lambda s: any(tag in s for tag in ("hsp-1739", "hsp-1740", "cph-1741",
                                        "hymns-on-gods-everlasting-love",
                                        "promise-of-sanctification")),
     "cw-named-hymn-collections", "GREEN",
     "Named 18th-c. Charles Wesley hymn collections (HSP 1739/1740, "
     "Collection of Psalms & Hymns 1741, etc.)", "",
     "Raw files carry 'Source: Hymns and Sacred Poems (YEAR), Part N' "
     "headers — well-known, identifiable collections."),

    (lambda s: "journal" in s and s.startswith("cw-"), "cw-journal",
     "GREEN", "The Journal of Charles Wesley 1707-1788 (wesley.nnu.edu)",
     "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/",
     "URL hardcoded per date-range in scripts/download_cw_journal.py."),
]

FALLBACK = ("uncategorized", "RED",
            "No collection rule matched", "",
            "Did not match any known collection pattern — needs manual "
            "classification before trusting its provenance.")


def classify(sid):
    for match, collection, verdict, edition, url, note in RULES:
        if match(sid):
            return collection, verdict, edition, url, note
    return (FALLBACK[0], FALLBACK[1], FALLBACK[2], FALLBACK[3], FALLBACK[4])


def main():
    meta_by_source = {}
    counts = defaultdict(lambda: {"passages": 0, "words": 0, "has_url": False})
    with open(PASSAGES, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            sid = d["source_id"]
            counts[sid]["passages"] += 1
            counts[sid]["words"] += d.get("word_count", 0)
            if d.get("source_url"):
                counts[sid]["has_url"] = True
            if sid not in meta_by_source:
                meta_by_source[sid] = {
                    "author": d.get("author"),
                    "title": d.get("source_title"),
                    "type": d.get("source_type"),
                }

    log_sids = set()
    with open(ROOT / "metadata" / "ingestion-log.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            log_sids.add(row["source_id"])

    rows = []
    verdict_counts = defaultdict(int)
    for sid, c in counts.items():
        collection, verdict, edition, url, note = classify(sid)
        # Per-passage source_url present bumps YELLOW to GREEN (real, recorded provenance).
        if verdict == "YELLOW" and c["has_url"]:
            verdict = "GREEN"
            note += " [per-passage source_url IS populated for this source_id.]"
        verdict_counts[verdict] += 1
        meta = meta_by_source[sid]
        rows.append({
            "source_id": sid,
            "author": meta["author"],
            "title": meta["title"],
            "source_type": meta["type"],
            "collection": collection,
            "verdict": verdict,
            "edition": edition,
            "known_url": url,
            "passages": c["passages"],
            "words": c["words"],
            "in_ingestion_log": sid in log_sids,
            "note": note,
        })

    rows.sort(key=lambda r: ({"RED": 0, "YELLOW": 1, "GREEN": 2}[r["verdict"]], -r["words"]))

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_id", "author", "title", "source_type", "collection",
            "verdict", "edition", "known_url", "passages", "words",
            "in_ingestion_log", "note",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} sources to {OUT_CSV}")
    print(f"Verdicts: {dict(verdict_counts)}")
    total_words = sum(r["words"] for r in rows)
    for v in ("RED", "YELLOW", "GREEN"):
        w = sum(r["words"] for r in rows if r["verdict"] == v)
        print(f"  {v}: {verdict_counts[v]} sources, {w} words ({100*w/total_words:.1f}% of corpus)")

    print("\nCollections:")
    coll_counts = defaultdict(lambda: [0, 0, ""])
    for r in rows:
        coll_counts[r["collection"]][0] += 1
        coll_counts[r["collection"]][1] += r["words"]
        coll_counts[r["collection"]][2] = r["verdict"]
    for coll, (n, w, v) in sorted(coll_counts.items(), key=lambda kv: -kv[1][1]):
        print(f"  [{v}] {coll}: {n} sources, {w} words")


if __name__ == "__main__":
    main()
