# Sentinel-quote regression suite (Phase 3c)

The corpus's **regression net** — 46 famous Wesley passages with canonical wording
and expected source, built and baselined *before* any OCR cleanup so we can prove a
cleanup closed damage without opening new gaps. Part of
`plans/2026-07-07-swi-v2-ocr-cleanup-verification.md` (Phase 3c: "Opus writes the
list once, Haiku runs it").

## Files

| File | Role |
|---|---|
| `metadata/sentinel-quotes.jsonl` | the authored sentinels (one JSON object per line) |
| `scripts/build_sentinel_quotes.py` | regenerates the JSONL + prints an anchor-locate baseline |
| `scripts/check_sentinels.py` | **the runner** — checks the corpus, exit 0 iff all pass |

## Running

```sh
python3.11 scripts/check_sentinels.py            # summary (shows only non-PASS)
python3.11 scripts/check_sentinels.py --verbose  # every sentinel
```

Run it **before and after** every OCR cleanup / re-chunk (Phases 1–2) and before
each `fly deploy`. A sentinel that was PASS and turns FAIL/WORDING is a regression
the change introduced. It is deterministic and LLM-free (cheap — safe for any tier).

## Schema (per line)

| field | meaning |
|---|---|
| `id` | slug |
| `author` | `john-wesley` \| `charles-wesley` |
| `work`, `reference` | human title + edition-independent citation |
| `source_id` | expected serving source (used as a **prefix scope** hint) |
| `alt_source_ids` | other legitimate loci (optional) |
| `anchor` | short, distinctive, OCR-robust locate key (case-insensitive substring) |
| `canonical` | verbatim expected wording from the critical text |
| `expect` | `present` (default) or `absent` (anti-contamination tripwire) |
| `catches` | what a failure reveals |
| `notes` | authenticity / known-garble / missing-content flag (optional) |

## How the runner decides

- **present**: the `anchor` must locate a passage; among *all* chunks containing the
  anchor it takes the best wording match (in-scope `source_id` gets a small tie-break
  bonus). `canonical` must match within tolerance (`WORDING_TOL = 0.82`, normalized
  `SequenceMatcher`). Verdicts: `PASS` / `WORDING` (located but drifted) / `FAIL`
  (anchor absent = missing content or heavy OCR damage).
- **absent**: the `anchor` must NOT appear anywhere. Used for the three
  **anti-Barnes tripwires** (`Rosenmuller`, `Tholuck`, `Kuinoel` — 19th-c. scholars
  Wesley never cited). If one ever appears, Barnes-style commentary has crept back in
  — the 2026-05-13 contamination in reverse.

The 0.82 tolerance is deliberately coarse: it flags gross damage, missing content,
and mislabeled sources — not single-character OCR slips (Aldersgate's `trust 'n
Christ` still PASSes). Tighten `WORDING_TOL` if you want a stricter net.

## Coverage (46 sentinels)

29 John Wesley · 17 Charles Wesley — Journal (Aldersgate, world-my-parish,
"who shall convert me"), Standard Sermons, doctrinal standards (General Rules,
Character of a Methodist, Plain Account of Christian Perfection, Free Grace),
the genuine 1755 NT/OT Notes (anti-Barnes), 17 landmark Charles Wesley hymns,
3 contamination tripwires, and 1 missing-content probe.

## Baseline (2026-07-07, pre-cleanup)

**45 PASS · 0 WORDING-DRIFT · 1 FAIL.** The lone FAIL is `no-holiness-but-social`
— an authentic Wesley line ("no religion but social; no holiness but social
holiness") from the **1739 Preface to *Hymns and Sacred Poems*** (per Wilson — NOT
the Journal), which is simply not ingested. It is a real content gap to fill, not an
OCR error; the suite stays red until the preface is added. That the famous passages
otherwise pass at the word level confirms Phase 0's finding: OCR damage concentrates
in tabular/less-famous material, not the landmark quotes.

## Extending

Add lines to the JSONL directly, or add `add(...)` calls in the generator and re-run
it. Keep every `present` anchor confirmed against the current serving file so a
baseline failure always means a real gap, never a typo.
