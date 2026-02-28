"""
SWI API (Phase 2E)
====================

FastAPI router for the StrangelyWarmIndex.
Mount on existing web_app or run standalone.

Endpoints:
    POST /api/swi/score     — score a text
    GET  /api/swi/score     — score text from URL
    POST /api/swi/compare   — compare multiple texts
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .scoring import score_text, compare_texts

FEEDBACK_FILE = Path(__file__).resolve().parent.parent / "metadata" / "feedback.jsonl"

router = APIRouter(prefix="/api/swi", tags=["StrangelyWarmIndex"])


class ScoreRequest(BaseModel):
    text: str
    include_semantic: bool = True


class CompareItem(BaseModel):
    label: str
    text: str


class CompareRequest(BaseModel):
    texts: list[CompareItem]


class FeedbackRequest(BaseModel):
    text_snippet: str = Field(..., max_length=500, description="First 500 chars of scored text")
    overall_score: int
    expected: str = Field(..., description="too-high, too-low, or about-right")
    expected_score: int | None = None
    comment: str = Field("", max_length=1000)
    author: str = Field("", max_length=200, description="Tradition or affiliation of the text")


@router.post("/score")
def api_score(req: ScoreRequest):
    """Score a text for Wesleyan affinity."""
    if not req.text.strip():
        raise HTTPException(400, "Text is required")
    if len(req.text) > 50000:
        raise HTTPException(400, "Text too long (max 50,000 characters)")
    return score_text(req.text, include_semantic=req.include_semantic)


@router.get("/score")
def api_score_url(url: str = Query(..., description="URL to fetch and score")):
    """Fetch a URL and score its text content."""
    import re

    html = _fetch_url_safely(url)

    # Strip HTML tags (basic extraction)
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise HTTPException(400, "No text content found at URL")

    text = text[:50000]
    return score_text(text)


def _fetch_url_safely(url: str) -> str:
    """
    Fetch URL with SSRF protection using DNS-pinned connections.

    Prevents DNS rebinding by resolving DNS once, validating all IPs are
    public, then connecting directly to the validated IP via a custom
    httpcore network backend. The DNS is never re-resolved.
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    import httpcore
    from httpcore._backends.sync import SyncBackend, SyncStream

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(400, "Only HTTPS URLs are allowed")

    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(400, "Invalid URL")

    port = parsed.port or 443

    # Resolve DNS once and validate ALL resolved IPs are public
    try:
        addrs = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(400, "Could not resolve hostname")

    target = None
    for family, socktype, proto, _, addr in addrs:
        ip = ipaddress.ip_address(addr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(400, "Access to private/internal addresses is not allowed")
        if target is None:
            target = (family, socktype, proto, addr)

    if target is None:
        raise HTTPException(400, "Could not resolve hostname")

    # Connect directly to the validated IP — prevents DNS rebinding.
    # TLS still verifies the certificate against the hostname via SNI.
    fam, stype, sproto, saddr = target

    class _PinnedBackend(SyncBackend):
        """Network backend that connects to a pre-validated IP address."""
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            sock = socket.socket(fam, stype, sproto)
            sock.settimeout(timeout)
            if local_address:
                sock.bind((local_address, 0))
            for opt in socket_options or []:
                sock.setsockopt(*opt)
            sock.connect(saddr)
            return SyncStream(sock)

    try:
        with httpcore.ConnectionPool(
            network_backend=_PinnedBackend(),
            max_connections=1,
        ) as pool:
            resp = pool.request(
                "GET",
                url,
                headers=[(b"User-Agent", b"WesleyCorpusSWI/1.0")],
            )
            if resp.status < 200 or resp.status >= 300:
                raise HTTPException(400, "URL did not return a successful response")
            return resp.content.decode("utf-8", errors="replace")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Failed to fetch URL")


@router.post("/compare")
def api_compare(req: CompareRequest):
    """Compare multiple texts for Wesleyan affinity."""
    if len(req.texts) < 2:
        raise HTTPException(400, "At least 2 texts required")
    if len(req.texts) > 5:
        raise HTTPException(400, "Maximum 5 texts for comparison")
    return compare_texts([{"label": t.label, "text": t.text} for t in req.texts])


@router.post("/feedback")
def api_feedback(req: FeedbackRequest):
    """Submit feedback on a surprising score."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text_snippet": req.text_snippet[:500],
        "overall_score": req.overall_score,
        "expected": req.expected,
        "expected_score": req.expected_score,
        "comment": req.comment,
        "author": req.author,
    }
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "ok", "message": "Thanks for the feedback!"}


@router.get("/feedback")
def api_feedback_list():
    """List all feedback entries."""
    if not FEEDBACK_FILE.exists():
        return []
    entries = []
    for line in FEEDBACK_FILE.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def create_standalone_app():
    """Create a standalone FastAPI app for the SWI API."""
    from fastapi import FastAPI
    app = FastAPI(title="StrangelyWarmIndex", description="How Wesleyan is your text?")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://wesley-corpus.fly.dev"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app
