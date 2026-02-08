"""Shared OCR cleaning utilities for the Wesley corpus.

Provides text-cleaning functions used by clean_corpus.py, generate_calendar.py,
and any other consumer that needs to fix OCR artifacts in passage text.
"""

import re
import unicodedata


# ── Compiled Patterns ────────────────────────────────────────────────────────

# Lines that are mostly symbols/noise — printer marks, page nums, OCR garbage
NOISE_LINE_RE = re.compile(
    r'^[\s\-\*\.\,\;\:\|\#\@\&\$\%\{\}\[\]\<\>\d\!\?\"\'\^\~\=\+\\_\/\(\)]+$'
)

# Metadata header lines that appear at the start of some passages
METADATA_LINE_RE = re.compile(
    r'^\s*(?:Source:\s|Author:\s|Printed by\s|DEAR\s[A-Z]+,)',
    re.I
)

# Page-number artifacts: standalone numbers, "A 2", "[19]", "Vol. 3", etc.
PAGE_ARTIFACT_RE = re.compile(
    r'(?:^|\n)\s*(?:[A-Z]\s*\d+|\[\d+\]|\d{1,3})\s*(?:\n|$)'
)

# Day/date markers in journals: "Mon. 16.", "Tues. 3.", "Wed. Jan. 5."
DAY_MARKER_RE = re.compile(
    r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.\s*\d+\.?'
)

# Page references: "(Page 175.)", "(p. 11)", "(page 42)"
PAGE_REF_RE = re.compile(r'\((?:[Pp]age|p\.)\s*\d+\.?\)')

# Hymn/section numbers like "540 Hymns of Adoration."
HYMN_HEADER_RE = re.compile(r'^\d+\s+[A-Z][a-z]+.*\.')

# Scripture footnote references: "* Cor, xi", "Ezek. xxxvi. 26", "+ Heb. viii."
SCRIPTURE_FOOTNOTE_RE = re.compile(
    r'^\s*[\*\+]?\s*\d?\s*[A-Z][a-z]+\.?\s+[ivxlc]+',
    re.I
)

# Symbols to strip (OCR junk)
STRIP_SYMBOLS_RE = re.compile(r'[|*#@&$%{}\[\]<>^~\\]')


# ── Public API ───────────────────────────────────────────────────────────────

def clean_text(text):
    """Clean OCR artifacts from a passage.

    Fixes long-s, normalizes unicode, removes noise lines and metadata headers,
    strips stray symbols, fixes common broken/stuck words, and collapses whitespace.
    """
    # Fix long-s (ſ → s)
    text = text.replace('\u017f', 's')

    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)

    # Replace curly/smart quotes with straight
    for old, new in [('\u201c', '"'), ('\u201d', '"'), ('\u201e', '"'),
                     ('\u2018', "'"), ('\u2019', "'")]:
        text = text.replace(old, new)

    # Remove noise lines and metadata headers
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if NOISE_LINE_RE.match(stripped):
            continue
        if METADATA_LINE_RE.match(stripped):
            continue
        # Skip very short lines that look like OCR noise
        if len(stripped) < 5 and not re.search(r'[aeiouAEIOU]', stripped):
            continue
        cleaned_lines.append(stripped)

    # Join lines, collapsing internal newlines into spaces
    # (the original text has line breaks within sentences from OCR)
    text = ' '.join(cleaned_lines)

    # Remove page artifacts
    text = PAGE_ARTIFACT_RE.sub(' ', text)

    # Strip stray symbols
    text = STRIP_SYMBOLS_RE.sub('', text)

    # Remove double-dashes used as line separators
    text = re.sub(r'\s*--\s*', ' ', text)

    # Remove day/date markers
    text = DAY_MARKER_RE.sub('', text)

    # Remove page references
    text = PAGE_REF_RE.sub('', text)

    # Fix common OCR broken words
    text = re.sub(r'chr!\s*stianity', 'christianity', text, flags=re.I)

    # Fix specific known OCR misspellings
    text = re.sub(r'\bbefievers\b', 'believers', text)
    text = re.sub(r'\brelign\b', 'resign', text)
    text = re.sub(r'\bcer tainly\b', 'certainly', text)
    text = re.sub(r'\bdis sem bled\b', 'dissembled', text)
    text = re.sub(r'\bdissem bled\b', 'dissembled', text)
    text = re.sub(r'\bviru lence\b', 'virulence', text)
    text = re.sub(r'\bparticu larly\b', 'particularly', text)
    text = re.sub(r'\bimme diately\b', 'immediately', text)
    text = re.sub(r'\bconse quently\b', 'consequently', text)
    text = re.sub(r'\bthere fore\b', 'therefore', text)
    text = re.sub(r'\bwhether soever\b', 'whithersoever', text)
    text = re.sub(r'\bMo ravians\b', 'Moravians', text)
    text = re.sub(r'\bmo ravians\b', 'moravians', text)
    text = re.sub(r'\bhappi mess\b', 'happiness', text)
    text = re.sub(r'\bhappi ness\b', 'happiness', text)

    # Fix double-spaced words from column alignment
    text = re.sub(r'(\w{3,})\s{2,}(\w{3,})', r'\1 \2', text)

    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    text = text.strip()

    return text


def artifact_density(text):
    """Fraction of non-alpha chars (excluding spaces and common punctuation).

    Returns a float between 0.0 (clean) and 1.0 (all artifacts).
    An empty string returns 1.0.
    """
    if not text:
        return 1.0
    allowed_punct = set('.,;:!?\'"()-  ')
    total = 0
    artifacts = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if not ch.isalpha() and ch not in allowed_punct:
            artifacts += 1
    return artifacts / total if total > 0 else 1.0
