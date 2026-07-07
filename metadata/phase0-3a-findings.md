# Phase 0 (noise) + 3a (provenance) findings — 2026-07-07

Ran per the execution plan (`plans/2026-07-07-swi-v2-ocr-cleanup-verification.md`),
step 1: cheap measurement, no corpus changes. Outputs:
`metadata/noise-report.csv` (3,337 rows), `metadata/provenance-audit.csv` (3,337 rows).

## Noise report

- Dictionary: `/usr/share/dict/words` (234,502 words) + a period/KJV supplement
  (thee/thou/-eth/-est forms, saith, shew, connexion...) + a proper-noun
  whitelist harvested from the corpus itself (8,682 capitalized tokens
  appearing 5+ times).
- **Running headers (strict pattern `REV\.?\s*J\.?\s*WES[LI][EL]Y.*JOURNAL.*\d+`):
  584 passages**, all in `jw-journal*` sources. This is lower than the
  1,123 estimated in an earlier looser scan (per NOW.md/CLAUDE.md) —
  spot-checked the loose pattern (`REV.? J` + `JOURNAL` anywhere in the
  same passage) and it returns 637 matches, mostly false positives from
  footnote citations like "the Rev. James Clark ... Journal, 1755" (a
  different Rev. J. and an unrelated mention of "Journal"). **584 is the
  more trustworthy count** — use it as the before/after yardstick for
  header-stripping.
- Journal sources overall: 19 sources, 1.29M words, weighted-average
  non-word rate 3.9%.
- Noisiest sources by rate (>=500 words, to exclude tiny-sample noise):
  1. `jw-primitive-physick` — 11.4% (26K words; archaic medical/Latin
     recipe terms, plausibly legitimate rather than OCR damage — worth a
     manual spot-check, not blind substitution)
  2. `cw-1816-memoir` — 8.7%
  3. `jw-general-rules` — 8.0%
  4. Several Charles Wesley sermons/hymn-collections in the 6-7% range —
     CW material is systematically noisier than JW material in this
     corpus.
- Short letters (under ~15 words) dominate the raw noise-rate ranking but
  are sample-size artifacts (a single unrecognized surname in an 8-word
  passage looks like 20%+ noise) — **filter to >=500 words** when using
  this report to prioritize cleanup work, per the plan's own caveat about
  over-counting proper nouns.

## Provenance audit

Classified all 3,337 source_ids into ~13 collections by embedded
`Source:` header lines in raw files, hardcoded URLs in
`download_*.py`/`extract_*.py` scripts, and documented history
(CLAUDE.md, memory). Verdict distribution:

| Verdict | Sources | Words | % of corpus |
|---|---|---|---|
| GREEN | 571 | 3.66M | 46.4% |
| YELLOW | 2,732 | 3.12M | 39.5% |
| RED | 34 | 1.11M | 14.1% |

**YELLOW is overwhelmingly one collection: `jw-letter*` (2,717 sources,
1.82M words).** Every raw letter file carries an embedded
`Source: The Letters of John Wesley (YEAR)` header confirming these are
genuinely Wesley's letters, organized by the letter's year — but no
`download_*.py` script or `source_url` was ever logged for this
collection (unlike sermons, Duke Charles Wesley material, or the 1816
Charles Wesley sermons, which all have a script or per-passage URL).
Recommend Wilson confirm which edition this is (Telford's 1931 8-vol
*Standard Letters*, or an older PD compilation — the per-year grouping is
consistent with either) and backfill a URL once confirmed. Not urgent —
text authenticity looks solid — but it's the single largest unverified
slice of the corpus.

**RED — the actual finding worth flagging before any cleanup work:**
34 sources didn't match any collection rule. Of these, four are large and
concerning:

- `jw-wesley-collected-works-vol-8/9/10/11` — **914K words total**, each
  ingested 2026-01-30 as one flat file (`wesley-collected-works-vol-N.txt`
  → 582-614 chunks each). These are the *entire* Zondervan reprint volumes
  10 and 11 (and 8, 9), dumped whole. **Spot-checked and confirmed these
  duplicate content already served via the individually-named
  `jw-treatise-*` sources**, which were separately extracted and cleaned
  from the same four volumes (`Source: The Works of John Wesley, Volume
  10/11 (Zondervan)` headers). Exact-string match on the treatise's body
  text against the corresponding volume dump confirms literal duplication
  for 11/128 sampled treatise files; most others use a different
  transcription/OCR pass of the same underlying text (so not
  byte-identical, but the same works served twice under different
  source_ids). **This means anywhere from a few hundred to a couple
  thousand passages of the 24,656 total may be near-duplicate content**
  competing in search results and skewing SWI scores if a text is more
  "findable." Recommend before Phase 1-2 cleanup: decide whether to
  retire the four `wesley-collected-works-vol-*` sources entirely (the
  treatises are individually attributed and presumably cleaner) or keep
  them and dedupe against treatises. This is a real decision, not a
  measurement — flagging for Wilson rather than acting.
- `cw-hymns-1780` (167K words) — not a duplication concern; sources.csv
  marks this "pending" from Jan 2025 but it was in fact downloaded and
  ingested later without updating that row. sources.csv is simply
  abandoned after the first 12 entries, not a signal of a real problem.
- The remaining ~29 RED sources are individually small (famous named
  hymns like "Love Divine," "O for a Thousand Tongues," plus
  `jw-thoughts-slavery`, `jw-means-of-grace`, `jw-plain-account-of-
  kingswood-school`) — low word count, low risk, just need a one-line
  collection-rule addition to reclassify as GREEN; no content concern.

## Recommended next steps (per the plan's execution order)

1. **Wilson decision on the Works vol-8/9/10/11 duplication** — retire,
   keep, or dedupe. This blocks nothing else but should happen before
   Phase 1-2 (re-chunking is more work if these get retired after).
2. **3c sentinel-quote suite** (per plan) — build next, before any
   cleaning, so there's a regression net. Given the finding above, add a
   sentinel case for at least one of the duplicated treatises to catch
   future re-duplication.
3. **Phase 1-2 OCR fixes** on the confirmed noisiest sources (Primitive
   Physick, CW material, journal headers) — informed by this report.
