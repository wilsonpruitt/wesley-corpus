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

# Metadata header lines that appear at the start of some passages.
# Note: do NOT include "Dear <Name>," patterns here — those are real
# letter salutations in Wesley's correspondence and conference addresses.
METADATA_LINE_RE = re.compile(
    r'^\s*(?:Source:\s|Author:\s|Printed by\s)',
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

    # Phase 2 (2026-07-07): dictionary-gated long-s substitution table.
    # 18th-c. long-s ("ſ") consistently misread as "f" by OCR, concentrated
    # in Primitive Physick's 1770s typesetting. Built by
    # scripts/build_ocr_substitutions.py -> metadata/ocr-substitutions.csv,
    # manually verified occurrence-by-occurrence (not just sampled) against
    # false positives from hyphenation-split fragments and Latin
    # quotations, reviewed and approved by Wilson before shipping.
    text = re.sub(r'\bfhould\b', 'should', text)
    text = re.sub(r'\bfpoonful\b', 'spoonful', text)
    text = re.sub(r'\balfo\b', 'also', text)
    text = re.sub(r'\bfome\b', 'some', text)
    text = re.sub(r'\bfeldom\b', 'seldom', text)
    text = re.sub(r'\bfafting\b', 'fasting', text)
    text = re.sub(r'\bfmall\b', 'small', text)
    text = re.sub(r'\bftrong\b', 'strong', text)
    text = re.sub(r'\bfuch\b', 'such', text)
    text = re.sub(r'\beafy\b', 'easy', text)
    text = re.sub(r'\bmoft\b', 'most', text)
    text = re.sub(r'\bfoon\b', 'soon', text)
    text = re.sub(r'\bfirft\b', 'first', text)
    text = re.sub(r'\blikewife\b', 'likewise', text)
    text = re.sub(r'\binfufe\b', 'infuse', text)
    text = re.sub(r'\bthofe\b', 'those', text)
    text = re.sub(r'\bthefe\b', 'these', text)
    text = re.sub(r'\bfeveral\b', 'several', text)
    text = re.sub(r'\bufually\b', 'usually', text)
    text = re.sub(r'\bfpread\b', 'spread', text)
    text = re.sub(r'\bfeven\b', 'seven', text)
    text = re.sub(r'\bphyfic\b', 'physic', text)
    text = re.sub(r'\bfweat\b', 'sweat', text)
    text = re.sub(r'\bjuft\b', 'just', text)
    text = re.sub(r'\bfweet\b', 'sweet', text)
    text = re.sub(r'\bconftantly\b', 'constantly', text)
    text = re.sub(r'\bbeft\b', 'best', text)
    text = re.sub(r'\bftand\b', 'stand', text)
    text = re.sub(r'\bfickness\b', 'sickness', text)
    text = re.sub(r'\bleaft\b', 'least', text)
    text = re.sub(r'\bfafe\b', 'safe', text)
    text = re.sub(r'\bfnuff\b', 'snuff', text)
    text = re.sub(r'\blefs\b', 'less', text)
    text = re.sub(r'\bfick\b', 'sick', text)
    text = re.sub(r'\bfince\b', 'since', text)
    text = re.sub(r'\bfometimes\b', 'sometimes', text)
    text = re.sub(r'\blaft\b', 'last', text)
    text = re.sub(r'\bfalt\b', 'salt', text)
    text = re.sub(r'\bfure\b', 'sure', text)
    text = re.sub(r'\broaft\b', 'roast', text)
    text = re.sub(r'\bclofe\b', 'close', text)
    text = re.sub(r'\bftrain\b', 'strain', text)
    text = re.sub(r'\buniverfal\b', 'universal', text)
    text = re.sub(r'\badvife\b', 'advise', text)
    text = re.sub(r'\bdefire\b', 'desire', text)
    text = re.sub(r'\breafon\b', 'reason', text)
    text = re.sub(r'\bfimple\b', 'simple', text)
    text = re.sub(r'\bphyfician\b', 'physician', text)
    text = re.sub(r'\bdigeftion\b', 'digestion', text)
    text = re.sub(r'\beafe\b', 'ease', text)
    text = re.sub(r'\bftrongly\b', 'strongly', text)
    text = re.sub(r'\bftanding\b', 'standing', text)
    text = re.sub(r'\balmoft\b', 'almost', text)
    text = re.sub(r'\bftrew\b', 'strew', text)
    text = re.sub(r'\bftop\b', 'stop', text)
    text = re.sub(r'\bftamp\b', 'stamp', text)
    text = re.sub(r'\bfwallow\b', 'swallow', text)
    text = re.sub(r'\bflice\b', 'slice', text)
    text = re.sub(r'\bConferve\b', 'Conserve', text)
    text = re.sub(r'\bToaft\b', 'Toast', text)
    text = re.sub(r'\bcaufe\b', 'cause', text)
    text = re.sub(r'\bfaid\b', 'said', text)
    text = re.sub(r'\bphilofophical\b', 'philosophical', text)
    text = re.sub(r'\bftomach\b', 'stomach', text)
    text = re.sub(r'\bfomething\b', 'something', text)
    text = re.sub(r'\bdiftemper\b', 'distemper', text)
    text = re.sub(r'\bfparingly\b', 'sparingly', text)
    text = re.sub(r'\bThofe\b', 'Those', text)
    text = re.sub(r'\bftrengthen\b', 'strengthen', text)
    text = re.sub(r'\bconftant\b', 'constant', text)
    text = re.sub(r'\bexercife\b', 'exercise', text)
    text = re.sub(r'\bCoftiveness\b', 'Costiveness', text)
    text = re.sub(r'\bfliced\b', 'sliced', text)
    text = re.sub(r'\bEfpecially\b', 'Especially', text)
    text = re.sub(r'\bConvulfive\b', 'Convulsive', text)
    text = re.sub(r'\bfharp\b', 'sharp', text)
    text = re.sub(r'\bHorfe\b', 'Horse', text)
    text = re.sub(r'\bAnife\b', 'Anise', text)
    text = re.sub(r'\bfoft\b', 'soft', text)
    text = re.sub(r'\bTafte\b', 'Taste', text)
    text = re.sub(r'\bClyfter\b', 'Clyster', text)
    text = re.sub(r'\bdefperate\b', 'desperate', text)
    text = re.sub(r'\bHartfhorn\b', 'Hartshorn', text)
    text = re.sub(r'\bCruft\b', 'Crust', text)
    text = re.sub(r'\bfwelled\b', 'swelled', text)
    text = re.sub(r'\bfecond\b', 'second', text)
    text = re.sub(r'\bFiftula\b', 'Fistula', text)
    text = re.sub(r'\bHyfteric\b', 'Hysteric', text)
    text = re.sub(r'\bBreakfaft\b', 'Breakfast', text)
    text = re.sub(r'\bRheumatifm\b', 'Rheumatism', text)

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
