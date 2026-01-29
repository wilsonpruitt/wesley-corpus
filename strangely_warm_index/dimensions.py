"""
SWI Dimension Scorers (Phase 2B)
=================================

Eight dimension scorers, each returning:
    (score: 0-100, markers: list[dict], explanation: str)

Dimensions:
1. Grace Theology
2. Scriptural Density
3. Holiness Emphasis
4. Experiential Religion
5. Catholic Spirit
6. Social Holiness
7. Wesleyan Vocabulary
8. Rhetorical Style
"""

import json
import math
import re
from pathlib import Path
from typing import NamedTuple

CORPUS_ROOT = Path(__file__).resolve().parent.parent
LEXICON_PATH = CORPUS_ROOT / "metadata" / "wesleyan-lexicon.json"

_lexicon_cache = None


def _load_lexicon() -> dict:
    global _lexicon_cache
    if _lexicon_cache is None:
        if LEXICON_PATH.exists():
            with open(LEXICON_PATH) as f:
                _lexicon_cache = json.load(f)
        else:
            _lexicon_cache = {"curated_phrases": {}, "distinctive_terms": {}, "top_distinctive": []}
    return _lexicon_cache


class DimensionResult(NamedTuple):
    score: int  # 0-100
    markers: list  # [{"text": ..., "type": ...}, ...]
    explanation: str


def _find_phrases(text: str, phrases: list[str]) -> list[dict]:
    """Find all occurrences of phrases in text."""
    markers = []
    text_lower = text.lower()
    for phrase in phrases:
        phrase_lower = phrase.lower()
        start = 0
        while True:
            idx = text_lower.find(phrase_lower, start)
            if idx == -1:
                break
            markers.append({
                "text": text[idx:idx + len(phrase)],
                "phrase": phrase,
                "offset": idx,
            })
            start = idx + 1
    return markers


def _count_pattern_matches(text: str, patterns: list[str]) -> tuple[int, list[dict]]:
    """Count regex pattern matches and return markers."""
    count = 0
    markers = []
    text_lower = text.lower()
    for pattern in patterns:
        for m in re.finditer(pattern, text_lower):
            count += 1
            markers.append({
                "text": m.group(),
                "pattern": pattern,
                "offset": m.start(),
            })
    return count, markers


def _clamp_score(density: float, max_density: float = 20.0,
                  raw_count: int = 0, max_count: float = 30.0) -> int:
    """Convert density + raw count to 0-100 score with diminishing returns.

    Uses the better of density-based or count-based scoring so that
    long texts with many markers aren't penalized for lower density.
    """
    if density <= 0 and raw_count <= 0:
        return 0
    # Density-based (works well for short texts / chunks)
    d_norm = min(density / max_density, 1.0)
    d_score = 100 * (1 - math.exp(-3 * d_norm))
    # Count-based (works well for long texts / full sermons)
    c_norm = min(raw_count / max_count, 1.0)
    c_score = 100 * (1 - math.exp(-3 * c_norm))
    return min(int(max(d_score, c_score)), 100)


# ── Dimension 1: Grace Theology ──────────────────────────────────────────

GRACE_PHRASES = [
    "prevenient grace", "preventing grace", "justifying grace",
    "sanctifying grace", "free grace", "pardoning grace",
    "grace of God", "saving grace", "grace upon grace",
    "grace that goes before", "pardoning love", "saving faith",
    "imputed righteousness", "new birth", "born again", "born of God",
    "born of the spirit",
    # christology
    "blood of Christ", "death of Christ", "merits of Christ",
    "lamb of God", "saviour of the world", "Son of God",
    "mediator", "propitiation", "atoning blood",
    # universal redemption
    "died for all", "for all mankind", "tasted death for every man",
    "unlimited atonement", "saviour of all", "sins of the whole world",
    # free will
    "free will", "resist grace", "power to choose",
]

GRACE_PATTERNS = [
    r"\b(grace|pardon|forgiv|justif|sanctif|redeem|ransom|atone)\w*\b",
    r"\bprevenient\b",
    r"\b(new\s+birth|born\s+again|born\s+of\s+god)\b",
    r"\b(perfection|perfect\s+love|entire\s+sanctification)\b",
    # christology — Wesleyan-specific phrasing, not bare "Christ"
    r"\b(incarnat|propitiat|mediator)\w*\b",
    r"\b(atoning\s+blood|merits\s+of\s+christ|death\s+of\s+christ)\b",
    r"\b(saviour\s+of\s+(all|the\s+world)|lamb\s+of\s+god)\b",
    # universal redemption
    r"\b(whosoever|for\s+all\s+m|tasted\s+death\s+for\s+every|unlimited\s+atonement)\b",
    r"\b(died\s+for\s+all|sins\s+of\s+the\s+whole\s+world)\b",
    # free will
    r"\b(free\s+will|resist\s+grace|predestination\s+rejected)\b",
]


def score_grace_theology(text: str) -> DimensionResult:
    phrase_markers = _find_phrases(text, GRACE_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, GRACE_PATTERNS)

    word_count = len(text.split())
    raw = len(phrase_markers) * 3 + pattern_count  # phrases weighted more
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=15, raw_count=raw)

    markers = [{"text": m["text"], "type": "grace-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "grace-pattern"} for m in pattern_markers[:10]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} grace phrase(s)")
    if pattern_count:
        parts.append(f"{pattern_count} grace-related term(s)")
    explanation = "; ".join(parts) if parts else "No grace theology markers found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 2: Scriptural Density ──────────────────────────────────────

SCRIPTURE_PATTERN = re.compile(
    r"\b(?:(?:1|2|3)\s+)?(?:Gen|Exod|Lev|Num|Deut|Josh|Judg|Ruth|Sam|Kings|Chron|"
    r"Ezra|Neh|Esth|Job|Ps|Psa|Prov|Eccles|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|"
    r"Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal|Matt|Mark|Luke|John|Acts|"
    r"Rom|Cor|Gal|Eph|Phil|Col|Thess|Tim|Tit|Philem|Heb|Jas|Pet|Jude|Rev|"
    r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Samuel|Kings|"
    r"Chronicles|Psalms|Proverbs|Isaiah|Jeremiah|Ezekiel|Daniel|Matthew|Mark|"
    r"Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|"
    r"Colossians|Thessalonians|Timothy|Titus|Hebrews|James|Peter|Revelation)"
    r"\.?\s*\d+(?::\d+(?:\s*[-,]\s*\d+)*)?",
    re.IGNORECASE,
)

ALLUSION_PATTERNS = [
    r"\b(it is written|the scripture saith|saith the Lord|thus saith|word of God)\b",
    r"\b(as St\. Paul|as our Lord)\b",
]


def score_scriptural_density(text: str) -> DimensionResult:
    refs = SCRIPTURE_PATTERN.findall(text) if hasattr(SCRIPTURE_PATTERN, 'findall') else []
    ref_matches = list(SCRIPTURE_PATTERN.finditer(text))
    allusion_count, allusion_markers = _count_pattern_matches(text, ALLUSION_PATTERNS)

    word_count = len(text.split())
    ref_count = len(ref_matches)
    raw = ref_count * 2 + allusion_count
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=12, raw_count=raw)

    markers = [{"text": m.group(), "type": "scripture-ref"} for m in ref_matches[:15]]
    markers += [{"text": m["text"], "type": "allusion"} for m in allusion_markers[:5]]

    parts = []
    if ref_count:
        parts.append(f"{ref_count} scripture reference(s)")
    if allusion_count:
        parts.append(f"{allusion_count} scriptural allusion(s)")
    explanation = "; ".join(parts) if parts else "No scripture references found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 3: Holiness Emphasis ───────────────────────────────────────

HOLINESS_PHRASES = [
    "entire sanctification", "christian perfection", "perfect love",
    "going on to perfection", "holiness of heart and life",
    "holy living", "growth in grace", "means of grace",
    "works of piety", "works of mercy", "instituted means",
    "prudential means", "class meeting", "band meeting",
    "searching the scriptures", "pure heart", "clean heart",
    "circumcision of the heart",
    # repentance
    "conviction of sin", "sorrow for sin", "amendment of life",
    "flee from the wrath", "godly sorrow",
    # communion
    "Lord's Supper", "table of the Lord", "body and blood",
    "bread and wine",
]

HOLINESS_PATTERNS = [
    r"\b(sanctif|holiness|perfection|perfected)\w*\b",
    r"\b(means\s+of\s+grace|holy\s+living|growth\s+in\s+grace)\b",
    r"\b(fasting|communion|sacrament|ordinance)\b",
    # repentance
    r"\b(repent|repentance|contrition|penitent|convict)\w*\b",
    r"\b(turn|turning)\s+(from|to)\s+(sin|god|christ)\b",
    # communion
    r"\b(eucharist|lord's\s+supper|sacrament|partake)\b",
]


def score_holiness_emphasis(text: str) -> DimensionResult:
    phrase_markers = _find_phrases(text, HOLINESS_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, HOLINESS_PATTERNS)

    word_count = len(text.split())
    raw = len(phrase_markers) * 3 + pattern_count
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=15, raw_count=raw)

    markers = [{"text": m["text"], "type": "holiness-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "holiness-term"} for m in pattern_markers[:10]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} holiness phrase(s)")
    if pattern_count:
        parts.append(f"{pattern_count} holiness-related term(s)")
    explanation = "; ".join(parts) if parts else "No holiness emphasis found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 4: Experiential Religion ───────────────────────────────────

EXPERIENTIAL_PHRASES = [
    "heart strangely warmed", "strangely warmed",
    "religion of the heart", "heart religion",
    "experimental religion", "inward religion",
    "witness of the spirit", "direct witness", "inward witness",
    "assurance of faith", "felt his presence",
    "I felt", "my heart", "inward feeling",
    "know that we are children", "testimony of the spirit",
    # pneumatology
    "Holy Ghost", "Holy Spirit", "Spirit of God", "Spirit of Christ",
    "fruits of the Spirit", "gifts of the Spirit", "indwelling",
    "filled with the Spirit",
]

EXPERIENTIAL_PATTERNS = [
    r"\b(experiential|experimental\s+religion|inward\s+religion)\b",
    r"\b(assurance\s+of\s+faith|witness\s+of\s+the\s+spirit|testimony\s+of\s+the\s+spirit)\b",
    r"\b(I\s+felt|my\s+heart|my\s+soul)\b",
    # pneumatology
    r"\b(holy\s+ghost|holy\s+spirit|spirit\s+of\s+god)\b",
    r"\b(anoint|filled|indwell|pentecost)\w*\b",
]


def score_experiential_religion(text: str) -> DimensionResult:
    phrase_markers = _find_phrases(text, EXPERIENTIAL_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, EXPERIENTIAL_PATTERNS)

    word_count = len(text.split())
    raw = len(phrase_markers) * 3 + pattern_count
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=18, raw_count=raw)

    markers = [{"text": m["text"], "type": "experiential-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "experiential-term"} for m in pattern_markers[:10]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} experiential phrase(s)")
    if pattern_count:
        parts.append(f"{pattern_count} experiential term(s)")
    explanation = "; ".join(parts) if parts else "No experiential religion markers found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 5: Catholic Spirit ─────────────────────────────────────────

CATHOLIC_PHRASES = [
    "catholic spirit", "if thy heart is as my heart",
    "give me thy hand", "think and let think",
    "no solitary religion", "no solitary christian",
    "unity in essentials", "opinions", "modes of worship",
    # trinity (shared creedal conviction)
    "Father, Son, and Holy Ghost", "three persons", "triune",
    "Godhead",
    # scriptural authority (theological conviction)
    "word of God", "sola scriptura", "analogy of faith",
]

CATHOLIC_PATTERNS = [
    r"\b(ecumenical|unity|united|universal|catholic|denomin)\w*\b",
    r"\b(all\s+christians|every\s+believer|every\s+denomination)\b",
    r"\b(one\s+heart|one\s+mind|one\s+spirit)\b",
    r"\b(sects?|sectarian|schism|schismatic|division|boundary)\b",
    # trinity
    r"\b(trinity|triune|godhead|three\s+persons)\b",
    # scriptural authority — Wesleyan phrasing
    r"\b(analogy\s+of\s+faith|word\s+of\s+god|sola\s+scriptura)\b",
]


def score_catholic_spirit(text: str) -> DimensionResult:
    phrase_markers = _find_phrases(text, CATHOLIC_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, CATHOLIC_PATTERNS)

    word_count = len(text.split())
    raw = len(phrase_markers) * 4 + pattern_count
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=10, raw_count=raw)

    markers = [{"text": m["text"], "type": "catholic-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "catholic-term"} for m in pattern_markers[:8]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} catholic spirit phrase(s)")
    if pattern_count:
        parts.append(f"{pattern_count} ecumenical term(s)")
    explanation = "; ".join(parts) if parts else "No catholic spirit markers found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 6: Social Holiness ─────────────────────────────────────────

SOCIAL_PHRASES = [
    "social holiness", "no holiness but social holiness",
    "do all the good you can", "gain all you can",
    "save all you can", "give all you can",
    "visiting the sick", "visiting the prisoner",
    "feeding the hungry", "clothing the naked",
    "relieve the poor", "acts of mercy",
    "works of mercy", "doing good to all",
    "love of neighbor", "love thy neighbor",
    # reign of God
    "kingdom of God", "kingdom of heaven", "thy kingdom come",
    "reign of God", "God reigneth",
]

SOCIAL_PATTERNS = [
    r"\b(poor|hungry|naked|sick|prisoner|widow|orphan|oppress)\w*\b",
    r"\b(mercy|compassion|charity|justice|injustice|inequal)\w*\b",
    r"\b(community|fellowship|neighbor|brotherhood)\w*\b",
    r"\b(slave|slavery|freedom|liberty)\b",
    # reign of God
    r"\b(kingdom|reign|judgment|eternal\s+life|everlast)\w*\b",
]


def score_social_holiness(text: str) -> DimensionResult:
    phrase_markers = _find_phrases(text, SOCIAL_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, SOCIAL_PATTERNS)

    word_count = len(text.split())
    raw = len(phrase_markers) * 3 + pattern_count
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=15, raw_count=raw)

    markers = [{"text": m["text"], "type": "social-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "social-term"} for m in pattern_markers[:10]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} social holiness phrase(s)")
    if pattern_count:
        parts.append(f"{pattern_count} social justice term(s)")
    explanation = "; ".join(parts) if parts else "No social holiness markers found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 7: Wesleyan Vocabulary ─────────────────────────────────────

def score_wesleyan_vocabulary(text: str) -> DimensionResult:
    """Score based on TF-IDF distinctive Wesley vocabulary from lexicon."""
    lexicon = _load_lexicon()
    curated = lexicon.get("curated_phrases", {})
    distinctive = lexicon.get("top_distinctive", [])

    # Check curated phrases across all groups
    all_curated = []
    for group_phrases in curated.values():
        all_curated.extend(group_phrases)
    phrase_markers = _find_phrases(text, all_curated)

    # Check distinctive terms
    text_lower = text.lower()
    distinctive_markers = []
    for item in distinctive[:100]:
        term = item["term"]
        if term in text_lower:
            count = text_lower.count(term)
            distinctive_markers.append({
                "text": term,
                "count": count,
                "distinctiveness": item.get("distinctiveness", 0),
            })

    word_count = len(text.split())
    raw = len(phrase_markers) * 2 + sum(m["count"] for m in distinctive_markers)
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=25, raw_count=raw)

    markers = [{"text": m["text"], "type": "curated-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "distinctive-term"} for m in distinctive_markers[:10]]

    parts = []
    if phrase_markers:
        parts.append(f"{len(phrase_markers)} curated Wesleyan phrase(s)")
    if distinctive_markers:
        parts.append(f"{len(distinctive_markers)} distinctive term(s)")
    explanation = "; ".join(parts) if parts else "No distinctive Wesleyan vocabulary found"

    return DimensionResult(score, markers, explanation)


# ── Dimension 8: Rhetorical Style ────────────────────────────────────────

RHETORICAL_PATTERNS = [
    # Direct address
    r"\b(brethren|beloved|my\s+dear\s+brethren|my\s+friends)\b",
    # Rhetorical questions
    r"[A-Z][^.!?]*\?\s",
    # Scripture-then-exposition ("The text says... This means...")
    r"\b(the\s+text\s+says|the\s+apostle\s+says|as\s+the\s+scripture|but\s+what\s+saith)\b",
    # Antithesis (not X but Y)
    r"\bnot\s+\w+\s+but\s+\w+\b",
    # Enumeration
    r"\b(first|secondly|thirdly|in\s+the\s+first\s+place|in\s+the\s+second\s+place)\b",
    # Imperative/hortatory
    r"\b(let\s+us|take\s+heed|mark\s+this|consider|observe|I\s+say)\b",
]


def score_rhetorical_style(text: str) -> DimensionResult:
    total_count = 0
    all_markers = []
    for pattern in RHETORICAL_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            total_count += 1
            all_markers.append({"text": m.group(), "type": "rhetorical"})

    # Count rhetorical questions specifically
    questions = re.findall(r"[A-Z][^.!?]*\?", text)
    q_count = len(questions)

    word_count = len(text.split())
    sentences = len(re.findall(r"[.!?]+", text)) or 1
    q_ratio = q_count / sentences

    raw = total_count + q_count * 2
    density = raw / max(word_count / 100, 1)
    score = _clamp_score(density, max_density=12, raw_count=raw)

    markers = all_markers[:15]

    parts = []
    if q_count:
        parts.append(f"{q_count} rhetorical question(s)")
    if total_count - q_count > 0:
        parts.append(f"{total_count - q_count} rhetorical device(s)")
    explanation = "; ".join(parts) if parts else "No distinctive rhetorical style markers found"

    return DimensionResult(score, markers, explanation)


# ── Calvinist Penalty Detection ──────────────────────────────────────────
# Wesley explicitly opposed these doctrines. Their presence indicates
# a non-Wesleyan (typically Reformed/Calvinist) theological framework.

CALVINIST_PHRASES = [
    "unconditional election", "limited atonement", "irresistible grace",
    "total depravity", "perseverance of the saints", "tulip",
    "God's eternal decree", "God's decrees", "divine decree",
    "double predestination", "decree of reprobation",
    "effectual calling", "particular redemption",
    "sovereign grace", "sovereign election",
    "predestinated",
    "chosen before the foundation", "elected before",
    "unconditional covenant", "limited redemption",
    "cannot fall from grace", "once saved always saved",
    "eternal security", "monergism",
    "Westminster Confession", "Canons of Dort", "five points",
    "God's sovereign will", "God's sovereign purpose",
    "decreed before", "ordained before",
]

CALVINIST_PATTERNS = [
    r"\b(predestina)\w*\b",
    r"\b(calvinis|reformed\s+theolog)\w*\b",
    r"\bgod'?s?\s+(eternal\s+)?decree\w*\b",
    r"\b(unconditional\s+election|limited\s+atonement|irresistible\s+grace)\b",
    r"\b(total\s+depravity|perseverance\s+of\s+the\s+saints)\b",
    r"\bthe\s+elect\b",
    r"\b(effectual\s+call|particular\s+redemption)\b",
    r"\b(reprobation\s+of\s+the|decree\s+of\s+reprobation)\b",  # only Calvinist-specific reprobation
    r"\b(monergis)\w*\b",
]


def detect_calvinist_markers(text: str) -> dict:
    """Detect Calvinist theological markers that are anti-Wesleyan.

    Returns:
        {"count": int, "density": float, "markers": list, "penalty": int}
    """
    phrase_markers = _find_phrases(text, CALVINIST_PHRASES)
    pattern_count, pattern_markers = _count_pattern_matches(text, CALVINIST_PATTERNS)

    # Detect refutation context: Wesley often mentions Calvinist terms
    # extensively when arguing AGAINST them. If the text also contains
    # strong Wesleyan/Arminian counter-markers, reduce or cancel the penalty.
    # Refutation markers: distinctly Wesleyan/Arminian soteriological phrases
    # that indicate the author is ARGUING AGAINST Calvinism, not just
    # discussing philosophical free will (which Calvinists also affirm).
    REFUTATION_PHRASES = re.compile(
        r"(horrible\s+decree|"
        r"died\s+for\s+all|for\s+all\s+mankind|tasted\s+death\s+for\s+every|"
        r"whosoever\s+will|whosoever\s+believeth|"
        r"universal\s+redemption|unlimited\s+atonement|"
        r"free\s+grace|prevenient\s+grace|preventing\s+grace|"
        r"all\s+men\s+may\s+be\s+saved|salvation\s+for\s+all|"
        r"not\s+irresistible|resistible\s+grace|"
        r"entire\s+sanctification|christian\s+perfection|perfect\s+love)",
        re.IGNORECASE
    )
    refutation_count = len(REFUTATION_PHRASES.findall(text))
    # Each refutation marker cancels ~3 raw Calvinist hits
    refutation_offset = refutation_count * 3

    word_count = max(len(text.split()), 1)
    raw = max(0, len(phrase_markers) * 3 + pattern_count - refutation_offset)
    density = raw / max(word_count / 100, 1)

    # Penalty scales: a few mentions = small penalty, pervasive = large
    # 1-2 raw hits: -5, 3-5: -10, 6-10: -15, 11-20: -20, 20+: -25
    if raw == 0:
        penalty = 0
    elif raw <= 2:
        penalty = 5
    elif raw <= 5:
        penalty = 10
    elif raw <= 10:
        penalty = 15
    elif raw <= 20:
        penalty = 20
    else:
        penalty = 25

    markers = [{"text": m["text"], "type": "calvinist-phrase"} for m in phrase_markers]
    markers += [{"text": m["text"], "type": "calvinist-pattern"} for m in pattern_markers[:10]]

    return {
        "count": raw,
        "density": round(density, 2),
        "markers": markers,
        "penalty": penalty,
    }


# ── Public API ───────────────────────────────────────────────────────────

ALL_DIMENSIONS = [
    ("grace_theology", "Grace Theology", score_grace_theology),
    ("scriptural_density", "Scriptural Density", score_scriptural_density),
    ("holiness_emphasis", "Holiness Emphasis", score_holiness_emphasis),
    ("experiential_religion", "Experiential Religion", score_experiential_religion),
    ("catholic_spirit", "Catholic Spirit", score_catholic_spirit),
    ("social_holiness", "Social Holiness", score_social_holiness),
    ("wesleyan_vocabulary", "Wesleyan Vocabulary", score_wesleyan_vocabulary),
]


def score_all_dimensions(text: str) -> dict:
    """Score text on all 8 dimensions. Returns dict keyed by dimension_id."""
    results = {}
    for dim_id, dim_name, scorer in ALL_DIMENSIONS:
        result = scorer(text)
        results[dim_id] = {
            "id": dim_id,
            "name": dim_name,
            "score": result.score,
            "markers": result.markers,
            "explanation": result.explanation,
        }
    return results
