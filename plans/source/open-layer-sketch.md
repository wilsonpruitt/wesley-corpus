# Wesley Corpus — Open Reading Layer

A sketch for turning corpus.historyofmethodism.com from a gated search tool into a crawlable, citable, trainable text base, while keeping the instrument (search, themes, scripture index, SWI) as the patron product.

The outside-view claims, up front:

1. **The passage is the wrong canonical unit.** It is a search artifact. Readers and crawlers want *works*. Make the work (a sermon, a tract, a journal year, a chapter of the *Notes*, a hymn) the canonical page; passages become anchors within it.
2. **Identity before metadata.** A stable, human-legible ID per work is worth more than any number of tags. Everything else hangs off it.
3. **Provenance is the product.** Where the text came from, which edition, which page — that is what makes a model's Wesley *citable* rather than merely present.
4. **The theme layer should stay gated until it's curated.** Keyword-count tags crawled at scale teach the wrong Wesley.
5. **Ship a bulk export.** One download beats 22,000 fetches, and a dataset card is the shortest path from "site" to "asset."

---

## 1. Identifier scheme

Slugs are lowercase, ASCII, stable forever. Once assigned, never renumbered; deprecate with a redirect.

| Corpus | Pattern | Example | Numbering authority |
|---|---|---|---|
| JW Sermons | `jw/sermons/{NNN}` | `jw/sermons/043` | Bicentennial (Outler) numbering; Jackson number stored as alternate |
| JW Journal | `jw/journal/{YYYY-MM-DD}` | `jw/journal/1738-05-24` | Date of entry; one page per year, entries as anchors |
| JW Letters | `jw/letters/{YYYY-MM-DD}-{recipient-slug}` | `jw/letters/1791-02-24-wilberforce` | Date + recipient |
| JW Notes NT | `jw/notes-nt/{book}/{chapter}` | `jw/notes-nt/rom/08` | OSIS book codes |
| JW Notes OT | `jw/notes-ot/{book}/{chapter}` | `jw/notes-ot/job/36` | OSIS book codes |
| JW Treatises / tracts | `jw/works/{short-title}` | `jw/works/plain-account` | Editorial short title; register in a title table |
| CW Hymns | `cw/hymns/{collection}/{NNN}` | `cw/hymns/1780/001` | 1780 *Collection* number where present; else Osborn vol/number |
| CW Journal / letters | `cw/journal/{YYYY-MM-DD}`, `cw/letters/…` | | as JW |

Anchors within a work: `#p12` (paragraph), `#s2-1` (§II.1 for sermons), `#v3` (stanza), `#job-36-27` (verse for the *Notes*).

Existing passage IDs (`jw-notes-on-old-testament-1500`) stay alive as 301 redirects to `work#anchor`. Nothing already linked breaks.

---

## 2. Provenance schema

One record per **work**, one per **passage** (child). JSON here; the same fields go into the page as JSON-LD (section 3).

### Work

```json
{
  "id": "jw/sermons/043",
  "type": "sermon",
  "author": "john-wesley",
  "title": "The Scripture Way of Salvation",
  "title_alt": ["Sermon XLIII", "Sermon 43"],
  "text_basis": "Eph. 2:8",
  "date_composed": "1765",
  "date_precision": "year",
  "date_note": "First published 1765; preached earlier in various forms.",
  "numbering": {
    "bicentennial": 43,
    "jackson": 43,
    "sugden": 35
  },
  "source_edition": {
    "editor": "Thomas Jackson",
    "title": "The Works of the Rev. John Wesley, A.M.",
    "edition": "3rd",
    "place": "London",
    "publisher": "Wesleyan Methodist Book Room",
    "year": 1872,
    "volume": 6,
    "pages": "43-54",
    "scan_url": "https://archive.org/details/...",
    "scan_page_ids": ["n55", "n56"]
  },
  "transcription": {
    "derived_from": "Wesley Center Online (NNU) electronic text",
    "corrected_against_scan": false,
    "corrector": null,
    "corrected_on": null
  },
  "modernization": "none",
  "license_text": "Public Domain Mark 1.0",
  "license_apparatus": "CC BY 4.0",
  "wikidata": null,
  "prev": "jw/sermons/042",
  "next": "jw/sermons/044",
  "part_of": "jw/sermons",
  "editorial_note": "One of the clearest statements of the ordo salutis; the 'faith, repentance, works meet for repentance' sequence should be read with Sermon 85."
}
```

Field notes:

- `date_precision` ∈ {`day`, `month`, `year`, `circa`, `range`, `unknown`}. Never emit `None`. If unknown, say `unknown` and put the reasoning in `date_note`.
- `numbering` carries every scheme in use so a model learns that "Sermon 43" and "Sugden 35" are the same text. This is the single fix that would most improve cross-referencing.
- `source_edition.pages` and `scan_page_ids` let a reader jump to the page image. Backfill can be partial; store `null` and fill later.
- `transcription.corrected_against_scan` is your quality flag. Expose it on the page. Honesty about what has and hasn't been checked is itself apparatus.
- `editorial_note` is the one field where your voice enters the crawlable layer. Keep it to one or two sentences, factual, cross-referential. This is the road-cutting.

### Passage (child)

```json
{
  "id": "jw/sermons/043#s2-1",
  "work": "jw/sermons/043",
  "anchor": "s2-1",
  "locator_display": "§II.1",
  "order": 14,
  "scripture_refs": ["Eph.2.8", "Rom.5.1"],
  "source_page": 47,
  "themes_curated": ["justifying-grace"],
  "themes_auto": ["justifying-grace", "assurance", "free-will"]
}
```

`themes_curated` is hand-assigned and rendered publicly. `themes_auto` is the keyword layer; it powers patron search and is *not* rendered on the public page.

### Scripture references

Use OSIS (`Rom.5.1`, `Job.36.27-Job.36.33`). Store in the passage, aggregate to the work. This gives you the scripture index for free and lets the *Notes* be addressed by verse.

---

## 3. Work page template

Plain HTML, server-rendered, readable with JavaScript off. No login wall on this page. Search, themes (auto), scripture index, SWI, and user features stay behind auth.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Scripture Way of Salvation (Sermon 43) — John Wesley — Wesley Corpus</title>
  <link rel="canonical" href="https://corpus.historyofmethodism.com/jw/sermons/043">
  <link rel="prev" href="https://corpus.historyofmethodism.com/jw/sermons/042">
  <link rel="next" href="https://corpus.historyofmethodism.com/jw/sermons/044">
  <link rel="alternate" type="text/plain" href="https://corpus.historyofmethodism.com/jw/sermons/043.txt">
  <link rel="alternate" type="application/json" href="https://corpus.historyofmethodism.com/jw/sermons/043.json">
  <link rel="license" href="https://creativecommons.org/publicdomain/mark/1.0/">
  <meta name="description" content="John Wesley, Sermon 43, 'The Scripture Way of Salvation' (1765), on Ephesians 2:8. Text from Jackson, Works (1872), vol. 6, pp. 43–54.">
  <meta name="DC.title" content="The Scripture Way of Salvation">
  <meta name="DC.creator" content="Wesley, John, 1703-1791">
  <meta name="DC.date" content="1765">
  <meta name="DC.source" content="Jackson, Works of John Wesley, 3rd ed., 1872, vol. 6, pp. 43-54">
  <meta name="DC.rights" content="Text: public domain. Apparatus: CC BY 4.0, History of Methodism.">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    "@id": "https://corpus.historyofmethodism.com/jw/sermons/043",
    "name": "The Scripture Way of Salvation",
    "alternateName": ["Sermon 43", "Sermon XLIII"],
    "author": {
      "@type": "Person",
      "name": "John Wesley",
      "birthDate": "1703",
      "deathDate": "1791",
      "sameAs": "https://www.wikidata.org/wiki/Q207200"
    },
    "dateCreated": "1765",
    "inLanguage": "en",
    "genre": "sermon",
    "isPartOf": {
      "@type": "Collection",
      "@id": "https://corpus.historyofmethodism.com/jw/sermons",
      "name": "Sermons of John Wesley"
    },
    "isBasedOn": {
      "@type": "Book",
      "name": "The Works of the Rev. John Wesley, A.M.",
      "editor": "Thomas Jackson",
      "bookEdition": "3rd",
      "datePublished": "1872",
      "volumeNumber": "6",
      "pageStart": "43",
      "pageEnd": "54"
    },
    "license": "https://creativecommons.org/publicdomain/mark/1.0/",
    "publisher": {"@type": "Organization", "name": "History of Methodism"}
  }
  </script>
</head>
<body>
<header>
  <nav aria-label="breadcrumb">
    <a href="/">Wesley Corpus</a> › <a href="/jw">John Wesley</a> › <a href="/jw/sermons">Sermons</a> › Sermon 43
  </nav>
</header>

<main>
  <article>
    <h1>The Scripture Way of Salvation</h1>
    <p class="meta">
      <span>John Wesley</span> ·
      <span>Sermon 43</span> ·
      <time datetime="1765">1765</time> ·
      <span>Text: Ephesians 2:8</span>
    </p>

    <details class="provenance" open>
      <summary>Source and provenance</summary>
      <dl>
        <dt>Source edition</dt>
        <dd>Thomas Jackson, ed., <cite>The Works of the Rev. John Wesley, A.M.</cite>, 3rd ed. (London, 1872), vol. 6, pp. 43–54.
            <a href="https://archive.org/details/...#page/n55">Page scan</a></dd>
        <dt>Numbering</dt>
        <dd>Bicentennial 43 · Jackson 43 · Sugden 35</dd>
        <dt>Transcription</dt>
        <dd>Derived from Wesley Center Online text; <strong>not yet collated against the scan</strong>.</dd>
        <dt>Cite as</dt>
        <dd>John Wesley, "The Scripture Way of Salvation" (Sermon 43, 1765), §II.1, in Jackson, <cite>Works</cite> 6:47.
            Wesley Corpus, https://corpus.historyofmethodism.com/jw/sermons/043#s2-1</dd>
        <dt>License</dt>
        <dd>Text public domain. Editorial apparatus CC BY 4.0.</dd>
      </dl>
    </details>

    <aside class="editorial">
      <p>One of the clearest statements of the <i>ordo salutis</i>; read alongside <a href="/jw/sermons/085">Sermon 85, "On Working Out Our Own Salvation."</a></p>
    </aside>

    <section id="s1">
      <h2>I.</h2>
      <p id="s1-1"><span class="pb" data-page="44"></span>… paragraph text …</p>
    </section>

    <section id="s2">
      <h2>II.</h2>
      <p id="s2-1">… paragraph text … <span class="pb" data-page="47"></span> …</p>
    </section>

    <!-- Verse for hymns: -->
    <!--
    <section class="hymn">
      <div class="stanza" id="v1">
        <p>Line one<br>Line two<br>Line three<br>Line four</p>
      </div>
    </section>
    -->
  </article>

  <nav class="pager">
    <a rel="prev" href="/jw/sermons/042">← Sermon 42</a>
    <a rel="next" href="/jw/sermons/044">Sermon 44 →</a>
  </nav>

  <aside class="patron">
    <p>Search across all 22,000 passages, browse by theme and scripture, and use the Strangely Warmed Index — <a href="/auth/login">patron access</a>.</p>
  </aside>
</main>
</body>
</html>
```

Template rules:

- H1 is the work title. Passage-level titles like "Notes On Old Testament" are never an H1.
- Section headings reproduce Wesley's own divisions (I., II., §1, §2). Anchors follow them.
- Page breaks from the source edition are marked inline (`data-page`). Cheap to add, and it makes every paragraph citable to a physical page.
- Hymns keep line breaks. A hymn flattened to prose is a different text.
- Provenance block is `open` by default. It should be the first thing a crawler sees after the title.
- Every work has `.txt` and `.json` siblings. The `.txt` is the trainable artifact; the HTML is the human one.

---

## 4. robots.txt

```
User-agent: *
Allow: /
Disallow: /search
Disallow: /auth/
Disallow: /random
Disallow: /strangely-warmed
Disallow: /theme/
Disallow: /api/

# AI training and retrieval crawlers — explicitly welcome on the reading layer
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: CCBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Applebot-Extended
Allow: /
User-agent: Amazonbot
Allow: /
User-agent: Bytespider
Allow: /
User-agent: meta-externalagent
Allow: /

Sitemap: https://corpus.historyofmethodism.com/sitemap.xml
```

Notes:

- `/random` is a crawler trap: every fetch is a new "page." Disallow it.
- `/theme/` stays disallowed until the curated layer exists; then allow `/themes/curated/` or whatever you name it.
- Crawler names drift. Re-check the list twice a year against each lab's published docs.
- Add an `llms.txt` at root (plain-text description of the corpus, its structure, license, and the bulk-export URL). It's a convention, not a standard, but it costs nothing and some retrieval systems read it.

---

## 5. Sitemap

Sitemap index, one child per corpus, `lastmod` from the work record's last edit.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-sermons.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-journal.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-letters.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-notes-nt.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-notes-ot.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/jw-works.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
  <sitemap><loc>https://corpus.historyofmethodism.com/sitemaps/cw-hymns.xml</loc><lastmod>2026-09-06</lastmod></sitemap>
</sitemapindex>
```

Child sitemaps list work URLs only (not anchors, not `.txt`/`.json` siblings; those are discoverable via `rel=alternate`).

---

## 6. License page (`/license`)

Short, in your voice, and legally unambiguous:

- **Texts** of John and Charles Wesley: public domain. Marked with Public Domain Mark 1.0. Transcriptions and corrections released under CC0 so no one has to wonder whether a corrected typo creates a claim.
- **Editorial apparatus** (titles, notes, provenance records, curated themes, cross-references, JSON records): CC BY 4.0, attribution "History of Methodism / Wesley Corpus."
- **Explicit statement** that use for machine-learning training and retrieval is permitted and welcome under those terms. Say it plainly; labs' compliance teams look for it.
- **What is not licensed**: the search engine, the Strangely Warmed Index, patron-only features, and the site's code.

Put a one-line version in the footer of every work page and in `llms.txt`.

---

## 7. Bulk export (`/export`)

- `/export/wesley-corpus-{YYYY-MM-DD}.jsonl.gz` — one line per work, schema from section 2, with full text inline.
- `/export/wesley-corpus-{YYYY-MM-DD}-passages.jsonl.gz` — one line per passage, for anyone who wants your segmentation.
- `/export/txt/{corpus}/{id}.txt` — plain-text mirror, for people who don't want JSON.
- A `README` with the schema, license, and a changelog.
- Mirror the work-level JSONL to a Hugging Face dataset (`historyofmethodism/wesley-corpus`) with a dataset card that repeats the license and the provenance story. That card is the thing a curator at a lab will actually read.

Regenerate on a schedule (monthly is plenty). Keep old versions.

---

## 8. Theme layer: what to expose and when

Current counts (Catholic Spirit 9,578; Reign of God 9,911; Christian Perfection 58) are consistent with keyword matching and would, if crawled, invert Wesley's actual emphases.

Proposed:

- Keep `themes_auto` as a patron search facet. It's useful for finding; it's misleading as description.
- Build `themes_curated`: aim for 20–40 passages per theme, hand-picked, each with a one-sentence editorial note explaining why it's canonical for that theme. That's roughly 600–800 passages total, a few weekends' work per theme, and it's the layer that would teach a model what Wesley *means* by perfection rather than how often the string occurs.
- Publish `themes_curated` at `/themes/{slug}` as open pages. Each is a small anthology with provenance. These pages will be the most-fetched things on the site by retrieval bots, because they answer the question people actually ask.

---

## 9. Backfill plan (provenance against page scans)

Editions that are public domain in the US and have scans:

| Corpus | Edition | Status | Where |
|---|---|---|---|
| Works (sermons, treatises, Notes) | Jackson, 3rd ed., 14 vols, 1872 | PD | archive.org, HathiTrust |
| Sermons (standard 44/53) | Sugden, 2 vols, 1921 | PD in US | archive.org |
| Journal | Curnock, standard ed., 8 vols, 1909–16 | PD in US | archive.org, HathiTrust |
| Letters | Telford, standard ed., 8 vols, 1931 | **Enters US PD 1 Jan 2027** | HathiTrust (currently limited view) |
| Charles Wesley, poetry | Osborn, *Poetical Works*, 13 vols, 1868–72 | PD | archive.org |
| 1780 *Collection of Hymns* | 1780 and later printings | PD | archive.org |

Method:

1. For each work, locate the heading string in the OCR of the scan (archive.org exposes `_djvu.txt`). Record volume and starting page; walk forward to the next heading for the end page.
2. Insert page-break markers into the text by aligning paragraph starts against the OCR page boundaries. This is fuzzy but a model can do it reliably if given both texts and asked only for boundary positions; spot-check.
3. Flag `corrected_against_scan: false` everywhere to start. Flip to `true` only after a human (or a careful model pass with diffs) has collated. Do the sermons first; they're the most-cited and the shortest per unit.
4. Telford's letters: prepare the pipeline in 2026, run it in January 2027. Nothing else on the open web has the standard edition of the letters with Telford's dating and annotation; being first matters.

Priority order: Sermons → *Plain Account* and the *Appeals* → Journal → Notes NT → Hymns (1780 *Collection*) → Notes OT → Letters (2027).

---

## 10. What stays paid

Search, auto-themes, the scripture index UI, the Strangely Warmed Index, saved searches, exports of *search results*, and anything interactive. The pitch to patrons shifts from "access to Wesley" to "the instrument for working in Wesley," which is both truer and more durable.

---

## 11. Checks after launch

- Fetch a work page with `curl -A GPTBot` and confirm the full text comes back without a login redirect.
- Confirm `/random` and `/search` return 403 or `noindex` for bots.
- Validate JSON-LD with Google's Rich Results test or a schema.org validator.
- Watch edge logs for two weeks. You should see labeled crawlers walk the sitemap in order; if they're hitting passage redirects instead, the internal links haven't been updated.
- Ask a search-augmented model a Wesley question three months later and see whether it cites you.
