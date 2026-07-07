"""SWI v2 LLM judge — Phase 2b (plans/2026-07-07-swi-v2-ocr-cleanup-verification.md).

Calls Claude with rubric.py's system prompt, forces the structured-output
schema via tool use, and returns the validated judge result. Raises on any
API error or malformed response — scoring.py's dispatcher decides whether to
fall back to the lexicon engine; this module has no fallback logic of its own.

Runtime model: Haiku 4.5. This is volume inference (public endpoint, ~3
users but no auth gate on /api/swi/score), not judgment-dense work — do not
upgrade the runtime model without evidence from scripts/swi_eval.py that
Haiku can't hold the subtle refutation cases.
"""
import os

import anthropic

from . import rubric

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2000
TOOL_NAME = "submit_swi_assessment"


def _tool_definition() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Submit the structured Wesleyan-affinity assessment.",
        "input_schema": rubric.build_schema(),
    }


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def score_with_judge(text: str) -> dict:
    """Score `text` with the LLM judge. Returns the validated schema dict
    augmented with engine/rubric_version/word_count. Raises RuntimeError /
    anthropic.APIError on failure — callers must catch and fall back."""
    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=rubric.SYSTEM_PROMPT,
        tools=[_tool_definition()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": rubric.build_user_prompt(text)}],
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError("Judge response contained no tool_use block")

    result = dict(tool_use.input)
    _validate(result)

    result["engine"] = "judge"
    result["rubric_version"] = rubric.RUBRIC_VERSION
    result["word_count"] = len(text.split())
    return result


def _validate(result: dict) -> None:
    """Defensive check beyond the API's own schema enforcement — a model
    can technically satisfy the JSON schema while omitting a key our
    consumers assume is present, or returning an out-of-range score."""
    required = {"dimensions", "counter_indicators", "overall_score", "label", "summary"}
    missing = required - result.keys()
    if missing:
        raise RuntimeError(f"Judge result missing keys: {missing}")

    dim_ids = {d for d, _ in rubric.DIMENSIONS}
    if set(result["dimensions"].keys()) != dim_ids:
        raise RuntimeError(f"Judge result dimension keys mismatch: {result['dimensions'].keys()}")

    counter_ids = {c for c, _ in rubric.COUNTER_INDICATORS}
    if set(result["counter_indicators"].keys()) != counter_ids:
        raise RuntimeError(f"Judge result counter_indicators keys mismatch")

    score = result["overall_score"]
    if not isinstance(score, int) or not (0 <= score <= 100):
        raise RuntimeError(f"Judge overall_score out of range: {score!r}")

    for dim, payload in result["dimensions"].items():
        s = payload.get("score")
        if not isinstance(s, int) or not (0 <= s <= 100):
            raise RuntimeError(f"Judge dimension {dim} score out of range: {s!r}")

    for ci, payload in result["counter_indicators"].items():
        stance = payload.get("stance")
        if stance not in ("advocacy", "refutation", "absent"):
            raise RuntimeError(f"Judge counter_indicator {ci} bad stance: {stance!r}")


def to_v1_shape(judge_result: dict, text: str) -> dict:
    """Adapt the judge's schema into v1's response shape so api.py and the
    existing UI need no changes. Locates each dimension's verbatim evidence
    quotes in the text for highlighting (same UX as v1's lexicon markers)."""
    dim_names = dict(rubric.DIMENSIONS)
    dimensions = {}
    for dim_id, payload in judge_result["dimensions"].items():
        markers = _locate_evidence(text, payload.get("evidence", []))
        dimensions[dim_id] = {
            "id": dim_id,
            "name": dim_names[dim_id],
            "score": payload["score"],
            "markers": markers,
            "explanation": payload.get("note", ""),
        }

    counter_names = dict(rubric.COUNTER_INDICATORS)
    counter_indicators = {}
    for ci_id, payload in judge_result["counter_indicators"].items():
        markers = _locate_evidence(text, payload.get("evidence", []))
        counter_indicators[ci_id] = {
            "id": ci_id,
            "name": counter_names[ci_id],
            "stance": payload["stance"],
            "markers": markers,
            "note": payload.get("note", ""),
        }

    all_markers = []
    for dim_data in dimensions.values():
        for m in dim_data["markers"]:
            m = dict(m)
            m["dimension"] = dim_data["name"]
            all_markers.append(m)
    seen = set()
    top_markers = []
    for m in all_markers:
        key = m["text"].lower()
        if key not in seen:
            seen.add(key)
            top_markers.append(m)
    top_markers = top_markers[:20]

    return {
        "overall_score": judge_result["overall_score"],
        "label": judge_result["label"],
        "dimensions": dimensions,
        "counter_indicators": counter_indicators,
        "top_markers": top_markers,
        "summary": judge_result["summary"],
        "word_count": judge_result["word_count"],
        "engine": "judge",
        "rubric_version": judge_result["rubric_version"],
    }


def _locate_evidence(text: str, quotes: list) -> list:
    """Find each evidence quote's offset in text via substring search.
    A quote the model paraphrased instead of copying verbatim simply
    won't be found and is dropped -- fails safe (no highlight) rather
    than highlighting the wrong span."""
    text_lower = text.lower()
    markers = []
    for q in quotes:
        if not q:
            continue
        idx = text_lower.find(q.lower())
        if idx == -1:
            continue
        markers.append({"text": text[idx:idx + len(q)], "offset": idx})
    return markers
