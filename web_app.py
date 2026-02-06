"""Wesley Corpus Web Interface — FastAPI app with Jinja2 templates."""
from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
CHUNKED = BASE / "chunked"
META = BASE / "metadata"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Wesley Corpus")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def highlight_terms(text: str, query: str) -> str:
    """Highlight search terms in text by wrapping them in <mark> tags."""
    if not query:
        return text
    import html
    text = html.escape(text)
    for term in query.split():
        if len(term) >= 2:  # Only highlight terms with 2+ chars
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            text = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", text)
    return text


templates.env.filters["highlight"] = highlight_terms

# Mount SWI API router
from strangely_warm_index.api import router as swi_router
app.include_router(swi_router)

# ---------------------------------------------------------------------------
# Data (loaded once at startup)
# ---------------------------------------------------------------------------
PASSAGES: list[dict] = []
PASSAGES_BY_ID: dict[str, dict] = {}
THEMES: list[dict] = []
THEMES_BY_ID: dict[str, dict] = {}
SCRIPTURE_INDEX: dict = {}
SOURCES: list[dict] = []
EMBEDDINGS: np.ndarray | None = None
EMBED_IDS: list[str] = []


def _load_passages():
    with open(CHUNKED / "passages.jsonl") as f:
        for line in f:
            p = json.loads(line)
            PASSAGES.append(p)
            PASSAGES_BY_ID[p["id"]] = p


def _load_themes():
    with open(META / "themes.csv", newline="") as f:
        for row in csv.DictReader(f):
            THEMES.append(row)
            THEMES_BY_ID[row["theme_id"]] = row
    # attach passage counts
    counts: dict[str, int] = {}
    for p in PASSAGES:
        for t in p.get("themes", []):
            counts[t] = counts.get(t, 0) + 1
    for t in THEMES:
        t["count"] = counts.get(t["theme_id"], 0)


def _load_scripture():
    global SCRIPTURE_INDEX
    with open(META / "scripture-index.json") as f:
        SCRIPTURE_INDEX = json.load(f)


def _load_sources():
    path = META / "sources.csv"
    if path.exists():
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                SOURCES.append(row)


def _load_embeddings():
    global EMBEDDINGS, EMBED_IDS
    path = CHUNKED / "embeddings.npz"
    if path.exists():
        data = np.load(path, allow_pickle=True)
        EMBEDDINGS = data["embeddings"]
        EMBED_IDS = list(data["ids"])
        # normalise for cosine similarity via dot product
        norms = np.linalg.norm(EMBEDDINGS, axis=1, keepdims=True)
        norms[norms == 0] = 1
        EMBEDDINGS = EMBEDDINGS / norms


@app.on_event("startup")
def startup():
    _load_passages()
    _load_themes()
    _load_scripture()
    _load_sources()
    _load_embeddings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _keyword_search(q: str, author: str | None = None, source_type: str | None = None, limit: int = 50):
    """Simple case-insensitive keyword search."""
    terms = q.lower().split()
    results = []
    for p in PASSAGES:
        if author and p.get("author") != author:
            continue
        if source_type and p.get("source_type") != source_type:
            continue
        text_lower = p["text"].lower()
        if all(t in text_lower for t in terms):
            results.append(p)
        if len(results) >= limit:
            break
    return results


def _semantic_search(q: str, top_k: int = 20):
    """Semantic search using pre-computed embeddings."""
    if EMBEDDINGS is None:
        return []
    try:
        from sentence_transformers import SentenceTransformer
        model = _get_st_model()
        qvec = model.encode([q])[0].astype(np.float32)
        qvec = qvec / (np.linalg.norm(qvec) or 1)
        scores = EMBEDDINGS @ qvec
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            {**PASSAGES_BY_ID[EMBED_IDS[i]], "score": float(scores[i])}
            for i in top_idx if EMBED_IDS[i] in PASSAGES_BY_ID
        ]
    except ImportError:
        return []

_st_model = None
def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


# Canonical Bible book order
BOOK_ORDER = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
    "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation"
]


def _get_book_order(book: str) -> int:
    """Get canonical order for a book, with unknown books at end."""
    try:
        return BOOK_ORDER.index(book)
    except ValueError:
        return 999


NT_BOOKS = {
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
    "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation"
}


def _scripture_browse():
    """Get browseable list of all books with reference counts."""
    books = []
    total_refs = 0
    for book, chapters in SCRIPTURE_INDEX.items():
        ref_count = sum(len(refs) for refs in chapters.values())
        total_refs += ref_count
        books.append({
            "name": book,
            "chapters": len(chapters),
            "references": ref_count,
            "is_nt": book in NT_BOOKS,
        })
    books.sort(key=lambda b: _get_book_order(b["name"]))
    return books, total_refs


def _scripture_lookup(q: str):
    """Parse a scripture query like 'Romans 8' or 'John 3:16' and return matching entries."""
    q = q.strip()
    # Try to parse book, chapter, verse
    m = re.match(r"^(\d?\s*[A-Za-z]+)\s*(\d+)?(?::(\d+))?", q)
    if not m:
        return [], q
    book_q = m.group(1).strip()
    chapter = m.group(2)
    verse = m.group(3)

    # find matching book in index
    matched_book = None
    for book in SCRIPTURE_INDEX:
        if book.lower() == book_q.lower() or book.lower().startswith(book_q.lower()):
            matched_book = book
            break
    if not matched_book:
        return [], q

    entries = []
    book_data = SCRIPTURE_INDEX[matched_book]
    if chapter and chapter in book_data:
        for entry in book_data[chapter]:
            passage = PASSAGES_BY_ID.get(entry["passage_id"], {})
            text_snippet = passage.get("text", "")[:200] + "..." if passage.get("text") else ""
            if verse:
                if entry.get("verses") and verse in entry["verses"].split("-"):
                    entries.append({**entry, "book": matched_book, "chapter": chapter, "snippet": text_snippet})
                elif entry.get("verses") == verse:
                    entries.append({**entry, "book": matched_book, "chapter": chapter, "snippet": text_snippet})
            else:
                entries.append({**entry, "book": matched_book, "chapter": chapter, "snippet": text_snippet})
    elif not chapter:
        for ch, refs in sorted(book_data.items(), key=lambda x: int(x[0])):
            for entry in refs:
                passage = PASSAGES_BY_ID.get(entry["passage_id"], {})
                text_snippet = passage.get("text", "")[:200] + "..." if passage.get("text") else ""
                entries.append({**entry, "book": matched_book, "chapter": ch, "snippet": text_snippet})
    return entries, f"{matched_book}{' ' + chapter if chapter else ''}{':' + verse if verse else ''}"


def _corpus_stats():
    authors = set()
    types = set()
    theme_set = set()
    total_words = 0
    for p in PASSAGES:
        authors.add(p.get("author", ""))
        types.add(p.get("source_type", ""))
        total_words += p.get("word_count", 0)
        for t in p.get("themes", []):
            theme_set.add(t)
    return {
        "passage_count": len(PASSAGES),
        "author_count": len(authors),
        "source_type_count": len(types),
        "theme_count": len(theme_set),
        "total_words": total_words,
    }


# ---------------------------------------------------------------------------
# HTML Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    stats = _corpus_stats()
    rp = random.choice(PASSAGES) if PASSAGES else None
    return templates.TemplateResponse("index.html", {
        "request": request, "stats": stats, "themes": THEMES,
        "random_passage": rp,
    })


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", author: str = "", type: str = ""):
    results = _keyword_search(q, author=author or None, source_type=type or None) if q else []
    return templates.TemplateResponse("search.html", {
        "request": request, "q": q, "author": author, "type": type,
        "results": results,
    })


@app.get("/semantic", response_class=HTMLResponse)
def semantic_page(request: Request, q: str = ""):
    results = _semantic_search(q) if q else []
    return templates.TemplateResponse("search.html", {
        "request": request, "q": q, "author": "", "type": "",
        "results": results, "semantic": True,
    })


@app.get("/themes", response_class=HTMLResponse)
def themes_page(request: Request):
    return templates.TemplateResponse("themes.html", {
        "request": request, "themes": sorted(THEMES, key=lambda t: -t["count"]),
    })


@app.get("/theme/{theme_id}", response_class=HTMLResponse)
def theme_page(request: Request, theme_id: str):
    theme = THEMES_BY_ID.get(theme_id, {"theme_id": theme_id, "theme_name": theme_id})
    passages = [p for p in PASSAGES if theme_id in p.get("themes", [])]
    return templates.TemplateResponse("theme.html", {
        "request": request, "theme": theme, "passages": passages,
    })


@app.get("/passage/{passage_id}", response_class=HTMLResponse)
def passage_page(request: Request, passage_id: str, q: str = ""):
    p = PASSAGES_BY_ID.get(passage_id)
    if not p:
        return HTMLResponse("Passage not found", status_code=404)
    theme_details = [THEMES_BY_ID[t] for t in p.get("themes", []) if t in THEMES_BY_ID]
    return templates.TemplateResponse("passage.html", {
        "request": request, "passage": p, "theme_details": theme_details, "q": q,
    })


@app.get("/scripture", response_class=HTMLResponse)
def scripture_page(request: Request, q: str = ""):
    entries, label = _scripture_lookup(q) if q else ([], "")
    books, total_refs = _scripture_browse()
    return templates.TemplateResponse("scripture.html", {
        "request": request, "q": q, "label": label, "entries": entries,
        "books": books, "total_refs": total_refs,
    })


@app.get("/random")
def random_page():
    p = random.choice(PASSAGES) if PASSAGES else None
    if p:
        return RedirectResponse(url=f"/passage/{p['id']}")
    return RedirectResponse(url="/")


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    return templates.TemplateResponse("sources.html", {
        "request": request, "sources": SOURCES,
    })


@app.get("/strangely-warmed", response_class=HTMLResponse)
def swi_page(request: Request):
    return templates.TemplateResponse("swi.html", {"request": request})


@app.get("/swi", response_class=HTMLResponse)
def swi_page_alt(request: Request):
    return templates.TemplateResponse("swi.html", {"request": request})


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.get("/api/search")
def api_search(q: str = "", author: str = "", type: str = ""):
    return _keyword_search(q, author=author or None, source_type=type or None) if q else []


@app.get("/api/semantic")
def api_semantic(q: str = ""):
    return _semantic_search(q) if q else []


@app.get("/api/themes")
def api_themes():
    return THEMES


@app.get("/api/passage/{passage_id}")
def api_passage(passage_id: str):
    p = PASSAGES_BY_ID.get(passage_id)
    if not p:
        return JSONResponse({"error": "not found"}, status_code=404)
    return p


@app.get("/api/scripture")
def api_scripture(q: str = ""):
    entries, label = _scripture_lookup(q) if q else ([], "")
    return {"label": label, "entries": entries}


@app.get("/api/random")
def api_random():
    return random.choice(PASSAGES) if PASSAGES else {}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
