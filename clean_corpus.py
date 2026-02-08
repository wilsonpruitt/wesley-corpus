#!/usr/bin/env python3
"""Clean OCR artifacts from the entire Wesley corpus.

Reads chunked/passages.jsonl, applies OCR cleaning to each passage's text field,
and writes chunked/cleaned_passages.jsonl. The original file is preserved.

Usage:
    python3 clean_corpus.py              # clean and write output
    python3 clean_corpus.py --dry-run    # preview stats without writing
"""

import argparse
import json
from pathlib import Path

from ocr_cleaning import clean_text, artifact_density

BASE = Path(__file__).parent
INPUT_PATH = BASE / "chunked" / "passages.jsonl"
OUTPUT_PATH = BASE / "chunked" / "cleaned_passages.jsonl"


def main():
    parser = argparse.ArgumentParser(description="Clean OCR artifacts from the Wesley corpus.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show stats without writing output file")
    args = parser.parse_args()

    # Load passages
    passages = []
    with open(INPUT_PATH) as f:
        for line in f:
            if line.strip():
                passages.append(json.loads(line))

    print("Loaded %d passages from %s" % (len(passages), INPUT_PATH))

    # Clean
    changed = 0
    density_before_sum = 0.0
    density_after_sum = 0.0

    for p in passages:
        original = p["text"]
        cleaned = clean_text(original)

        density_before_sum += artifact_density(original)
        density_after_sum += artifact_density(cleaned)

        if cleaned != original:
            changed += 1
            p["text"] = cleaned
            p["word_count"] = len(cleaned.split())

    n = len(passages)
    avg_before = density_before_sum / n if n else 0
    avg_after = density_after_sum / n if n else 0

    print("\n-- Stats --")
    print("  Passages processed: %d" % n)
    print("  Passages changed:   %d (%.1f%%)" % (changed, 100.0 * changed / n if n else 0))
    print("  Avg artifact density before: %.4f" % avg_before)
    print("  Avg artifact density after:  %.4f" % avg_after)

    if args.dry_run:
        print("\n[DRY RUN] No output file written.")
        return

    # Write cleaned corpus
    with open(OUTPUT_PATH, "w") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("\nWrote %s" % OUTPUT_PATH)


if __name__ == "__main__":
    main()
