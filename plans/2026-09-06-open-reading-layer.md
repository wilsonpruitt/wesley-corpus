# Plan: Open Reading Layer — works as canonical pages, provenance, crawlable text, bulk export

Written 2026-09-06 (Fable session) from the sketch in
`~/Downloads/wesley-corpus-open-layer.md` (copied to `plans/source/open-layer-sketch.md`).
This is the execution plan — build phases run in cheaper sessions (model tier noted per
phase). Repo: `~/wesley-corpus`. Deploys go to Fly app `wesley-corpus` under
**gryngamour@gmail.com** (see CLAUDE.md). Every deploy is a HARD STOP for Wilson's OK.

The thesis, in one line: **the work (a sermon, a letter, a journal year, a chapter of the
Notes, a hymn) becomes the canonical public page; passages become anchors within it; the
instrument (search, auto-themes, scripture index, SWI) stays behind Patreon.**

---

## What the sketch assumes vs. what is on disk (verified 2026-09-06)

The sketch is right about direction. Four of its assumptions do not match the corpus as
it exists, and they set the phase order.

| Sketch assumes | On disk | Consequence |
|---|---|---|
| Works are already a unit | Only for sermons (141 sources), treatises (134), letters (2,717 single-letter sources), CW individual hymns (253). Journal = 15 big undifferentiated multi-chunk sources. Notes NT/OT = 2 sources of 931 / 1,979 chunks split by *size*, not by chapter. 1780 *Collection* = one 453-chunk source, hymns not separated. | **Re-segmentation is the real work** for Journal, Notes, and the 1780 hymns. Sermons/treatises/letters can ship as work pages with zero re-segmentation. |
| Passages carry structural anchors (§II.1) | Passages are `source_id-NNN` with a `chunk_index`; no section markers | Anchors start as `#p{chunk_index}`. §-anchors are a later, sermons-first enrichment. |
| A numbering table exists | `metadata/sermon-reextraction-manifest.csv` has Jackson number ↔ source_id for JW sermons. No Bicentennial/Sugden columns. | Build the numbering table in Phase 1; it is a small, high-value lookup. |
| Text is publishable as-is | 45 sources exceed 5% non-word rate (43 letters, 2 treatises). Several treatises are visibly garbled (e.g. `jw-genuine-christianity`, non-word 4.4% but the opening is OCR soup). | **Quality gate** (below). Publishing garbled text as "trainable" teaches the wrong Wesley — the sketch's own argument against auto-themes applies to bad OCR too. |

Two things the sketch gets wrong for *this* site and which the plan overrides:

- `/random` and `/passage/*` are already public (`PUBLIC_PREFIXES` in `web_app.py`). The
  sketch wants `/random` disallowed for crawlers — agreed — but it must stay a working
  human feature (it's on the nav and linked from every passage page).
- The sketch's letter ID (`jw/letters/{date}-{recipient}`) needs a day-precision date.
  Our letter slugs carry `{year}-{seq}` (`jw-letter-1779-15-to-mrs-knapp`), not a day.
  Use `jw/letters/{year}/{seq}-{recipient}` and put the full date in `date_note` when
  Telford's dating is backfilled (2027).

---

## Decisions Wilson has to make before Phase 1 (answer in one line each)

1. **Quality gate threshold.** Proposal: a work is *open* (in sitemap, in export, full
   page) only if `non_word_rate ≤ 0.03` (from `metadata/noise-report.csv`) **or** it has
   been swapped to clean text (the 134 ResourceUMC sermons). Works above the threshold
   still get a page but with a "damaged transcription — not yet collated" banner,
   `noindex`, and exclusion from the JSONL export. Approve threshold or name another.
2. **License for transcriptions.** Sketch says CC0 on transcription corrections, CC BY
   4.0 on apparatus. That is the recommendation. Confirm — this is a rights statement
   and goes on every page.
3. **Hugging Face mirror.** Publishing there is an outward-facing send (hard stop #5).
   Decide now whether Phase 6 includes it or stops at `/export` on our own domain.
4. **Curated themes (Phase 7).** This is *your* reading time, not build time
   (20–40 passages × ~25 themes, each with a one-sentence note). Decide whether it
   is in scope for this cycle or deferred; it does not block anything else.

---

## Phase 0 — Work registry (gates everything; Sonnet)

**Goal:** one authoritative table mapping every open-layer *work* to its passages, stable
slug, and provenance, without touching `cleaned_passages.jsonl`.

Deliverable: `metadata/works.jsonl`, one record per work, schema from the sketch §2
(fields may be `null`; `date_precision` never null — use `"unknown"`). Built by a new
script `scripts/build_works.py` that reads `chunked/cleaned_passages.jsonl`,
`metadata/noise-report.csv`, `metadata/sermon-reextraction-manifest.csv`,
`metadata/swap-source-id-map.csv`, `metadata/ingestion-log.csv`.

Slug rules (from the sketch, adjusted to disk reality):

| Corpus | Slug | Built from |
|---|---|---|
| JW sermons | `jw/sermons/{NNN}` | Jackson number from manifest (Bicentennial column added in Phase 1) |
| JW treatises | `jw/works/{short-title}` | `source_id` minus `jw-treatise-`/`jw-` prefix; register short titles in `metadata/work-titles.csv` so a rename is a redirect, never a re-slug |
| JW letters | `jw/letters/{year}/{seq}-{recipient}` | parsed from `source_id` |
| JW journal | `jw/journal/{year}` | **Phase 2 re-segmentation**; Phase 0 registers each raw journal file as a placeholder work (`jw/journal/vol/{name}`) so nothing is orphaned |
| JW Notes | `jw/notes-nt/{osis}/{ch}`, `jw/notes-ot/{osis}/{ch}` | **Phase 3 re-segmentation**; Phase 0 placeholder = the two whole-source works |
| JW minutes | `jw/works/minutes-{year}` or one work `jw/works/minutes-1744-1798` | one work for now; per-year later if the text has clean year heads |
| CW hymns (individual) | `cw/hymns/{collection-slug}/{NNN}` | the 253 `cw-NNN-*` sources; collection from Duke metadata |
| CW hymn collections | `cw/hymns/{collection-slug}` | the 56 `cw-duke-*` sources as single works **until** Phase 4 splits the 1780 *Collection* |
| CW sermons/treatise | `cw/sermons/{n}`, `cw/works/{short-title}` | as JW |

Every work record also carries: `passage_ids` (ordered), `open` (bool, from the quality
gate), `quality.non_word_rate`, `quality.corrected_against_scan` (false everywhere),
`legacy_ids` (the passage IDs that must 301 to it).

**Gate to leave Phase 0:** every passage in `cleaned_passages.jsonl` belongs to exactly
one work; every work has ≥1 passage; slugs are unique; `python3 scripts/build_works.py
--check` exits 0. Commit `works.jsonl` and the script.

---

## Phase 1 — Numbering + provenance backfill for sermons (Sonnet; Wilson for the table)

**Goal:** the sermons are the most-cited unit and the cheapest to make citable.

1. `metadata/sermon-numbering.csv`: `jackson, bicentennial, sugden, title, text_basis,
   date_composed, date_precision`. Jackson ↔ Bicentennial is a known table (Outler's
   ordering matches Jackson 1–53 and diverges thereafter); Sugden covers 1–53 only. A
   Sonnet session drafts it from the Bicentennial contents (Wilson owns vols 9, 13, 32 —
   the sermon vols 1–4 are not on the shelf; use the published tables of contents).
   **Wilson spot-checks 10 rows before it is committed.**
2. ~~Jackson 1872 page ranges via archive.org `_djvu.txt`~~ — **DEFERRED to a future
   version (Wilson, 2026-09-06).** Checked ~18 archive.org copies of the 14-vol 1872
   reprint; every one is controlled-digital-lending (`access-restricted-item:true`), no
   free OCR text. HathiTrust blocks both WebFetch and a browser-UA `curl` (403); Chrome
   automation doesn't work on this machine (CLAUDE.md). The only freely accessible PD
   scan found is the *different* 1856 Emory 3rd American edition
   (`worksofrevjohnwe05/06/07wesluoft` on archive.org), whose pagination does not match
   the Jackson volume:page citations already in `sermon-numbering.csv` — linking to it
   would cite one edition's page number against a different edition's scan. Plain-text
   `jackson_ref` volume:page citations (no scan link) are unaffected and already in the
   numbering table; `source_edition.scan_url`/`scan_page_ids` stay `null` per the "partial
   backfill" allowance below. Revisit when a free, correctly-paginated source turns up
   (a personal Internet Archive lending account, a library scan, or similar).
3. `build_works.py` merges both files into `works.jsonl`.

Gate: 141 JW sermons have `numbering.jackson`; ≥120 have `source_edition.pages`;
misses listed. Memory rule applies: the digits in an archive.org ID are the *item*
number, not the volume — check the running head.

---

## Phase 2 — Journal re-segmentation into years (Opus for the boundary pass; Sonnet to wire) — DONE 2026-09-06

**Goal:** `jw/journal/{YYYY}` pages with dated entries as anchors.

The 15 journal sources are OCR-repaired but undated at the passage level. Method:

1. ~~Overlap check~~ **DONE 2026-09-06 (Opus boundary pass)** → `metadata/journal-overlap.csv`.
   The overlap is bigger and differently shaped than this plan assumed. Three edition
   families are mixed in the 15 journal sources, not one:
   - **`jw-journal-vol4-7` is a full duplicate of `jw-journal-1773-to-1776`** — same
     London 3rd ed. vol IV, two scans. Both open "NUMBER XVII / VOL. IV" at 1773-09-13
     with identical wording and both close with the identical Brigstock deed. `vol4-7`
     has markedly worse word-joining OCR ("Iwas muchworse,mypalate" vs "I was much
     worse, my palate"; non-word rate 0.029 vs 0.010). **Close `vol4-7`** (546
     passages / 213K words of duplication). ⚠ `1773-to-1776`'s filename is misleading:
     it runs to **1790**, not 1776.
   - **The `vol4-part09…13` files are Curnock's Standard Edition (1909–16)**, not the
     same edition at all, with Curnock's editorial notes inline and unmarked. Parts 09,
     10, 12, 13 duplicate spans the other spines already carry (their FROM/TO headers
     match the other files' extract headers exactly).
   - **`vol4-part11` is the one indispensable part file**: it covers 1758-06-17 →
     1760-05-05, exactly the gap between the Emory spine (ends 1758-06-16) and the
     London vol III spine (starts 1760-05-06). Without it the corpus has a 23-month
     hole. Applying the ledger gives continuous coverage **1728-02-01 → 1790-10-24**.
2. Entry heads + dates — **DONE 2026-09-06** (Sonnet, same session as the boundary
   pass) → `scripts/journal_boundaries.py` → `metadata/journal-entry-boundaries.csv`,
   **96.0% dated (10,182 / 10,605), past the plan's 95% target**. What the pass
   established:
   - **Wesley states the weekday of every entry, so dates self-validate.** Pre-1752
     dates are Julian (Britain switched 1752-09-14); the validator handles both and
     was checked against 12 known entries across all four editions, 12/12.
   - **The weekday check cannot pick a month, only reject one.** Measured: within a
     year ~2 months share a starting weekday, so a run of entries fits ~2 candidate
     months regardless of run length (flat from 1 to 8 entries). Date resolution is
     therefore a *constrained walk* — explicit signals set state, month advances only
     when the day number goes backwards, weekday + forward chronology are hard
     constraints — not an inference. A fully-stated date (year AND month both given)
     is trusted on the weekday check alone, never second-guessed against a
     possibly-already-wrong prior state.
   - **The inline-entry trap:** entries run into the previous line with no `.—`
     separator ("Friday, 17. I went to…") are ordinary entries. A regex tuned only on
     `.—` silently drops them.
   - **process_corpus.py's cleaning strips the FROM/TO extract headers as
     front-matter noise** — they don't exist in `cleaned/`, only in `raw/`. Recovered
     by finding each header + its extract's first entry in the RAW file, then mapping
     that entry's body text onto the equivalent offset in the CLEANED file via a
     letters-only anchor (`find_checkpoints`). Without this, only 1 of vol1-3's 9
     extracts had a reseed point at all.
   - **Curnock's `[Journal, YYYY]` page-tag can lag a New Year's Day entry that
     announces the rollover inline** ("[Journal, 1755] 1756, Jan. 1.-") — Curnock
     updates the tag per printed page, not per calendar day. An inline year now
     outranks the tag, and state-continuation is tried before the tag's year is
     trusted as absolute. This one fix alone took the weakest Curnock files from
     ~50% to 97-100%.
   - **A second-pass rescue catches entries the constrained walk can never reach at
     all.** Emory's opening extract, "FROM FEBRUARY 1, 1728, TO AUGUST 12, 1738",
     turns out to be Wesley's decade-spanning retrospective narrative quoting
     Moravian testimonies out of strict order, not a day-by-day diary — by the time
     a forward walk reaches **the Aldersgate entry** ("Wednesday, May 24" = 1738,
     the date the site's own Strangely Warmed Index is named for) its state is stuck
     a decade earlier. `rescue_with_nearby_year` recovers these by searching
     backward in the actual text for the nearest bare year mention. Aldersgate now
     resolves correctly. Known imperfection: one entry (of 729 rescued) pulled a
     wrong year from an embedded quoted narrative with its own date context —
     tagged `status="rescued"`, distinct from the primary walk's `"ok"`, so it reads
     as lower-confidence rather than silently equal.
   - **A bare "MONTH YEAR, In <place>" section head with no FROM/TO header at all**
     (`journal-vol4-part11-section02`, which fills half of the indispensable
     1758-60 gap) left its ctx_year-only first entries with no month to anchor on,
     guessing an entire year wrong at the file's start. `MONTH_YEAR_HEAD_RE` catches
     this specific convention as a fallback checkpoint type when no `FROM...TO`
     header exists in a file — took that file from 68% to 90%.
   - **A final consistency guard** (`demote_inconsistent_dates`) catches runs the
     rescue mechanism gets wrong in files thick with quoted correspondence carrying
     their own embedded dates — found a 14-entry run resolved to 1752 sitting inside
     an otherwise-continuous 1757 stretch in a Curnock part file (self-reinforcing:
     once state drifted, each next entry's weekday check "confirmed" the wrong year
     in turn). Any date more than 3 years from the median of its surrounding 15
     dated neighbors is demoted back to unresolved rather than published as if it
     were as trustworthy as the rest.
   - Dates past the Journal's documented 1735-10-14 → 1790-10-24 span are flagged
     `out-of-range` rather than published.
   - Remaining 4.0% unresolved is concentrated in the two files this doesn't need to
     be perfect on: `vol4-7` (closing as a duplicate per the overlap ledger) and the
     rest of vol1-3's decade-spanning preface (the rescue catches the highest-value
     entry; a few obscure ones in that same essay stay flagged). Every file that
     matters for the actual year-page build — the three KEEP-SPINE files and
     `vol4-part11` — is at 88-100%.
3. Re-chunk on entry boundaries into a parallel file `chunked/journal_by_entry.jsonl` —
   **DONE 2026-09-06** (`scripts/build_journal_entries.py`). 6,712 passages, 56 years
   (1735-1790), zero gaps, `work = jw/journal/{YYYY}`, `anchor = {YYYY-MM-DD}` (+`-b`,
   `-c` for genuine same-day multiple entries — 66 dates have one). Only KEEP-marked
   sources from the overlap ledger are used; KEEP-UNIQUE sources are additionally
   trimmed to their own stated gap-filling window (`covers_from`..`covers_to`), which
   caught 16 stray entries from `vol4-part11-section02` dated months past its actual
   1758-60 gap — all colliding with the spine file that already owns that ground.
   Two real bugs caught by re-running the plan's own sentinel gate before trusting
   this file:
   - **Text needs `ocr_cleaning.clean_text()`, same as every other passage gets via
     `clean_corpus.py`.** Entries are sliced straight from `cleaned/*.txt`, which is
     only `process_corpus.py`'s first cleaning pass — line-wrap newlines inside
     sentences are still there ("I felt my\nheart strangely warmed"). Skipping the
     second pass meant a literal-substring sentinel search for the Aldersgate quote
     found nothing, despite the words being right there split across a line break.
   - **Unresolved entries between two successfully-dated ones get silently absorbed**
     into the preceding entry's sliced text (nothing in between to cut it off at).
     `jw-journal-1738-010` — Aldersgate itself — came out at 20,445 words because
     everything unresolved between May 24 and the next resolved entry (August 12,
     from vol1-3's messy decade-spanning preface) rode along inside it. Rather than
     let that stand as if it were one day's writing, any entry over 1,500 words
     (corpus mean 129 / median 69) is marked `date_precision: "range"` with a
     `content_extends_to` field naming the next entry's date — 48 passages flagged.
4. Overlap/duplication ledger: `metadata/journal-overlap.csv`.

Gate: every day from 1735-10-14 (embarkation) to 1790-10-24 (last entry) that the
raw text contains is assigned — **confirmed, 56/56 years present, no gaps**; year
pages are contiguous; the 3 journal-scoped sentinel quotes (of 52 total) resolve
against `chunked/journal_by_entry.jsonl`, checked directly since
`scripts/check_sentinels.py` is hardcoded to the old serving file — **all 3 pass**,
including "I felt my heart strangely warmed" (Aldersgate) and "I look upon all the
world as my parish". Known gap to record, not fix: the journal's own coverage gaps
(Wesley printed 21 extracts; the corpus may not hold all of them).

---

## Phase 3 — Notes re-segmentation into chapters (Sonnet)

**Goal:** `jw/notes-nt/{osis}/{ch}` and `jw/notes-ot/{osis}/{ch}`, addressable by verse.

The Notes text has explicit chapter heads (`Chapter V`) and Wesley's bare verse-number
style (`16. And were carried over…`). This is the same problem the scripture extractor
never solved (CLAUDE.md gotcha) — solve it here once, at the segmentation layer:

1. `scripts/segment_notes.py`: book heads → OSIS code; `Chapter N` → chapter; leading
   `NN.` at paragraph start → verse anchor `#v{NN}`. Emit
   `chunked/notes_by_chapter.jsonl`.
2. Feed the resulting `(book, chapter, verse)` triples back into `scripture-index.json`
   as `Rom.8.16`-style OSIS refs — this closes the CLAUDE.md gap where the Notes
   contribute near-zero to the scripture index.

Gate: NT = 260 chapters, OT = 929 chapters, minus any Wesley did not annotate (record the
list); no chapter has zero text; verse anchors monotonic within a chapter.

---

## Phase 4 — 1780 *Collection* split into hymns (Sonnet)

**Goal:** `cw/hymns/1780/{NNN}` for all 525 hymns, line breaks preserved.

`cw-hymns-1780` is one 453-chunk source from CCEL. Hymn heads are numbered in the
source. Split on hymn number; keep stanza/line structure (**a hymn flattened to prose is a
different text** — verify the raw file still has line breaks; if `process_corpus.py
clean` collapsed them, re-derive from `raw/`). The 56 Duke collections stay whole works
this cycle; the 253 individual `cw-NNN-*` hymns are already works.

Gate: 525 hymns numbered 1–525 with no gaps; stanza count per hymn matches the source.

---

## Phase 5 — Work pages, siblings, redirects, robots, sitemap (Sonnet; deploy = HARD STOP)

**Goal:** the public reading layer is live on the existing FastAPI app. No new infra.

1. Loader: `web_app.py` loads `metadata/works.jsonl` at startup alongside passages;
   builds `WORKS_BY_SLUG`, `WORK_BY_PASSAGE_ID`.
2. Routes (all added to `PUBLIC_PREFIXES`):
   - `GET /{author}/{corpus}/{...slug}` → `templates/work.html` (sketch §3: H1 = work
     title; provenance `<details open>`; `<p id="p{n}">` per passage; hymns use
     `<div class="stanza">`; `rel=prev/next`; JSON-LD; DC meta; `rel=alternate`
     `.txt`/`.json`; one-line license footer). **No `_ctx` login gating**, readable with
     JS off, no fonts required to read.
   - `GET /{slug}.txt` → plain text, `text/plain; charset=utf-8`, a 6-line provenance
     header then the text.
   - `GET /{slug}.json` → the work record with `passages[]` inline.
   - `GET /{author}` and `GET /{author}/{corpus}` → collection index pages (these are
     what a crawler walks; keep them plain lists).
   - `GET /passage/{id}` → **301** to `/{work}#p{n}`. Keep `/api/passage/{id}` as is
     (patron API).
   - Not-open works (quality gate) render with the damage banner and
     `<meta name="robots" content="noindex">`.
3. `static/robots.txt` served at `/robots.txt` — the sketch §4 list verbatim, plus
   `Disallow: /passage/` (they are all redirects now) and `Disallow: /sources`.
   `static/llms.txt` at `/llms.txt`.
4. `/sitemap.xml` index + `/sitemaps/{corpus}.xml` children generated at startup from
   `works.jsonl` (`lastmod` = work `updated_at`, only `open` works, work URLs only).
5. `/license` page (sketch §6), in Wilson's voice — **Wilson writes or edits the
   prose**; the build session drafts it.
6. Nav: add "Browse" (→ `/jw`) to `base.html`; keep Random.
7. Memory: 1 GB VM. `works.jsonl` with passage lists is small; the `.txt`/`.json`
   siblings are generated per request, not cached. Check RSS after startup stays under
   ~600 MB before deploy.

**HARD STOP before `fly deploy`.** After deploy, run the sketch §11 checks and record
them in `metadata/open-layer-launch-checks.md`:
`curl -A GPTBot https://corpus.historyofmethodism.com/jw/sermons/043` returns full text
with no login redirect; `/search` still redirects to login; `/random` still works for a
human; JSON-LD validates; an old `/passage/…` URL 301s to the right anchor.

---

## Phase 6 — Bulk export (Sonnet; HF mirror = HARD STOP)

1. `scripts/build_export.py` → `export/wesley-corpus-{date}.jsonl.gz` (one line per
   *open* work, full text inline), `export/wesley-corpus-{date}-passages.jsonl.gz`,
   `export/txt/{corpus}/{id}.txt`, `export/README.md` (schema, license, changelog).
2. Serve `/export/` from the app (static mount). Size check: whole corpus is ~9M words
   ≈ 50 MB text, ~15 MB gzipped — fine on the Fly volume, but **do not bake into the
   Docker image**; build in CI or locally and upload. If it pushes the image past what
   the 1 GB VM likes, put `export/` on Cloudflare R2 behind `export.` (Wilson's domains
   are all at Cloudflare) and link from `/export`.
3. Cadence: regenerate on each deploy that touches text; keep old versions.
4. **If approved in decision 3:** Hugging Face dataset `historyofmethodism/wesley-corpus`
   with a dataset card repeating the license + provenance story. Outward-facing send —
   ask before pushing.

---

## Phase 7 — Curated themes (Wilson's reading; Sonnet for scaffolding) — optional this cycle

- Scaffold: `metadata/themes-curated.jsonl` (`theme, passage, note`), a `/themes/{slug}`
  open page (small anthology with provenance), and `Allow: /themes/` in robots once ≥5
  themes have ≥20 passages each. `/theme/` (auto) stays disallowed and gated.
- Working method that respects attention: a Sonnet session proposes 60 candidates per
  theme from `themes_auto` ranked by SWI; Wilson keeps 20–40 and writes the notes.
  The counts in the sketch (Catholic Spirit 9,578 vs Christian Perfection 58) are the
  argument for why this cannot be automated.

---

## Phase 8 — Provenance against page scans (Haiku/Sonnet per unit; Telford in 2027)

**Whole phase deferred to a future version (Wilson, 2026-09-06)** pending a free,
correctly-paginated source for Jackson's 1872 edition — see the Phase 1 note above.
Sermons hit this first since they were the first work type slugged; the same blocker
applies to every other work type below, not just sermons.

Priority order from the sketch: Sermons → *Plain Account* + the *Appeals* → Journal
(Curnock) → Notes NT → 1780 hymns → Notes OT → Letters (Telford enters US PD
2027-01-01; build the pipeline in Q4 2026, run it in January).

Per work: locate in scan (Phase 1 script generalised), align paragraph starts to OCR
page boundaries, insert `<span class="pb" data-page>` markers, flip
`corrected_against_scan` only after a diff has been read. Memory rules that bite here:
plate-sweep marker false-rates vary **by work** (never one policy over the backlog);
a contiguous sample is not a rule; check the *built* page, not the data, before calling
a work collated.

---

## Order and model tier

| Phase | What | Tier | Blocks |
|---|---|---|---|
| 0 | Work registry | Sonnet | everything |
| 1 | Sermon numbering + scan pages | Sonnet (+Wilson check) | 5 (nice), 8 |
| 2 | Journal → years | Opus boundaries, Sonnet wiring | 5 for journal only |
| 3 | Notes → chapters | Sonnet | 5 for notes only |
| 4 | 1780 hymns split | Sonnet | 5 for hymns only |
| 5 | Pages/robots/sitemap/redirects | Sonnet | 6 |
| 6 | Export (+HF) | Sonnet | — |
| 7 | Curated themes | Wilson | — |
| 8 | Scan provenance | Haiku/Sonnet | — |

**Ship in two releases.** Release A = Phases 0, 1, 5, 6 with sermons, treatises, letters,
individual CW hymns as real works and Journal/Notes/1780 as placeholder whole-source
works (the redirects and robots are right from day one). Release B = Phases 2, 3, 4
swap the placeholders for real segmentation; the placeholder slugs 301 to the new ones.
This gets crawlers the sermons — the most-cited unit — weeks before the journal is
segmented, and nothing already linked ever breaks.

---

## Out of scope — do not scope-creep into these

- Changing the paywall, Patreon tiers, or which instrument features are gated.
- Re-running OCR cleanup on the 45 gated works (separate plan; the gate makes them
  invisible to crawlers, which is enough for now).
- Semantic search / embeddings (dropped deliberately; stays dropped).
- Bicentennial (in-copyright) text — the open layer is Jackson/CCEL/ResourceUMC PD text only.
- Rewriting `process_corpus.py`. All segmentation writes parallel files; the serving
  file changes only in Phase 5/Release B and only after sentinels pass.
