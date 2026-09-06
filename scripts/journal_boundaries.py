#!/usr/bin/env python3
"""Phase 2 boundary pass for the open reading layer
(plans/2026-09-06-open-reading-layer.md).

Finds journal ENTRY boundaries and resolves each entry's date, reading the
cleaned journal text (cleaned/john-wesley/journal-*.txt — the OCR-fixed copies,
so the day-name garbles handled by journal_ocr_fixes.py are already repaired).

Method, and why it is built this way:

Wesley states the weekday of every entry, so a candidate (year, month, day) can
be checked against the real calendar. That check cannot by itself *choose* the
month — within any year about two months share a starting weekday, so a run of
entries from one month fits ~2 months no matter how long the run is (measured:
mean 2.0 candidates, flat from 1 to 8 entries). What it can do is *reject* a
wrong month, which is exactly the guard needed: date drift is the failure mode
that would silently misfile entries onto the wrong year page.

So the date is resolved by a constrained walk rather than by inference alone:
  - explicit signals set the state (Curnock's "[Journal, 1758]" tag, an explicit
    "1752. MARCH 15, Sun.-", or a month named in the entry head) — but a
    fully-stated date (year AND month both given) is trusted on the weekday
    check alone, never second-guessed against a possibly-already-wrong prior
    state, and a ctx_year tag is treated as advisory, not absolute: it can lag
    a New Year's Day entry that announces the rollover inline (Curnock updates
    it per printed page, not per calendar day), so state-continuation steps
    are tried with their own computed year before falling back to a year-wide
    search under the tag's year, then under tag-year+1;
  - otherwise the month advances only when the day number goes backwards;
  - every resulting date must satisfy the stated weekday, and chronology must
    not run backwards. Where the default step fails the weekday test, nearby
    months are tried and the earliest chronologically-consistent fit wins;
  - the FROM/TO extract headers process_corpus.py's cleaning strips as
    front-matter noise are recovered from the RAW file and mapped back onto
    the cleaned file's offsets (find_checkpoints, via a letters-only anchor
    phrase), so each printed extract still gets a fresh reseed;
  - a second-pass rescue (rescue_with_nearby_year) catches entries the walk
    can never reach at all — Emory's opening extract turns out to be Wesley's
    decade-spanning retrospective narrative (1728-1738), not a day-by-day
    diary, so entries like the Aldersgate date ("Wednesday, May 24" = 1738,
    no year of its own) are recovered by searching backward in the actual
    text for the nearest bare year mention. This rescue is best-effort and
    knowingly imperfect: tracing it found one entry (of 729 rescued) pulled
    in a wrong nearby year from an embedded quoted narrative with its own
    date context. Rescued rows are tagged status="rescued", distinct from
    the primary walk's "ok", so a consumer can weight them differently;
  - anything still unresolved is written out flagged, never guessed.

Pre-1752 dates are Julian (Britain switched 1752-09-14; weekdays ran unbroken
across the switch), handled in weekday().

Writes metadata/journal-entry-boundaries.csv. Read-only: re-chunking into
chunked/journal_by_entry.jsonl is the separate wiring step.
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT / "cleaned" / "john-wesley"
RAW_DIR = ROOT / "raw" / "john-wesley"
OUT = ROOT / "metadata" / "journal-entry-boundaries.csv"

DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ALIASES = {
    "mon": "Monday", "monday": "Monday",
    "tues": "Tuesday", "tue": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "wednes": "Wednesday", "wednesday": "Wednesday",
    "thur": "Thursday", "thurs": "Thursday", "thu": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "satur": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
DAY_RE = "|".join(sorted(DAY_ALIASES, key=len, reverse=True))
MON_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

# Entry head, covering every convention seen across the edition families:
#   Emory vol1-3 ....... "Tuesday, October 14, 1735.--"   "Fri. 17.--"
#   London vol III ..... "Tues. MAY 6.--"  "Wed, 7.--"  inline "Saturday, 10. I"
#   London vol IV ...... "Mon. SEPTEMBER 13.--"  inline "Friday, 17. I went"
#   Curnock parts ...... "[Journal, 1758] Wed. 21.-"  "1752. MARCH 15, Sun.-"
# The inline forms (no dash, run into the previous line) are the trap: a regex
# tuned only on ".--" silently drops them, and they are ordinary entries.
ENTRY_RE = re.compile(
    rf"(?:\[Journal,\s*(?P<ctx_year>1[67]\d\d)\]\s*)?"
    rf"(?:"
    # lead_year binds ONLY to the month-first branch ("1752. MARCH 15, Sun.-")
    # and only across a short gap — it must NOT be free to attach to the
    # day-name-first branch below, where a bare year is far more likely to be
    # leftover text from the end of the PREVIOUS sentence ("...since Oct. 14,
    # 1735.\n\nSun. 18.--") than a genuine date declaration for this entry.
    rf"(?:(?P<lead_year>1[67]\d\d)\.[ \t]*\n?[ \t]*)?"
    rf"(?P<lead_month>{MON_RE})\b\.?,?\s*(?P<lead_dnum>\d{{1,2}}),?\s*(?P<lead_day>{DAY_RE})\b"
    rf"|\b(?P<day>{DAY_RE})\b\.?,?\s*(?:(?P<month>{MON_RE})\b\.?,?\s*)?(?P<dnum>\d{{1,2}})"
    rf"(?:st|nd|rd|th)?\s*(?:,\s*(?P<year>1[67]\d\d))?)"
    rf"\s*(?P<sep>\.\s*-{{1,2}}|\.\s|,\s*-{{1,2}}|-)",
    re.IGNORECASE,
)
RANGE_RE = re.compile(
    rf"FROM\s+(?P<m1>{MON_RE})\w*\.?\s*(?P<d1>\d{{1,2}}),?\s*(?P<y1>1[67]\d\d)\s*,?\s*"
    rf"TO\s+(?P<m2>{MON_RE})\w*\.?\s*(?P<d2>\d{{1,2}}),?\s*(?P<y2>1[67]\d\d)",
    re.IGNORECASE,
)
# A handful of Curnock section files (journal-vol4-part11-section02, found by
# tracing a bad date at its very start) open on a bare "MONTH YEAR, In <place>"
# section head instead of a "FROM ... TO ..." extract header, and carry no
# other reseed point at all — without one, the file's ctx_year-only first
# entry has no month to anchor on and the blind year-wide search guesses
# wrong. Matched only at start-of-line, since this is not a recurring running
# head in the files that have it (checked: exactly one occurrence apiece).
MONTH_YEAR_HEAD_RE = re.compile(
    rf"^(?P<m1>{MON_RE})\.?\s+(?P<y1>1[67]\d\d),", re.IGNORECASE | re.MULTILINE,
)

# Word-level day-name garbles specific to the raw scans (journal_ocr_fixes.py
# repairs these before the text reaches cleaned/ — see CLAUDE.md's OCR-gotchas
# section — so they only matter here, where checkpoints are located in the
# RAW file before being mapped onto the cleaned file's offsets).
RAW_DAY_GARBLES = {
    "tvrspay": "Tuesday", "wepnespay": "Wednesday", "saturpay": "Saturday",
    "frwway": "Friday", "toespay": "Tuesday", "monpay": "Monday",
    "sunpay": "Sunday", "thurspay": "Thursday", "tvesday": "Tuesday",
    "wednespay": "Wednesday",
}
RAW_DAY_GARBLE_RE = re.compile(r"\b(" + "|".join(RAW_DAY_GARBLES) + r")\b", re.IGNORECASE)


def jdn_julian(y, m, d):
    a = (14 - m) // 12
    y2, m2 = y + 4800 - a, m + 12 * a - 3
    return d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - 32083


def jdn_gregorian(y, m, d):
    a = (14 - m) // 12
    y2, m2 = y + 4800 - a, m + 12 * a - 3
    return d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - y2 // 100 + y2 // 400 - 32045


def jdn(y, m, d):
    return jdn_gregorian(y, m, d) if (y, m, d) >= (1752, 9, 14) else jdn_julian(y, m, d)


def weekday(y, m, d):
    return DOW[jdn(y, m, d) % 7]


def days_in_month(y, m):
    if m == 2:
        leap = (y % 4 == 0) if y < 1752 else (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        return 29 if leap else 28
    return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def valid(y, m, d, dow):
    return d <= days_in_month(y, m) and weekday(y, m, d) == dow


def step_month(y, m, n=1):
    idx = (y * 12 + (m - 1)) + n
    return idx // 12, idx % 12 + 1


def parse_entries(text):
    """Yield raw entry hits with whatever the text states explicitly."""
    for mt in ENTRY_RE.finditer(text):
        g = mt.groupdict()
        if g["lead_dnum"]:
            day_name, dnum = DAY_ALIASES[g["lead_day"].lower()], int(g["lead_dnum"])
            month = MONTHS[g["lead_month"].lower()]
        else:
            if not g["day"] or not g["dnum"]:
                continue
            day_name, dnum = DAY_ALIASES[g["day"].lower()], int(g["dnum"])
            month = MONTHS[g["month"].lower()] if g["month"] else None
        if not 1 <= dnum <= 31:
            continue
        # An inline year stated IN the entry ("1756, Jan. 1.-") outranks
        # Curnock's page-level "[Journal, 1755]" tag: the bracketed tag can
        # legitimately lag a page or two behind a New Year's Day entry that
        # announces the rollover inline. Found by tracing a real mismatch —
        # ctx_year said 1755 for an entry that opens "1756, Jan. 1.-".
        year = g["lead_year"] or g["year"] or g["ctx_year"]
        yield {
            "offset": mt.start(), "dow": day_name, "dnum": dnum,
            "month": month, "year": int(year) if year else None,
            "snippet": text[mt.start():mt.start() + 64].replace("\n", " "),
        }


def resolve(entries, seed_y, seed_m, year_bounds):
    """Constrained forward walk: explicit signals win, the month advances only
    when the day number goes backwards, and every date must satisfy the stated
    weekday without running chronologically backwards. year_bounds, when given,
    is the (first, last) year declared by the extract's own range header — a
    date outside it is rejected outright rather than allowed to drift."""
    y, m = seed_y, seed_m
    prev_jdn = None
    prev_dnum = None
    out = []
    for e in entries:
        ey, em, d, dow = e["year"], e["month"], e["dnum"], e["dow"]
        explicit = bool(ey and em)  # fully-stated date: trust weekday alone,
        cands = []                 # never second-guess it against prior drift
        if ey and em:
            cands = [(ey, em)]
        elif ey:
            # ctx_year (e.g. Curnock's "[Journal, 1755]" tag) confirms the
            # year but says nothing about month. Prefer continuing from the
            # running month state, then step forward, before falling back to
            # a year-wide search — a blind 1..12 search usually lands on a
            # false match, since ~2 months in any year share a weekday for
            # a given day-of-month (measured in scripts/journal_boundaries.py
            # development; see the module docstring).
            # Discovered by tracing real failures: the tag can lag past a New
            # Year's Day entry by several lines (Curnock updates it per
            # printed page, not per calendar day), so state-continuation
            # steps are tried with their OWN computed year — not forced to
            # ey — before falling back to a year-wide search under ey, then
            # under ey+1 for a stale tag.
            if m is not None:
                cands = [step_month(y if y is not None else ey, m, k) for k in (0, 1, 2, 3)]
            else:
                cands = []
            cands += [(ey, mm) for mm in range(1, 13)]
            cands += [(ey + 1, mm) for mm in range(1, 13)]
        elif em:
            base_y = y if y is not None else seed_y
            if base_y is not None:
                # a named month that goes backwards means the year rolled
                cands = [(base_y, em)] if (m is None or em >= m) else [(base_y + 1, em)]
                cands += [(base_y + 1, em), (base_y, em)]
        elif y is not None and m is not None:
            # default: same month; if the day number went backwards, next month.
            same = (y, m)
            nxt = step_month(y, m, 1)
            forward = prev_dnum is None or d > prev_dnum
            cands = [same, nxt] if forward else [nxt, same]
            cands += [step_month(y, m, k) for k in (2, 3)]
        fit = None
        for cy, cm in cands:
            if year_bounds and not (year_bounds[0] <= cy <= year_bounds[1]):
                continue
            if not valid(cy, cm, d, dow):
                continue
            j = jdn(cy, cm, d)
            if not explicit and prev_jdn is not None and not (0 <= j - prev_jdn <= 400):
                continue
            fit = (cy, cm)
            break
        if fit is None:
            # State is left untouched so one bad entry cannot derail the walk.
            out.append({**e, "date": None, "resolved_y": None, "resolved_m": None,
                        "status": "unresolved"})
            continue
        y, m = fit
        prev_jdn = jdn(y, m, d)
        prev_dnum = d
        # The Journal demonstrably runs 1735-10-14 to 1790-10-24. A date outside
        # that window is drift by definition, so it is flagged, not published.
        outside = (y, m, d) < (1735, 10, 14) or (y, m, d) > (1790, 10, 24)
        out.append({**e, "date": f"{y:04d}-{m:02d}-{d:02d}", "resolved_y": y,
                    "resolved_m": m,
                    "status": "out-of-range" if outside else "ok"})
    return out


def norm_letters(text):
    """Lowercase-letters-only projection of text, with an index back to each
    kept character's original offset — the alignment device that lets a
    phrase found in RAW text be located in the differently-whitespaced
    CLEANED text without caring about dashes, quotes, or line breaks."""
    out, idx = [], []
    for i, ch in enumerate(text):
        lc = ch.lower()
        if "a" <= lc <= "z":
            out.append(lc)
            idx.append(i)
        elif out and out[-1] != " ":
            out.append(" ")
            idx.append(i)
    return "".join(out), idx


def find_checkpoints(raw_path, cleaned_text, window=12000):
    """Locate each extract's "FROM <date> TO <date>" header in the RAW file
    (process_corpus.py's cleaning strips these as front-matter noise — see
    Phase 2 commit notes — so they no longer exist in cleaned/), then find
    that extract's first entry in the RAW text and use its body text as an
    anchor to recover the equivalent offset in the CLEANED file. Returns a
    list of (cleaned_offset, year, month), in file order, one per extract that
    could be located; extracts whose first entry can't be found (very long
    prefaces, in a couple of cases) are silently skipped rather than guessed —
    the constrained walk still covers that ground from the *previous*
    checkpoint, just without a fresh reseed at that specific boundary."""
    if not raw_path.exists():
        return []
    raw = raw_path.read_text(encoding="utf-8", errors="replace")
    raw = raw.replace("—", "--").replace("–", "-")  # em/en dash -> ascii
    raw = RAW_DAY_GARBLE_RE.sub(lambda m: RAW_DAY_GARBLES[m.group(1).lower()], raw)

    cn, cn_idx = norm_letters(cleaned_text)
    checkpoints = []
    seen = set()
    search_from = 0

    def try_header(h_end, y1, m1):
        nonlocal search_from
        after = raw[h_end:h_end + window]
        em = ENTRY_RE.search(after)
        if not em:
            return False
        body = after[em.end():em.end() + 40]
        anchor, _ = norm_letters(body)
        anchor = anchor.strip()[:30]
        if not anchor:
            return False
        pos = cn.find(anchor, search_from)
        if pos < 0:
            return False
        search_from = pos
        checkpoints.append((cn_idx[pos], y1, m1))
        return True

    for h in RANGE_RE.finditer(raw):
        key = h.group(0).lower()
        if key in seen:
            continue
        before = raw[max(0, h.start() - 30):h.start()]
        if "\n" not in before:
            continue  # a date range quoted in running prose, not a real header
        seen.add(key)
        try_header(h.end(), int(h.group("y1")), MONTHS[h.group("m1").lower()])

    if not checkpoints:
        # Fallback for files with no "FROM ... TO ..." header at all (see
        # MONTH_YEAR_HEAD_RE above).
        for h in MONTH_YEAR_HEAD_RE.finditer(raw):
            try_header(h.end(), int(h.group("y1")), MONTHS[h.group("m1").lower()])

    return checkpoints


NEARBY_YEAR_RE = re.compile(r"\b(1[67]\d\d)\b")


def rescue_with_nearby_year(rows, text, lookback=4000):
    """Second-pass rescue for entries the forward walk cannot reach.

    Found while tracing the Aldersgate entry ("Wednesday, May 24" — 1738-05-24,
    the date the site's own Strangely Warmed Index is named for): Emory's
    opening "FROM FEBRUARY 1, 1728, TO AUGUST 12, 1738" extract is not a
    day-by-day diary at all — it is Wesley's decade-spanning retrospective
    narrative, quoting Moravian testimonies and his own letters out of strict
    calendar order, with only ~14 bare year mentions in 158K characters of
    prose to anchor it. The forward-walk model (state carries the running
    month, advances only when the day number drops) assumes a continuous
    diary and cannot follow this structure — by the time the walk reaches
    Aldersgate its state is still stuck a decade earlier.

    So for any entry the walk left unresolved, with no year of its own, look
    backward in the actual source text for the nearest bare year mention and
    retry validity against it directly (no forward-chronology requirement —
    this is explicitly for entries the chronological walk cannot reach)."""
    rescued = 0
    for r in rows:
        if r["status"] != "unresolved" or r.get("year"):
            continue
        before = text[max(0, r["offset"] - lookback):r["offset"]]
        matches = NEARBY_YEAR_RE.findall(before)
        if not matches:
            continue
        y = int(matches[-1])  # nearest (last) year mention before this entry
        d, dow = r["dnum"], r["dow"]
        months = [r["month"]] if r["month"] else range(1, 13)
        for mm in months:
            if valid(y, mm, d, dow):
                r["date"] = f"{y:04d}-{mm:02d}-{d:02d}"
                r["resolved_y"], r["resolved_m"] = y, mm
                r["status"] = "rescued"
                rescued += 1
                break
    return rescued


def demote_inconsistent_dates(rows, window=15, tolerance=3, passes=4):
    """Final consistency guard, in document order (rows must already be
    offset-sorted). Found necessary while checking vol4-part11-section02,
    which quotes another correspondent's testimony at length, itself full of
    footnotes citing dates from entirely different years (1755, 1758, 1763,
    1764, 1780...) — the rescue's nearest-bare-year heuristic has much less
    to work with there than in the isolated Aldersgate case, and produced
    short runs of entries years away from their true neighbors (an 1769 run
    and an 1761 run both sitting inside an otherwise-1759/1760 stretch).

    A date more than `tolerance` years from the median of its surrounding
    `window` dated neighbors (on both sides) is demoted back to unresolved
    rather than published as if it were as trustworthy as the rest. Iterated
    a few times so a short run of bad entries doesn't shield its own
    interior members from the neighbors just outside the run."""
    import statistics
    demoted_total = 0
    for _ in range(passes):
        dated = [r for r in rows if r["status"] in ("ok", "rescued")]
        demote_ids = set()
        for i, r in enumerate(dated):
            neighbor_years = [
                dated[j]["resolved_y"]
                for j in range(max(0, i - window), min(len(dated), i + window + 1))
                if j != i
            ]
            if len(neighbor_years) < 3:
                continue
            med = statistics.median(neighbor_years)
            if abs(r["resolved_y"] - med) > tolerance:
                demote_ids.add(id(r))
        if not demote_ids:
            break
        for r in rows:
            if id(r) in demote_ids:
                r["status"] = "unresolved"
                r["date"] = None
                r["resolved_y"] = None
                r["resolved_m"] = None
                demoted_total += 1
    return demoted_total


def scan_file(path):
    """Each file holds several printed extracts, each starting from its own
    explicit "FROM <date> TO <date>" header. Those headers are re-seed points:
    resolving each extract independently stops drift in one extract from
    propagating through the rest of the volume."""
    text = path.read_text(encoding="utf-8", errors="replace")
    entries = list(parse_entries(text))
    seeds = find_checkpoints(RAW_DIR / path.name, text)

    if not seeds:
        seed_y = seed_m = None
        for e in entries:                      # fall back to the first stated year
            if e["year"]:
                seed_y, seed_m = e["year"], e["month"]
                break
        out = resolve(entries, seed_y, seed_m, None)
        rescue_with_nearby_year(out, text)
        return out

    out = []
    for i, (off, y1, m1) in enumerate(seeds):
        end = seeds[i + 1][0] if i + 1 < len(seeds) else len(text)
        block = [e for e in entries if off <= e["offset"] < end]
        out.extend(resolve(block, y1, m1, None))
    # entries before the first checkpoint (front matter, prefaces)
    head0 = seeds[0][0]
    out = resolve([e for e in entries if e["offset"] < head0], None, None, None) + out
    rescue_with_nearby_year(out, text)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the boundaries CSV")
    args = ap.parse_args()

    all_rows = []
    print(f"{'file':46s} {'entries':>8s} {'dated':>7s} {'unres':>7s} {'rate':>7s}  span")
    for path in sorted(CLEAN_DIR.glob("journal-*.txt")):
        rows = scan_file(path)
        for r in rows:
            r["source_file"] = path.stem
        demote_inconsistent_dates(rows)
        ok = [r for r in rows if r["status"] in ("ok", "rescued")]
        yrs = sorted({r["resolved_y"] for r in ok})
        span = f"{yrs[0]}-{yrs[-1]}" if yrs else "-"
        rate = len(ok) / len(rows) if rows else 0
        print(f"{path.stem:46s} {len(rows):8d} {len(ok):7d} {len(rows)-len(ok):7d} {rate:6.1%}  {span}")
        all_rows.extend(rows)

    ok = [r for r in all_rows if r["status"] in ("ok", "rescued")]
    print(f"\nTOTAL entry heads detected: {len(all_rows)}")
    print(f"  dated (weekday-verified): {len(ok)} ({len(ok)/max(1,len(all_rows)):.1%})")
    print(f"  unresolved (flagged):     {len(all_rows)-len(ok)}")
    yrs = Counter(r["resolved_y"] for r in ok)
    print(f"  validated year span:      {min(yrs)}-{max(yrs)} across {len(yrs)} years")

    if args.write:
        with OUT.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "source_file", "offset", "date", "resolved_y", "resolved_m",
                "dnum", "dow", "status", "snippet"], extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nWrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
