"""SWI v2 judge-result cache + daily spend cap — Phase 2b.

SQLite, keyed on sha256(text + rubric_version) so a rubric bump naturally
invalidates old scores instead of serving stale judgments under a new
rubric. On Fly this file lives on the machine's ephemeral disk (per the
plan: "fine -- it's a cost/latency optimization, not state").

The daily counter bounds worst-case spend on this publicly-reachable
endpoint: once SWI_DAILY_JUDGE_CAP LLM scores have run today, further
requests fall back to the lexicon engine (scoring.py's job, not this
module's) rather than calling the API.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "chunked" / "swi_cache.db"
DAILY_CAP = int(os.environ.get("SWI_DAILY_JUDGE_CAP", "200"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS swi_cache (
            cache_key TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS swi_daily_count (
            day TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        )
    """)
    return conn


def cache_key(text: str, rubric_version: str) -> str:
    return hashlib.sha256(f"{rubric_version}:{text}".encode("utf-8")).hexdigest()


def get_cached(text: str, rubric_version: str) -> dict | None:
    key = cache_key(text, rubric_version)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT result_json FROM swi_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def set_cached(text: str, rubric_version: str, result: dict) -> None:
    key = cache_key(text, rubric_version)
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO swi_cache (cache_key, result_json, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(result, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def under_daily_cap() -> bool:
    """True if today's judge-call count is still under DAILY_CAP."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT count FROM swi_daily_count WHERE day = ?", (_today(),)
        ).fetchone()
        return (row[0] if row else 0) < DAILY_CAP
    finally:
        conn.close()


def record_judge_call() -> int:
    """Increment today's judge-call counter. Returns the new count."""
    today = _today()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO swi_daily_count (day, count) VALUES (?, 1)
            ON CONFLICT(day) DO UPDATE SET count = count + 1
            """,
            (today,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM swi_daily_count WHERE day = ?", (today,)
        ).fetchone()
        return row[0]
    finally:
        conn.close()
