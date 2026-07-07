#!/usr/bin/env python3.11
"""Run metadata/sentinel-quotes.jsonl against the serving corpus.

Phase 3c regression net (plans/2026-07-07-swi-v2-ocr-cleanup-verification.md).
Cheap + deterministic — no LLM. Run before AND after every OCR cleanup / re-chunk
to prove the cleanup closed damage without opening new gaps.

For each sentinel:
  present  -> anchor must locate a passage in the expected source_id (or anywhere),
              and canonical wording must match within tolerance (SequenceMatcher).
  absent   -> anchor must NOT appear anywhere (anti-contamination tripwire).

Exit code 0 iff every sentinel passes. Use as a CI-style gate.

  python3.11 scripts/check_sentinels.py            # summary
  python3.11 scripts/check_sentinels.py --verbose  # per-sentinel detail
"""
import json, os, sys, re
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVING = os.path.join(ROOT, "chunked", "cleaned_passages.jsonl")
SENTINELS = os.path.join(ROOT, "metadata", "sentinel-quotes.jsonl")
WORDING_TOL = 0.82  # normalized-similarity floor for a "wording OK" pass

VERBOSE = "--verbose" in sys.argv

rows = [json.loads(l) for l in open(SERVING, encoding="utf-8")]
sentinels = [json.loads(l) for l in open(SENTINELS, encoding="utf-8")]


def norm(t):
    return re.sub(r"[^a-z0-9 ]", " ", t.lower())


def collapse(t):
    return re.sub(r"\s+", " ", norm(t)).strip()


def in_scope(row, source_id):
    """source_id is a prefix: matches the true source, or a passage-id prefix."""
    return source_id and (row["source_id"] == source_id or row["id"].startswith(source_id))


def best_match(anchor, canonical, source_id=None):
    """Among ALL chunks containing the anchor, return the best wording match,
    preferring in-scope passages when scores tie-ish."""
    a = anchor.lower()
    hits = [r for r in rows if a in r["text"].lower()]
    if not hits:
        return None, 0.0, False
    scored = []
    for r in hits:
        sc = wording_score(canonical, r["text"])
        # small bonus keeps an in-scope passage ahead of an incidental mention elsewhere
        scored.append((sc + (0.05 if in_scope(r, source_id) else 0.0), sc, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    _, raw, r = scored[0]
    return r, raw, in_scope(r, source_id)


def wording_score(canonical, passage_text):
    """Best sliding-window similarity of canonical against the passage."""
    c = collapse(canonical)
    p = collapse(passage_text)
    if c in p:
        return 1.0
    # window the passage to canonical length +/- slack, take best ratio
    cw = c.split()
    pw = p.split()
    L = len(cw)
    if L == 0 or not pw:
        return 0.0
    best = 0.0
    step = max(1, L // 6)
    for i in range(0, max(1, len(pw) - L + 1), step):
        window = " ".join(pw[i:i + L + 4])
        best = max(best, SequenceMatcher(None, c, window).ratio())
        if best >= 0.999:
            break
    return best


results = []
for s in sentinels:
    exp = s.get("expect", "present")
    if exp == "absent":
        found = [r for r in rows if s["anchor"].lower() in r["text"].lower()]
        ok = not found
        results.append((s, "PASS" if ok else "FAIL",
                        "absent as required" if ok else f"CONTAMINATION in {found[0]['id']}", None))
        continue
    passage, score, scoped = best_match(s["anchor"], s["canonical"], s.get("source_id"))
    if passage is None:
        results.append((s, "FAIL", "anchor not found (missing content or heavy OCR damage)", None))
        continue
    scope_note = "" if scoped else f" [found in {passage['source_id']}, not expected {s.get('source_id')}]"
    if score >= WORDING_TOL:
        results.append((s, "PASS", f"wording {score:.2f} @ {passage['id']}{scope_note}", score))
    else:
        results.append((s, "WORDING", f"located but drifted {score:.2f} @ {passage['id']}{scope_note}", score))

npass = sum(1 for _, v, *_ in results if v == "PASS")
nword = sum(1 for _, v, *_ in results if v == "WORDING")
nfail = sum(1 for _, v, *_ in results if v == "FAIL")

for s, verdict, detail, score in results:
    if VERBOSE or verdict != "PASS":
        mark = {"PASS": "  ok  ", "WORDING": " drift", "FAIL": " FAIL "}[verdict]
        print(f"[{mark}] {s['id']:38s} {detail}")

print(f"\n{npass} PASS · {nword} WORDING-DRIFT · {nfail} FAIL   of {len(results)} sentinels")
print("(WORDING-DRIFT / FAIL are the OCR + missing-content net; expected high pre-cleanup.)")
sys.exit(0 if nfail == 0 and nword == 0 else 1)
