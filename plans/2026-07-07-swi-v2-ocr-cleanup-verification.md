# Plan: SWI v2 (LLM judge) · Corpus OCR Cleanup · Text Accuracy Verification

Written 2026-07-07 (Fable session). This is the execution plan — run the build
phases in cheaper sessions (model tier noted per phase). Repo: `~/wesley-corpus`.
Deploys go to Fly app `wesley-corpus` under **gryngamour@gmail.com** (see CLAUDE.md).

---

## Part 1 — SWI v2: a better way to measure "how Wesleyan is this text"

### What v1 actually is (assessment)

The current SWI (`strangely_warm_index/`) is a **keyword counter**: seven
regex/phrase-list dimensions, density- and count-clamped, blended 60/20/20
(theology/scripture/language), with a subtractive Calvinist penalty and a
hand-tuned refutation heuristic. Known weaknesses:

1. **It measures vocabulary overlap, not theology.** A Calvinist sermon dense
   in "grace/sanctification/holiness" scores high unless it uses the exact
   TULIP phrases in the penalty list. A genuinely Wesleyan text in modern
   idiom (no 18th-century vocabulary) scores low. The tool answers "does this
   sound like 1770?" more than "is this Wesleyan?"
2. **Length bias is baked in.** Count-based clamps mean full sermons score 80+
   almost automatically; under-200-word texts are flagged unreliable. The
   advisory banner is a workaround, not a fix.
3. **Dead code / drift.** `score_rhetorical_style` is defined but excluded from
   `ALL_DIMENSIONS` (docstrings still say "8 dimensions"). `classifier.py`
   semantic scoring was deliberately dropped but is still called and
   swallowed by a bare `except`. Magic numbers throughout with no
   regression set to protect them.
4. **The feedback endpoint writes to the container filesystem** —
   `metadata/feedback.jsonl` doesn't exist locally and is lost on every Fly
   redeploy. (Moot: Wilson confirms there's no feedback worth keeping.)
5. **Refutation detection is brittle** — phrase-offset arithmetic
   ("each refutation marker cancels ~3 Calvinist hits") to approximate what
   is really a discourse-level judgment: is the author advocating or refuting?

### Why an LLM judge is now the right architecture

Usage reality: **~3 users, low volume.** That removes the constraint that
forced a lexicon model. An LLM judge:

- understands **advocacy vs. refutation** natively (Wesley quoting the
  "horrible decree" to attack it),
- recognizes Wesleyan theology in **any register** — modern sermons,
  paraphrase, other languages,
- has **no length bias**,
- produces genuinely useful explanations with **quoted evidence**, which is
  the most-loved part of the current UI.

Cost/latency: a 4,000-word sermon ≈ 6K input + ~1K output tokens.
Haiku 4.5 ≈ $0.01/score; Sonnet ≈ $0.04. Even 200 scores/month is pocket
change. Latency 5–20 s — acceptable with a "scoring…" state in the UI.

### Proposed design

**Keep the seven-dimension frame** (it's good Wesleyan theology — grace,
holiness, experiential religion, catholic spirit, social holiness, scriptural
density, Wesleyan voice). Replace the *scoring mechanism*:

```
strangely_warm_index/
  judge.py        # NEW — Anthropic API call, structured output
  rubric.py       # NEW — the rubric prompt, versioned (RUBRIC_VERSION const)
  scoring.py      # becomes dispatcher: judge if API key present, lexicon fallback
  dimensions.py   # KEPT — fallback scorer + marker highlighting for the UI
  cache.py        # NEW — sha256(text+rubric_version) → result JSON
```

- **Judge call**: single Claude API call with a structured-output schema:
  per-dimension `{score 0-100, evidence: [verbatim quotes], note}`, plus
  `counter_indicators` (Calvinist / antinomian / works-righteousness /
  quietist frameworks, each with advocacy-vs-refutation judgment),
  `overall_score`, `label` (reuse the existing SCORE_LABELS ladder),
  `summary` (2–3 sentences). Instruct the judge to score **theological
  substance, not vocabulary** — explicitly: a text may be deeply Wesleyan in
  modern language, and grace-vocabulary inside a Reformed framework is not
  Wesleyan.
- **Overall score comes from the judge**, not a code-side blend — but the
  rubric states the tier priorities (theology ≫ scripture ≫ style) so it's
  principled. No subtractive penalty arithmetic; counter-indicators inform
  the judge's overall directly.
- **Evidence quotes → UI highlighting**: locate the judge's verbatim quotes
  in the text by string search (same UX as current markers). Lexicon markers
  remain as a secondary layer if wanted.
- **Fallback**: no `ANTHROPIC_API_KEY` / API error → current lexicon scorer,
  response flagged `"engine": "lexicon-fallback"` so the UI can say so.
- **Cache**: keyed on text hash + rubric version, stored in a small SQLite
  file. On Fly it lives on the machine disk (ephemeral across deploys — fine;
  it's a cost/latency optimization, not state).
- **Spend guard**: this endpoint is publicly reachable. Cap LLM scores at
  e.g. 200/day globally (counter in the cache DB); overflow gets the lexicon
  fallback with a note. That bounds worst-case spend at ~$2–8/day even if
  someone scripts it.
- **Runtime model**: start with **Haiku 4.5** (`claude-haiku-4-5-20251001`).
  If the golden set (below) shows miscalibration on subtle cases (refutation,
  modern idiom), step up to Sonnet. Do NOT use a premium model at runtime —
  this is volume-shaped inference.

### Calibration without feedback data: the golden set

Build `metadata/swi-golden-set.jsonl` — **30–50 texts with expected score
ranges and a one-line rationale each**. This replaces feedback as ground truth
and becomes the regression suite for every rubric change. Composition:

| Bucket | Examples | Expected |
|---|---|---|
| Wesley core | Sermons 1, 5, 40, 43; Plain Account; "Free Grace" | 85–100 |
| Wesley refuting Calvinism | "Free Grace", Predestination Calmly Considered | 85+ (the acid test — v1 needed a special cap for these) |
| Wesleyan tradition | Fletcher, Watson, Charles hymns, a modern UMC sermon, BOD doctrinal standards excerpt | 65–90 |
| Grace-dense but Reformed | Whitefield sermon, Spurgeon, Calvin's Institutes excerpt | 15–40, counter-indicators flagged as *advocacy* |
| Adjacent Christian | Aquinas, BCP collects, a Catholic homily, Luther | 30–60 |
| Control | secular essay, news article, generic self-help | 0–15 |

Harness: `scripts/swi_eval.py` runs the judge over the set, prints
score-vs-expected deltas, fails if any bucket drifts out of range. Run it on
every rubric edit and before deploy.

### Build phases & model tiers

| Phase | Work | Session model |
|---|---|---|
| 2a | Write rubric prompt + golden set (judgment-dense) | Opus (the design above is most of it) |
| 2b | judge.py / cache.py / dispatcher / API wiring / spend cap | Sonnet |
| 2c | Run eval harness, tune rubric until golden set passes | Opus or Sonnet |
| 2d | UI: engine badge, spinner, evidence highlighting | Sonnet/Haiku |
| 2e | `fly secrets set ANTHROPIC_API_KEY=…` + deploy | Haiku — **deploy = hard stop, per-action OK** |

Independent of the OCR work — can ship before or after it. (SWI scores
user-submitted text; corpus cleanliness barely affects it.)

---

## Part 2 — OCR cleanup of the full corpus

### What we know (measured 2026-07-07)

- **1,123 of 24,656 served passages contain embedded running headers**
  (`REV. J. WESLEY'S JOURNAL` variants — 710 passages match `REV. J. WES`
  exactly; case/garble variants add the rest).
- Journal raw files (`raw/john-wesley/journal-vol*.txt`) have the systematic
  garbles documented in CLAUDE.md: day-name garbles (`Tvrspay`→`Tuesday` —
  italic-d misread as p), `tlie`→`the`, `WESLLY`→`WESLEY`, `rot/aot`→`not`,
  bare page numbers, header lines.
- A quick heuristic scan suggests noise also concentrates in
  `jw-minutes-conferences` (tables/columns), `jw-primitive-physick`, and the
  Charles Wesley material — but that scan over-counted proper nouns.
  **Phase 0 below produces the real scorecard before any fixing.**
- Cleaning history: `ocr_cleaning.py` already had one destructive regression
  (the `DEAR <NAME>,` pattern nuked real letter salutations, fixed
  2026-04-09). Every new rule needs a before/after diff review.

### Pipeline + gotchas (read before executing)

```
raw/ → process_corpus.py clean → cleaned/ → process_corpus.py chunk
     → chunked/passages.jsonl → clean_corpus.py → chunked/cleaned_passages.jsonl
     → tag_passages.py → extract_scripture_references.py → fly deploy
```

- **Passage IDs are `{source_id}-{chunk_index:03d}`** (process_corpus.py:204).
  Fixing raw text shifts chunk boundaries → **public `/passage/*` URLs churn**
  for the affected works. With ~3 users this is acceptable — but say so at
  deploy time. (Header-stripping *only* could be done at the chunk level to
  preserve IDs; the journal garble fixes genuinely need the raw pass, so
  accept churn for journals.)
- **Hymn/verse sources chunk by stanza** — line-joining rules must not touch
  the stanza chunker's input assumptions. Exclude `duke-cw-verse` and hymn
  files from any line-rejoining rule; verify a hymn passage renders with
  stanzas intact after re-run.
- `clean_corpus.py` must be re-run after ANY chunk-level change (serving file).
- Back up `chunked/passages.jsonl` and `cleaned_passages.jsonl` first
  (pattern already established: `.bak-pre-<change>-<date>`).
- Fly deploy under gryngamour@gmail.com.

### Phase 0 — Measure (Haiku/Sonnet, ~1 session)

Build `scripts/noise_report.py`: per-source **non-word rate** using
`/usr/share/dict/words` + a period/KJV supplement (thee/thou/-eth/-est forms,
saith, shew, connexion…) + a proper-noun whitelist harvested from the corpus
itself (capitalized tokens appearing 5+ times). Output
`metadata/noise-report.csv`: source_id, passages, words, non-word rate, top-20
offending tokens with counts. **This ranks the work and is the before/after
yardstick.** Also count header-containing passages per source.

### Phase 1 — Mechanical fixes, high confidence (Sonnet, 1–2 sessions)

Apply to `raw/` (journals + any source Phase 0 flags), as a new module or
extension of `ocr_cleaning.py`, each rule with a unit test:

1. **Running headers**: strip lines matching
   `REV\.?\s*J\.?\s*WESL[EL]Y.*JOURNAL.*\d+` and analogous per-work header
   patterns Phase 0 surfaces (all-caps title + page number lines).
2. **Journal garble table** from CLAUDE.md: day names (`Tvrspay, Wepnespay,
   Saturpay, Frwway, Toespay, Monpay, Sunpay, Thurspay`), `JOTN`→`JOHN`,
   `WESLLY`→`WESLEY`, `Inghart/Inghan`→`Ingham`, `tlie`→`the`, `[was`→`I was`,
   `'7`-style quote-bleed on day numbers. Word-boundary anchored, case-preserving.
   (Skip risky ones like bare `ot`→`of` unless dictionary-gated per Phase 2.)
3. **De-hyphenation / split-word rejoin**: generalize the hardcoded pairs in
   `ocr_cleaning.py` (`particu larly` etc.): rejoin `(\w{2,})[- ](\w{2,})`
   only when the joined form is in the dictionary AND at least one fragment
   is not. Dictionary gate makes this safe.
4. Re-run full pipeline, diff word counts per source (should change <1–2%),
   re-run Phase 0 report, compare.

### Phase 2 — Dictionary-gated substitution table (Sonnet builds, Wilson reviews table)

From the Phase 0 non-word list: for each non-word with frequency ≥ 3,
generate candidate fixes via known OCR confusion pairs
(`li↔h, rn↔m, c↔e, f↔s, p↔d(italic), t↔l, vv↔w, I↔l↔1`) — accept only if the
result is a dictionary/period word and the garble itself is not. Emit
`metadata/ocr-substitutions.csv` (garble, fix, count, sample context).
**Wilson reviews the table once** (not each instance), then it's applied
corpus-wide + added to `ocr_cleaning.py`'s permanent rules.

### Phase 3 — LLM cleanup of the worst passages (OPTIONAL, gated)

Rank remaining passages by non-word rate; the top slice (likely the
minutes' tables, Primitive Physick's recipes) gets an LLM pass with a strict
"fix OCR errors only — change no wording, no spelling modernization, no
punctuation style" prompt, applied as a reviewed diff.
**This is a volume job → Haiku, and a HARD STOP: estimate token burn first
(e.g. 500 passages × ~1.5K tokens ≈ 1.5M tokens round-trip) and ask
"which model, and go?"** Skip entirely if Phases 1–2 get non-word rates
under ~1% — likely for everything except tables.

### Phase 4 — Re-run + deploy + spot-check (Haiku)

Full pipeline re-run, `fly deploy` (hard stop), then spot-check:
search "Tuesday" for Georgia-period journal entries; open 3 previously
header-contaminated passages; confirm hymn stanzas intact; re-run Phase 0
report and record before/after in this file.

---

## Part 3 — Text accuracy verification (is it Wesley, and faithful?)

Distinct from noise: noise = garbled characters; accuracy = wrong/missing/
misattributed content. The Barnes contamination (2026-05-13: 1,208 chunks of
Albert Barnes served as Wesley's NT Notes for weeks) is the precedent —
assume there may be another one.

### 3a — Provenance audit (Sonnet, 1 session)

`metadata/sources.csv` + `ingestion-log.csv` → verify every `source_id` has:
edition identified, source URL, public-domain status, ingest date. Produce
`metadata/provenance-audit.csv` with a RED/YELLOW/GREEN per source. RED =
no known edition or URL. Prioritize: the works ingested in bulk
(letters-individual: 2,637 files; notes; minutes) where a mislabel would be
invisible.

### 3b — Attribution spot-check (the anti-Barnes pass)

For each multi-passage source: pull 3 random passages, check the text is
actually the claimed work — LLM-assisted ("is this passage plausibly from
<work> by <author>? quote the tell-tale features") + human eyeball on
anything flagged. Barnes was catchable this way in minutes. ~60 sources ×
3 passages — cheap Haiku fan-out, but cap at the 6-agent limit
(feedback_acta-usage) and keep it one session.

### 3c — Sentinel-quote regression suite (Opus writes the list once, Haiku runs it)

`metadata/sentinel-quotes.jsonl`: ~50 famous Wesley passages with canonical
wording and source ("I felt my heart strangely warmed" → Journal 24 May 1738;
"catholic spirit" passages; "gain all you can…"; General Rules triad; Notes
on Rom 8; a Charles hymn stanza…). Script searches the corpus for each and
verifies (a) found, (b) wording matches canonical within tolerance.
Catches OCR damage, missing content, and mislabeled sources in one shot —
and doubles as the permanent regression test after every cleanup/re-chunk.

### 3d — Sample collation against reference editions (slow-burn, optional)

For the highest-value works (Sermons, Journal, Plain Account): diff sampled
passages against Wesley Center (wesley.nnu.edu) / CCEL texts. LLM-assisted
comparison, N=5 passages/work. Only escalate to full collation if sampling
shows real divergence.

---

## Execution order (recommended)

1. **Phase 0 noise report + 3a provenance audit** — cheap, pure measurement,
   informs everything else. (One Sonnet session.)
2. **3c sentinel suite** — build it BEFORE cleaning, so cleanup has a
   regression net. (Golden-set/sentinel authoring is the one judgment-dense
   piece — Opus.)
3. **Phases 1–2 OCR fixes** → re-run → deploy (hard stop).
4. **SWI v2** (Part 1) — parallel track, independent of corpus state.
5. **3b/3d and Phase 3** — as appetite allows; each is optional and gated.

## Open decisions for Wilson

- SWI v2 runtime judge model: start Haiku 4.5, escalate to Sonnet only if the
  golden set demands it? (Recommended: yes.)
- Accept `/passage/*` URL churn from re-chunking? (Recommended: yes, 3 users.)
- Keep the lexicon engine visible as a "classic mode," or fallback-only?
  (Recommended: fallback-only; delete the dead rhetorical/semantic code.)
- Phase 3 LLM cleanup: only if Phase 0 shows Phases 1–2 left real damage —
  decision deferred until the after-report exists.
