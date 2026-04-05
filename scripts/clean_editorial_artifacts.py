"""Strip editorial/footnote artifacts from chunked/cleaned_passages.jsonl.

Telford's editorial apparatus (section headers, cross-references, gloss notes)
was OCR-flattened into the body text. This script removes the most common
patterns. Run with --dry-run first to review what will change.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "chunked" / "cleaned_passages.jsonl"

# Patterns — each is (name, regex, replacement). Order matters.
# The whole list is applied twice so that removals of compound headers
# (which leave behind simple headers) get cleaned up on the second pass.
PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # "In Bristol Journal, 1758 October 1758" — compound date header
    # Must run before journal_header or it leaves orphaned simple headers.
    (
        "compound_date_header",
        re.compile(r"\s*\bIn\s+Bristol\s+Journal,?\s*\d{4}\s+\w+\s+\d{4}\s*", re.IGNORECASE),
        " ",
    ),
    # "Journal, 1758" section header bleed — only when it appears mid-text,
    # surrounded by sentence punctuation or whitespace. Never at position 0.
    (
        "journal_header",
        re.compile(r"(?<=[.!?])\s+Journal,?\s*\d{4}\s*[-–]?\s*", re.IGNORECASE),
        " ",
    ),
    # "See above, pp. 262-3" / "See above, p. 10"
    (
        "see_above",
        re.compile(r"\s*See above,?\s*pp?\.\s*\d+(?:[\-–,]\s*\d+)*\.?", re.IGNORECASE),
        "",
    ),
    # "See below, pp. 330, 331"
    (
        "see_below",
        re.compile(r"\s*See below,?\s*pp?\.\s*\d+(?:[\-–,]\s*\d+)*\.?", re.IGNORECASE),
        "",
    ),
    # "Cf. above, vol. iii. p. 368." — cross-references
    (
        "cf_ref",
        re.compile(r"\s*Cf\.\s+(?:above|below)?,?\s*(?:vol\.\s*[ivxlcd]+\.?,?\s*)?pp?\.\s*\d+(?:[\-–,\s]+\d+)*\.?", re.IGNORECASE),
        "",
    ),
    # Parenthetical editor citations: "(H. Moore's Life of Wesley, vol. ii. p. 186)"
    # Matches the shortest parenthetical containing any post-Wesley editor name.
    (
        "editorial_parens",
        re.compile(
            r"\s*\([^()]{0,250}?"
            r"(?:Tyerman|Whitehead|H\.\s*Moore|Moore'?s\s+Life|Curnock|Southey|"
            r"Atmore|W\.?\s*H\.?\s*S\.?|Standard\s+ed|Arminian\s+Magazine|"
            r"Methodist\s+Magazine|Meth\.\s*Mag\.|Wesley\s+Banner|Watson'?s\s+Reply)"
            r"[^()]{0,250}?\)",
            re.IGNORECASE,
        ),
        "",
    ),
    # "Tyerman's Life of Wesley, vol. ii. pp. 164-5" — inline, outside parens
    (
        "tyerman_inline",
        re.compile(
            r"\s*(?:See\s+)?(?:also\s+)?Tyerman'?s?(?:\s+Life\s+of\s+Wesley)?,?\s*"
            r"vol\.\s*[ivxlcd]+[.,]?\s*pp?\.\s*\d+(?:[\-–]\s*\d+)?\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    # "See W.H.S. Proceedings, vol. iv. p. 79" — Wesley Historical Society refs.
    # Eats an optional leading "See"/"also"/"See also" so nothing is orphaned.
    (
        "whs_proceedings",
        re.compile(
            r"\s*(?:See\s+)?(?:also\s+)?W\.?\s*H\.?\s*S\.?(?:\s+Proceedings)?,?\s*"
            r"vol\.\s*[ivxlcd]+[.,]?\s*pp?\.\s*\d+(?:[\-–]\s*\d+)?\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    # "Arminian Magazine, 1779, 598-601" and variants
    (
        "arminian_mag",
        re.compile(
            r"\s*(?:See\s+)?(?:in\s+the\s+)?Arminian\s+Magazine,?\s*\d{4},?\s*"
            r"(?:pp?\.\s*)?\d+(?:[\-–,\s]+\d+)*\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    # "Methodist Magazine, 1805, p 37" / "Meth. Mag. 1847, p. 869"
    (
        "methodist_mag",
        re.compile(
            r"\s*(?:See\s+)?(?:in\s+the\s+)?(?:Methodist|Meth\.)\s+(?:Magazine|Mag\.),?\s*\d{4},?\s*"
            r"(?:pp?\.\s*)?\d+(?:[\-–,\s]+\d+)*\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    # "Standard edition of the Journal vol 4. p."
    (
        "standard_ed",
        re.compile(
            r"\s*(?:the\s+)?Standard\s+ed(?:ition)?\s+of\s+the\s+Journal\s+"
            r"vol\.?\s*\d+\.?\s*p\.?\s*\d*\.?",
            re.IGNORECASE,
        ),
        "",
    ),
    # "Watson's Reply to Southey, p. 197 n." outside parens
    (
        "watsons_reply",
        re.compile(r"\s*Watson'?s\s+Reply\s+to\s+Southey,?\s*p\.\s*\d+(?:\s*n\.)?\.?", re.IGNORECASE),
        "",
    ),
    # "Note: John Wesley's personal copy of …." — editorial annotations
    (
        "note_insertion",
        re.compile(r"(?<=[.!?])\s+Note\s*[-—:]\s[^.]{0,150}\.", re.IGNORECASE),
        "",
    ),
    # "See Atmore's Memorial, p. 225."
    (
        "see_atmore",
        re.compile(r"\s*See\s+Atmore'?s\s+Memorial,?\s*p\.\s*\d+\.?", re.IGNORECASE),
        "",
    ),
    # "Green's Bibliography, No. 187"
    (
        "green_biblio",
        re.compile(r"\s*(?:a'?so\s+)?Green'?s\s+Bibliography,?\s*No\.\s*\d+\.?", re.IGNORECASE),
        "",
    ),
    # "Tyerman, vol. ii, p. 415" and similar editorial citations
    (
        "tyerman",
        re.compile(r"\s*Tyerman,?\s*vol\.\s*[ivxlcd]+,?\s*p\.\s*\d+\.?", re.IGNORECASE),
        "",
    ),
    # "I-gathered" / "I-went" / "I-rode" — orphan hyphen inside I-verb
    (
        "i_hyphen_verb",
        re.compile(r"\bI[-–](\w+ed|\w+t|went|rode|saw|had|was|did|came|met)\b"),
        r"I \1",
    ),
    # Orphaned dash at sentence start: ". -We rode" → ". We rode"
    (
        "sentence_dash",
        re.compile(r"(?<=[.!?])\s*[-–]\s*(I|We|He|She|They)\b"),
        r" \1",
    ),
    # Clean up multi-space after removals
    (
        "collapse_ws",
        re.compile(r"\s{2,}"),
        " ",
    ),
    # Orphaned punctuation clusters left when a citation is removed mid-sentence:
    # "p. 526;, and" → "p. 526, and"; ", :" → ":"; ",;" → ";"
    (
        "orphan_punct",
        re.compile(r"([,;:])\s*([,;:])"),
        r"\2",
    ),
    # ").; " orphan semicolon after a closing-paren-period, left when a follow-on
    # citation was removed. Safe because ").;" is never grammatical. Scripture
    # reference lists like "Luke xvii.; particularly" are not matched.
    (
        "orphan_paren_semi",
        re.compile(r"(\)\.)\s*;+\s+"),
        r"\1 ",
    ),
]


def clean(text: str, counter: dict[str, int]) -> str:
    # Two passes — compound removals can reveal simple patterns.
    for _ in range(2):
        for name, pat, repl in PATTERNS:
            new_text, n = pat.subn(repl, text)
            if n:
                counter[name] = counter.get(name, 0) + n
                text = new_text
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report only, don't write")
    ap.add_argument("--samples", type=int, default=3, help="Show N before/after examples")
    args = ap.parse_args()

    counter: dict[str, int] = {}
    samples: list[tuple[str, str, str]] = []  # (pattern, before, after)
    touched_passages = 0
    total_passages = 0

    out_path = SRC.with_suffix(".jsonl.tmp")
    out = None if args.dry_run else out_path.open("w")

    with SRC.open() as f:
        for line in f:
            total_passages += 1
            rec = json.loads(line)
            before = rec["text"]
            per_pattern_before = dict(counter)
            after = clean(before, counter)
            if after != before:
                touched_passages += 1
                if len(samples) < args.samples:
                    # Which pattern made the biggest difference in this passage?
                    triggered = [k for k in counter if counter[k] != per_pattern_before.get(k, 0)]
                    samples.append((",".join(triggered), before, after))
                rec["text"] = after
                rec["word_count"] = len(after.split())
            if out:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if out:
        out.close()

    print(f"\nTotal passages: {total_passages}")
    print(f"Passages touched: {touched_passages} ({touched_passages/total_passages*100:.1f}%)")
    print("\nHits per pattern:")
    for name in [p[0] for p in PATTERNS]:
        print(f"  {name:<22} {counter.get(name, 0):>6}")

    if samples:
        print(f"\n=== {len(samples)} sample diffs ===")
        for i, (trig, b, a) in enumerate(samples, 1):
            print(f"\n--- Sample {i} (triggered: {trig}) ---")
            print(f"BEFORE: {b[:400]}...")
            print(f"AFTER:  {a[:400]}...")

    if args.dry_run:
        print("\n[dry-run] No file written. Re-run without --dry-run to apply.")
    else:
        import shutil
        bak = SRC.with_suffix(".jsonl.bak")
        shutil.copy2(SRC, bak)
        out_path.replace(SRC)
        print(f"\nWrote {SRC}")
        print(f"Backup at {bak}")


if __name__ == "__main__":
    main()
