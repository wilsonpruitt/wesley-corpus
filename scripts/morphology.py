"""Light English suffix-stripping check.

/usr/share/dict/words on this machine is base-form-heavy: it has "large" but
not "larger", "signify" but not "signifies", "punish" but not "punished",
"worship" but not "worshipped". A straight dictionary-membership test flags
huge numbers of ordinary inflected words as OCR "non-words" -- discovered
2026-07-07 while building the Phase 2 substitution table, where several of
the highest-frequency "garbles" (larger, signifies, sinned, worshipped...)
turned out to be perfectly correct English the wordlist simply doesn't list.

This is NOT a spellchecker -- it only undoes standard English inflection
(plural/3rd-person -s, past tense -ed, -ing, comparative/superlative
-er/-est, adverbial -ly) plus the respelling rules that go with them
(silent-e, consonant doubling, y/i alternation, British double-consonant
spellings). A token is treated as "just an inflected real word" if ANY
candidate base form is in the dictionary.
"""


def strip_inflection(word):
    """Yield candidate base forms for a lowercase word."""
    candidates = set()
    w = word

    def maybe_dedouble(base):
        if len(base) > 1 and base[-1] == base[-2] and base[-1] not in "aeiou":
            candidates.add(base[:-1])

    def maybe_yi(base):
        if base.endswith("i") and len(base) > 1:
            candidates.add(base[:-1] + "y")

    # plural / 3rd-person singular -s / -es / -ies
    if w.endswith("ies") and len(w) > 4:
        candidates.add(w[:-3] + "y")            # signifies -> signify
    if w.endswith("es") and len(w) > 3:
        candidates.add(w[:-2])
        candidates.add(w[:-1])                  # causes -> cause
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        candidates.add(w[:-1])                  # tribes -> tribe, hopes -> hope

    # past tense / past participle -ed
    if w.endswith("ed") and len(w) > 3:
        base = w[:-2]
        candidates.add(base)                    # reached -> reach
        candidates.add(base + "e")              # loved -> love
        maybe_dedouble(base)                    # sinned -> sin, worshipped -> worship
        maybe_yi(base)                          # died -> die

    # present participle / gerund -ing
    if w.endswith("ing") and len(w) > 4:
        base = w[:-3]
        candidates.add(base)                    # reaching -> reach
        candidates.add(base + "e")              # living -> live
        maybe_dedouble(base)                    # running -> run

    # comparative / superlative -er / -est
    for suf in ("est", "er"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            base = w[: -len(suf)]
            candidates.add(base)
            candidates.add(base + "e")          # larger -> large
            maybe_dedouble(base)                # bigger -> big
            maybe_yi(base)                       # happier -> happy

    # adverb -ly
    if w.endswith("ily") and len(w) > 4:
        candidates.add(w[:-3] + "y")            # happily -> happy
    elif w.endswith("ly") and len(w) > 4:
        candidates.add(w[:-2])                  # quickly -> quick

    candidates.discard(word)
    return candidates


def is_regular_inflection(word, dictionary):
    return any(c in dictionary for c in strip_inflection(word))


def is_period_elision(word, dictionary):
    """Catch deliberate 18th-c. poetic elision (a dropped unstressed vowel
    marked with an apostrophe, to preserve a hymn's metrical scansion):
    heav'n->heaven, pow'r->power, promis'd->promised, know'st->knowest,
    op'ning->opening. This is original-text style, not OCR damage -- found
    2026-07-07 while scoping Phase 3, where most of the corpus's remaining
    "noise" turned out to be exactly this, concentrated in Charles Wesley's
    hymn collections. Must NOT be "fixed" -- the elision is the poem."""
    if word.count("'") != 1:
        return False
    i = word.index("'")
    if i == 0 or i == len(word) - 1:
        return False
    for vowel in ("", "a", "e", "i", "o", "u"):
        candidate = word[:i] + vowel + word[i + 1:]
        if candidate in dictionary or is_regular_inflection(candidate, dictionary):
            return True
    return False
