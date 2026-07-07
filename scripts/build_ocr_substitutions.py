"""Phase 2: dictionary-gated OCR substitution table.

plans/2026-07-07-swi-v2-ocr-cleanup-verification.md, Part 2 Phase 2:
"From the Phase 0 non-word list: for each non-word with frequency >= 3,
generate candidate fixes via known OCR confusion pairs ... accept only if
the result is a dictionary/period word and the garble itself is not."

Read-only. Writes metadata/ocr-substitutions.csv for Wilson to review once;
nothing is applied to the corpus by this script. Reuses noise_report.py's
dictionary + proper-noun-whitelist logic so "non-word" means the same thing
in both reports.

Usage: python3 scripts/build_ocr_substitutions.py
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from noise_report import load_dictionary, harvest_proper_noun_whitelist, WORD_RE
from morphology import is_regular_inflection

ROOT = Path(__file__).resolve().parent.parent
PASSAGES = ROOT / "chunked" / "cleaned_passages.jsonl"
OUT_CSV = ROOT / "metadata" / "ocr-substitutions.csv"

MIN_COUNT = 3
MIN_FIX_LEN = 3  # avoid noise from 1-2 char "fixes"

# (garble_substring, fix_substring) -- OCR confusion pairs.
#
# Evidence run 2026-07-07: tried the full plan-documented set (li<->h,
# rn<->m, c<->e, f<->s, p<->d, t<->l, vv<->w, i<->l<->1) against this corpus.
# Only f->s (long-s "ſ" misread as "f", the classic 18th-c. typesetting
# artifact -- fhould->should, fpoonful->spoonful, philofophical->
# philosophical, dozens more, concentrated in Primitive Physick) held up:
# effectively 100% correct at every token length. Every other pair produced
# far more noise than signal at this corpus's token lengths -- coincidental
# hits on real English words the dictionary is missing (wilful->witful,
# overtook->overlook), proper names (Dermot->Dermol, Matlock->Mattock),
# Latin quotations misread as English non-words (imperii->imperil), and
# hyphenation-split fragments that need REJOINING, not substitution
# (tion->lion, ture->lure, ful->fut -- these are de-hyphenation candidates,
# a distinct and still-open piece of Phase 1, not a confusion-pair fix).
# Kept narrow rather than shipping a noisy table Wilson has to hand-audit.
CONFUSION_PAIRS = [
    ("f", "s"),
]

# Manual context review 2026-07-07: even within the trusted f->s rule, these
# tokens are NOT long-s garbles -- they're hyphenation-split fragments
# (fol- "lowers" = followers; suf- 616 = suffering, cross-column table
# bleed; dif- cern'd = discerned; uncom|fortable = uncomfortable; fer|tile
# = fertile) or Latin quotation text mistaken for English ("fac ut proxumo
# ... vincas" -- Latin "fac", not "sac"), or too garbled to trust (Fal n /
# IFT / fea contexts are themselves damaged beyond a single-substitution
# repair). The f->s rule's candidate is technically dictionary-valid but
# wrong in context -- caught by reading every row, not by a mechanical
# filter. Excluded rather than shipped for Wilson to also have to catch.
#
# Second pass 2026-07-07 (systematic, not spot-check): for every remaining
# candidate, checked whether the word immediately before it in its sample
# context concatenates into a real dictionary word -- catches the same
# fragment failure mode at a prefix length the first pass's context read
# missed. Found 5 more, and verified EVERY occurrence of each across the
# whole corpus (not just the sample), not just one: "fect"/"fection" are
# always "per-fect(ion)" (perfect/perfection), never "sect"/"section" (10
# and 14 occurrences respectively, zero counterexamples); "fession" is
# always "con-/pro-fession" (confession/profession), never "session" (3/3);
# "fane"/"faneness" are always "pro-fane(ness)" (profane/profaneness),
# never "sane"/"saneness" (3/3 and 3/3).
KNOWN_FALSE_POSITIVES = {
    "fol", "suf", "dif", "fortable", "fer", "fac", "Fal", "IFT", "fea",
    "fect", "fection", "fession", "fane", "faneness",
    # Third pass: checked EVERY occurrence corpus-wide (not just the
    # sample) for tokens with any Latin-quotation signal nearby. "fuit" is
    # genuine Latin ("was/has been") in 10 of 11 occurrences -- sermons and
    # journal entries quoting Latin tags ("vir magnus...fuit", "Nam fuit
    # ante Helenam", "seges est ubi Troja fuit"). Only 1/11 is the true
    # English garble ("To fuit the quality...food" = "suit", Primitive
    # Physick). A blanket fix would correct 1 and corrupt 10 Latin
    # quotations -- excluded (the one true positive is an acceptable loss
    # for a table meant to ship unattended).
    "fuit",
}


def generate_candidates(token_lower):
    """Yield (candidate, rule) for every single-occurrence substitution."""
    for garble, fix in CONFUSION_PAIRS:
        for m in re.finditer(re.escape(garble), token_lower):
            candidate = token_lower[:m.start()] + fix + token_lower[m.end():]
            if candidate != token_lower:
                yield candidate, f"{garble}->{fix}"


def restore_case(fixed_lower, original):
    """Best-effort: mirror the original token's capitalization pattern."""
    if original.isupper():
        return fixed_lower.upper()
    if original[0].isupper():
        return fixed_lower[0].upper() + fixed_lower[1:]
    return fixed_lower


def main():
    dictionary = load_dictionary()

    passages_by_source = defaultdict(list)
    all_passages = []
    with open(PASSAGES, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            passages_by_source[d["source_id"]].append(d["text"])
            all_passages.append(d)

    proper_nouns = harvest_proper_noun_whitelist(passages_by_source)
    print(f"Dictionary: {len(dictionary)} words. Proper-noun whitelist: {len(proper_nouns)} tokens.")

    # Global non-word frequency + first-seen sample passage.
    non_word_counts = Counter()
    sample_context = {}
    sample_id = {}
    for d in all_passages:
        for tok in WORD_RE.findall(d["text"]):
            low = tok.lower().strip("'")
            if not low or len(low) <= 1:
                continue
            if low in dictionary or low in proper_nouns:
                continue
            if is_regular_inflection(low, dictionary):
                continue
            non_word_counts[tok] += 1
            if tok not in sample_context:
                i = d["text"].find(tok)
                sample_context[tok] = d["text"][max(0, i - 30): i + 40].replace("\n", " ")
                sample_id[tok] = d["id"]

    candidates_at_min = {t: n for t, n in non_word_counts.items() if n >= MIN_COUNT}
    print(f"Non-words with count >= {MIN_COUNT}: {len(candidates_at_min)}")

    rows = []
    ambiguous = 0
    for token, count in candidates_at_min.items():
        if token in KNOWN_FALSE_POSITIVES:
            continue
        low = token.lower()
        valid_fixes = set()
        rules_used = set()
        for cand_lower, rule in generate_candidates(low):
            if len(cand_lower) < MIN_FIX_LEN:
                continue
            if cand_lower in dictionary and cand_lower != low:
                valid_fixes.add(cand_lower)
                rules_used.add(rule)
        if not valid_fixes:
            continue
        if len(valid_fixes) == 1:
            fix_lower = next(iter(valid_fixes))
            fix = restore_case(fix_lower, token)
            rows.append({
                "garble": token,
                "fix": fix,
                "count": count,
                "rule": ";".join(sorted(rules_used)),
                "ambiguous": "",
                "sample_passage_id": sample_id[token],
                "sample_context": sample_context[token],
            })
        else:
            ambiguous += 1
            rows.append({
                "garble": token,
                "fix": "AMBIGUOUS: " + " | ".join(sorted(valid_fixes)),
                "count": count,
                "rule": ";".join(sorted(rules_used)),
                "ambiguous": "yes",
                "sample_passage_id": sample_id[token],
                "sample_context": sample_context[token],
            })

    rows.sort(key=lambda r: -r["count"])

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "garble", "fix", "count", "rule", "ambiguous",
            "sample_passage_id", "sample_context",
        ])
        writer.writeheader()
        writer.writerows(rows)

    unambiguous = len(rows) - ambiguous
    print(f"Wrote {len(rows)} candidate fixes -> {OUT_CSV}")
    print(f"  {unambiguous} single-candidate fixes, {ambiguous} ambiguous (multiple candidates -- needs a human pick)")
    print("\nTop 20 by frequency:")
    for r in rows[:20]:
        print(f"  {r['count']:>4}  {r['garble']!r:25s} -> {r['fix']}")


if __name__ == "__main__":
    main()
