# Sermon re-extraction from ResourceUMC — clean Jackson text

**Date:** 2026-07-20
**Target session:** Sonnet (mechanical, high-volume, verification-gated)
**Prereq reading:** `memory/reference_jackson-clean-text-source.md`, this file, `CLAUDE.md`

## The problem (verified on disk 2026-07-20)

`raw/john-wesley/sermon-*.txt` = 140 files. **137 of them contain zero `?`.**
Only 3 have any question marks at all (sermon-004: 15, sermon-016: 20, sermon-103: 1).

The corpus is a scrape of Wesley Center Online (wesley.nnu.edu), which systematically
stripped question marks. Every interrogative in Wesley's sermons currently reads as a
declarative. 2,248 passages across 151 sermon source_ids are affected.

## The decision: re-extract, do not repair

**Do NOT use an LLM to re-insert punctuation.** That is hallucination-shaped work on a
public-domain critical text. Instead pull the clean text from **ResourceUMC**
(`resourceumc.org`, official UMC digitization of the 1872 Jackson edition, punctuation
intact — On Eternity has 43 `?`).

The extractor already exists and is proven:
`~/wroot-press/wesley-metaphysical-sermons/build/extract-sermon.py`
(handles the `1872 edition` body marker, `</article>` bound, Acknowledgements/CCEL
boilerplate cut, `<br/>` verse breaks, scripture epigraph → blockquote).

---

## Phase 0 — Slug index (do this first, it gates everything)

Slugs have quirks and **must not be guessed** (J56 `...his-work` singular, J60
`...deliverence` misspelled).

1. Fetch `https://www.resourceumc.org/en/topics/history/john-wesley-sermons/title-index`
2. Parse every `sermon-<JNUM>-<slug>` href into `metadata/resourceumc-slugs.csv`
   columns: `jackson_num, slug, title, url`
3. **Reconcile against disk**: join to the 140 `raw/john-wesley/sermon-NNN-*.txt` files
   by Jackson number. Write `metadata/sermon-reextraction-manifest.csv`:
   `jackson_num, local_file, source_id, slug, status`
   where status ∈ `matched | no-remote | no-local | title-mismatch`.
4. **STOP and report the non-`matched` rows to Wilson before extracting.**
   Expect a handful: Sermons 142–151 are Abingdon-copyright (not in Jackson, will be
   `no-local`/`no-remote` — leave them alone), and local numbering may drift from
   Jackson on a few.

Do not proceed to Phase 1 until the manifest is clean and Wilson has seen the exceptions.

## Phase 1 — Extract to a parallel tree (non-destructive)

Extract into **`raw/john-wesley/sermons-resourceumc/`** — a new directory. Do not
overwrite `raw/john-wesley/sermon-*.txt` in this phase.

- Loop the manifest, `curl -sL <url> | python3.11 extract-sermon.py > sermons-resourceumc/<local_file>`
- **Rate-limit: 1–2 s sleep between requests.** ~140 requests, single-threaded. This is
  a courtesy crawl of a church-agency site, not a scrape race. Sequential only — no
  parallel fetching (also: 8 GB Mac).
- Retry once on non-200 or on the extractor's `ERROR:` exits; log failures, don't die.
- Write `metadata/reextraction-log.csv`: `jackson_num, http_status, bytes, q_count, word_count, result`

## Phase 2 — Verification gates (all three must pass per file)

A file is only eligible to replace its counterpart if:

1. **`?` present** — `q_count > 0`. A zero-`?` extraction means the fetch hit a mirror of
   the damaged text or the extractor mis-bounded the body. Quarantine it.
2. **Word-count delta within ±8%** of the local file. A large negative delta = truncated
   body (boilerplate cut fired too early). A large positive delta = teaser paragraphs or
   nav leaked in. Quarantine either way.
3. **Opening-sentence match** — normalize both texts (lowercase, strip punctuation and
   whitespace) and confirm the first 60 characters of Wesley's first body paragraph
   agree. Catches wrong-sermon slug collisions, which the first two gates miss.

Produce `metadata/reextraction-verification.csv` with per-file pass/fail per gate.
**Report the failure count to Wilson before the swap.** Quarantined files stay in
`sermons-resourceumc/` unused; the old file remains in place for those.

**Swap policy: per-file, not all-or-nothing (decided 2026-07-20).** A handful of bad
slugs must not block ~135 good fixes. But partial success has to be *legible*, or the
corpus quietly becomes half-clean with no record of which half:

- Write `metadata/sermons-still-damaged.csv` listing every sermon left on the old text,
  with the gate it failed and why. This file is the to-do list for the follow-up pass.
- If **more than 15 files** fail the gates, that is not a slug problem — it is a
  systematic extractor or site-structure problem. **Halt, do not swap any file**, and
  report to Wilson. Fixing the root cause once beats hand-patching 15 sermons.
- If a file is left damaged, it keeps its `?`-free text. Do not mark it clean anywhere.

Also spot-check by hand: diff 3 sermons (one short, one long, one with verse) and read
the diff — confirm the *only* systematic change is punctuation restoration, not
rewording. Paste one diff into the session for Wilson.

## Phase 3 — Swap + re-ingest

1. `git commit` the parallel tree and all metadata first, so the pre-swap state is a
   named commit (this replaces the `.bak-` file convention for this phase — the corpus
   already carries 6 backup copies of `passages.jsonl` and does not need a 7th).
2. Move verified files over `raw/john-wesley/sermon-*.txt`.
3. Re-run the pipeline for sermons only:
   `python scripts/ingest_batch.py raw/john-wesley/sermon-*.txt --author john-wesley --type sermon`
   **Critical: `source_id` must stay stable** (`jw-sermon-NNN`). Passage *ids/offsets*
   will shift as chunk boundaries move — that is expected and fine — but a changed
   `source_id` breaks `scripture-index.json`, `themes.csv`, and every saved link.
   Verify the 151 sermon source_ids before and after are the same set.
4. Regenerate `scripture-index.json` and re-tag themes (ingest_batch does both).
5. Re-run `scripts/noise_report.py` — expect sermon noise to **drop**; if it rises,
   something in the extraction is introducing artifacts.

## Phase 4 — Sentinel suite (the regression net)

`python scripts/check_sentinels.py` — baseline is **45 PASS / 1 FAIL**
(the lone known fail is `no-holiness-but-social`, a real content gap, not damage).

Any *new* failure blocks the swap. If a sentinel breaks, the likely cause is that
ResourceUMC's punctuation-intact text splits a chunk differently than the sentinel's
recorded span — inspect before assuming damage, but **do not "fix" it by loosening the
sentinel** without Wilson's OK.

**Required, not optional: add 6 interrogative sentinels.** Pick 6 question-lines from
6 *different* re-extracted sermons ("What is it to be almost a Christian?"), append them
to `metadata/sentinel-quotes.jsonl`, and confirm each PASSES post-swap and would have
FAILED pre-swap (verify the second half against the pre-swap commit — a sentinel that
passes in both directions is testing nothing).

New baseline after this session: **51 PASS / 1 FAIL.** Record that in the commit message
and in the memory file, so the next session knows the expected number.

Rationale: nothing in the current regression net detects punctuation stripping. Without
these, a future re-ingest from a bad source silently reintroduces the exact defect this
session exists to fix. This is the most durable output of the work — do not skip it if
the session runs long; drop Phase 5 instead and deploy later.

## Phase 5 — Deploy (HARD STOP)

`fly deploy -a wesley-corpus` under **`gryngamour@gmail.com`** (run `fly auth login`
with the right email first — not littleeachdayapp).

**This is a protected action. Surface the command and wait for Wilson's explicit OK.**
Merging/committing ≠ deploying.

---

## Known side effects to expect and mention

- **SWI judge cache is invalidated for every sermon.** Cache key is
  `sha256(text + rubric_version)`; changing the text changes every key. Sermons will
  re-judge on next request at ~20 s + API cost each, against the default 200/day cap.
  Nothing breaks — it just re-warms lazily. No action needed, but don't be surprised.
- **Passage counts will shift.** Restored punctuation changes sentence boundaries, so
  chunking will not land identically. Record before/after totals in the commit message.
- **`wesley-loci` has the same damage** (`~/wroot-press/wesley-loci/raw/*.txt`).
  Out of scope for this session — but the clean tree produced here is the fix for it
  too. Note it for a follow-up; do not touch that repo now.
- Residual typos in the ResourceUMC/CCEL lineage survive re-extraction
  ("presences"→presence, "forty-forth"→fourth). Those are an errata pass, not this pass.
  Log any spotted, fix none.

## Out of scope — do not scope-creep into these

- Sermons 142–151 (Abingdon copyright)
- The Charles Wesley sermons (different source, already clean)
- `jw-genuine-christianity` (the parked Phase-3 content-filter failure from 2026-07-07)
- Any SWI rubric or golden-set change
