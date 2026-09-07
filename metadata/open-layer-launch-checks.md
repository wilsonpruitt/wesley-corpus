# Open Reading Layer — post-deploy launch checks

Run 2026-09-07 against `corpus.historyofmethodism.com`, per the sketch §11 checklist
referenced in `plans/2026-09-06-open-reading-layer.md` (Phase 5 hard-stop section).

Two deploys this session: the Phase 5 code (`f160ff9`/`3489511`), then a same-day fix
(`7022d5c`) for a route-ordering bug the first deploy's own checks caught (see below).
Both are pushed to `origin/master`.

## Results

1. **GPTBot / bot access to a work page, no login gate.**
   `curl -A GPTBot https://corpus.historyofmethodism.com/jw/sermons/043` → `200`, full
   sermon text in the body (5,045 words), only a "Log in" nav link present — not a
   redirect. **PASS.**

2. **`/search` still gated.** → `302` to `/auth/login`. **PASS**, paywalled instrument
   untouched by the open-layer work.

3. **`/random` still works for a human.** `curl -L` (GET, matching real browser
   behavior): `307` → `/passage/{id}` → `301` → `/jw/{work}` → `200`, 2 redirects,
   final 200. **PASS.** (A `HEAD`-only probe 405s at the `/passage/{id}` hop — that
   route only declares `GET`; not a defect, since neither browsers nor the crawlers
   this layer targets issue HEAD against it.)

4. **Old `/passage/…` URL 301s to the right anchor.**
   - Re-segmented types (journal/Notes/1780-hymn — re-chunked onto new boundaries,
     no 1:1 anchor by design): `jw-notes-on-old-testament-1435` → `301` →
     `/jw/notes-ot` (collection index, no fragment). Matches the documented intent
     in `passage_page()`'s comment. **PASS.**
   - Unchanged-chunking types (sermons/treatises/letters): `jw-letter-roman-catholic-000`
     → `/jw/works/letter-roman-catholic#p0`; `jw-sermon-053-000` →
     `/jw/sermons/053#p0`. Anchor present and correctly numbered. **PASS.**

5. **JSON-LD validates.** `/jw/sermons/043` — well-formed `application/ld+json`,
   `@type: CreativeWork`, author/dateCreated/inLanguage/license/isPartOf/publisher
   all populated. **PASS**, with one flagged issue below.

6. **RSS after startup.** Main uvicorn process (pid 635) on the live `iad` machine:
   **~223 MB VmRSS**, well under the plan's ~600 MB gate on the 1 GB VM (`MemTotal`
   985 MB, `MemFree` 564 MB at check time). **PASS** — closes out the plan's open
   memory-footprint item (previously estimated only, never measured).

## Bug found + fixed during this pass

**Route-ordering regression, caught by check 1's own family of static-route checks.**
Phase 5 registered `@app.get("/{author}")` (line 890, at the time) *before* the more
specific `/robots.txt`, `/llms.txt`, `/license`, `/sitemap.xml`, `/sitemaps/{corpus}.xml`
routes further down the file. Starlette matches routes in registration order, so any
single-segment path not in `KNOWN_AUTHORS` — `license`, `robots.txt`, `sitemap.xml`,
`llms.txt` — hit `author_index()`'s "unknown author" 404 branch instead of ever
reaching its real handler. First deploy shipped with `/license` 404ing; caught
immediately by curling it post-deploy, fixed by moving the five specific routes above
the catch-all (commit `7022d5c`), redeployed, reverified all five return `200`/`200`/
`200`/`200`/`301` as expected.

## Flagged, not blocking

- **Canonical URL and JSON-LD `@id` are `http://`, not `https://`** (e.g.
  `<link rel="canonical" href="http://corpus.historyofmethodism.com/jw/sermons/043">`).
  Fly terminates TLS at the proxy, so `request.base_url` reflects the internal `http`
  scheme — the same class of bug the Patreon OAuth redirect URI already works around
  via `_build_redirect_uri()` forcing `https` (see repo `CLAUDE.md`). The `http://` URL
  does 301 to the correct `https://` address, so nothing is broken, but every canonical
  tag and JSON-LD `@id` costs bots an extra redirect hop and doesn't match the address
  actually served. Worth the same fix applied to `_ctx()` / wherever `base_url` is read
  for these fields — not done in this pass, since it's cosmetic/SEO-only and outside
  the plan's explicit checklist.

## Regression baseline

`scripts/check_sentinels.py`: **51 PASS / 0 WORDING-DRIFT / 1 FAIL of 52** — unchanged
from the pre-deploy baseline (the one known FAIL is `no-holiness-but-social`, an
authentic 1739 Hymns-preface line not yet ingested, a real content gap not damage).
Zero regressions from this deploy.

## Status

Phase 5 fully closed: code done, deployed, launch-checked, both commits pushed to
`origin/master`. Remaining project work: Phase 6 (bulk export + optional HF mirror —
HF mirror is its own hard stop, outward-facing send) and Phase 7 (curated themes,
Wilson's reading, optional this cycle).
