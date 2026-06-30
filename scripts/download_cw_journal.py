#!/usr/bin/env python3
"""Download Charles Wesley's Journal from Wesley Center Online (wesley.nnu.edu).

Fetches each journal section page, extracts the main content text,
and saves as plain text files in raw/charles-wesley/journal/.

Usage:
    python3 scripts/download_cw_journal.py
"""

import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "raw" / "charles-wesley" / "journal"

PAGES = [
    ("1736-03-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-march-9-august-30-1736/"),
    ("1736-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-4-december-30-1736/"),
    ("1737-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-3-april-30-1737/"),
    ("1737-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-2-august-31-1737/"),
    ("1737-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-9-december-31-1737/"),
    ("1738-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-5-april-30-1738/"),
    ("1738-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-31-1738/"),
    ("1738-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-26-1738/"),
    ("1739-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-2-april-30-1739/"),
    ("1739-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-31-1739/"),
    ("1739-09-to-11", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-november-6-1739/"),
    ("1740-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-6-1740/"),
    ("1740-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-7-december-31-1740/"),
    ("1741-04-to-09", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-april-3-september-22-1741/"),
    ("1743-01-to-02", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-2-february-27-1743/"),
    ("1743-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-17-august-28-1743/"),
    ("1743-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-2-december-31-1743/"),
    ("1744-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-1-april-30-1744/"),
    ("1744-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-2-august-31-1744/"),
    ("1745-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-4-april-28-1745/"),
    ("1745-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-5-august-26-1745/"),
    ("1745-09-to-12a", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-2-december-30-1745/"),
    ("1745-09-to-12b", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-29-1745/"),
    ("1746-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-1-april-30-1746/"),
    ("1746-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-31-1746/"),
    ("1746-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-2-december-31-1746/"),
    ("1747-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-1-april-27-1747/"),
    ("1747-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-3-august-31-1747/"),
    ("1747-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-28-1747/"),
    ("1748-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-januray-15-april-29-1748/"),
    ("1748-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-31-1748/"),
    ("1748-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-31-1748/"),
    ("1749-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-january-3-april-30-1749/"),
    ("1749-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-31-1749/"),
    ("1749-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-25-1749/"),
    ("1750-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-januray-1-april-20-1750/"),
    ("1750-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-2-august-28-1750/"),
    ("1750-09-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-1-december-28-1750/"),
    ("1751-01-to-04", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-janurary-1-april-30-1751/"),
    ("1751-05-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-may-1-august-26-1751/"),
    ("1753-11-to-12", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-november-29-december-61753/"),
    ("1754-07-to-08", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-july-8-august-13-1754/"),
    ("1756-09-to-11", "https://wesley.nnu.edu/charles-wesley/the-journal-of-charles-wesley-1707-1788/the-journal-of-charles-wesley-september-17-november-5-1756/"),
]


class ContentExtractor(HTMLParser):
    """Extract main article text from Wesley Center Online pages (TYPO3 CMS)."""

    def __init__(self):
        super().__init__()
        self.in_bodytext = False
        self.text_parts = []
        self.skip_first_h1 = True  # Skip the page title h1

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get('class', '')

        if tag == 'p' and 'bodytext' in cls:
            self.in_bodytext = True
            self.text_parts.append('\n\n')
        elif tag == 'br' and self.in_bodytext:
            self.text_parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'p' and self.in_bodytext:
            self.in_bodytext = False

    def handle_data(self, data):
        if self.in_bodytext:
            self.text_parts.append(data)

    def get_text(self):
        text = ''.join(self.text_parts)
        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        # Clean HTML entities that slipped through
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()


def download_page(url):
    """Download and extract text from a Wesley Center Online page."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Wesley-Corpus-Research/1.0 (academic research)'
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    parser = ContentExtractor()
    parser.feed(html)
    return parser.get_text()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for slug, url in PAGES:
        outfile = OUTPUT_DIR / f"cw-journal-{slug}.txt"
        if outfile.exists() and outfile.stat().st_size > 100:
            print(f"  SKIP {slug} (already exists)")
            continue

        try:
            text = download_page(url)
            if len(text) < 100:
                print(f"  WARN {slug}: very short ({len(text)} chars)")

            outfile.write_text(text, encoding='utf-8')
            print(f"  OK   {slug}: {len(text):,} chars")
        except Exception as e:
            print(f"  FAIL {slug}: {e}")

        # Be polite to the server
        time.sleep(1.5)

    # Summary
    files = list(OUTPUT_DIR.glob("cw-journal-*.txt"))
    total_chars = sum(f.stat().st_size for f in files)
    print(f"\nDownloaded {len(files)} files, {total_chars:,} chars total")


if __name__ == "__main__":
    main()
