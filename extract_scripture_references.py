#!/usr/bin/env python3
"""
Extract Bible/scripture references from Wesley corpus passages.
Saves results to scripture-references.csv and scripture-index.json
"""

import json
import re
import csv
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Bible book name mappings - abbreviations and full names to canonical forms
BOOK_MAPPINGS = {
    # Old Testament - Genesis to Malachi
    "gen": "Genesis", "genesis": "Genesis",
    "exod": "Exodus", "exodus": "Exodus",
    "lev": "Leviticus", "leviticus": "Leviticus",
    "num": "Numbers", "numbers": "Numbers",
    "deut": "Deuteronomy", "deuteronomy": "Deuteronomy",
    "josh": "Joshua", "joshua": "Joshua",
    "judg": "Judges", "judges": "Judges",
    "ruth": "Ruth",
    "1 sam": "1 Samuel", "1sam": "1 Samuel", "1 samuel": "1 Samuel",
    "2 sam": "2 Samuel", "2sam": "2 Samuel", "2 samuel": "2 Samuel",
    "1 kings": "1 Kings", "1kings": "1 Kings",
    "2 kings": "2 Kings", "2kings": "2 Kings",
    "1 chron": "1 Chronicles", "1chron": "1 Chronicles", "1 chronicles": "1 Chronicles",
    "2 chron": "2 Chronicles", "2chron": "2 Chronicles", "2 chronicles": "2 Chronicles",
    "ezra": "Ezra",
    "neh": "Nehemiah", "nehemiah": "Nehemiah",
    "esth": "Esther", "esther": "Esther",
    "job": "Job",
    "ps": "Psalms", "psa": "Psalms", "psalm": "Psalms", "psalms": "Psalms",
    "prov": "Proverbs", "proverbs": "Proverbs",
    "eccles": "Ecclesiastes", "ecclesiastes": "Ecclesiastes",
    "song": "Song of Solomon", "song of songs": "Song of Solomon", "songs": "Song of Solomon",
    "isa": "Isaiah", "isaiah": "Isaiah",
    "jer": "Jeremiah", "jeremiah": "Jeremiah",
    "lam": "Lamentations", "lamentations": "Lamentations",
    "ezek": "Ezekiel", "ezekiel": "Ezekiel",
    "dan": "Daniel", "daniel": "Daniel",
    "hos": "Hosea", "hosea": "Hosea",
    "joel": "Joel",
    "amos": "Amos",
    "obad": "Obadiah", "obadiah": "Obadiah",
    "jonah": "Jonah",
    "mic": "Micah", "micah": "Micah",
    "nah": "Nahum", "nahum": "Nahum",
    "hab": "Habakkuk", "habakkuk": "Habakkuk",
    "zeph": "Zephaniah", "zephaniah": "Zephaniah",
    "hag": "Haggai", "haggai": "Haggai",
    "zech": "Zechariah", "zechariah": "Zechariah",
    "mal": "Malachi", "malachi": "Malachi",

    # New Testament - Matthew to Revelation
    "matt": "Matthew", "matthew": "Matthew",
    "mark": "Mark",
    "luke": "Luke",
    "john": "John",
    "acts": "Acts",
    "rom": "Romans", "romans": "Romans",
    "1 cor": "1 Corinthians", "1cor": "1 Corinthians", "1 corinthians": "1 Corinthians",
    "2 cor": "2 Corinthians", "2cor": "2 Corinthians", "2 corinthians": "2 Corinthians",
    "gal": "Galatians", "galatians": "Galatians",
    "eph": "Ephesians", "ephesians": "Ephesians",
    "phil": "Philippians", "philippians": "Philippians",
    "col": "Colossians", "colossians": "Colossians",
    "1 thess": "1 Thessalonians", "1thess": "1 Thessalonians", "1 thes": "1 Thessalonians", "1thes": "1 Thessalonians", "1 thessalonians": "1 Thessalonians",
    "2 thess": "2 Thessalonians", "2thess": "2 Thessalonians", "2 thes": "2 Thessalonians", "2thes": "2 Thessalonians", "2 thessalonians": "2 Thessalonians",
    "1 tim": "1 Timothy", "1tim": "1 Timothy", "1 timothy": "1 Timothy",
    "2 tim": "2 Timothy", "2tim": "2 Timothy", "2 timothy": "2 Timothy",
    "tit": "Titus", "titus": "Titus",
    "philem": "Philemon", "philemon": "Philemon",
    "heb": "Hebrews", "hebrews": "Hebrews",
    "jas": "James", "james": "James",
    "1 pet": "1 Peter", "1pet": "1 Peter", "1 peter": "1 Peter",
    "2 pet": "2 Peter", "2pet": "2 Peter", "2 peter": "2 Peter",
    "1 john": "1 John", "1john": "1 John",
    "2 john": "2 John", "2john": "2 John",
    "3 john": "3 John", "3john": "3 John",
    "jude": "Jude",
    "rev": "Revelation", "revelation": "Revelation",
}

def normalize_book_name(book_str: str) -> Optional[str]:
    """Normalize a book name to canonical form."""
    normalized = book_str.strip().lower().replace(".", "")
    return BOOK_MAPPINGS.get(normalized)

def extract_scripture_references(text: str) -> List[Dict]:
    """
    Extract Bible references from text using regex.
    Returns list of dicts with: book, chapter, verse_start, verse_end, full_reference
    """
    references = []

    # Build regex pattern for book names
    # Match: Book Name chapter:verse, chapter:verse-verse, chapter:verse,verse

    # Create pattern parts
    # Abbreviated forms (with optional period)
    abbrev_books = [
        r"(?:1\s+)?(?:Sam|Kings|Chron|Thess|Thes|Cor|Tim|Pet|John)",
        r"(?:Gen|Exod|Lev|Num|Deut|Josh|Judg|Ruth|Neh|Esth|Job|Psa?|Prov|Eccles|Song|Isa|Jer|Lam|Ezek|Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal)",
        r"(?:Matt|Mark|Luke|John|Acts|Rom|Gal|Eph|Phil|Col|Tit|Heb|Jas|Jude|Rev)",
    ]

    # Full book names
    full_books = [
        r"(?:1\s+)?(?:Samuel|Kings|Chronicles|Thessalonians|Corinthians|Timothy|Peter|John)",
        r"(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Nehemiah|Esther|Job|Psalms|Proverbs|Ecclesiastes|Song(?:\s+of\s+Solomon)?|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi)",
        r"(?:Matthew|Mark|Luke|Acts|Romans|Galatians|Ephesians|Philippians|Colossians|Titus|Hebrews|James|Jude|Revelation)",
    ]

    # Combine all book patterns with optional period
    book_pattern = "(?:" + "|".join(abbrev_books + full_books) + r")\.?"

    # Verse pattern: chapter:verse, optionally with -verse or ,verse
    verse_pattern = r"\s*(\d+):(\d+)(?:-(\d+)|,\s*(\d+))?"

    # Full pattern: book name followed by chapter:verse
    pattern = r"\b(" + book_pattern + r")" + verse_pattern

    # Find all matches
    for match in re.finditer(pattern, text, re.IGNORECASE):
        book_str = match.group(1)
        chapter = match.group(2)
        verse_start = match.group(3)
        verse_end = match.group(4) or match.group(5) or verse_start  # Handle both - and , notation

        # Normalize book name
        normalized_book = normalize_book_name(book_str)
        if normalized_book:
            full_ref = f"{normalized_book} {chapter}:{verse_start}"
            if verse_end and verse_end != verse_start:
                full_ref = f"{normalized_book} {chapter}:{verse_start}-{verse_end}"

            references.append({
                "book": normalized_book,
                "chapter": int(chapter),
                "verse_start": int(verse_start),
                "verse_end": int(verse_end) if verse_end else int(verse_start),
                "full_reference": full_ref,
                "original_match": match.group(0)
            })

    return references

def process_corpus(corpus_path: str) -> Tuple[List[Dict], Dict]:
    """
    Process the corpus and extract scripture references.
    Returns: (references_list, index_dict)
    """
    references_list = []
    index = defaultdict(lambda: defaultdict(list))

    with open(corpus_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                passage = json.loads(line)
                passage_id = passage.get('id')
                text = passage.get('text', '')
                source_title = passage.get('source_title', '')
                author = passage.get('author', '')

                # Extract references from this passage
                refs = extract_scripture_references(text)

                for ref in refs:
                    # Add to references list
                    ref_record = {
                        "passage_id": passage_id,
                        "reference": ref["full_reference"],
                        "book": ref["book"],
                        "chapter": ref["chapter"],
                        "verse_start": ref["verse_start"],
                        "verse_end": ref["verse_end"],
                        "source_title": source_title,
                        "author": author
                    }
                    references_list.append(ref_record)

                    # Add to index
                    index[ref["book"]][ref["chapter"]].append({
                        "passage_id": passage_id,
                        "source_title": source_title,
                        "author": author,
                        "verses": f"{ref['verse_start']}-{ref['verse_end']}" if ref['verse_start'] != ref['verse_end'] else str(ref['verse_start'])
                    })

                if line_num % 1000 == 0:
                    print(f"Processed {line_num} passages...")

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue
            except Exception as e:
                print(f"Error processing line {line_num}: {e}")
                continue

    return references_list, dict(index)

def save_csv(references: List[Dict], output_path: str):
    """Save references to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'passage_id', 'reference', 'book', 'chapter', 'verse_start',
            'verse_end', 'source_title', 'author'
        ])
        writer.writeheader()
        writer.writerows(references)
    print(f"Saved {len(references)} references to {output_path}")

def save_json_index(index: Dict, output_path: str):
    """Save index to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)
    print(f"Saved index to {output_path}")

def print_stats(references: List[Dict]):
    """Print summary statistics."""
    print("\n" + "="*60)
    print("SCRIPTURE REFERENCE EXTRACTION SUMMARY")
    print("="*60)

    total_refs = len(references)
    print(f"\nTotal references found: {total_refs}")

    # Top 10 books
    book_counter = Counter(ref['book'] for ref in references)
    print("\nTop 10 Most Cited Books:")
    for i, (book, count) in enumerate(book_counter.most_common(10), 1):
        print(f"  {i:2d}. {book:20s} {count:4d} references")

    # Top 10 verses (book:chapter:verse)
    verse_counter = Counter(
        f"{ref['book']} {ref['chapter']}:{ref['verse_start']}"
        for ref in references
    )
    print("\nTop 10 Most Cited Verses:")
    for i, (verse, count) in enumerate(verse_counter.most_common(10), 1):
        print(f"  {i:2d}. {verse:30s} {count:3d} references")

    # Top 10 passages (by number of references)
    passage_counter = Counter(ref['passage_id'] for ref in references)
    print("\nTop 10 Passages with Most Scripture References:")
    for i, (passage_id, count) in enumerate(passage_counter.most_common(10), 1):
        matching_refs = [r for r in references if r['passage_id'] == passage_id]
        source = matching_refs[0]['source_title'] if matching_refs else 'Unknown'
        print(f"  {i:2d}. {passage_id:30s} {count:3d} references - {source}")

    print("\n" + "="*60)

def main():
    # Paths
    corpus_path = "/Users/wilsonpruitt/Documents/Personal/wesley-corpus/chunked/passages.jsonl"
    output_csv = "/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-references.csv"
    output_json = "/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-index.json"

    print("Starting scripture reference extraction...")
    print(f"Reading from: {corpus_path}")

    # Process corpus
    references, index = process_corpus(corpus_path)

    # Save results
    save_csv(references, output_csv)
    save_json_index(index, output_json)

    # Print statistics
    print_stats(references)

if __name__ == '__main__':
    main()
