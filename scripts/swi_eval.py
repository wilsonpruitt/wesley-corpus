"""SWI v2 eval harness — Phase 2c (plans/2026-07-07-swi-v2-ocr-cleanup-verification.md).

Runs the LLM judge over metadata/swi-golden-set.jsonl and checks two things
per entry:
  1. overall_score falls within [expected_min, expected_max]
  2. every asserted expected_counter stance matches the judge's actual stance

This is the regression gate for every future rubric.py edit — run it before
any change ships, and always before a deploy (Phase 2e). Requires
ANTHROPIC_API_KEY (calls the judge directly, bypassing the cache/dispatcher
so every run is a fresh live score — that's the point of an eval).

Usage:
    python3 scripts/swi_eval.py              # full run, summary + failures
    python3 scripts/swi_eval.py --verbose    # print every entry
    python3 scripts/swi_eval.py --bucket wesley-core   # filter to one bucket

Exit code 0 iff every entry passes both checks.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (dev convenience only) — no new dependency for
    a trivial KEY=VALUE format. Does not override already-set env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE / ".env")

from strangely_warm_index import judge as swi_judge

GOLDEN_SET = BASE / "metadata" / "swi-golden-set.jsonl"


def load_golden_set(bucket_filter=None):
    entries = [json.loads(l) for l in open(GOLDEN_SET, encoding="utf-8")]
    if bucket_filter:
        entries = [e for e in entries if e["bucket"] == bucket_filter]
    return entries


def check_entry(entry: dict, result: dict) -> tuple[bool, list[str]]:
    """Returns (passed, list of failure reason strings)."""
    reasons = []
    score = result["overall_score"]
    lo, hi = entry["expected_min"], entry["expected_max"]
    if not (lo <= score <= hi):
        reasons.append(f"score {score} outside expected [{lo}, {hi}]")

    for ci, expected_stance in entry.get("expected_counter", {}).items():
        actual = result["counter_indicators"].get(ci, {}).get("stance")
        if actual != expected_stance:
            reasons.append(f"{ci}: expected stance '{expected_stance}', judge said '{actual}'")

    return (len(reasons) == 0, reasons)


def main():
    parser = argparse.ArgumentParser(description="SWI v2 golden-set regression eval")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--bucket", default=None, help="Filter to one bucket")
    args = parser.parse_args()

    entries = load_golden_set(args.bucket)
    if not entries:
        print(f"No golden-set entries matched bucket={args.bucket!r}")
        sys.exit(1)

    from strangely_warm_index.rubric import RUBRIC_VERSION
    print(f"Running judge over {len(entries)} golden-set entries (rubric {RUBRIC_VERSION})...\n")

    by_bucket = defaultdict(lambda: {"pass": 0, "fail": 0})
    failures = []

    for entry in entries:
        try:
            raw = swi_judge.score_with_judge(entry["text"])
        except Exception as e:
            passed, reasons = False, [f"judge call failed: {e}"]
            raw = None
        else:
            passed, reasons = check_entry(entry, raw)

        bucket = entry["bucket"]
        by_bucket[bucket]["pass" if passed else "fail"] += 1

        score_str = str(raw["overall_score"]) if raw else "ERR"
        mark = "PASS" if passed else "FAIL"
        line = (f"[{mark}] {entry['id']:34s} bucket={bucket:20s} "
                f"score={score_str:>4s} expect=[{entry['expected_min']},{entry['expected_max']}]")
        if args.verbose or not passed:
            print(line)
            if not passed:
                for r in reasons:
                    print(f"        - {r}")
                print(f"        rationale: {entry['rationale']}")
        if not passed:
            failures.append(entry["id"])

    total_pass = sum(b["pass"] for b in by_bucket.values())
    total_fail = sum(b["fail"] for b in by_bucket.values())

    print(f"\n=== By bucket ===")
    for bucket, counts in sorted(by_bucket.items()):
        print(f"  {bucket:24s} {counts['pass']}/{counts['pass']+counts['fail']} passed")

    print(f"\n{total_pass}/{total_pass + total_fail} PASS")
    if failures:
        print(f"FAILED: {failures}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
