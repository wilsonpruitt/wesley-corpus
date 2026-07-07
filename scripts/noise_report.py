"""Phase 0 measurement: per-source non-word rate + running-header count.

Ranks corpus sources by OCR noise so cleanup work (Phase 1-2) targets the
worst offenders first, and gives a before/after yardstick. Read-only —
writes metadata/noise-report.csv, touches nothing under raw/ or chunked/.

Usage: python3 scripts/noise_report.py
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from morphology import is_regular_inflection, is_period_elision

ROOT = Path(__file__).resolve().parent.parent
PASSAGES = ROOT / "chunked" / "cleaned_passages.jsonl"
DICT_PATH = Path("/usr/share/dict/words")
OUT_CSV = ROOT / "metadata" / "noise-report.csv"

# Period/KJV-English forms not in a modern dictionary but legitimate here.
PERIOD_SUPPLEMENT = {
    "thee", "thou", "thy", "thine", "ye", "hath", "doth", "shew", "shewn",
    "shewed", "saith", "unto", "wast", "wilt", "shalt", "art", "canst",
    "wouldst", "couldst", "shouldst", "durst", "givest", "hast", "doest",
    "knowest", "believest", "seest", "sayest", "receivest", "lovest",
    "keepest", "walkest", "cometh", "goeth", "loveth", "believeth",
    "keepeth", "sinneth", "liveth", "dieth", "worketh", "seeketh",
    "knoweth", "giveth", "maketh", "taketh", "speaketh", "heareth",
    "seeth", "findeth", "helpeth", "sufferest", "connexion", "connexions",
    "'tis", "'twas", "'twill", "o'er", "e'er", "ne'er", "methinks",
    "howbeit", "peradventure", "whensoever", "whosoever", "whatsoever",
    "wheresoever", "howsoever", "notwithstanding",
    # Irregular verb forms missing from /usr/share/dict/words (found
    # 2026-07-07: identical counts before/after Phase 1 journal cleanup
    # proved these were always false positives, e.g. "began" x557).
    "began", "bidden", "forgave", "forgiven", "woken",
    # British/period spelling variants (not OCR damage) found while scoping
    # Phase 3 -- concentrated in the Minutes and Charles Wesley's hymns.
    "favourite", "controul", "controuled", "confest", "offence", "offences",
    "lovefeast", "lovefeasts", "preachinghouses", "viz", "wilful", "wilfully",
    # Irregular verbs missed by the morphology suffix-stripper.
    "overtook", "overtaken",
}

HEADER_RE = re.compile(r"REV\.?\s*J\.?\s*WES[LI][EL]Y.*JOURNAL.*\d+", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-z']+")


def load_dictionary():
    words = set()
    if DICT_PATH.exists():
        with open(DICT_PATH, encoding="utf-8", errors="ignore") as f:
            for line in f:
                words.add(line.strip().lower())
    words |= PERIOD_SUPPLEMENT
    return words


def harvest_proper_noun_whitelist(passages_by_source):
    """Capitalized tokens appearing 5+ times across the corpus."""
    cap_counts = Counter()
    for passages in passages_by_source.values():
        for text in passages:
            for tok in WORD_RE.findall(text):
                if tok[0].isupper() and len(tok) > 1:
                    cap_counts[tok.lower()] += 1
    return {tok for tok, n in cap_counts.items() if n >= 5}


def main():
    dictionary = load_dictionary()

    passages_by_source = defaultdict(list)
    meta_by_source = {}
    with open(PASSAGES, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            sid = d["source_id"]
            passages_by_source[sid].append(d["text"])
            if sid not in meta_by_source:
                meta_by_source[sid] = {
                    "author": d.get("author"),
                    "title": d.get("source_title"),
                    "type": d.get("source_type"),
                }

    proper_nouns = harvest_proper_noun_whitelist(passages_by_source)
    print(f"Dictionary: {len(dictionary)} words. Proper-noun whitelist: {len(proper_nouns)} tokens.")

    rows = []
    for sid, texts in passages_by_source.items():
        non_word_counts = Counter()
        total_words = 0
        header_passages = 0
        for text in texts:
            if HEADER_RE.search(text):
                header_passages += 1
            for tok in WORD_RE.findall(text):
                total_words += 1
                low = tok.lower().strip("'")
                if not low:
                    continue
                if low in dictionary or low in proper_nouns:
                    continue
                if is_regular_inflection(low, dictionary):
                    continue
                if is_period_elision(low, dictionary):
                    continue
                # single-letter tokens (I, A, initials) are not noise
                if len(low) <= 1:
                    continue
                non_word_counts[tok] += 1

        non_word_total = sum(non_word_counts.values())
        rate = non_word_total / total_words if total_words else 0.0
        top20 = non_word_counts.most_common(20)
        meta = meta_by_source[sid]
        rows.append({
            "source_id": sid,
            "author": meta["author"],
            "title": meta["title"],
            "source_type": meta["type"],
            "passages": len(texts),
            "words": total_words,
            "non_word_rate": round(rate, 4),
            "header_passages": header_passages,
            "top_offenders": "; ".join(f"{tok}:{n}" for tok, n in top20),
        })

    rows.sort(key=lambda r: r["non_word_rate"], reverse=True)

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_id", "author", "title", "source_type", "passages",
            "words", "non_word_rate", "header_passages", "top_offenders",
        ])
        writer.writeheader()
        writer.writerows(rows)

    total_header_passages = sum(r["header_passages"] for r in rows)
    print(f"Wrote {len(rows)} sources to {OUT_CSV}")
    print(f"Total passages with embedded running headers: {total_header_passages}")
    print("\nTop 15 noisiest sources:")
    for r in rows[:15]:
        print(f"  {r['non_word_rate']:.4f}  {r['source_id']}  ({r['words']} words, {r['header_passages']} headers)")


if __name__ == "__main__":
    main()
