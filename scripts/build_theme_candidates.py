#!/usr/bin/env python3
"""Phase 7 scaffolding (plans/2026-09-06-open-reading-layer.md): propose ~60
SWI-ranked candidates per theme, from themes_auto, for Wilson to pare down
to 20-40 hand-picked passages + a one-sentence note each.

Ranking is the corpus's own SWI v1 lexicon score (overall_score, 0-100) --
free and local, no ANTHROPIC_API_KEY / network calls needed. It's a proxy
for "how doctrinally dense and characteristically Wesleyan," not for
theme-fit specifically (themes_auto keyword tagging already filtered for
that); within an already-tagged pool it surfaces the meatier passages
first. Each unique passage is scored once and reused across every theme
it's tagged with.

Excludes: passages under 200 words (corpus's own documented SWI reliability
floor -- see CLAUDE.md/wesley-corpus.md), and any passage belonging to a
closed (quality-gate-failed) work.

Three re-segmented sources (1780 hymn Collection, Notes NT, Notes OT) have
no 1:1 mapping from their old theme-tagged chunks to the new per-work
pages (see _FANOUT_COLLECTIONS below) -- those candidates link to the
collection browse page, not an exact anchor, and are marked as such.
Separately, Notes OT's OLD source_id (jw-notes-on-old-testament) doesn't
match any current work at all, so its passages are silently absent from
candidate pools entirely, not merely browse-only -- a real content gap,
not a bug in this script.

Outputs:
  metadata/themes-candidates.jsonl        machine-readable, all themes
  metadata/themes-candidates/{theme}.md   one human review sheet per theme

Requires numpy/scipy/anthropic installed (this repo isn't set up for local
dev by default -- see wesley-corpus/CLAUDE.md). Run from a venv:
  python3 -m venv .venv-themes && .venv-themes/bin/pip install numpy scipy anthropic
  .venv-themes/bin/python3 scripts/build_theme_candidates.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
META = BASE / "metadata"
CHUNKED = BASE / "chunked"

sys.path.insert(0, str(BASE))
os.environ.pop("ANTHROPIC_API_KEY", None)  # force the free lexicon path
from strangely_warm_index.scoring import score_text  # noqa: E402

MIN_WORDS = 200
CANDIDATES_PER_THEME = 60


def load_themes() -> list[dict]:
    with open(META / "themes.csv") as f:
        return list(csv.DictReader(f))


def load_open_source_ids() -> set[str]:
    open_ids = set()
    with open(META / "works.jsonl") as f:
        for line in f:
            w = json.loads(line)
            if w.get("open") and w.get("source_id"):
                open_ids.add(w["source_id"])
    return open_ids


def load_candidate_passages(open_source_ids: set[str]) -> list[dict]:
    out = []
    with open(CHUNKED / "cleaned_passages.jsonl") as f:
        for line in f:
            p = json.loads(line)
            if not p.get("themes"):
                continue
            if p.get("word_count", 0) < MIN_WORDS:
                continue
            if p.get("source_id") not in open_source_ids:
                continue
            out.append(p)
    return out


def score_passages(passages: list[dict]) -> dict[str, dict]:
    scores = {}
    n = len(passages)
    for i, p in enumerate(passages):
        scores[p["id"]] = score_text(p["text"], include_semantic=False)
        if (i + 1) % 2000 == 0:
            print(f"  scored {i + 1}/{n}...", file=sys.stderr)
    return scores


def snippet(text: str, length: int = 280) -> str:
    text = " ".join(text.split())
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0]
    return cut + "…"


# Three source_ids were re-segmented (Phase 2-4 of the open-layer plan) from
# one big chunked source into hundreds of individual works, with no 1:1
# mapping preserved back to the old chunk boundaries (build_works.py sets
# legacy_ids=[] for the new segmented works — see wesley-corpus.md). A theme
# tagged against the OLD chunking can't be deep-linked to a specific new
# work; web_app.py's own passage-redirect logic hits the same wall and
# falls back to the collection index. Route candidates the same way, and
# flag them as browse-only rather than claiming a precise anchor that isn't
# real (a wrong-but-plausible-looking URL is worse than an honest one).
_FANOUT_COLLECTIONS = {
    "cw-hymns-1780": "https://corpus.historyofmethodism.com/cw/hymns/1780",
    "jw-notes-nt": "https://corpus.historyofmethodism.com/jw/notes-nt",
    "jw-notes-ot": "https://corpus.historyofmethodism.com/jw/notes-ot",
}


def work_url(passage: dict, works_by_source: dict[str, list[dict]]) -> tuple[str, bool]:
    """Returns (url, resolved) — resolved=False means the URL is a
    collection browse page, not a deep link to this exact passage."""
    sid = passage["source_id"]
    if sid in _FANOUT_COLLECTIONS:
        return _FANOUT_COLLECTIONS[sid], False
    candidates = works_by_source.get(sid) or []
    for w in candidates:
        if passage["id"] in (w.get("passage_ids") or []):
            anchor = w["passage_ids"].index(passage["id"])
            return f"https://corpus.historyofmethodism.com/{w['id']}#p{anchor}", True
    return f"https://corpus.historyofmethodism.com/passage/{passage['id']}", False


def main() -> None:
    themes = load_themes()
    open_source_ids = load_open_source_ids()

    works_by_source: dict[str, list[dict]] = {}
    with open(META / "works.jsonl") as f:
        for line in f:
            w = json.loads(line)
            works_by_source.setdefault(w["source_id"], []).append(w)

    print("Loading candidate passages (themed, >=200 words, open works)...", file=sys.stderr)
    passages = load_candidate_passages(open_source_ids)
    print(f"{len(passages)} candidate passages across all themes.", file=sys.stderr)

    print("Scoring (SWI lexicon fallback, no API calls)...", file=sys.stderr)
    scores = score_passages(passages)

    by_theme: dict[str, list[dict]] = {t["theme_id"]: [] for t in themes}
    for p in passages:
        for t in p["themes"]:
            if t in by_theme:
                by_theme[t].append(p)

    md_dir = META / "themes-candidates"
    md_dir.mkdir(exist_ok=True)
    master_path = META / "themes-candidates.jsonl"

    summary = []
    with open(master_path, "w") as master_f:
        for t in themes:
            tid = t["theme_id"]
            pool = by_theme.get(tid, [])
            pool.sort(key=lambda p: scores[p["id"]]["overall_score"], reverse=True)
            top = pool[:CANDIDATES_PER_THEME]
            n_unresolved = sum(1 for p in top if p["source_id"] in _FANOUT_COLLECTIONS)
            summary.append((tid, len(pool), len(top), n_unresolved))

            lines = [
                f"# {t['theme_name']}",
                "",
                f"_{t['description']}_",
                "",
                f"Tagged (auto, >=200w, open works): {len(pool)}. "
                f"Showing top {len(top)} by SWI overall score. "
                "**Target: keep 20-40, write a one-sentence note for each kept "
                "passage explaining why it's canonical for this theme.**",
                "",
                "Ranking is a density proxy, not a theme-fit judgment — themes_auto "
                "keyword tagging already selected for the theme; SWI score just "
                "surfaces the more substantively Wesleyan passages first within "
                "that pool. Read past a low-fit passage if a better one sits "
                "lower in the list.",
                "",
            ]
            for rank, p in enumerate(top, start=1):
                sc = scores[p["id"]]
                url, resolved = work_url(p, works_by_source)
                link_label = "Read full" if resolved else "Browse collection (no exact anchor)"
                lines.append(
                    f"- [ ] **{rank}.** {p.get('source_title', p['source_id'])} "
                    f"({p['word_count']}w, SWI {sc['overall_score']}) "
                    f"— {snippet(p['text'])} [{link_label} →]({url})"
                )
                lines.append("  - Note: ")
                lines.append("")

                record = {
                    "theme": tid,
                    "rank": rank,
                    "passage_id": p["id"],
                    "source_id": p["source_id"],
                    "source_title": p.get("source_title"),
                    "word_count": p["word_count"],
                    "swi_overall_score": sc["overall_score"],
                    "url": url,
                    "url_resolved": resolved,
                    "snippet": snippet(p["text"]),
                }
                master_f.write(json.dumps(record, ensure_ascii=False) + "\n")

            (md_dir / f"{tid}.md").write_text("\n".join(lines) + "\n")

    print("\nCandidates per theme (tagged pool -> shown, [browse-only]):", file=sys.stderr)
    for tid, pool_n, shown_n, n_unresolved in sorted(summary, key=lambda x: -x[1]):
        flag = "  <- fewer than 20, may need a lower bar or stays a small theme" if shown_n < 20 else ""
        unresolved_note = f"  [{n_unresolved} browse-only]" if n_unresolved else ""
        print(f"  {shown_n:3d} / {pool_n:5d}  {tid}{unresolved_note}{flag}", file=sys.stderr)

    print(f"\nWrote {master_path.relative_to(BASE)} and {md_dir.relative_to(BASE)}/*.md", file=sys.stderr)


if __name__ == "__main__":
    main()
