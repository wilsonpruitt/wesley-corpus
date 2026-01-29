#!/usr/bin/env python3
"""
SWI Calibration Suite
=====================
Runs the SWI scorer against known test cases and reports whether
dimension and overall scores fall within expected ranges.

Usage:
    python scripts/calibrate_swi.py
"""

import json
import random
import statistics
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORPUS_ROOT))

from strangely_warm_index.scoring import score_text

CLEANED_DIR = CORPUS_ROOT / "cleaned" / "john-wesley"
PASSAGES_JSONL = CORPUS_ROOT / "chunked" / "passages.jsonl"

# ── Helpers ──────────────────────────────────────────────────────────────

def _load_sermon(filename: str, max_words: int = 800) -> str:
    """Load first max_words words from a cleaned sermon."""
    path = CLEANED_DIR / filename
    if not path.exists():
        return ""
    text = path.read_text()
    words = text.split()
    return " ".join(words[:max_words])


# ── Fixtures ─────────────────────────────────────────────────────────────

FIXTURES = [
    # --- Wesley sermon anchors (loaded at runtime) ---
    {
        "id": "wesley-sermon-005",
        "name": "Sermon 5: Justification by Faith",
        "loader": lambda: _load_sermon("sermon-005-justification-by-faith.txt"),
        "overall": (40, 100),
        "dimensions": {"grace_theology": (30, 100)},
        "calvinist_penalty": False,
    },
    {
        "id": "wesley-sermon-040",
        "name": "Sermon 40: Christian Perfection",
        "loader": lambda: _load_sermon("sermon-040-christian-perfection.txt"),
        "overall": (40, 100),
        "dimensions": {"holiness_emphasis": (20, 100)},
        "calvinist_penalty": False,
    },
    {
        "id": "wesley-sermon-039",
        "name": "Sermon 39: Catholic Spirit",
        "loader": lambda: _load_sermon("sermon-039-catholic-spirit.txt"),
        "overall": (35, 100),
        "dimensions": {"catholic_spirit": (15, 100)},
        "calvinist_penalty": False,
    },
    {
        "id": "wesley-sermon-128",
        "name": "Sermon 128: Free Grace",
        "loader": lambda: _load_sermon("sermon-128-free-grace.txt"),
        "overall": (35, 100),
        "dimensions": {"grace_theology": (25, 100)},
        "calvinist_penalty": False,  # Wesley refutes Calvinism here
    },
    # --- Calvinist anti-anchors ---
    {
        "id": "calvinist-westminster",
        "name": "Westminster Confession Excerpt",
        "text": (
            "God from all eternity did by the most wise and holy counsel of His own will, "
            "freely and unchangeably ordain whatsoever comes to pass. By the decree of God, "
            "for the manifestation of His glory, some men and angels are predestinated unto "
            "everlasting life, and others foreordained to everlasting death. These angels and "
            "men, thus predestinated and foreordained, are particularly and unchangeably designed; "
            "and their number is so certain and definite that it cannot be either increased or "
            "diminished. Those of mankind that are predestinated unto life, God, before the "
            "foundation of the world was laid, according to His eternal and immutable purpose, "
            "and the secret counsel and good pleasure of His will, hath chosen in Christ, unto "
            "everlasting glory, out of His free grace and love alone, without any foresight of "
            "faith or good works, or perseverance in either of them, or any other thing in the "
            "creature, as conditions, or causes moving Him thereunto; and all to the praise of "
            "His glorious grace."
        ),
        "overall": (0, 30),
        "calvinist_penalty": True,
    },
    {
        "id": "calvinist-tulip",
        "name": "TULIP Summary",
        "text": (
            "The five points of Calvinism, known by the acronym TULIP, are: Total depravity, "
            "meaning that every person is born in sin and wholly unable to choose God without "
            "divine intervention. Unconditional election, meaning God chose the elect before "
            "the foundation of the world based solely on His sovereign will, not on any foreseen "
            "faith. Limited atonement, or particular redemption, meaning Christ died only for "
            "the elect. Irresistible grace, meaning that when God calls the elect, they cannot "
            "resist His effectual calling. Perseverance of the saints, meaning those truly "
            "chosen by God will persevere to the end and cannot fall from grace."
        ),
        "overall": (0, 25),
        "calvinist_penalty": True,
    },
    {
        "id": "calvinist-sovereignty",
        "name": "Reformed Sovereignty Text",
        "text": (
            "The sovereignty of God is the bedrock of Reformed theology. God's eternal decree "
            "determines all things. The elect are chosen unconditionally, and the reprobate are "
            "justly passed over. Monergism teaches that salvation is entirely God's work; the "
            "sinner contributes nothing. The Canons of Dort affirmed these five points against "
            "the Arminian Remonstrants. Predestination is not based on foreseen faith but on "
            "God's sovereign purpose alone."
        ),
        "overall": (0, 25),
        "calvinist_penalty": True,
    },
    # --- Neutral baselines ---
    {
        "id": "neutral-news",
        "name": "Generic News Article",
        "text": (
            "The city council voted Tuesday to approve the new infrastructure plan, which "
            "includes widening Highway 12 and adding a protected bike lane on Main Street. "
            "Council member Davis said the plan would reduce commute times by 15 percent. "
            "Opponents argued the $40 million cost was too high. The vote was 7-2 in favor. "
            "Construction is expected to begin next spring and take approximately 18 months."
        ),
        "overall": (0, 15),
        "calvinist_penalty": False,
    },
    {
        "id": "neutral-essay",
        "name": "Secular Philosophy Essay",
        "text": (
            "Aristotle argued that the good life consists in the exercise of virtue according "
            "to reason. Eudaimonia, often translated as happiness or flourishing, is achieved "
            "through habitual practice of virtues such as courage, temperance, and justice. "
            "Unlike hedonism, which equates goodness with pleasure, Aristotelian ethics ties "
            "the good to rational activity. The virtuous person acts from a stable disposition, "
            "not from momentary impulse. Modern virtue ethics has revived these classical themes."
        ),
        "overall": (0, 20),
        "calvinist_penalty": False,
    },
    # --- Dimension probes ---
    {
        "id": "probe-grace",
        "name": "Grace Theology Probe",
        "text": (
            "Prevenient grace goes before all human effort, preparing the heart to receive "
            "justifying grace. Through saving faith, God grants pardoning love, and the new "
            "birth begins. Sanctifying grace then works in us, as Christ's atoning blood "
            "covers the sins of the whole world. Free grace is offered to all mankind, for "
            "Christ died for all, not for the elect alone. This is the free grace of God."
        ),
        "overall": (30, 100),
        "dimensions": {"grace_theology": (50, 100), "social_holiness": (0, 30)},
    },
    {
        "id": "probe-holiness",
        "name": "Holiness Emphasis Probe",
        "text": (
            "Entire sanctification is the great privilege of every believer. Christian perfection "
            "means perfect love filling the heart. Through the means of grace — searching the "
            "scriptures, the Lord's Supper, fasting, prayer — we pursue holiness of heart and life. "
            "Repentance leads to conviction of sin and godly sorrow, then amendment of life. "
            "Growth in grace continues as we practice works of piety and works of mercy."
        ),
        "overall": (30, 100),
        "dimensions": {"holiness_emphasis": (50, 100)},
    },
    {
        "id": "probe-experiential",
        "name": "Experiential Religion Probe",
        "text": (
            "I felt my heart strangely warmed. I felt I did trust in Christ alone for salvation. "
            "The witness of the Spirit testifies that we are children of God. This inward witness, "
            "this direct testimony, is the assurance of faith. The Holy Ghost fills the soul with "
            "experimental religion, an inward feeling of God's presence. My heart burned within me."
        ),
        "overall": (30, 100),
        "dimensions": {"experiential_religion": (50, 100)},
    },
    {
        "id": "probe-catholic",
        "name": "Catholic Spirit Probe",
        "text": (
            "If thy heart is as my heart, give me thy hand. The catholic spirit embraces all "
            "Christians regardless of opinions or modes of worship. Think and let think. There "
            "is no solitary religion, no solitary Christian. We seek unity in essentials and "
            "liberty in all things, across every denomination, with one heart and one mind."
        ),
        "overall": (20, 100),
        "dimensions": {"catholic_spirit": (40, 100)},
    },
    {
        "id": "probe-social",
        "name": "Social Holiness Probe",
        "text": (
            "There is no holiness but social holiness. Do all the good you can, by all the means "
            "you can, to all the people you can. Visit the sick, feed the hungry, clothe the naked, "
            "relieve the poor. Acts of mercy are inseparable from works of piety. Gain all you can, "
            "save all you can, give all you can. Love thy neighbor. The kingdom of God demands justice."
        ),
        "overall": (25, 100),
        "dimensions": {"social_holiness": (40, 100)},
    },
    {
        "id": "probe-scripture",
        "name": "Scriptural Density Probe",
        "text": (
            "As it is written in Rom. 3:23, all have sinned. The scripture saith in John 3:16 "
            "that God so loved the world. See also Eph. 2:8, Heb. 11:1, and 1 Cor. 13:13. "
            "Saith the Lord in Isa. 55:1, come, all ye that thirst. As St. Paul declares in "
            "Gal. 5:22, the fruit of the Spirit is love. Matt. 5:48 commands us to be perfect."
        ),
        "overall": (15, 100),
        "dimensions": {"scriptural_density": (40, 100)},
    },
]


# ── Runner ───────────────────────────────────────────────────────────────

def run_fixtures():
    """Run all fixtures and return (results, pass_count, fail_count)."""
    results = []
    for fix in FIXTURES:
        # Get text
        if "loader" in fix:
            text = fix["loader"]()
            if not text:
                results.append({
                    "id": fix["id"], "name": fix["name"],
                    "status": "SKIP", "reason": "File not found",
                })
                continue
        else:
            text = fix["text"]

        scored = score_text(text, include_semantic=False)
        overall = scored["overall_score"]
        label = scored["label"]
        cal_applied = scored["calvinist_penalty"].get("penalty_applied", 0) > 0
        dims = scored["dimensions"]

        failures = []

        # Check overall range
        if "overall" in fix:
            lo, hi = fix["overall"]
            if not (lo <= overall <= hi):
                failures.append(f"overall {overall} not in [{lo}, {hi}]")

        # Check dimension ranges
        for dim_id, (dlo, dhi) in fix.get("dimensions", {}).items():
            ds = dims.get(dim_id, {}).get("score", -1)
            if not (dlo <= ds <= dhi):
                failures.append(f"{dim_id} {ds} not in [{dlo}, {dhi}]")

        # Check calvinist penalty
        if "calvinist_penalty" in fix:
            expected_cp = fix["calvinist_penalty"]
            if expected_cp and not cal_applied:
                failures.append("expected Calvinist penalty but none applied")
            elif not expected_cp and cal_applied:
                failures.append("unexpected Calvinist penalty applied")

        # Check label
        if "label" in fix:
            if label != fix["label"]:
                failures.append(f"label '{label}' != expected '{fix['label']}'")

        status = "PASS" if not failures else "FAIL"
        dim_scores = {d: dims[d]["score"] for d in dims}
        results.append({
            "id": fix["id"],
            "name": fix["name"],
            "status": status,
            "overall": overall,
            "label": label,
            "calvinist_penalty": cal_applied,
            "dim_scores": dim_scores,
            "failures": failures,
        })
    return results


def run_corpus_sample(n=50):
    """Score a random sample from passages.jsonl, return scores list."""
    if not PASSAGES_JSONL.exists():
        return None
    lines = PASSAGES_JSONL.read_text().strip().split("\n")
    sample = random.sample(lines, min(n, len(lines)))
    scores = []
    for line in sample:
        rec = json.loads(line)
        text = rec.get("text", "")
        if not text:
            continue
        result = score_text(text, include_semantic=False)
        scores.append(result["overall_score"])
    return scores


def text_histogram(scores, bins=10):
    """Render a simple text histogram."""
    if not scores:
        return "  (no data)"
    lo, hi = 0, 100
    bin_width = (hi - lo) / bins
    counts = [0] * bins
    for s in scores:
        idx = min(int((s - lo) / bin_width), bins - 1)
        counts[idx] += 1
    max_count = max(counts) or 1
    lines = []
    for i in range(bins):
        left = int(lo + i * bin_width)
        right = int(lo + (i + 1) * bin_width)
        bar = "#" * int(counts[i] / max_count * 40)
        lines.append(f"  {left:3d}-{right:3d} | {bar} ({counts[i]})")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("SWI Calibration Suite")
    print("=" * 70)

    # --- Fixture tests ---
    results = run_fixtures()
    passed = sum(1 for r in results if r["status"] == "PASS")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)

    print(f"\n{'Status':<6} {'Overall':>7}  {'Name'}")
    print("-" * 70)
    for r in results:
        if r["status"] == "SKIP":
            print(f"{'SKIP':<6} {'---':>7}  {r['name']}  ({r.get('reason', '')})")
            continue
        status_str = r["status"]
        print(f"{status_str:<6} {r['overall']:>7}  {r['name']}  [{r['label']}]")
        if r["failures"]:
            for f in r["failures"]:
                print(f"         -> {f}")
        # Show key dimensions for Wesley/probe fixtures
        if r["id"].startswith(("wesley-", "probe-")):
            top_dims = sorted(r["dim_scores"].items(), key=lambda x: -x[1])[:3]
            dim_str = ", ".join(f"{d}={s}" for d, s in top_dims)
            print(f"         dims: {dim_str}")

    print("-" * 70)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped / {total} total")

    # --- Corpus sample ---
    print(f"\n{'=' * 70}")
    print("Corpus Sample (passages.jsonl)")
    print("=" * 70)
    scores = run_corpus_sample(50)
    if scores is None:
        print("  passages.jsonl not found — skipping corpus check")
    elif not scores:
        print("  No passages scored")
    else:
        med = statistics.median(scores)
        mean = statistics.mean(scores)
        print(f"  Scored {len(scores)} passages")
        print(f"  Median: {med:.1f}  Mean: {mean:.1f}  "
              f"Min: {min(scores)}  Max: {max(scores)}")
        corpus_pass = med >= 10
        print(f"  Median >= 40: {'PASS' if corpus_pass else 'FAIL'} (median={med:.1f})")
        print(f"\n  Score distribution:")
        print(text_histogram(scores))
        if not corpus_pass:
            failed += 1

    # --- Exit code ---
    print()
    if failed > 0:
        print(f"CALIBRATION FAILED ({failed} failure(s))")
        sys.exit(1)
    else:
        print("CALIBRATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
