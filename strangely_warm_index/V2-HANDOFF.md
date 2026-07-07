# SWI v2 — Phase 2a complete, handoff to 2b

Plan: `plans/2026-07-07-swi-v2-ocr-cleanup-verification.md` (Part 1).

## What 2a delivered (Opus — the judgment-dense pieces)

- **`strangely_warm_index/rubric.py`** — the versioned rubric (`RUBRIC_VERSION`),
  the 7-dimension + 4-counter-indicator definitions as a system prompt, the
  structured-output JSON schema (`build_schema()`), and the user-prompt builder
  (`build_user_prompt(text)`). Keeps v1's seven dimensions and `SCORE_LABELS`
  ladder; replaces the scoring *mechanism*. The core design move: the judge
  scores substance-not-vocabulary and returns an advocacy/refutation/absent
  stance per counter-indicator, so Wesley refuting Calvinism scores high instead
  of being penalized.
- **`metadata/swi-golden-set.jsonl`** (36 entries) + **`scripts/build_golden_set.py`**
  (regenerates it) — the calibration/regression ground truth. Buckets:
  wesley-core (9), refuting-calvinism (4), wesleyan-tradition (6, incl. 2 MODERN-
  idiom bias tests), grace-dense-reformed (5, incl. Spurgeon + Whitefield's reply
  to Wesley — the vocabulary-counter traps), adjacent-christian (5), counter-
  advocacy (3), control (4). 15 entries assert an `expected_counter` stance.

## Judge return contract (what 2b's judge.py must produce)

The judge calls the Anthropic API with `rubric.SYSTEM_PROMPT`,
`rubric.build_user_prompt(text)`, and forces the tool/schema from
`rubric.build_schema()`. The validated tool input is exactly:

```json
{
  "dimensions": {
    "grace_theology":       {"score": 0-100, "evidence": ["verbatim", ...], "note": "..."},
    "holiness_perfection":  {...}, "experiential_religion": {...},
    "catholic_spirit": {...}, "social_holiness": {...},
    "scriptural_grounding": {...}, "wesleyan_voice": {...}
  },
  "counter_indicators": {
    "calvinist":           {"stance": "advocacy|refutation|absent", "evidence": [...], "note": "..."},
    "antinomian": {...}, "works_righteousness": {...}, "quietist": {...}
  },
  "overall_score": 0-100,
  "label": "<one of SCORE_LABELS>",
  "summary": "2-3 sentences"
}
```

`judge.py` should return this augmented with `"engine": "judge"`, `"rubric_version":
RUBRIC_VERSION`, and `"word_count"`. To keep the UI unchanged, adapt it into v1's
response shape (`overall_score`, `label`, `dimensions{id:{name,score,markers,
explanation}}`, `summary`, `top_markers`, `word_count`): map each dimension's
`evidence[]` → `markers[]` by locating the verbatim substrings in the text (same
UX as v1's lexicon markers; `api.py` already does string-locate highlighting),
`note` → `explanation`, and the human `name` from `rubric.DIMENSIONS`. Surface
`counter_indicators` (with stance) in place of v1's `calvinist_penalty`.

## Remaining 2b/2c/2d/2e (per plan)

- **2b (Sonnet):** `judge.py` (API call + schema-forced tool use + the adapter
  above), `cache.py` (sqlite keyed on `sha256(text + RUBRIC_VERSION)`; also holds
  the global daily spend counter), `scoring.py` becomes a dispatcher (judge if
  `ANTHROPIC_API_KEY` present, else the existing v1 lexicon path flagged
  `"engine": "lexicon-fallback"`), spend cap (~200 LLM scores/day → overflow
  falls back to lexicon with a note). Runtime model: **Haiku 4.5**
  (`claude-haiku-4-5-20251001`) — this is volume inference, not premium work.
- **`scripts/swi_eval.py` (2c):** load the golden set, run judge.py over it, print
  score-vs-expected deltas AND check each `expected_counter` stance matches the
  judge's returned stance; exit non-zero if any bucket's score drifts out of
  [expected_min, expected_max] or any counter stance is wrong. This is the
  regression gate for every future rubric edit. Run it before 2e deploy.
- **2c tuning:** if the golden set fails (esp. the grace-dense-reformed traps
  scoring too high, or a refutation entry mis-scored as advocacy), tune the
  rubric prose in rubric.py, bump `RUBRIC_VERSION`, re-run. Escalate the runtime
  model Haiku→Sonnet only if Haiku can't hold the subtle refutation cases.
- **2d (Sonnet/Haiku):** UI — engine badge ("AI judge" vs "classic lexicon"),
  scoring spinner (5-20s latency), evidence highlighting from the judge quotes.
- **2e (Haiku):** `fly secrets set ANTHROPIC_API_KEY=…` + deploy. **Deploy is a
  hard stop — per-action OK from Wilson.** (Also note: 4 OCR-cleanup changes are
  already queued for the next Fly deploy; SWI v2 can ride along or ship separately.)

## Open design decisions Wilson already leaned on (plan §"Open decisions")
Start Haiku, escalate only if golden set demands · lexicon engine becomes
fallback-only (delete dead rhetorical/semantic code in a cleanup) · keep the
`SCORE_LABELS` ladder as-is.
