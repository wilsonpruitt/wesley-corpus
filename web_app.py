"""Wesley Corpus Web Interface — FastAPI app with Jinja2 templates."""
from __future__ import annotations

import csv
import json
import os
import random
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
import numpy as np
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
CHUNKED = BASE / "chunked"
META = BASE / "metadata"

# ---------------------------------------------------------------------------
# Patreon OAuth config
# ---------------------------------------------------------------------------
PATREON_CLIENT_ID = os.environ.get("PATREON_CLIENT_ID", "")
PATREON_CLIENT_SECRET = os.environ.get("PATREON_CLIENT_SECRET", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
MIN_PLEDGE_CENTS = int(os.environ.get("MIN_PLEDGE_CENTS", "500"))
DEV_BYPASS_AUTH = os.environ.get("DEV_BYPASS_AUTH", "").lower() == "true"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

PATREON_AUTH_URL = "https://www.patreon.com/oauth2/authorize"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
PATREON_IDENTITY_URL = "https://www.patreon.com/api/oauth2/v2/identity"

SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds

# Paywall activation date — free access before this date
PAYWALL_DATE = date(2026, 3, 15)

# Public paths that skip auth
PUBLIC_PATHS = frozenset({
    "/", "/auth/login", "/auth/callback", "/auth/logout", "/admin/unlock", "/random",
    "/jw", "/cw",  # bare author collection index (no trailing segment)
    "/robots.txt", "/llms.txt", "/sitemap.xml", "/license",
})
# Open reading layer (plans/2026-09-06-open-reading-layer.md): work pages,
# author/corpus collection indexes, and .txt/.json siblings all live under
# /jw/ and /cw/. Everything the plan keeps paid (search, auto-themes,
# scripture UI, SWI, /sources) is NOT under those prefixes, so this stays a
# narrow addition rather than inverting the allowlist into a denylist.
PUBLIC_PREFIXES = ("/static/", "/passage/", "/jw/", "/cw/", "/sitemaps/", "/export/")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Wesley Corpus")

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------
class PatreonAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Free access before paywall date
        if date.today() < PAYWALL_DATE:
            return await call_next(request)

        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Admin bypass — session flag set via /admin/unlock?token=...
        if request.session.get("admin"):
            request.state.user = {"name": "Admin", "pledge_cents": MIN_PLEDGE_CENTS}
            return await call_next(request)

        # Dev bypass — act as if logged in with a qualifying pledge
        if DEV_BYPASS_AUTH:
            request.state.user = {
                "name": "Dev User",
                "pledge_cents": MIN_PLEDGE_CENTS,
            }
            return await call_next(request)

        user = _get_session_user(request)

        if user is None:
            # Not logged in
            is_api = path.startswith("/api/")
            if is_api:
                return JSONResponse(
                    {"error": "Authentication required"},
                    status_code=401,
                )
            # Stash intended destination and redirect to login
            next_url = str(request.url.path)
            if request.url.query:
                next_url += "?" + str(request.url.query)
            request.session["next_url"] = next_url
            return RedirectResponse(url="/auth/login", status_code=302)

        if user.get("pledge_cents", 0) < MIN_PLEDGE_CENTS:
            # Logged in but insufficient pledge
            is_api = path.startswith("/api/")
            if is_api:
                return JSONResponse(
                    {"error": "Patron pledge of $%.2f/month required" % (MIN_PLEDGE_CENTS / 100)},
                    status_code=403,
                )
            return templates.TemplateResponse(request, "upgrade.html", {
                "request": request,
                "user": user,
                "min_pledge_dollars": MIN_PLEDGE_CENTS / 100,
                "current_pledge_dollars": user.get("pledge_cents", 0) / 100,
            })

        # Qualified patron — attach user and proceed
        request.state.user = user
        return await call_next(request)


# Middleware ordering: last added = outermost in the stack.
# SessionMiddleware must be outermost so request.session is available
# to PatreonAuthMiddleware.
app.add_middleware(PatreonAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wesley-corpus.fly.dev"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
_on_fly = bool(os.environ.get("FLY_APP_NAME"))
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="wc_session",
    max_age=SESSION_MAX_AGE,
    https_only=_on_fly,
    same_site="lax",
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


def nl2br(text: str):
    """Escape then convert internal newlines to <br> — for prose/hymn text
    that carries meaningful line breaks (paragraph gaps within one passage,
    or stanza lines) that CSS white-space alone won't render predictably
    across browsers with the rest of the page's box model."""
    import html
    from markupsafe import Markup
    escaped = html.escape(text or "")
    return Markup(escaped.replace("\n", "<br>\n"))


templates.env.filters["nl2br"] = nl2br

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

# Open reading layer (plans/2026-09-06-open-reading-layer.md, Phase 5).
# Kept deliberately separate from PASSAGES/PASSAGES_BY_ID above: those feed
# patron search, SWI, and the scripture index, and must not silently change
# just because the open layer re-chunks the journal/Notes/1780 hymns
# differently. OPEN_PASSAGES_BY_ID is a superset used only to resolve a
# work's passage_ids to full passage records for rendering.
WORKS: list[dict] = []
WORKS_BY_SLUG: dict[str, dict] = {}
OPEN_PASSAGES_BY_ID: dict[str, dict] = {}
# legacy passage id -> (work slug, anchor|None) for the /passage/{id} 301.
# anchor is None where the old chunking has no clean 1:1 mapping onto the
# new segmentation (journal/Notes/1780 hymns) — those redirect to the work's
# collection index instead of a specific paragraph; see _load_open_layer().
LEGACY_PASSAGE_REDIRECT: dict[str, tuple[str, str | None]] = {}


def _load_passages():
    with open(CHUNKED / "cleaned_passages.jsonl") as f:
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


# source_id prefixes/values replaced by Phase 2-4 re-segmentation, and the
# collection-index URL an old passage from one of them should 301 to when no
# specific new anchor can be derived (see LEGACY_PASSAGE_REDIRECT above).
_LEGACY_COLLECTION_REDIRECTS = {
    "jw-notes-nt": "/jw/notes-nt",
    "jw-notes-on-old-testament": "/jw/notes-ot",
    "cw-hymns-1780": "/cw/hymns/1780",
}


def _load_open_layer():
    global WORKS
    works_path = META / "works.jsonl"
    if works_path.exists():
        with open(works_path) as f:
            for line in f:
                w = json.loads(line)
                WORKS.append(w)
                WORKS_BY_SLUG[w["id"]] = w

    for extra_name in ("journal_by_entry.jsonl", "notes_by_chapter.jsonl",
                       "hymns_1780_by_number.jsonl"):
        path = CHUNKED / extra_name
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                p = json.loads(line)
                OPEN_PASSAGES_BY_ID[p["id"]] = p

    for w in WORKS:
        # A known-duplicate work (e.g. jw/duplicates/sermon-cw1816-xiii)
        # redirects straight to its canonical target rather than to its own
        # closed/noindex stub — no reason to make a reader land on a page
        # that just says "see the other one."
        reason = w.get("closed_reason") or ""
        target_slug = reason.split("duplicate-of:", 1)[1] if reason.startswith("duplicate-of:") else w["id"]
        for i, pid in enumerate(w.get("legacy_ids") or []):
            anchor = f"p{i}" if target_slug == w["id"] else None
            LEGACY_PASSAGE_REDIRECT[pid] = (target_slug, anchor)

    # Old passages under a replaced whole-source (journal/Notes/1780 hymns)
    # have no legacy_ids entry above (build_works.py sets legacy_ids=[] for
    # the new segmented works) — send them to the collection index instead
    # of 404ing, since no 1:1 anchor exists across the re-segmentation.
    for p in PASSAGES:
        if p["id"] in LEGACY_PASSAGE_REDIRECT:
            continue
        sid = p.get("source_id", "")
        target = _LEGACY_COLLECTION_REDIRECTS.get(sid)
        if target is None and sid.startswith("jw-journal-"):
            target = "/jw/journal"
        if target:
            LEGACY_PASSAGE_REDIRECT[p["id"]] = (target, None)


def _resolve_passage(pid: str) -> dict | None:
    """A work's passage_ids may point into PASSAGES_BY_ID (un-resegmented
    works) or OPEN_PASSAGES_BY_ID (journal/Notes/1780 hymns)."""
    return PASSAGES_BY_ID.get(pid) or OPEN_PASSAGES_BY_ID.get(pid)


@app.on_event("startup")
def startup():
    _load_passages()
    _load_themes()
    _load_scripture()
    _load_sources()
    _load_embeddings()
    _load_open_layer()


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
# Auth helpers
# ---------------------------------------------------------------------------

def _get_session_user(request: Request) -> dict | None:
    """Read user from session cookie. Returns None if not logged in or expired."""
    session = request.session
    if "user_name" not in session:
        return None
    expires_at = session.get("expires_at", 0)
    if time.time() > expires_at:
        request.session.clear()
        return None
    return {
        "name": session["user_name"],
        "pledge_cents": session.get("pledge_cents", 0),
    }


def _ctx(request: Request, **kwargs) -> dict:
    """Build template context with user info for nav display."""
    user = getattr(request.state, "user", None) or _get_session_user(request)
    paywall_active = date.today() >= PAYWALL_DATE
    return {"request": request, "user": user, "paywall_active": paywall_active, **kwargs}


def _build_redirect_uri(request: Request) -> str:
    """Build the OAuth redirect URI, forcing https on production."""
    base = str(request.base_url)
    if _on_fly:
        base = base.replace("http://", "https://")
    return base + "auth/callback"


def _patreon_oauth_url(request: Request) -> str:
    """Build the Patreon OAuth authorization URL."""
    redirect_uri = _build_redirect_uri(request)
    params = {
        "response_type": "code",
        "client_id": PATREON_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "identity identity.memberships",
    }
    return PATREON_AUTH_URL + "?" + urlencode(params)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/login", response_class=HTMLResponse)
def auth_login(request: Request, error: str = ""):
    oauth_url = _patreon_oauth_url(request)
    return templates.TemplateResponse(request, "login.html", {
        "request": request,
        "user": None,
        "oauth_url": oauth_url,
        "error": error,
    })


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(
            url="/auth/login?error=" + quote(error or "Authorization was denied"),
            status_code=302,
        )

    redirect_uri = _build_redirect_uri(request)

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(PATREON_TOKEN_URL, data={
            "code": code,
            "grant_type": "authorization_code",
            "client_id": PATREON_CLIENT_ID,
            "client_secret": PATREON_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
        })
        if token_resp.status_code != 200:
            return RedirectResponse(
                url="/auth/login?error=" + quote("Failed to authenticate with Patreon"),
                status_code=302,
            )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(
                url="/auth/login?error=" + quote("No access token received"),
                status_code=302,
            )

        # Fetch identity + memberships
        identity_resp = await client.get(
            PATREON_IDENTITY_URL,
            params={
                "include": "memberships",
                "fields[user]": "full_name",
                "fields[member]": "currently_entitled_amount_cents,patron_status",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if identity_resp.status_code != 200:
            return RedirectResponse(
                url="/auth/login?error=" + quote("Failed to fetch Patreon identity"),
                status_code=302,
            )
        identity_data = identity_resp.json()

    # Extract user name
    user_name = identity_data.get("data", {}).get("attributes", {}).get("full_name", "Patron")

    # Find highest pledge amount across memberships
    pledge_cents = 0
    for item in identity_data.get("included", []):
        if item.get("type") == "member":
            attrs = item.get("attributes", {})
            if attrs.get("patron_status") == "active_patron":
                amount = attrs.get("currently_entitled_amount_cents", 0)
                pledge_cents = max(pledge_cents, amount)

    # Store in session
    request.session["user_name"] = user_name
    request.session["pledge_cents"] = pledge_cents
    request.session["expires_at"] = time.time() + SESSION_MAX_AGE

    # Redirect to originally requested page or home
    next_url = request.session.pop("next_url", "/")
    return RedirectResponse(url=next_url, status_code=302)


@app.get("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/admin/unlock")
def admin_unlock(request: Request, token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        return JSONResponse({"error": "Invalid token"}, status_code=403)
    request.session["admin"] = True
    return RedirectResponse(url="/", status_code=302)


# ---------------------------------------------------------------------------
# HTML Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    stats = _corpus_stats()
    rp = random.choice(PASSAGES) if PASSAGES else None
    return templates.TemplateResponse(request, "index.html", _ctx(
        request, stats=stats, themes=THEMES, random_passage=rp,
    ))


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", author: str = "", type: str = ""):
    results = _keyword_search(q, author=author or None, source_type=type or None) if q else []
    return templates.TemplateResponse(request, "search.html", _ctx(
        request, q=q, author=author, type=type, results=results,
    ))


@app.get("/semantic", response_class=HTMLResponse)
def semantic_page(request: Request, q: str = ""):
    results = _semantic_search(q) if q else []
    return templates.TemplateResponse(request, "search.html", _ctx(
        request, q=q, author="", type="", results=results, semantic=True,
    ))


@app.get("/themes", response_class=HTMLResponse)
def themes_page(request: Request):
    return templates.TemplateResponse(request, "themes.html", _ctx(
        request, themes=sorted(THEMES, key=lambda t: -t["count"]),
    ))


@app.get("/theme/{theme_id}", response_class=HTMLResponse)
def theme_page(request: Request, theme_id: str):
    theme = THEMES_BY_ID.get(theme_id, {"theme_id": theme_id, "theme_name": theme_id})
    passages = [p for p in PASSAGES if theme_id in p.get("themes", [])]
    return templates.TemplateResponse(request, "theme.html", _ctx(
        request, theme=theme, passages=passages,
    ))


@app.get("/passage/{passage_id}", response_class=HTMLResponse)
def passage_page(request: Request, passage_id: str, q: str = ""):
    # Open reading layer (Phase 5): every old passage id now has a home work
    # page. Un-resegmented works (sermons/treatises/letters/...) redirect to
    # a specific paragraph anchor; journal/Notes/1780-hymn ids — re-chunked
    # onto different boundaries entirely — redirect to the work's collection
    # index instead, since no 1:1 anchor survives the re-segmentation.
    redirect = LEGACY_PASSAGE_REDIRECT.get(passage_id)
    if redirect:
        slug, anchor = redirect
        url = slug if slug.startswith("/") else f"/{slug}"
        if anchor:
            url += f"#{anchor}"
        return RedirectResponse(url=url, status_code=301)

    p = PASSAGES_BY_ID.get(passage_id)
    if not p:
        return HTMLResponse("Passage not found", status_code=404)
    theme_details = [THEMES_BY_ID[t] for t in p.get("themes", []) if t in THEMES_BY_ID]
    return templates.TemplateResponse(request, "passage.html", _ctx(
        request, passage=p, theme_details=theme_details, q=q,
    ))


@app.get("/scripture", response_class=HTMLResponse)
def scripture_page(request: Request, q: str = ""):
    entries, label = _scripture_lookup(q) if q else ([], "")
    books, total_refs = _scripture_browse()
    return templates.TemplateResponse(request, "scripture.html", _ctx(
        request, q=q, label=label, entries=entries,
        books=books, total_refs=total_refs,
    ))


@app.get("/random")
def random_page():
    p = random.choice(PASSAGES) if PASSAGES else None
    if p:
        return RedirectResponse(url=f"/passage/{p['id']}")
    return RedirectResponse(url="/")


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    # Build sources dynamically from passages data
    source_map = {}
    for p in PASSAGES:
        sid = p.get("source_id", "")
        if sid not in source_map:
            source_map[sid] = {
                "source_id": sid,
                "title": p.get("source_title", sid),
                "author": p.get("author", ""),
                "source_type": p.get("source_type", ""),
                "year": p.get("year"),
                "passages": 0,
            }
        source_map[sid]["passages"] += 1

    # Group by author, then by type
    from collections import defaultdict
    grouped = defaultdict(lambda: defaultdict(list))
    for s in source_map.values():
        grouped[s["author"]][s["source_type"]].append(s)

    # Sort within each group
    for author in grouped:
        for stype in grouped[author]:
            grouped[author][stype].sort(key=lambda x: (x.get("year") or 9999, x["title"]))

    # Type display order
    type_order = ["sermon", "treatise", "journal", "letter", "notes",
                  "hymn", "hymn-collection", "hymn-stanza"]

    total_passages = len(PASSAGES)
    total_sources = len(source_map)

    return templates.TemplateResponse(request, "sources.html", _ctx(
        request,
        grouped=dict(grouped),
        type_order=type_order,
        total_passages=total_passages,
        total_sources=total_sources,
    ))


@app.get("/strangely-warmed", response_class=HTMLResponse)
def swi_page(request: Request):
    return templates.TemplateResponse(request, "swi.html", _ctx(request))


@app.get("/swi", response_class=HTMLResponse)
def swi_page_alt(request: Request):
    return templates.TemplateResponse(request, "swi.html", _ctx(request))


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
# Open reading layer (plans/2026-09-06-open-reading-layer.md, Phase 5)
# ---------------------------------------------------------------------------
# corpus -> ordered list of work ids, and work id -> (prev_id, next_id),
# built once at first use (not startup, since it only matters once a work
# page is actually requested) and cached.
_WORK_ORDER_BY_CORPUS: dict[str, list[str]] | None = None
_WORK_PREV_NEXT: dict[str, tuple[str | None, str | None]] = {}

_NATSORT_RE = re.compile(r"(\d+)")


def _natural_sort_key(slug: str):
    parts = _NATSORT_RE.split(slug)
    return [int(p) if p.isdigit() else p for p in parts]


def _build_work_order():
    global _WORK_ORDER_BY_CORPUS
    by_corpus: dict[str, list[str]] = {}
    for w in WORKS:
        by_corpus.setdefault(w["corpus"], []).append(w["id"])
    for corpus, ids in by_corpus.items():
        ids.sort(key=_natural_sort_key)
        for i, wid in enumerate(ids):
            prev_id = ids[i - 1] if i > 0 else None
            next_id = ids[i + 1] if i + 1 < len(ids) else None
            _WORK_PREV_NEXT[wid] = (prev_id, next_id)
    _WORK_ORDER_BY_CORPUS = by_corpus


def _work_prev_next(work_id: str):
    if _WORK_ORDER_BY_CORPUS is None:
        _build_work_order()
    return _WORK_PREV_NEXT.get(work_id, (None, None))


def _work_passages(work: dict) -> list[dict]:
    out = []
    for pid in work.get("passage_ids") or []:
        p = _resolve_passage(pid)
        if p:
            out.append(p)
    return out


KNOWN_AUTHORS = {"jw": "John Wesley", "cw": "Charles Wesley"}


def _corpus_display_name(author: str, corpus: str) -> str:
    names = {
        "jw-sermons": "Sermons", "jw-works": "Works", "jw-letters": "Letters",
        "jw-journal": "Journal", "jw-notes-nt": "Notes on the New Testament",
        "jw-notes-ot": "Notes on the Old Testament",
        "cw-sermons": "Sermons", "cw-works": "Works",
        "cw-hymns-1780": "A Collection of Hymns (1780)",
        "cw-hymns-misc": "Hymns", "cw-hymns-collection-placeholder": "Hymn Collections",
    }
    return names.get(corpus, corpus.replace("-", " ").title())


@app.get("/robots.txt")
def robots_txt():
    return Response((BASE / "static" / "robots.txt").read_text(), media_type="text/plain")


@app.get("/llms.txt")
def llms_txt():
    return Response((BASE / "static" / "llms.txt").read_text(), media_type="text/plain")


@app.get("/license", response_class=HTMLResponse)
def license_page(request: Request):
    return templates.TemplateResponse(request, "license.html", _ctx(request))


_SITEMAP_NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


@app.get("/sitemap.xml")
def sitemap_index(request: Request):
    base = str(request.base_url).rstrip("/")
    corpora = sorted({w["corpus"] for w in WORKS if w["open"]})
    entries = "\n".join(
        f"  <sitemap><loc>{base}/sitemaps/{c}.xml</loc></sitemap>" for c in corpora
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex {_SITEMAP_NS}>\n{entries}\n</sitemapindex>\n'
    return Response(xml, media_type="application/xml")


@app.get("/sitemaps/{corpus}.xml")
def sitemap_child(request: Request, corpus: str):
    base = str(request.base_url).rstrip("/")
    items = [w for w in WORKS if w["corpus"] == corpus and w["open"]]
    entries = "\n".join(
        f"  <url><loc>{base}/{w['id']}</loc></url>" for w in items
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {_SITEMAP_NS}>\n{entries}\n</urlset>\n'
    return Response(xml, media_type="application/xml")


@app.get("/{author}", response_class=HTMLResponse)
def author_index(request: Request, author: str):
    if author not in KNOWN_AUTHORS:
        return HTMLResponse("Not found", status_code=404)
    corpora = sorted({w["corpus"] for w in WORKS if w["id"].startswith(f"{author}/")})
    counts = {c: sum(1 for w in WORKS if w["corpus"] == c) for c in corpora}
    return templates.TemplateResponse(request, "open_author_index.html", _ctx(
        request,
        author=author, author_name=KNOWN_AUTHORS[author],
        corpora=[{"slug": c, "name": _corpus_display_name(author, c), "count": counts[c]}
                 for c in corpora],
    ))


@app.get("/{author}/{corpus}", response_class=HTMLResponse)
def corpus_index(request: Request, author: str, corpus: str):
    if author not in KNOWN_AUTHORS:
        return HTMLResponse("Not found", status_code=404)
    prefix = f"{author}/{corpus}/"
    items = [w for w in WORKS if w["id"].startswith(prefix)]
    if not items:
        return HTMLResponse("Not found", status_code=404)
    items.sort(key=lambda w: _natural_sort_key(w["id"]))
    return templates.TemplateResponse(request, "open_corpus_index.html", _ctx(
        request,
        author=author, author_name=KNOWN_AUTHORS[author],
        corpus=corpus, corpus_name=_corpus_display_name(author, corpus),
        works=items,
    ))


@app.get("/{author}/{corpus}/{rest:path}")
def work_page(request: Request, author: str, corpus: str, rest: str):
    if author not in KNOWN_AUTHORS:
        return HTMLResponse("Not found", status_code=404)

    fmt = "html"
    if rest.endswith(".txt"):
        fmt, rest = "txt", rest[:-4]
    elif rest.endswith(".json"):
        fmt, rest = "json", rest[:-5]

    slug = f"{author}/{corpus}/{rest}"
    work = WORKS_BY_SLUG.get(slug)
    if not work:
        return HTMLResponse("Not found", status_code=404)

    passages = _work_passages(work)

    if fmt == "json":
        return JSONResponse({**work, "passages": passages})

    if fmt == "txt":
        header = (
            f"{work['title']}\n"
            f"{work.get('author', '').replace('-', ' ').title()}\n"
            f"Source: {work.get('source_edition', {}).get('title') or 'see ' + request.url_for('work_page', author=author, corpus=corpus, rest=rest)}\n"
            f"License: text public domain; apparatus {work.get('license_apparatus', 'CC BY 4.0')}, History of Methodism / Wesley Corpus.\n"
            f"Cite as: {work['title']}, Wesley Corpus, {request.url_for('work_page', author=author, corpus=corpus, rest=rest)}\n"
            f"{'-' * 40}\n\n"
        )
        body = "\n\n".join(p.get("text", "") for p in passages)
        return Response(header + body, media_type="text/plain; charset=utf-8")

    prev_id, next_id = _work_prev_next(work["id"])
    prev_work = WORKS_BY_SLUG.get(prev_id) if prev_id else None
    next_work = WORKS_BY_SLUG.get(next_id) if next_id else None
    is_hymn = work["type"] == "hymn"

    # A hymn flattened to prose is a different text (plan) — split each hymn
    # passage into its stanzas so the template can wrap each one separately,
    # preserving internal line breaks with <br>. Splitting on every blank
    # line over-fragments badly on this source's heavy OCR damage (Phase 4):
    # spurious blank lines inside a single real stanza are common, and a
    # naive split produced 20+ "stanzas" for hymns that print 6-11. Splitting
    # on the stanza's own leading number (present at every real stanza start,
    # "1 FOR a thousand tongues...", "2 My gracious Master...") is the real
    # structural marker and survives the internal OCR blank lines intact.
    _HYMN_HEADER_RE = re.compile(r"^HYMN\s+\d+\.[^\n]*\n+")
    _STANZA_SPLIT_RE = re.compile(r"\n\s*\n(?=\d{1,2}[ \t])")
    stanzas_by_passage = {}
    if is_hymn:
        for p in passages:
            body = _HYMN_HEADER_RE.sub("", p.get("text", ""), count=1)
            blocks = [b.strip("\n") for b in _STANZA_SPLIT_RE.split(body.strip()) if b.strip()]
            stanzas_by_passage[p["id"]] = blocks

    return templates.TemplateResponse(request, "work.html", _ctx(
        request,
        work=work, passages=passages, is_hymn=is_hymn,
        stanzas_by_passage=stanzas_by_passage,
        prev_work=prev_work, next_work=next_work,
        author_name=KNOWN_AUTHORS[author],
    ))




# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
