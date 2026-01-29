#!/usr/bin/env python3
"""
Wesley Corpus Processing Tools
==============================

Tools for cleaning, chunking, and managing the Wesley corpus for the Wesley Index project.

Usage:
    python process_corpus.py clean <input_file> <output_file>
    python process_corpus.py chunk <input_file> --source-id <id> --author <author> --type <type>
    python process_corpus.py stats
    python process_corpus.py validate
"""

import json
import re
import csv
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import unicodedata

# Configuration
CORPUS_ROOT = Path(__file__).parent
RAW_DIR = CORPUS_ROOT / "raw"
CLEANED_DIR = CORPUS_ROOT / "cleaned"
CHUNKED_DIR = CORPUS_ROOT / "chunked"
METADATA_DIR = CORPUS_ROOT / "metadata"
PASSAGES_FILE = CHUNKED_DIR / "passages.jsonl"

# Chunking parameters
MIN_CHUNK_WORDS = 100
MAX_CHUNK_WORDS = 400
OVERLAP_SENTENCES = 1


def clean_text(text: str) -> str:
    """
    Clean OCR artifacts and normalize text.
    
    - Fixes common OCR errors
    - Normalizes whitespace
    - Converts fancy quotes to standard
    - Removes page numbers and headers
    """
    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)
    
    # Common OCR fixes
    ocr_fixes = {
        'ﬁ': 'fi',
        'ﬂ': 'fl',
        'ﬀ': 'ff',
        'ﬃ': 'ffi',
        'ﬄ': 'ffl',
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '—': '--',
        '–': '-',
        '…': '...',
        '\u00AD': '',  # soft hyphen
    }
    for old, new in ocr_fixes.items():
        text = text.replace(old, new)
    
    # Remove page numbers (common patterns)
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    text = re.sub(r'\n\s*-\s*\d+\s*-\s*\n', '\n', text)
    
    # Remove running headers (lines that are ALL CAPS and short)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip if it's a short all-caps line (likely a header)
        if stripped and len(stripped) < 60 and stripped.isupper():
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
    text = re.sub(r'\n{3,}', '\n\n', text)  # Multiple newlines to double
    text = re.sub(r' +\n', '\n', text)  # Trailing spaces
    text = re.sub(r'\n +', '\n', text)  # Leading spaces on lines
    
    # Fix hyphenation at line breaks
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    
    return text.strip()


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, handling abbreviations."""
    # Split on sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    source_id: str,
    author: str,
    source_title: str,
    source_type: str,
    year: Optional[int] = None,
    source_url: Optional[str] = None
) -> List[Dict]:
    """
    Chunk text into passages suitable for embedding.
    
    Returns a list of passage dictionaries.
    """
    passages = []
    
    # Split into paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    current_chunk = []
    current_word_count = 0
    chunk_index = 0
    
    for para in paragraphs:
        para_words = len(para.split())
        
        # If this paragraph alone exceeds max, split it by sentences
        if para_words > MAX_CHUNK_WORDS:
            # Save current chunk if any
            if current_chunk:
                passages.append(create_passage(
                    current_chunk, chunk_index, source_id, author,
                    source_title, source_type, year, source_url
                ))
                chunk_index += 1
                current_chunk = []
                current_word_count = 0
            
            # Split long paragraph by sentences
            sentences = split_into_sentences(para)
            sent_chunk = []
            sent_word_count = 0
            
            for sent in sentences:
                sent_words = len(sent.split())
                if sent_word_count + sent_words > MAX_CHUNK_WORDS and sent_chunk:
                    passages.append(create_passage(
                        [' '.join(sent_chunk)], chunk_index, source_id, author,
                        source_title, source_type, year, source_url
                    ))
                    chunk_index += 1
                    # Overlap: keep last sentence
                    sent_chunk = sent_chunk[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
                    sent_word_count = sum(len(s.split()) for s in sent_chunk)
                
                sent_chunk.append(sent)
                sent_word_count += sent_words
            
            if sent_chunk:
                current_chunk = [' '.join(sent_chunk)]
                current_word_count = sent_word_count
        
        # Normal case: add paragraph to current chunk
        elif current_word_count + para_words > MAX_CHUNK_WORDS and current_chunk:
            passages.append(create_passage(
                current_chunk, chunk_index, source_id, author,
                source_title, source_type, year, source_url
            ))
            chunk_index += 1
            current_chunk = [para]
            current_word_count = para_words
        else:
            current_chunk.append(para)
            current_word_count += para_words
    
    # Don't forget the last chunk
    if current_chunk:
        passages.append(create_passage(
            current_chunk, chunk_index, source_id, author,
            source_title, source_type, year, source_url
        ))
    
    return passages


def create_passage(
    paragraphs: List[str],
    chunk_index: int,
    source_id: str,
    author: str,
    source_title: str,
    source_type: str,
    year: Optional[int],
    source_url: Optional[str]
) -> Dict:
    """Create a passage dictionary from paragraphs."""
    text = '\n\n'.join(paragraphs)
    return {
        'id': f"{source_id}-{chunk_index:03d}",
        'author': author,
        'source_id': source_id,
        'source_title': source_title,
        'source_type': source_type,
        'year': year,
        'chunk_index': chunk_index,
        'text': text,
        'word_count': len(text.split()),
        'source_url': source_url,
        'themes': [],  # To be filled in later (manually or by AI)
        'created_at': datetime.now().isoformat()
    }


def chunk_hymn(
    text: str,
    source_id: str,
    hymn_title: str,
    year: Optional[int] = None,
    source_url: Optional[str] = None,
    by_stanza: bool = True
) -> List[Dict]:
    """
    Special chunking for hymns.
    
    - Creates one passage for the whole hymn
    - Optionally creates additional passages per stanza
    """
    passages = []
    
    # Full hymn as one passage
    passages.append({
        'id': f"{source_id}-full",
        'author': 'charles-wesley',
        'source_id': source_id,
        'source_title': hymn_title,
        'source_type': 'hymn',
        'year': year,
        'chunk_index': 0,
        'text': text.strip(),
        'word_count': len(text.split()),
        'source_url': source_url,
        'themes': [],
        'is_full_hymn': True,
        'created_at': datetime.now().isoformat()
    })
    
    if by_stanza:
        # Split by stanza (typically blank lines or numbered verses)
        stanzas = re.split(r'\n\s*\n|\n\s*\d+\.\s*\n', text)
        stanzas = [s.strip() for s in stanzas if s.strip()]
        
        for i, stanza in enumerate(stanzas):
            passages.append({
                'id': f"{source_id}-stanza-{i+1:02d}",
                'author': 'charles-wesley',
                'source_id': source_id,
                'source_title': f"{hymn_title} (Stanza {i+1})",
                'source_type': 'hymn-stanza',
                'year': year,
                'chunk_index': i + 1,
                'text': stanza,
                'word_count': len(stanza.split()),
                'source_url': source_url,
                'themes': [],
                'stanza_number': i + 1,
                'created_at': datetime.now().isoformat()
            })
    
    return passages


def append_passages(passages: List[Dict], output_file: Path = PASSAGES_FILE):
    """Append passages to the JSONL file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'a', encoding='utf-8') as f:
        for passage in passages:
            f.write(json.dumps(passage, ensure_ascii=False) + '\n')
    
    print(f"Appended {len(passages)} passages to {output_file}")


def load_passages(input_file: Path = PASSAGES_FILE) -> List[Dict]:
    """Load all passages from the JSONL file."""
    if not input_file.exists():
        return []
    
    passages = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                passages.append(json.loads(line))
    return passages


def get_corpus_stats():
    """Print statistics about the current corpus."""
    passages = load_passages()
    
    if not passages:
        print("No passages found. Start by processing some texts!")
        return
    
    # Basic counts
    total_passages = len(passages)
    total_words = sum(p['word_count'] for p in passages)
    
    # By author
    by_author = {}
    for p in passages:
        author = p['author']
        by_author[author] = by_author.get(author, 0) + 1
    
    # By source type
    by_type = {}
    for p in passages:
        stype = p['source_type']
        by_type[stype] = by_type.get(stype, 0) + 1
    
    # By source
    by_source = {}
    for p in passages:
        source = p['source_title']
        by_source[source] = by_source.get(source, 0) + 1
    
    # Themes coverage
    themed = sum(1 for p in passages if p.get('themes'))
    
    print("\n" + "=" * 50)
    print("WESLEY CORPUS STATISTICS")
    print("=" * 50)
    print(f"\nTotal passages: {total_passages:,}")
    print(f"Total words: {total_words:,}")
    print(f"Average words/passage: {total_words // total_passages if total_passages else 0}")
    print(f"Passages with themes: {themed} ({100*themed//total_passages if total_passages else 0}%)")
    
    print("\nBy Author:")
    for author, count in sorted(by_author.items()):
        print(f"  {author}: {count}")
    
    print("\nBy Source Type:")
    for stype, count in sorted(by_type.items()):
        print(f"  {stype}: {count}")
    
    print("\nBy Source (top 10):")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
        print(f"  {source}: {count}")
    
    print("\n" + "=" * 50)


def validate_corpus():
    """Validate the corpus for common issues."""
    passages = load_passages()
    issues = []
    
    ids_seen = set()
    for i, p in enumerate(passages):
        # Check for duplicate IDs
        if p['id'] in ids_seen:
            issues.append(f"Duplicate ID: {p['id']}")
        ids_seen.add(p['id'])
        
        # Check for empty text
        if not p.get('text', '').strip():
            issues.append(f"Empty text in passage {p['id']}")
        
        # Check for very short passages
        if p['word_count'] < 20:
            issues.append(f"Very short passage ({p['word_count']} words): {p['id']}")
        
        # Check required fields
        required = ['id', 'author', 'source_title', 'source_type', 'text']
        for field in required:
            if field not in p:
                issues.append(f"Missing field '{field}' in passage at line {i+1}")
    
    if issues:
        print(f"\nFound {len(issues)} issues:")
        for issue in issues[:20]:  # Show first 20
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")
    else:
        print("\nCorpus validation passed! No issues found.")


def main():
    parser = argparse.ArgumentParser(description='Wesley Corpus Processing Tools')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean a text file')
    clean_parser.add_argument('input', help='Input file path')
    clean_parser.add_argument('output', help='Output file path')
    
    # Chunk command
    chunk_parser = subparsers.add_parser('chunk', help='Chunk a cleaned text file')
    chunk_parser.add_argument('input', help='Input file path')
    chunk_parser.add_argument('--source-id', required=True, help='Source ID (e.g., jw-sermon-001)')
    chunk_parser.add_argument('--author', required=True, choices=['john-wesley', 'charles-wesley'])
    chunk_parser.add_argument('--title', required=True, help='Source title')
    chunk_parser.add_argument('--type', required=True, help='Source type (sermon, treatise, hymn, etc.)')
    chunk_parser.add_argument('--year', type=int, help='Year of composition/publication')
    chunk_parser.add_argument('--url', help='Source URL')
    chunk_parser.add_argument('--hymn', action='store_true', help='Use hymn chunking (by stanza)')
    
    # Stats command
    subparsers.add_parser('stats', help='Show corpus statistics')
    
    # Validate command
    subparsers.add_parser('validate', help='Validate the corpus')
    
    args = parser.parse_args()
    
    if args.command == 'clean':
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
        cleaned = clean_text(text)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"Cleaned text saved to {args.output}")
    
    elif args.command == 'chunk':
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
        
        if args.hymn:
            passages = chunk_hymn(
                text, args.source_id, args.title,
                args.year, args.url
            )
        else:
            passages = chunk_text(
                text, args.source_id, args.author, args.title,
                args.type, args.year, args.url
            )
        
        append_passages(passages)
    
    elif args.command == 'stats':
        get_corpus_stats()
    
    elif args.command == 'validate':
        validate_corpus()
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
