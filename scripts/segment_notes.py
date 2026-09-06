#!/usr/bin/env python3
"""Phase 3 of the open reading layer (plans/2026-09-06-open-reading-layer.md).

Re-segments Wesley's Notes on the Bible into chapters, closing the CLAUDE.md
gap where jw-notes-nt and jw-notes-on-old-testament contribute near-zero to
scripture-index.json despite being mostly scripture commentary.

Sources (both raw, not cleaned/ — see the two "real structure" notes below):
  raw/john-wesley/notes-on-new-testament-wesley.txt   (CCEL text, 27 books)
  raw/john-wesley/notes-on-old-testament.txt          (Wesley's Henry/Poole
                                                        abridgment, 39 books)

NT structure (reliable, explicit): each book has its own bare-line heading
("ST. MATTHEW", "1st CORINTHIANS", "NOTES ON THE REVELATION OF JOHN" for the
one exception with no short form), chapters are bare roman numerals on their
own line, verses are "NN. text..." at the start of a paragraph.

OT structure is a different, harder problem, found by tracing why a naive
approach kept producing impossible chapter counts (a labeled "Daniel" block
with 48 headed chapters — Daniel only has 12):

  - There are NO book-name headers at all. Wesley's abridgment transitions
    between books through prose alone ("Moses in this book begins...").
    Chapters reset to "Chapter I" at every book start, so book boundaries are
    inferred by RESET POSITION, matched against the standard 39-book,
    929-chapter canonical order — then verified against the actual opening
    text of each resulting block (every single one confirmed by content,
    e.g. "Jehoiakim's first captivity... Daniel" for the Daniel block).
  - FOUR entire books are duplicated verbatim, back to back, in the raw
    file: Esther, Song of Solomon, Lamentations, and Jonah each appear
    twice with byte-identical opening text. A real transcription/ingestion
    defect, not a segmentation bug — the duplicate copy of each is dropped.
  - THREE books have NO annotation at all — zero "Chapter I" resets exist
    for them anywhere in the file: Psalms (150 ch.), Isaiah (66 ch.), and
    Zephaniah (3 ch.). Recorded, not silently absorbed into a neighbor.
  - One book (2 Samuel) is short by exactly one chapter (23 of 24 headed) —
    an ordinary, disclosed instance of "chapters Wesley did not annotate."
  - Verses are marked differently than in the NT file: a bare ARABIC number
    alone on its own line (not "NN. text" inline), e.g. "1" then a new
    paragraph of commentary. No ambiguity with the roman-numeral chapter
    markers (different character sets).

Writes chunked/notes_by_chapter.jsonl (one passage per chapter) and
metadata/notes-ot-missing-books.csv (Psalms/Isaiah/Zephaniah, disclosed).
Read-only against chunked/cleaned_passages.jsonl.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ocr_cleaning import clean_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "raw" / "john-wesley"
OUT = ROOT / "chunked" / "notes_by_chapter.jsonl"
MISSING_OUT = ROOT / "metadata" / "notes-ot-missing-books.csv"

ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s):
    s, total, prev = s.upper(), 0, 0
    for ch in reversed(s):
        v = ROMAN_MAP[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


# ---------------------------------------------------------------------------
# New Testament
# ---------------------------------------------------------------------------

# (search pattern, OSIS code, display name), in file order. Each is searched
# starting just after the previous match — deterministic, no fragile generic
# book-name regex needed since every one of these exact forms was confirmed
# by hand against the raw file.
NT_BOOKS = [
    (r"^[ \t]*ST\. MATTHEW[ \t]*$", "Matt", "Matthew"),
    (r"^[ \t]*MARK[ \t]*$", "Mark", "Mark"),
    (r"^[ \t]*THE GOSPEL OF LUKE[ \t]*$", "Luke", "Luke"),
    (r"^[ \t]*THE GOSPEL OF JOHN[ \t]*$", "John", "John"),
    (r"^[ \t]*THE ACTS[ \t]*$", "Acts", "Acts"),
    (r"^[ \t]*ROMANS[ \t]*$", "Rom", "Romans"),
    (r"^[ \t]*1st\s+CORINTHIANS[ \t]*$", "1Cor", "1 Corinthians"),
    (r"^[ \t]*2nd\s+CORINTHIANS[ \t]*$", "2Cor", "2 Corinthians"),
    (r"^[ \t]*GALATIANS[ \t]*$", "Gal", "Galatians"),
    (r"^[ \t]*EPHESIANS[ \t]*$", "Eph", "Ephesians"),
    (r"^[ \t]*PHILIPPIANS[ \t]*$", "Phil", "Philippians"),
    (r"^[ \t]*COLOSSIANS[ \t]*$", "Col", "Colossians"),
    (r"^[ \t]*1\s+THESSALONIANS[ \t]*$", "1Thess", "1 Thessalonians"),
    (r"^[ \t]*2nd\s+THESSALONIANS[ \t]*$", "2Thess", "2 Thessalonians"),
    (r"^[ \t]*1st\s+TIMOTHY[ \t]*$", "1Tim", "1 Timothy"),
    (r"^[ \t]*2nd\s+TIMOTHY[ \t]*$", "2Tim", "2 Timothy"),
    (r"^[ \t]*TITUS[ \t]*$", "Titus", "Titus"),
    (r"^[ \t]*PHILEMON[ \t]*$", "Phlm", "Philemon"),
    (r"^[ \t]*HEBREWS[ \t]*$", "Heb", "Hebrews"),
    (r"^[ \t]*JAMES[ \t]*$", "Jas", "James"),
    (r"^[ \t]*1st\s+PETER[ \t]*$", "1Pet", "1 Peter"),
    (r"^[ \t]*2nd\s+PETER[ \t]*$", "2Pet", "2 Peter"),
    (r"^[ \t]*1st\s+JOHN[ \t]*$", "1John", "1 John"),
    (r"^[ \t]*2nd\s+JOHN[ \t]*$", "2John", "2 John"),
    (r"^[ \t]*3rd\s+JOHN[ \t]*$", "3John", "3 John"),
    (r"^[ \t]*JUDE[ \t]*$", "Jude", "Jude"),
    (r"^[ \t]*NOTES ON THE REVELATION OF JOHN[ \t]*$", "Rev", "Revelation"),
]

CHAPTER_RE = re.compile(r"^[ \t]*([IVXLCDM]+)[ \t]*$", re.MULTILINE)
NT_VERSE_RE = re.compile(r"\n[ \t]*\n[ \t]*(\d{1,3})\.\s+")


def segment_nt():
    text = RAW_DIR.joinpath("notes-on-new-testament-wesley.txt").read_text(
        encoding="utf-8", errors="replace")
    positions = []
    cursor = 0
    for pattern, osis, name in NT_BOOKS:
        m = re.search(pattern, text[cursor:], re.MULTILINE)
        if not m:
            raise RuntimeError(f"NT book header not found: {name} ({pattern})")
        start = cursor + m.end()
        positions.append((start, osis, name))
        cursor = start
    positions.append((len(text), None, None))  # sentinel end

    chapters = []
    for i in range(len(positions) - 1):
        start, osis, name = positions[i]
        end = positions[i + 1][0]
        book_text = text[start:end]
        chapters.extend(segment_chapters(book_text, start, osis, name, "NT"))
    return chapters


def segment_chapters(book_text, base_offset, osis, name, testament):
    """Split one book's text on its chapter headers — bare roman numerals for
    the NT file, "Chapter <roman>" for the OT file (see module docstring)."""
    pattern = CHAPTER_RE if testament == "NT" else OT_CHAPTER_RE
    heads = [(m.start(), roman_to_int(m.group(1))) for m in pattern.finditer(book_text)]
    out = []
    for i, (off, ch) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(book_text)
        chapter_text = book_text[off:end]
        verses = segment_nt_verses(chapter_text) if testament == "NT" else segment_ot_verses(chapter_text)
        out.append({
            "osis": osis, "book_name": name, "chapter": ch,
            "text": chapter_text, "verses": verses,
        })
    return out


def enforce_monotonic(marks):
    """Verse numbers only ever increase within a chapter. Wesley's own prose
    restarts a "1. ... 2. ... 3." outline inside a sub-section (found tracing
    78 of 260 NT chapters with an impossible verse sequence like "...4, 4, 5,
    6" or "...14, 1, 2, 3, 1, 2, ..."), and that pattern is indistinguishable
    from a real verse marker by its shape alone — only by breaking the
    increasing sequence. Kept as the gate itself asks for (plan: "verse
    anchors monotonic within a chapter"): a candidate is accepted only if it
    is strictly greater than the last accepted one; a restart is dropped."""
    out, last = [], 0
    for off, n in marks:
        if n > last:
            out.append((off, n))
            last = n
    return out


def segment_nt_verses(chapter_text):
    marks = [(m.start(1), int(m.group(1))) for m in NT_VERSE_RE.finditer(chapter_text)]
    return enforce_monotonic(marks)


OT_VERSE_RE = re.compile(r"\n[ \t]*(\d{1,3})[ \t]*\n")


def segment_ot_verses(chapter_text):
    marks = [(m.start(1), int(m.group(1))) for m in OT_VERSE_RE.finditer(chapter_text)]
    return enforce_monotonic(marks)


# ---------------------------------------------------------------------------
# Old Testament
# ---------------------------------------------------------------------------

OT_CHAPTER_RE = re.compile(r"^[ \t]*Chapter\s+([IVXLCDM]+)[ \t]*$", re.MULTILINE)

# Verified by content against the actual text (see module docstring) — the
# 36 books that DO have chapter headers, in the order their blocks appear
# once exact-duplicate blocks are dropped. Psalms, Isaiah, and Zephaniah are
# absent from this list on purpose: zero "Chapter I" reset exists for them
# anywhere in the file.
OT_BOOKS_PRESENT = [
    ("Gen", "Genesis"), ("Exod", "Exodus"), ("Lev", "Leviticus"),
    ("Num", "Numbers"), ("Deut", "Deuteronomy"), ("Josh", "Joshua"),
    ("Judg", "Judges"), ("Ruth", "Ruth"), ("1Sam", "1 Samuel"),
    ("2Sam", "2 Samuel"), ("1Kgs", "1 Kings"), ("2Kgs", "2 Kings"),
    ("1Chr", "1 Chronicles"), ("2Chr", "2 Chronicles"), ("Ezra", "Ezra"),
    ("Neh", "Nehemiah"), ("Esth", "Esther"), ("Job", "Job"),
    ("Prov", "Proverbs"), ("Eccl", "Ecclesiastes"), ("Song", "Song of Solomon"),
    ("Jer", "Jeremiah"), ("Lam", "Lamentations"), ("Ezek", "Ezekiel"),
    ("Dan", "Daniel"), ("Hos", "Hosea"), ("Joel", "Joel"), ("Amos", "Amos"),
    ("Obad", "Obadiah"), ("Jonah", "Jonah"), ("Mic", "Micah"), ("Nah", "Nahum"),
    ("Hab", "Habakkuk"), ("Hag", "Haggai"), ("Zech", "Zechariah"),
    ("Mal", "Malachi"),
]
OT_BOOKS_MISSING = [("Ps", "Psalms", 150), ("Isa", "Isaiah", 66), ("Zeph", "Zephaniah", 3)]


def segment_ot():
    text = RAW_DIR.joinpath("notes-on-old-testament.txt").read_text(
        encoding="utf-8", errors="replace")
    heads = [(m.start(), roman_to_int(m.group(1))) for m in OT_CHAPTER_RE.finditer(text)]

    blocks, cur = [], []
    for off, n in heads:
        if n == 1 and cur:
            blocks.append(cur)
            cur = []
        cur.append((off, n))
    blocks.append(cur)

    def opener(block):
        off = block[0][0]
        return re.sub(r"\s+", " ", text[off:off + 100]).strip()

    seen, kept = {}, []
    dupes_dropped = 0
    for b in blocks:
        key = opener(b)
        if key in seen:
            dupes_dropped += 1
            continue
        seen[key] = True
        kept.append(b)

    if len(kept) != len(OT_BOOKS_PRESENT):
        raise RuntimeError(
            f"OT block count {len(kept)} != {len(OT_BOOKS_PRESENT)} expected "
            f"books present — the source file changed or a new duplicate/gap "
            f"appeared; re-verify by content before trusting this run."
        )
    print(f"OT: {dupes_dropped} duplicate block(s) dropped, {len(kept)} books matched")

    chapters = []
    for (osis, name), block in zip(OT_BOOKS_PRESENT, kept):
        book_start = block[0][0]
        book_end_idx = blocks.index(block) + 1
        # end of this book's real text = start of the NEXT block among the
        # ORIGINAL (undeduplicated) list, so a dropped duplicate immediately
        # following doesn't get folded into this book's last chapter.
        orig_idx = blocks.index(block)
        book_end = blocks[orig_idx + 1][0][0] if orig_idx + 1 < len(blocks) else len(text)
        book_text = text[book_start:book_end]
        chapters.extend(segment_chapters(book_text, book_start, osis, name, "OT"))
    return chapters


# ---------------------------------------------------------------------------


def build_passage(ch, testament, chunk_index):
    body = clean_text(ch["text"].strip())
    word_count = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", body))
    slug = "notes-nt" if testament == "NT" else "notes-ot"
    return {
        "id": f"jw-{slug}-{ch['osis'].lower()}-{ch['chapter']:03d}",
        "author": "john-wesley",
        "source_id": f"jw-{slug}",
        "source_title": f"Explanatory Notes on the {'New' if testament=='NT' else 'Old'} Testament",
        "source_type": "notes",
        "year": 1755 if testament == "NT" else 1765,
        "chunk_index": chunk_index,
        "text": body,
        "word_count": word_count,
        "source_url": None,
        "themes": [],
        "created_at": "2026-09-06T00:00:00+00:00",
        "work": f"jw/{slug}/{ch['osis'].lower()}/{ch['chapter']}",
        "osis_book": ch["osis"],
        "book_name": ch["book_name"],
        "chapter": ch["chapter"],
        "verse_count": len(ch["verses"]),
    }


def main():
    nt_chapters = segment_nt()
    print(f"NT: {len(nt_chapters)} chapters across 27 books")
    ot_chapters = segment_ot()
    print(f"OT: {len(ot_chapters)} chapters across {len(OT_BOOKS_PRESENT)} books")

    passages = []
    for i, ch in enumerate(nt_chapters):
        passages.append(build_passage(ch, "NT", i))
    for i, ch in enumerate(ot_chapters):
        passages.append(build_passage(ch, "OT", i))

    empty = [p["id"] for p in passages if p["word_count"] == 0]
    if empty:
        print(f"WARNING: {len(empty)} chapter(s) with zero text: {empty}", file=sys.stderr)

    with OUT.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"Wrote {len(passages)} passages to {OUT.relative_to(ROOT)}")

    with MISSING_OUT.open("w", encoding="utf-8") as f:
        f.write("osis,book_name,expected_chapters,reason\n")
        for osis, name, n in OT_BOOKS_MISSING:
            f.write(f"{osis},{name},{n},no Chapter-I reset found anywhere in "
                    f"notes-on-old-testament.txt -- Wesley's abridgment does "
                    f"not annotate this book at all\n")
    print(f"Wrote {MISSING_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
