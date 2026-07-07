# SWI v2 Phase 2c — findings from eval run 1 (2026-07-07)

First live run of `scripts/swi_eval.py` against the 36-entry golden set.
Raw log: `metadata/swi-eval-run1-2026-07-07.log`. Result: **19/36 PASS**
(after fixing 2 crashes — see below, not re-run yet with the fix).

## Bugs fixed (commit `99393c4`)

2 of 36 calls crashed: `'str' object has no attribute 'keys'` and
`Judge result missing keys: {'counter_indicators'}`. Root cause:
`MAX_TOKENS=2000` was too tight for the schema (7 dimensions + 4
counter-indicators, each needing evidence quotes + a note, plus a summary)
— Haiku truncated mid-JSON. Fixed: `MAX_TOKENS` 2000→4096, explicit
`stop_reason == "max_tokens"` check, one retry at 6144. Verified against
both failing entries — no longer crash (`gs-wesley-scripture-way` → 82,
`gs-athanasius-theosis` → 12). **Not yet re-run against the full 36** —
do that first in the next session, it's free information before deciding
what else to tune.

## Calibration findings — genuinely open questions, not yet acted on

### 1. wesley-core bucket: 1/9 passed, but likely my expectations were too tight
Scores cluster at 72–82 across genuinely core Wesley texts (Scripture Way
of Salvation, New Birth, Character of a Methodist, Catholic Spirit), just
under my 82–85 floors. These are single-paragraph excerpts (~250–400
words), each strongly on-topic for 1–2 of the 7 dimensions and necessarily
silent on the other 5. A holistic judge scoring "silent ≠ 0 but not full
credit" per dimension will naturally land in the 70s–80s for a focused
excerpt, even a theologically perfect one — the rubric may be working as
designed. **Hypothesis: loosen wesley-core's expected_min into the
low-to-mid 70s** rather than assume the judge is wrong. Test this by
re-running on a LONGER Wesley text (a full sermon, not an excerpt) to see
if score rises when more dimensions get textual support — if it does,
that confirms length/topical-focus is the driver, not a rubric defect.

### 2. Possible over-punitive counter-indicator gating (needs real investigation)
`gs-whitefield-reply` scored 8 (expected 12–38) and `gs-westminster-election`
scored 5 (expected 8–30) — both landed AT OR BELOW the floor, not just
under it. The rubric's guidance says a counter-indicator-advocacy text
"cannot exceed ~50," which should still leave room for warmth/experiential
credit within a 10–50 band depending on the text's other qualities.
Whitefield's reply is a genuinely warm, evangelical, experientially-charged
piece of writing — it should NOT score identically to a dry creedal
statement like Westminster III.3. If the judge is flattening all
Calvinist-advocacy text toward near-zero regardless of its other
qualities, that's a rubric-wording problem worth fixing: the "cannot
exceed ~50" ceiling language may be getting read by the model as "should
approach 0" in practice. **Action: after re-running the full set, isolate
just these entries and read the judge's full per-dimension breakdown
(not just overall_score) to see whether it's crediting grace_theology /
experiential_religion at all for Whitefield, or zeroing everything out
once calvinist=advocacy is detected.**

### 3. adjacent-christian bucket: 1/5, systematically low (Aquinas 28, Kempis 28,
Luther 28, Athanasius 12 — all near or below their floors)
Same shape as #2: possible general judge conservatism toward any text
that isn't distinctively Wesleyan, even when it's rich, serious, orthodox
Christian writing that Wesley himself drew on (Luther's Romans preface
triggered Aldersgate; Wesley abridged à Kempis for Methodist use). Could
be genuinely correct (none of these have Wesley's DISTINCTIVE holiness/
perfection/catholic-spirit/social-holiness content) or could be the same
"cannot exceed X" language reading too harshly. Needs the same
per-dimension inspection as #2 before concluding which.

### 4. Self-inflicted miss: gs-articles-of-religion (38 vs expected 62–85)
On reflection this was likely MY calibration error, not the judge's. The
Article IX excerpt is bare justification-by-faith-alone language Methodism
inherited nearly verbatim from the Anglican Articles — it contains NONE of
Wesley's seven-dimension distinctives (no holiness, perfection, catholic
spirit, social holiness — just grace/faith, shared with every Reformation
tradition). The judge has no way to know it's institutionally Methodist;
it can only score the text in front of it, per the rubric's own instruction
to judge substance not provenance. **Recommend: lower this entry's
expected range to something like 35–60 (matching adjacent-christian, not
wesleyan-tradition)** — or replace it with a different, more genuinely
Methodist-distinctive doctrinal-standard excerpt (e.g. from the General
Rules or the Articles' section on sanctification if one exists) if Wilson
wants a doctrinal-standard entry in that bucket at all.

## Recommended next steps (in order)
1. Re-run the full 36-entry eval with the token-budget fix — free
   information, confirms the crash fix and gives a clean current baseline.
2. For findings #2 and #3: pull the full per-dimension judge output (not
   just overall_score) for gs-whitefield-reply and the adjacent-christian
   entries, to see whether the judge is crediting non-Calvinist dimensions
   at all or zeroing them once a counter-indicator fires. This determines
   whether to edit rubric.py's ceiling language.
3. For finding #1: test one long-form Wesley text (full sermon) to check
   whether score rises with topical breadth — if so, adjust wesley-core's
   expected_min downward for the existing SHORT excerpts rather than
   conclude the rubric under-scores Wesley.
4. For finding #4: fix or replace gs-articles-of-religion.
5. Any rubric.py prose change → bump RUBRIC_VERSION → re-run full eval.
6. Only once the eval is clean (or Wilson accepts the remaining gaps):
   Phase 2d (UI) → Phase 2e (deploy, hard stop).
