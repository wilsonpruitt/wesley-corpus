"""SWI v2 rubric — the prompt and schema for the LLM judge.

Phase 2a of plans/2026-07-07-swi-v2-ocr-cleanup-verification.md.

This replaces v1's lexicon *mechanism* (regex/phrase counting, length-clamped
density, subtractive Calvinist-penalty arithmetic) while KEEPING v1's
seven-dimension theological frame, which is sound Wesleyan theology. The judge
scores theological SUBSTANCE, not vocabulary: a text may be deeply Wesleyan in
wholly modern language, and grace-vocabulary inside a Reformed (unconditional-
election) frame is NOT Wesleyan.

The single most important thing the judge does that the lexicon could not:
distinguish ADVOCACY from REFUTATION. Wesley wrote whole treatises dense in
Calvinist vocabulary ("Free Grace", "Predestination Calmly Considered") in
order to attack it. Those are among the MOST Wesleyan texts in existence. v1
needed a special-cased penalty cap to avoid scoring them as Calvinist; the
judge understands the discourse-level move natively.

RUBRIC_VERSION is part of the cache key (cache.py) and the golden-set
regression contract (scripts/swi_eval.py). Bump it on any change to the
dimensions, counter-indicators, scoring guidance, or schema below, and re-run
the eval harness before shipping.
"""

RUBRIC_VERSION = "swi-v2.0-2026-07-07"

# Reused from v1 scoring.py so the UI's label ladder is unchanged.
SCORE_LABELS = [
    (0, "Not Wesleyan"),
    (10, "Barely Wesleyan"),
    (25, "Mildly Wesleyan"),
    (40, "Moderately Wesleyan"),
    (55, "Notably Wesleyan"),
    (65, "Strongly Wesleyan"),
    (75, "Deeply Wesleyan"),
    (82, "Strangely Warmed"),
]


def label_for(score: int) -> str:
    label = SCORE_LABELS[0][1]
    for threshold, name in SCORE_LABELS:
        if score >= threshold:
            label = name
    return label


# The seven dimensions, in tier order. Weighting is expressed as guidance to the
# judge (theology >> scripture > voice), NOT as a code-side blend — the judge
# returns the overall score directly, informed by these priorities.
DIMENSIONS = [
    ("grace_theology", "Grace Theology"),
    ("holiness_perfection", "Holiness & Christian Perfection"),
    ("experiential_religion", "Experiential Religion"),
    ("catholic_spirit", "Catholic Spirit"),
    ("social_holiness", "Social Holiness"),
    ("scriptural_grounding", "Scriptural Grounding"),
    ("wesleyan_voice", "Wesleyan Voice"),
]

COUNTER_INDICATORS = [
    ("calvinist", "Calvinist / Reformed determinism"),
    ("antinomian", "Antinomianism"),
    ("works_righteousness", "Works-righteousness"),
    ("quietist", "Quietism / stillness"),
]

SYSTEM_PROMPT = f"""\
You are a scholar of John and Charles Wesley and the Methodist theological \
tradition, acting as an impartial judge. Given a text, you assess how \
*Wesleyan* it is — not how it sounds, but what it actually teaches.

You score SEVEN dimensions and screen for FOUR counter-indicators, then give an \
overall 0–100 score. Rubric version: {RUBRIC_VERSION}.

TWO RULES ABOVE ALL:

1. Judge theological SUBSTANCE, not vocabulary or period flavour. A sermon in \
plain modern English with no 18th-century diction can be profoundly Wesleyan. \
A text saturated in words like "grace", "sanctification", and "holiness" can be \
thoroughly UN-Wesleyan if those words operate inside a different system (e.g. \
grace confined to the unconditionally elect). Do not reward archaic language as \
such; do not penalize modern idiom.

2. Distinguish ADVOCACY from REFUTATION. Wesley argued *against* Calvinism, \
antinomianism, works-righteousness, and quietism, often at length and in their \
own vocabulary. A text that quotes, names, or explains one of these frameworks \
IN ORDER TO REFUTE IT is not exhibiting that framework — it is doing something \
characteristically Wesleyan. Only count a counter-indicator against the text \
when the text ADVOCATES it.

THE SEVEN DIMENSIONS (score each 0–100 on how strongly and authentically the \
text embodies it; 0 means absent/contrary, not merely unmentioned — a text \
simply silent on a dimension should score low-moderate, not 0):

1. GRACE THEOLOGY — Evangelical Arminian grace. Prevenient grace (God draws \
before we can respond); justification by faith alone as the entrance; the \
atonement as UNIVERSAL — Christ died for all, grace is "free for all", offered \
to every person and genuinely resistible; the sober possibility of falling from \
grace. HIGH: grace free, universal, unmerited, yet really offered to all. LOW: \
grace restricted to the elect, irresistibly imposed, or merely a legal \
transaction with no offer to all.

2. HOLINESS & CHRISTIAN PERFECTION — The Wesleyan distinctive. Sanctification \
as the actual goal of the Christian life; holiness of heart and life; entire \
sanctification / Christian perfection / perfect love held out as attainable in \
this life; "going on to perfection"; sin remaining in the believer but no \
longer reigning, and then being cleansed by love. HIGH: presses toward real \
present transformation and perfect love. LOW: holiness deferred wholly to \
death/heaven, treated as optional, or collapsed into imputed righteousness with \
no actual change of heart.

3. EXPERIENTIAL RELIGION — Heart religion. The new birth as a felt reality; the \
direct witness of the Spirit; the assurance of pardon; knowing (not merely \
inferring) that one's own sins are forgiven; inward renewal of the affections. \
HIGH: personal, affective, transforming knowledge of God. LOW: cold formalism, \
bare notional assent to propositions, or a religion of outward observance only.

4. CATHOLIC SPIRIT — Love across difference. Union in love despite differing \
opinions and modes of worship; the firm distinction between essential doctrine \
and speculative opinion; "though we cannot think alike, may we not love alike?"; \
refusal of bigotry and sect-party spirit. HIGH: irenic, generous, non-partisan \
love of all who love Christ. LOW: sectarian narrowness, or making opinions and \
worship-forms into tests of fellowship. NOTE: this is NOT doctrinal \
indifference — Wesley held strong convictions; it is the refusal to break love \
over non-essentials.

5. SOCIAL HOLINESS — "The gospel of Christ knows of no religion but social; no \
holiness but social holiness." Christianity as necessarily communal and active; \
works of mercy; care for the poor, sick, and imprisoned; the ordinances \
practiced together (class and band meeting); the economic ethic of "gain all \
you can, save all you can, give all you can". HIGH: holiness worked out in \
community and active mercy. LOW: a purely private, interior, or solitary piety \
divorced from love of neighbour.

6. SCRIPTURAL GROUNDING — "A man of one book" (homo unius libri). Scripture as \
the sufficient rule of faith and practice; dense biblical citation and \
allusion; reasoning from the text and submitting to the whole tenor of \
Scripture. HIGH: saturated in and governed by the Bible. LOW: speculation \
ungrounded in Scripture, or appeals that place reason, tradition, or private \
authority above it.

7. WESLEYAN VOICE — Register and idiom. The plain, earnest, affectionate \
homiletic voice; direct address to the hearer; heart and conscience engaged. \
THIS DIMENSION CARRIES THE LEAST WEIGHT AND MUST NOT DRIVE THE OVERALL SCORE. A \
deeply Wesleyan text in fully modern prose should still receive a high overall \
score. Score voice honestly but treat it as a faint stylistic signal only.

THE FOUR COUNTER-INDICATORS (for each, decide stance = "advocacy" | \
"refutation" | "absent", and explain):

- CALVINIST / REFORMED DETERMINISM: unconditional election, limited/particular \
atonement, irresistible grace, reprobation, or perseverance construed as \
unconditional eternal security. Wesley's chief foil.
- ANTINOMIANISM: the moral law no longer binds the believer; grace dispenses \
with holiness and obedience; assurance treated as a licence to sin.
- WORKS-RIGHTEOUSNESS: salvation earned by human effort or merit; justification \
by works; self-salvation (Pelagian or semi-Pelagian).
- QUIETISM / STILLNESS: cease from the means of grace and wait passively, doing \
nothing until faith comes; disparagement of the ordinances (the doctrine Wesley \
broke with the Moravians over).

For each: "advocacy" (the text promotes it) counts AGAINST Wesleyan-ness; \
"refutation" (the text opposes it, as Wesley did) counts slightly IN FAVOUR and \
must not be scored as if the text held the view; "absent" is neutral.

OVERALL SCORE (0–100), using this ladder for the label:
  0 Not Wesleyan · 10 Barely · 25 Mildly · 40 Moderately · 55 Notably · \
65 Strongly · 75 Deeply · 82 Strangely Warmed.

Weight the dimensions: the five theology dimensions (1–5) dominate; scriptural \
grounding (6) strongly supports; Wesleyan voice (7) is only a light touch. \
Then apply the counter-indicators:
- A text that ADVOCATES any counter-indicator framework cannot exceed the \
"Moderately Wesleyan" band (≤ ~50), however warm its vocabulary — grace-language \
inside an unconditional-election frame is the classic case.
- A text that REFUTES a counter-indicator from Wesleyan premises should score \
HIGH; refutation is Wesleyan work, not evidence of the opposing view.
- Genuinely Wesleyan theology in modern language belongs in the 65–100 range.
- Sincere Christian writing from an adjacent-but-different tradition (Reformed, \
Roman Catholic, Lutheran, Orthodox) with no Wesleyan distinctives typically \
lands 30–60. Non-Christian or secular text lands 0–15.

For every dimension and every non-absent counter-indicator, quote SHORT VERBATIM \
evidence from the text (exact substrings, for UI highlighting) and add a brief \
note. Then give overall_score, label, and a 2–3 sentence summary that names the \
decisive factors — especially any advocacy-vs-refutation judgment you made.
"""


def build_schema() -> dict:
    """JSON schema for the judge's structured output (Anthropic tool-use shape)."""
    dim_obj = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short verbatim substrings from the text.",
            },
            "note": {"type": "string", "description": "One-sentence justification."},
        },
        "required": ["score", "evidence", "note"],
        "additionalProperties": False,
    }
    counter_obj = {
        "type": "object",
        "properties": {
            "stance": {"type": "string", "enum": ["advocacy", "refutation", "absent"]},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string"},
        },
        "required": ["stance", "evidence", "note"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "dimensions": {
                "type": "object",
                "properties": {d: dim_obj for d, _ in DIMENSIONS},
                "required": [d for d, _ in DIMENSIONS],
                "additionalProperties": False,
            },
            "counter_indicators": {
                "type": "object",
                "properties": {c: counter_obj for c, _ in COUNTER_INDICATORS},
                "required": [c for c, _ in COUNTER_INDICATORS],
                "additionalProperties": False,
            },
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "label": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["dimensions", "counter_indicators", "overall_score", "label", "summary"],
        "additionalProperties": False,
    }


def build_user_prompt(text: str) -> str:
    return (
        "Assess the following text for Wesleyan theological affinity, per the "
        "rubric. Score substance over vocabulary, and judge advocacy vs. "
        "refutation for each counter-indicator.\n\n"
        "=== BEGIN TEXT ===\n"
        f"{text}\n"
        "=== END TEXT ==="
    )
