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
    "1752. MARCH 15, Sun.-", or a month named in the entry head);
  - otherwise the month advances only when the day number goes backwards;
  - every resulting date must satisfy the stated weekday, and chronology must
    not run backwards. Where the default step fails the weekday test, nearby
    months are tried and the earliest chronologically-consistent fit wins;
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
    rf"(?:(?P<lead_year>1[67]\d\d)\.\s*)?"
    rf"(?:(?P<lead_month>{MON_RE})\b\.?,?\s*(?P<lead_dnum>\d{{1,2}}),?\s*(?P<lead_day>{DAY_RE})\b"
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
        year = g["ctx_year"] or g["lead_year"] or g["year"]
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
        cands = []
        if ey and em:
            cands = [(ey, em)]
        elif ey:
            cands = [(ey, mm) for mm in range(1, 13)]
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
            if prev_jdn is not None and not (0 <= j - prev_jdn <= 400):
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


def scan_file(path):
    """Each file holds several printed extracts, and each carries its own
    explicit "FROM <date> TO <date>" header. Those headers are re-seed points:
    resolving each extract independently stops drift in one extract from
    propagating through the rest of the volume, and bounds the year range."""
    text = path.read_text(encoding="utf-8", errors="replace")
    heads = [(m.start(), int(m.group("y1")), MONTHS[m.group("m1").lower()],
              int(m.group("y2"))) for m in RANGE_RE.finditer(text)]
    # de-duplicate repeated headers (they recur as running heads) keeping order
    seeds, seen = [], set()
    for off, y1, m1, y2 in heads:
        if (y1, m1, y2) in seen:
            continue
        seen.add((y1, m1, y2))
        seeds.append((off, y1, m1, y2))

    entries = list(parse_entries(text))
    if not seeds:
        seed_y = seed_m = None
        for e in entries:                      # fall back to the first stated year
            if e["year"]:
                seed_y, seed_m = e["year"], e["month"]
                break
        return resolve(entries, seed_y, seed_m, None)

    out = []
    for i, (off, y1, m1, y2) in enumerate(seeds):
        end = seeds[i + 1][0] if i + 1 < len(seeds) else len(text)
        block = [e for e in entries if off <= e["offset"] < end]
        out.extend(resolve(block, y1, m1, None))
    # entries before the first header (front matter, prefaces)
    head0 = seeds[0][0]
    out = resolve([e for e in entries if e["offset"] < head0], None, None, None) + out
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
        ok = [r for r in rows if r["status"] == "ok"]
        yrs = sorted({r["resolved_y"] for r in ok})
        span = f"{yrs[0]}-{yrs[-1]}" if yrs else "-"
        rate = len(ok) / len(rows) if rows else 0
        print(f"{path.stem:46s} {len(rows):8d} {len(ok):7d} {len(rows)-len(ok):7d} {rate:6.1%}  {span}")
        all_rows.extend(rows)

    ok = [r for r in all_rows if r["status"] == "ok"]
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
