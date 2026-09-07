#!/usr/bin/env python3
"""Build the Open Reading Layer bulk export (Phase 6 of
plans/2026-09-06-open-reading-layer.md).

Reads the same on-disk sources web_app.py serves from (metadata/works.jsonl
+ chunked/*.jsonl) and writes:

  export/wesley-corpus-{date}.jsonl.gz           one line per OPEN work, full
                                                  text inline
  export/wesley-corpus-{date}-passages.jsonl.gz  one line per passage of an
                                                  open work
  export/txt/{id}.txt                            plain-text mirror of each
                                                  open work, path = work id
  export/README.md                               schema, license, changelog

Closed works (quality-gate failures, see plan Decision 1) are excluded from
every output — publishing garbled OCR as "trainable" teaches the wrong
Wesley.

Run after any deploy that touches text so export/ stays in sync (plan's
cadence note). NOT baked into the Docker image — see export/README.md for
the current hosting decision.
"""
from __future__ import annotations

import gzip
import json
import shutil
import tarfile
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
META = BASE / "metadata"
CHUNKED = BASE / "chunked"
EXPORT = BASE / "export"

RESEGMENTED_FILES = (
    "journal_by_entry.jsonl",
    "notes_by_chapter.jsonl",
    "hymns_1780_by_number.jsonl",
)


def load_works() -> list[dict]:
    works = []
    with open(META / "works.jsonl") as f:
        for line in f:
            works.append(json.loads(line))
    return works


def load_passages() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    with open(CHUNKED / "cleaned_passages.jsonl") as f:
        for line in f:
            p = json.loads(line)
            by_id[p["id"]] = p
    for name in RESEGMENTED_FILES:
        path = CHUNKED / name
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                p = json.loads(line)
                by_id[p["id"]] = p
    return by_id


def resolve_passages(work: dict, passages_by_id: dict[str, dict]) -> list[dict]:
    out = []
    for pid in work.get("passage_ids") or []:
        p = passages_by_id.get(pid)
        if p:
            out.append(p)
    return out


def main() -> None:
    today = date.today().isoformat()
    EXPORT.mkdir(exist_ok=True)
    txt_dir = EXPORT / "txt"
    txt_dir.mkdir(exist_ok=True)

    works = load_works()
    passages_by_id = load_passages()
    open_works = [w for w in works if w.get("open")]
    closed_count = len(works) - len(open_works)

    works_path = EXPORT / f"wesley-corpus-{today}.jsonl.gz"
    passages_path = EXPORT / f"wesley-corpus-{today}-passages.jsonl.gz"

    n_passages = 0
    total_words = 0

    with gzip.open(works_path, "wt", encoding="utf-8") as wf, \
         gzip.open(passages_path, "wt", encoding="utf-8") as pf:
        for w in open_works:
            passages = resolve_passages(w, passages_by_id)
            text = "\n\n".join(p.get("text", "") for p in passages)

            record = dict(w)
            record["text"] = text
            wf.write(json.dumps(record, ensure_ascii=False) + "\n")
            total_words += w.get("word_count", 0)

            for p in passages:
                prec = dict(p)
                prec["work_id"] = w["id"]
                pf.write(json.dumps(prec, ensure_ascii=False) + "\n")
                n_passages += 1

            out_path = txt_dir / f"{w['id']}.txt"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            header = (
                f"{w['title']}\n"
                f"{(w.get('author') or '').replace('-', ' ').title()}\n"
                f"License: text {w.get('license_text', 'Public Domain Mark 1.0')}; "
                f"apparatus {w.get('license_apparatus', 'CC BY 4.0')}, "
                f"History of Methodism / Wesley Corpus.\n"
                f"https://corpus.historyofmethodism.com/{w['id']}\n"
                f"{'-' * 40}\n\n"
            )
            out_path.write_text(header + text, encoding="utf-8")

    # Package the per-work .txt tree as one archive rather than thousands of
    # loose files — R2 (and any bulk download) handles one object far better
    # than 4,900+ of them.
    txt_archive = EXPORT / f"wesley-corpus-txt-{today}.tar.gz"
    with tarfile.open(txt_archive, "w:gz") as tar:
        tar.add(txt_dir, arcname="txt")
    shutil.rmtree(txt_dir)

    readme = EXPORT / "README.md"
    readme.write_text(_readme_text(today, len(open_works), closed_count, n_passages, total_words))

    manifest = {
        "generated": today,
        "open_works": len(open_works),
        "closed_works": closed_count,
        "passages": n_passages,
        "words": total_words,
        "files": [
            {
                "name": works_path.name,
                "description": "One JSON object per open work, full text inline.",
                "size_bytes": works_path.stat().st_size,
            },
            {
                "name": passages_path.name,
                "description": "One JSON object per passage of an open work.",
                "size_bytes": passages_path.stat().st_size,
            },
            {
                "name": txt_archive.name,
                "description": "Plain-text mirror of each open work, one file per work inside the archive.",
                "size_bytes": txt_archive.stat().st_size,
            },
            {
                "name": readme.name,
                "description": "Schema, license, and changelog.",
                "size_bytes": readme.stat().st_size,
            },
        ],
    }
    manifest_path = EXPORT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(open_works)} open works ({closed_count} closed works excluded), "
          f"{n_passages} passages, {total_words:,} words.")
    print(f"  {works_path.relative_to(BASE)}  ({works_path.stat().st_size:,} bytes)")
    print(f"  {passages_path.relative_to(BASE)}  ({passages_path.stat().st_size:,} bytes)")
    print(f"  {txt_archive.relative_to(BASE)}  ({txt_archive.stat().st_size:,} bytes)")
    print(f"  {readme.relative_to(BASE)}")
    print(f"  {manifest_path.relative_to(BASE)}")
    print("Run scripts/upload_export_r2.sh to publish these to R2.")


def _readme_text(today: str, n_open: int, n_closed: int, n_passages: int, total_words: int) -> str:
    return f"""# Wesley Corpus — bulk export

Generated {today}. {n_open} open works, {n_passages} passages, {total_words:,} words.
{n_closed} works are excluded — quality-gate failures (>5% non-word rate at the
source), disclosed at `/license` and on their (noindex) pages on the site.
Publishing damaged OCR as trainable text would teach a wrong Wesley, so those
sources are not in this export.

## Files

- `wesley-corpus-{today}.jsonl.gz` — one JSON object per open work, full text
  inline in the `text` field, plus all `metadata/works.jsonl` fields (title,
  author, date, numbering, source edition, themes, word count, etc.).
- `wesley-corpus-{today}-passages.jsonl.gz` — one JSON object per passage
  belonging to an open work (`work_id` added), matching the passage records
  the site itself serves.
- `wesley-corpus-txt-{today}.tar.gz` — plain-text mirror of each open work
  as `txt/{{work id}}.txt`, one file per work inside the archive, path
  mirrors the work's site id (e.g. `txt/jw/sermons/043.txt`). Each file
  opens with a short header (title, author, license, canonical URL) then
  the full text. Packaged as a single archive rather than thousands of
  individual downloads — extract locally if you want per-work files.

## Hosting

Served from a Cloudflare R2 bucket (`wesley-corpus-export`), not baked
into the app's Docker image — this lets the export refresh independently
of a code deploy, and keeps the text off the two stateless Fly machines
(a Fly volume would need a separate copy per machine; R2 is naturally
shared). The app proxies `/export/*` to R2 rather than exposing a public
bucket URL, so there's no new subdomain.

## License

**The texts.** John and Charles Wesley's writings are in the public domain
(Public Domain Mark 1.0). Where a transcription error has been corrected,
that correction is released under
[CC0](https://creativecommons.org/publicdomain/zero/1.0/).

**The apparatus.** Titles, provenance notes, editorial notes, cross-references,
curated themes, and the JSON records themselves are released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribute to
"History of Methodism / Wesley Corpus."

**Machine use.** Use for machine-learning training and retrieval is explicitly
permitted and welcome under the terms above — crawl it, index it, quote it,
train on it, keeping attribution on the apparatus.

Full license page: <https://corpus.historyofmethodism.com/license>

## Changelog

- {today} — first bulk export, generated by `scripts/build_export.py`
  (Open Reading Layer Phase 6).
"""


if __name__ == "__main__":
    main()
