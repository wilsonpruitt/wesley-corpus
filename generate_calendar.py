#!/usr/bin/env python3
"""Generate a monthly social media calendar from the Wesley corpus.

Reads passages from chunked/passages.jsonl, extracts the best tweetable
sentence from each, and outputs:
  - social-calendar/calendar.csv  (Buffer-compatible)
  - social-calendar/calendar.md   (readable markdown)
"""

import csv
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ocr_cleaning import clean_text, artifact_density

# ── Configuration ────────────────────────────────────────────────────────────

NUM_POSTS = 10  # Buffer free plan limit; rerun every ~2 weeks
POST_TIME = "09:00"  # daily posting time
MIN_SENTENCE_LEN = 60
MAX_SENTENCE_LEN = 240  # leaves room for "\n\n— Author Name"
MAX_TWEET_LEN = 280
ARTIFACT_THRESHOLD = 0.05  # skip passage if >5% non-alpha (excl spaces/punct)

AUTHOR_DISPLAY = {
    "john-wesley": "John Wesley",
    "charles-wesley": "Charles Wesley",
}

CORPUS_PATH = Path(__file__).parent / "chunked" / "cleaned_passages.jsonl"
OUTPUT_DIR = Path(__file__).parent / "social-calendar"


# ── Tweet-Selection Patterns ─────────────────────────────────────────────────

# Hymn/section numbers like "540 Hymns of Adoration."
HYMN_HEADER_RE = re.compile(r'^\d+\s+[A-Z][a-z]+.*\.')

# Scripture footnote references: "* Cor, xi", "Ezek. xxxvi. 26", "+ Heb. viii."
SCRIPTURE_FOOTNOTE_RE = re.compile(
    r'^\s*[\*\+]?\s*\d?\s*[A-Z][a-z]+\.?\s+[ivxlc]+',
    re.I
)

# Editorial commentary patterns (modern annotations, not Wesley's words)
EDITORIAL_RES = [
    re.compile(p, re.I) for p in [
        r'\bnotice\s+this\b',
        r'\bdiscuss\b',
        r'\bhow\s+would\s+you\b',
        r'\bwhat\s+activities\b',
        r'\bquestions?\s+to\s+discuss\b',
        r'\bcan\s+young\s+people\b',
        r'\bhow\s+much\s+do\s+names\b',
        r'\bhere\'?s\s+a\s+brief\s+note\b',
        r'\bin\s+plain\s+english,?\s+wesley\b',
        r'\bthis\s+was\s+truer\b',
        r'\bin\s+those\s+days\b',
        r'\bwesley\s+begins\b',
        r'\bwesley\'?s\s+(?:usual|objective)\b',
        r'\bfor\s+wesley\b',
        r'\bthe\s+methodist\s+movement\b',
        r'\bthe\s+official\s+church\b',
        r'\balong\s+with\s+other\s+(?:christian\s+)?denominations\b',
        r'\bprotestant\s+churches\b',
        r'\bin\s+the\s+18th\s+century\b',
        r'\bin\s+mainstream\s+usage\b',
        r'\bnote:\s',
        r'\bif\s+you\'?ve\s+ever\s+seen\b',
        r'\bby\s+the\s+way\b',
    ]
]



# ── Sentence Extraction ──────────────────────────────────────────────────────

def split_sentences(text):
    """Split text into sentences."""
    # Split on sentence-ending punctuation followed by space + uppercase or quote
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'])', text)
    result = []
    for part in parts:
        s = part.strip()
        if s:
            result.append(s)
    return result


def is_editorial(sentence):
    """Check if a sentence is editorial commentary rather than Wesley's words."""
    for pattern in EDITORIAL_RES:
        if pattern.search(sentence):
            return True
    return False


def has_ocr_problems(sentence):
    """Check if sentence has obvious OCR issues that make it unreadable."""
    # Caret/hat symbols from OCR
    if '^' in sentence:
        return True
    # Lots of single-char words (OCR fragments)
    words = sentence.split()
    if len(words) > 3:
        single_char = sum(1 for w in words if len(w) == 1 and w not in 'AIa')
        if single_char / len(words) > 0.2:
            return True
    # Consecutive consonants suggesting garbled text
    if re.search(r'[bcdfghjklmnpqrstvwxyz]{5,}', sentence, re.I):
        return True
    # Non-Latin characters (Greek, Hebrew, etc.)
    if re.search(r'[\u0370-\u03FF\u0400-\u04FF\u0590-\u05FF]', sentence):
        return True
    # Numbers stuck to words: "in28" or "4Uo"
    if re.search(r'[a-z]\d{2,}', sentence) or re.search(r'\d[A-Z][a-z]', sentence):
        return True
    # Stray hyphens stuck to words: "of -body"
    if re.search(r'\s-\w|\w-\s', sentence):
        return True
    # Words stuck together (missing space): "muchholier", "hisservice", "ofGod"
    # Detect by looking for lowercase immediately followed by uppercase mid-word
    if re.search(r'[a-z]{2}[A-Z]', sentence):
        return True
    # Also detect unusually long "words" that are likely stuck-together words
    for word in sentence.split():
        # Strip punctuation for checking
        clean_word = re.sub(r'[^a-zA-Z]', '', word)
        if len(clean_word) > 14 and clean_word.islower():
            return True
    # Stray OCR quote artifacts: '"¢' or similar
    if re.search(r'["\'][^a-zA-Z\s]', sentence):
        return True
    # OCR space-within-word: "bless ing", "happi ness" (3+ letters, space, 3+ letters
    # where the right part is a common suffix)
    common_suffixes = ['ing', 'tion', 'ness', 'ment', 'ful', 'less', 'ous', 'ive',
                       'able', 'ible', 'ally', 'erly', 'ance', 'ence',
                       'gation', 'dence', 'ance']
    for suffix in common_suffixes:
        if re.search(r'\b\w{2,}\s+' + suffix + r'\b', sentence):
            return True
    # Lowercase words stuck together without space: "dayand", "allthe"
    common_stuck = [r'dayand', r'nightand', r'allthe', r'forthe', r'inthe',
                    r'ofthe', r'tothe', r'fromthe', r'withthe', r'andthe']
    for stuck in common_stuck:
        if re.search(stuck, sentence, re.I):
            return True
    # "HYMN" or "l. m." in body text (metadata)
    if re.search(r'\bHYMN\s+\d+\b', sentence):
        return True
    if re.search(r'\bl\.\s*m\.\s*$', sentence):
        return True
    # Table of contents / page reference style: "Page VI 1 Time"
    if re.search(r'\bPage\s+[IVXLC]+\b', sentence):
        return True
    # Latin text detection: multiple consecutive Latin words
    latin_words = ['quo', 'mare', 'tellus', 'ardeat', 'mundi', 'moles',
                   'operosa', 'laboret', 'caeli', 'correptaque', 'regia']
    latin_count = sum(1 for w in latin_words if w in sentence.lower())
    if latin_count >= 2:
        return True
    # Multiple exclamation/question marks in weird places
    if len(re.findall(r'[!?]', sentence)) > 3:
        return True
    # Parentheses/brackets in the middle of words (OCR garbage)
    if re.search(r'\w[)\]]\s*\w\s+\w{1,3}\s+\w', sentence):
        return True
    # Redacted/abbreviated names: "Al r M r" or "R d N e"
    if re.search(r'\b[A-Z]\w?\s+[a-z]\b', sentence):
        # Could be abbreviations — check for multiple single-letter words near uppercase
        abbrev_matches = re.findall(r'\b[A-Z][a-z]?\s+[a-z]\b', sentence)
        if len(abbrev_matches) >= 2:
            return True
    return False


def score_sentence(sentence):
    """Score a sentence for tweet-worthiness. Higher is better."""
    score = 0.0

    length = len(sentence)

    # Prefer longer sentences (more complete thoughts), sweet spot 120-200 chars
    if length >= 120:
        score += 30
    elif length >= 80:
        score += 20
    else:
        score += 10

    # Penalize artifact density
    density = artifact_density(sentence)
    score -= density * 100

    # Bonus for sentences ending with proper punctuation
    if sentence.endswith('.') or sentence.endswith('!') or sentence.endswith('"'):
        score += 10
    # Penalize fragments that don't end properly
    elif not sentence[-1] in '.!?"\'':
        score -= 15

    # Penalize sentences with lots of numbers
    num_count = len(re.findall(r'\d+', sentence))
    score -= num_count * 5

    # Penalize sentences with parenthetical references
    if re.search(r'\(\w+\s+\d+\)', sentence):
        score -= 10

    # Bonus for inspirational/theological keywords
    inspirational = ['love', 'grace', 'faith', 'hope', 'peace', 'joy',
                     'mercy', 'heart', 'soul', 'holy', 'God', 'Christ',
                     'righteousness', 'truth', 'wisdom', 'prayer',
                     'salvation', 'eternal', 'heaven', 'spirit']
    for word in inspirational:
        if re.search(r'\b' + word + r'\b', sentence, re.I):
            score += 3

    # Penalize negative/harsh content (less suitable for social media)
    harsh = ['drunkenness', 'hell', 'brimstone', 'damnation', 'wrath',
             'damned', 'cursed', 'perishing']
    for word in harsh:
        if re.search(r'\b' + word + r'\b', sentence, re.I):
            score -= 5

    # Penalize letter salutations
    if re.search(r'\bDEAR\s+[A-Z]', sentence):
        score -= 40
    if re.search(r'\bMY\s+DEAR\b', sentence):
        score -= 40
    if re.search(r'\bREVERAND\b', sentence, re.I):
        score -= 40

    # Penalize argumentative/polemical content
    polemical = ['adversaries', 'lying', 'liars', 'absurd', 'nonsense',
                 'ignorance', 'ignorant', 'enemies', 'foolish']
    for word in polemical:
        if re.search(r'\b' + word + r'\b', sentence, re.I):
            score -= 3

    # Penalize sentences that start with conjunctions (likely mid-thought)
    if re.match(r'^(?:And|But|Or|For|Nor|Yet|So)\b', sentence):
        score -= 5

    # Heavily penalize sentences ending with prepositions/articles/abbrevs (cut off)
    if re.search(r'\b(?:in|at|to|of|the|a|an|with|from|Dr|Mr|Mrs|Vol|St)\.*\s*$', sentence):
        score -= 50

    return score


def extract_best_sentence(text):
    # type: (str) -> Optional[str]
    """Extract the best tweetable sentence from cleaned text."""
    sentences = split_sentences(text)
    candidates = []

    for s in sentences:
        # Strip leading section markers: "1.", "2.", "Sect. I."
        s = re.sub(r'^\s*(?:\d+\.?\s+|Sect\.\s*[IVXLC]+\.?\s*)', '', s)
        # Strip trailing section numbers: "...wisdom. 2." -> "...wisdom."
        s = re.sub(r'\s+\d+\.\s*$', '', s)
        # Remove parenthetical section markers: "(2)", "(3)"
        s = re.sub(r'\s*\(\d+\)\s*', ' ', s)
        # Remove trailing isolated markers like "2 Lo !" or "9 High above"
        s = re.sub(r'\s+\d+\s+[A-Z][a-z]*\s*!?\s*$', '', s)
        s = s.strip()

        if not s:
            continue

        # Skip scripture footnotes
        if SCRIPTURE_FOOTNOTE_RE.match(s):
            continue

        # Skip editorial content
        if is_editorial(s):
            continue

        # Skip if obvious OCR problems
        if has_ocr_problems(s):
            continue

        # Length filter
        if len(s) < MIN_SENTENCE_LEN or len(s) > MAX_SENTENCE_LEN:
            continue

        # Skip sentences that are mostly uppercase (headers/titles)
        alpha_chars = [c for c in s if c.isalpha()]
        if alpha_chars:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio > 0.35:
                continue

        # Skip hymn/section headers
        if HYMN_HEADER_RE.match(s):
            continue

        # Skip sentences that look like letter openings/closings
        if re.match(r'^(?:Your\s+(?:affectionate|obedient|humble)|I\s+am,?\s+(?:dear|with|your))', s, re.I):
            continue
        if re.search(r'Your\s+(?:affectionate|obliged|obedient)\s+', s, re.I):
            continue
        # Skip sentences containing letter salutations
        if re.search(r'MY DEAR\b', s):
            continue

        # Skip sentences that start lowercase (mid-sentence fragments)
        if s[0].islower():
            continue

        # Skip sentences containing Latin/foreign phrases
        if re.search(r'\b(?:Nihil|quod|hactenus|feci|focis|aris)\b', s):
            continue

        # Skip sentences that look like addresses or titles
        if re.match(r'^[A-Z][a-z]+\'?s?\s+[A-Z][a-z]+,\s+(?:In|At|Near)\s', s):
            continue
        # Skip "To Miss X, At Y" address lines
        if re.match(r'^To\s+(?:Miss|Mrs|Mr|Dr)\s', s):
            continue
        # Skip sentences with repeated words from editorial annotations
        if re.search(r'\b(\w{4,})\s+\1\b', s):
            continue
        # Skip "Alter'd from" / attribution lines
        if re.match(r"^Alter'?d\s+from\b", s):
            continue

        # Skip sentences with "From the German/French/Latin" (translation headers)
        if re.search(r'From the (?:German|French|Latin)\b', s):
            continue

        # Skip sentences ending with "Section" markers
        if re.search(r'Section\s+[IVX]+\.?\s*$', s):
            continue

        # Skip editorial metadata: "Adapted, in his..."
        if re.search(r'^Adapted\b', s):
            continue

        candidates.append(s)

    if not candidates:
        return None

    # Score and pick the best
    candidates.sort(key=score_sentence, reverse=True)
    return candidates[0]


# ── Main Pipeline ────────────────────────────────────────────────────────────

def load_passages():
    """Load all passages from the JSONL file."""
    passages = []
    with open(CORPUS_PATH) as f:
        for line in f:
            if line.strip():
                passages.append(json.loads(line))
    return passages


def process_passages(passages):
    """Clean passages and extract best sentences. Returns viable candidates."""
    candidates = []
    for p in passages:
        text = clean_text(p["text"])

        # Quality gate: skip if too many artifacts remain
        if artifact_density(text) > ARTIFACT_THRESHOLD:
            continue

        sentence = extract_best_sentence(text)
        if not sentence:
            continue

        author = AUTHOR_DISPLAY.get(p["author"], p["author"])
        tweet = "%s\n\n\u2014 %s" % (sentence, author)

        if len(tweet) > MAX_TWEET_LEN:
            continue

        candidates.append({
            "sentence": sentence,
            "tweet": tweet,
            "author": p["author"],
            "author_display": author,
            "source_id": p["source_id"],
            "source_title": p["source_title"],
            "passage_id": p["id"],
            "year": p.get("year"),
        })

    return candidates


def select_posts(candidates, n=NUM_POSTS):
    """Select n posts ensuring no two from the same source document, with author mix."""
    random.seed(99)  # reproducible; change seed for different months

    # Separate by author to ensure mix
    by_author = {}
    for c in candidates:
        by_author.setdefault(c["author"], []).append(c)
    for author in by_author:
        random.shuffle(by_author[author])

    # Reserve slots for minority author(s) — at least 3 Charles Wesley
    selected = []
    used_sources = set()

    # First, pick Charles Wesley posts
    cw_target = min(5, n // 6)  # ~5 out of 30
    for c in by_author.get("charles-wesley", []):
        if c["source_id"] in used_sources:
            continue
        selected.append(c)
        used_sources.add(c["source_id"])
        if len(selected) >= cw_target:
            break

    # Fill remaining with John Wesley
    remaining = n - len(selected)
    for c in by_author.get("john-wesley", []):
        if c["source_id"] in used_sources:
            continue
        selected.append(c)
        used_sources.add(c["source_id"])
        if len(selected) >= n:
            break

    # Shuffle final selection so authors are interspersed
    random.shuffle(selected)
    return selected


def generate_dates(n):
    """Generate n posting datetimes starting from tomorrow, one per day."""
    start = datetime.now().date() + timedelta(days=1)
    dates = []
    for i in range(n):
        d = start + timedelta(days=i)
        # Format as "YYYY-MM-DD HH:MM" for Buffer's posting_time column
        dates.append(d.strftime("%Y-%m-%d") + " " + POST_TIME)
    return dates


def write_csv(posts, dates, output_path):
    """Write Buffer-compatible CSV with text, image_url, tags, posting_time."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "image_url", "tags", "posting_time"])
        for post, date in zip(posts, dates):
            writer.writerow([post["tweet"], "", "", date])


def write_markdown(posts, dates, output_path):
    """Write readable markdown calendar."""
    lines = [
        "# Wesley Corpus Social Media Calendar",
        "",
        "Generated: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Posts: %d" % len(posts),
        "",
        "---",
        "",
    ]

    for post, date in zip(posts, dates):
        date_display = datetime.strptime(date, "%Y-%m-%d %H:%M").strftime("%B %d, %Y")
        year_str = " (%s)" % post["year"] if post["year"] else ""
        lines.extend([
            "## %s" % date_display,
            "",
            "> %s" % post["sentence"],
            "",
            "\u2014 **%s**, _%s%s_" % (post["author_display"], post["source_title"], year_str),
            "Tweet length: %d chars | Passage: `%s`" % (len(post["tweet"]), post["passage_id"]),
            "",
            "---",
            "",
        ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def main():
    print("Loading passages...")
    passages = load_passages()
    print("  Loaded %d passages" % len(passages))

    print("Processing passages...")
    candidates = process_passages(passages)
    print("  Found %d viable candidates" % len(candidates))

    print("Selecting posts...")
    posts = select_posts(candidates)
    print("  Selected %d posts from unique sources" % len(posts))

    # Verify constraints
    assert len(posts) == NUM_POSTS, "Expected %d posts, got %d" % (NUM_POSTS, len(posts))
    source_ids = [p["source_id"] for p in posts]
    assert len(source_ids) == len(set(source_ids)), "Duplicate source IDs found"
    for p in posts:
        assert len(p["tweet"]) <= MAX_TWEET_LEN, (
            "Tweet too long (%d chars): %s..." % (len(p["tweet"]), p["tweet"][:50])
        )

    dates = generate_dates(len(posts))

    # Write outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "calendar.csv"
    md_path = OUTPUT_DIR / "calendar.md"

    write_csv(posts, dates, csv_path)
    print("  Wrote %s" % csv_path)

    write_markdown(posts, dates, md_path)
    print("  Wrote %s" % md_path)

    # Summary
    print("\n── Summary ──")
    print("  Posts: %d" % len(posts))
    print("  Date range: %s to %s" % (dates[0], dates[-1]))
    tweet_lengths = [len(p["tweet"]) for p in posts]
    print("  Tweet lengths: %d-%d chars" % (min(tweet_lengths), max(tweet_lengths)))
    authors = {}
    for p in posts:
        authors[p["author_display"]] = authors.get(p["author_display"], 0) + 1
    for author, count in sorted(authors.items()):
        print("  %s: %d posts" % (author, count))


if __name__ == "__main__":
    main()
