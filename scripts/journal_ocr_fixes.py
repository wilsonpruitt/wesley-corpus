"""Journal-specific OCR garble fixes (Phase 1, plans/2026-07-07-swi-v2-ocr-cleanup-verification.md).

Documented in CLAUDE.md's "TODO: clean up JW Journal OCR" section. Scoped
deliberately to the 4 raw single-file journal sources (journal-vol1-3,
journal-vol4-7, journal-1760-to-1773, journal-1773-to-1776) — NOT wired into
process_corpus.py's generic clean_text(), so it cannot affect any other
source's already-cleaned text.

Deliberately excluded (per the plan, "risky" bucket):
  - bare `ot` -> `of`  (too ambiguous outside dictionary-gated Phase 2)
"""
import re

# Running header, e.g. "16 REV. J. WESLEY'S JOURNAL. |Jan. 1736." or
# "teb. 1736.] REV. J. WESLUY'S JUURNAL R 61". Both "WESLEY" and "JOURNAL"
# garble in inconsistent ways (WESLLY/WESLUY/WHSLEY, JOURNAL/JUURNAL), so
# match loosely on "REV." followed within a short span by "WESL".
#
# NOT sufficient alone: the journal also quotes real letters/affidavits
# addressed to Wesley ("To the Rev. Mr. WESLEY,") -- a bare REV+WESL match
# would nuke a genuine salutation, the exact shape of the 2026-04-09
# DEAR-name regression. A running header additionally always carries either
# a page number or a JOURNAL-like token; a quoted salutation carries neither.
_HEADER_LINE_RE = re.compile(r'REV\.?.{0,25}WESL', re.I)
_JOURNAL_TOKEN_RE = re.compile(r'J[O0][UV]?[RB]NA[L1]', re.I)
_DIGIT_RE = re.compile(r'\d')

# Day-name garbles: italic-d in the source font consistently misread as "p".
_DAY_NAME_FIXES = {
    'Tvrspay': 'Tuesday', 'Wepnespay': 'Wednesday', 'Saturpay': 'Saturday',
    'Frwway': 'Friday', 'Toespay': 'Tuesday', 'Monpay': 'Monday',
    'Sunpay': 'Sunday', 'Thurspay': 'Thursday',
}

# Proper-name / word-level garbles confirmed in journal-vol1-3 (CLAUDE.md).
_WORD_FIXES = {
    'JOTN': 'JOHN',
    'WESLLY': 'WESLEY',
    'Inghart': 'Ingham',
    'Inghan': 'Ingham',
    'tlie': 'the',
    'rot': 'not',
    'aot': 'not',
}


def strip_running_headers(text):
    """Drop whole lines matching the running-header pattern (REV+WESL, and
    a page number or JOURNAL-like token) -- preserves quoted salutations."""
    lines = text.split('\n')
    kept = [
        ln for ln in lines
        if not (_HEADER_LINE_RE.search(ln)
                and (_DIGIT_RE.search(ln) or _JOURNAL_TOKEN_RE.search(ln)))
    ]
    return '\n'.join(kept)


# The single most-quoted line in the corpus: OCR misread "i" as a curly
# apostrophe in "trust in Christ" (raw: "trust 'n Christ, Christ alone").
# Narrowly scoped to this exact phrase -- not a general quote-is-i rule.
_ALDERSGATE_RE = re.compile(r"trust\s*[‘’']n\s+Christ", re.I)


def fix_word_garbles(text):
    for garble, fix in _DAY_NAME_FIXES.items():
        text = re.sub(r'\b' + garble + r'\b', fix, text)
    for garble, fix in _WORD_FIXES.items():
        text = re.sub(r'\b' + garble + r'\b', fix, text)
    return text


def fix_bracket_i(text):
    """OCR misread of italic capital I as '[' at the start of 'I was'."""
    return re.sub(r'\[was\b', 'I was', text)


def fix_stray_quote_digit_bleed(text):
    """Drop an apostrophe immediately before a digit (day-number bleed,
    e.g. 'Sat. '7.' / 'Wed. 2'7.' -> '7.' / '27.'). Apostrophe-before-digit
    has no legitimate use in this corpus (contractions are letter-preceded),
    so this is safe with no dictionary gate needed."""
    return re.sub(r"'(?=\d)", '', text)


def apply_journal_garble_fixes(text):
    """Full journal-specific fix pass. Apply AFTER the generic clean_text()."""
    text = strip_running_headers(text)
    text = fix_word_garbles(text)
    text = fix_bracket_i(text)
    text = fix_stray_quote_digit_bleed(text)
    text = _ALDERSGATE_RE.sub('trust in Christ', text)
    return text
