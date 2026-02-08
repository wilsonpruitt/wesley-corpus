#!/usr/bin/env python3
"""
Wesley Corpus Search Tool

A comprehensive CLI for searching and browsing the Wesley corpus.
Features include keyword search, theme browsing, filtering, and random passages.
"""

import json
import sys
import argparse
import random
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import os
import textwrap

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

# Check if stdout is a terminal
USE_COLOR = sys.stdout.isatty()

def colorize(text: str, color: str) -> str:
    """Apply color to text if output is a terminal."""
    if not USE_COLOR:
        return text
    return f"{color}{text}{Colors.ENDC}"

def load_corpus(corpus_path: str) -> List[Dict]:
    """Load passages from JSONL file."""
    passages = []
    try:
        with open(corpus_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    passages.append(json.loads(line))
    except FileNotFoundError:
        print(colorize(f"Error: Corpus file not found at {corpus_path}", Colors.RED))
        sys.exit(1)
    return passages

def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length with ellipsis."""
    if len(text) <= max_length:
        return text
    # Try to truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:
        return truncated[:last_space] + '...'
    return truncated + '...'

def wrap_text(text: str, width: int = 80) -> str:
    """Wrap text to specified width."""
    return '\n'.join(textwrap.wrap(text, width=width))

def highlight_match(text: str, query: str) -> str:
    """Highlight matching text in context."""
    if not USE_COLOR:
        return text
    # Case-insensitive highlighting
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: colorize(m.group(0), Colors.YELLOW + Colors.BOLD), text)

def get_context(text: str, query: str, context_chars: int = 50) -> str:
    """Extract context around the first match of query."""
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return truncate_text(text, context_chars * 2)

    start = max(0, match.start() - context_chars)
    end = min(len(text), match.end() + context_chars)

    context = text[start:end]
    if start > 0:
        context = '...' + context
    if end < len(text):
        context = context + '...'

    return highlight_match(context, query)

def search_passages(passages: List[Dict], query: str, limit: int = 10,
                   author_filter: Optional[str] = None,
                   source_type_filter: Optional[str] = None) -> List[Tuple[Dict, int]]:
    """Search passages by keyword and return ranked results."""
    query_lower = query.lower()
    results = []

    for passage in passages:
        # Apply filters
        if author_filter and passage.get('author') != author_filter:
            continue
        if source_type_filter and passage.get('source_type') != source_type_filter:
            continue

        # Calculate relevance score
        text_lower = passage['text'].lower()
        title_lower = passage.get('source_title', '').lower()

        title_matches = len(re.findall(re.escape(query_lower), title_lower))
        text_matches = len(re.findall(re.escape(query_lower), text_lower))

        score = title_matches * 100 + text_matches

        if score > 0:
            results.append((passage, score))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]

def get_passages_by_theme(passages: List[Dict], theme: str,
                         limit: int = 10) -> List[Dict]:
    """Get all passages with a specific theme."""
    results = []
    for passage in passages:
        if theme in passage.get('themes', []):
            results.append(passage)
            if len(results) >= limit:
                break
    return results

def get_all_themes(passages: List[Dict]) -> Dict[str, int]:
    """Get all themes and their passage counts."""
    theme_counts = defaultdict(int)
    for passage in passages:
        for theme in passage.get('themes', []):
            theme_counts[theme] += 1
    return dict(sorted(theme_counts.items()))

def get_corpus_stats(passages: List[Dict]) -> Dict:
    """Calculate corpus statistics."""
    authors = defaultdict(int)
    sources = defaultdict(int)
    source_types = defaultdict(int)
    years = defaultdict(int)
    total_words = 0

    for passage in passages:
        authors[passage.get('author', 'unknown')] += 1
        sources[passage.get('source_id', 'unknown')] += 1
        source_types[passage.get('source_type', 'unknown')] += 1
        years[passage.get('year', 0)] += 1
        total_words += passage.get('word_count', 0)

    return {
        'total_passages': len(passages),
        'total_words': total_words,
        'authors': dict(authors),
        'sources': dict(sources),
        'source_types': dict(source_types),
        'year_range': (min(years.keys()), max(years.keys())) if years else (None, None),
    }

def print_passage(passage: Dict, query: Optional[str] = None, show_context: bool = True) -> None:
    """Pretty print a passage with all metadata."""
    print(f"\n{colorize('─' * 80, Colors.DIM)}")

    # ID and source
    print(colorize(f"ID: {passage['id']}", Colors.CYAN))
    print(colorize(f"Source: {passage['source_title']}", Colors.BOLD) +
          f" ({passage['source_type']})")
    print(f"Author: {passage['author']} | Year: {passage.get('year', 'N/A')}")
    print(f"Word count: {passage.get('word_count', 'N/A')}")

    # Themes
    themes = passage.get('themes', [])
    if themes:
        theme_str = ', '.join(themes)
        print(colorize(f"Themes: {theme_str}", Colors.GREEN))

    # URL
    if passage.get('source_url'):
        print(colorize(f"URL: {passage['source_url']}", Colors.DIM))

    print(colorize('─' * 80, Colors.DIM))

    # Text with context
    if show_context and query:
        context = get_context(passage['text'], query, context_chars=100)
        print(wrap_text(context))
    else:
        preview = truncate_text(passage['text'], 300)
        print(wrap_text(preview))

    print()

def print_passage_summary(passage: Dict, query: Optional[str] = None) -> None:
    """Print a brief summary of a passage for list views."""
    title = colorize(f"{passage['source_title']}", Colors.BOLD)
    author = colorize(f"by {passage['author']}", Colors.CYAN)
    year = f"({passage.get('year', 'N/A')})"

    print(f"{title} {author} {year}")
    print(f"  ID: {passage['id']}")

    # Context or preview
    if query:
        context = get_context(passage['text'], query, context_chars=80)
    else:
        context = truncate_text(passage['text'], 150)

    print(f"  {context}")

    themes = passage.get('themes', [])
    if themes:
        theme_str = ', '.join(themes)
        print(f"  Themes: {colorize(theme_str, Colors.GREEN)}")

    print()

def cmd_search(args, passages: List[Dict]) -> None:
    """Handle search command."""
    if not args.query:
        print(colorize("Error: Search query required", Colors.RED))
        sys.exit(1)

    results = search_passages(
        passages,
        args.query,
        limit=args.limit,
        author_filter=getattr(args, 'author', None),
        source_type_filter=getattr(args, 'source_type', None)
    )

    if not results:
        print(colorize("No passages found matching your search.", Colors.YELLOW))
        return

    print(colorize(f"\nFound {len(results)} passages matching '{args.query}':", Colors.BOLD))

    for passage, score in results:
        print_passage_summary(passage, args.query)

def cmd_theme(args, passages: List[Dict]) -> None:
    """Handle theme browse command."""
    if not args.theme:
        print(colorize("Error: Theme name required", Colors.RED))
        sys.exit(1)

    # Validate theme
    all_themes = get_all_themes(passages)
    if args.theme not in all_themes:
        print(colorize(f"Error: Theme '{args.theme}' not found", Colors.RED))
        print(colorize("Available themes:", Colors.YELLOW))
        for theme in sorted(all_themes.keys()):
            print(f"  - {theme}")
        sys.exit(1)

    # Filter by theme
    results = []
    for passage in passages:
        if args.theme in passage.get('themes', []):
            results.append(passage)
            if len(results) >= args.limit:
                break

    if not results:
        print(colorize(f"No passages found with theme '{args.theme}'", Colors.YELLOW))
        return

    print(colorize(f"\nPassages with theme '{args.theme}' ({len(results)} shown):", Colors.BOLD))

    for passage in results:
        print_passage_summary(passage)

def cmd_stats(args, passages: List[Dict]) -> None:
    """Handle stats command."""
    stats = get_corpus_stats(passages)

    print("\n" + colorize("Wesley Corpus Statistics", Colors.BOLD))
    print(colorize("═" * 80, Colors.DIM))

    print(f"\nTotal passages: {colorize(str(stats['total_passages']), Colors.GREEN)}")
    print(f"Total words: {colorize(str(stats['total_words']), Colors.GREEN)}")
    print(f"Average words per passage: {stats['total_words'] // stats['total_passages']}")

    year_range = stats['year_range']
    if year_range[0]:
        print(f"Year range: {year_range[0]} - {year_range[1]}")

    print(f"\n{colorize('Authors:', Colors.CYAN)}")
    for author in sorted(stats['authors'].keys()):
        count = stats['authors'][author]
        print(f"  {author}: {count} passages")

    print(f"\n{colorize('Source Types:', Colors.CYAN)}")
    for stype in sorted(stats['source_types'].keys()):
        count = stats['source_types'][stype]
        print(f"  {stype}: {count} passages")

    print(f"\n{colorize('Total Unique Sources:', Colors.CYAN)} {len(stats['sources'])}")
    print()

def cmd_themes(args, passages: List[Dict]) -> None:
    """Handle list themes command."""
    theme_counts = get_all_themes(passages)

    print("\n" + colorize("Available Themes", Colors.BOLD))
    print(colorize("═" * 80, Colors.DIM))

    for theme in sorted(theme_counts.keys()):
        count = theme_counts[theme]
        bar_length = (count * 40) // max(theme_counts.values())
        bar = '█' * bar_length
        print(f"  {theme:30s} {bar} {count:4d}")

    print(f"\nTotal passages tagged: {sum(theme_counts.values())}")
    print()

def cmd_random(args, passages: List[Dict]) -> None:
    """Handle random command."""
    passage = random.choice(passages)
    print(colorize("\nRandom Passage from Wesley Corpus", Colors.BOLD))
    print_passage(passage)

def cmd_scripture(args, passages: List[Dict]) -> None:
    """Handle scripture lookup command."""
    # Extract book name and chapter
    query = args.scripture_ref

    # Simple matching for scripture references
    print(colorize(f"\nSearching for passages referencing '{query}'", Colors.BOLD))

    results = search_passages(passages, query, limit=args.limit)

    if not results:
        print(colorize("No passages found matching that scripture reference.", Colors.YELLOW))
        return

    print(colorize(f"Found {len(results)} passages mentioning '{query}':", Colors.BOLD))

    for passage, score in results:
        print_passage_summary(passage, query)

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Wesley Corpus Search Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 search_corpus.py search "perfect love"
  python3 search_corpus.py search "perfect love" --limit 5
  python3 search_corpus.py theme sanctifying-grace
  python3 search_corpus.py search "love" --author charles-wesley
  python3 search_corpus.py search "faith" --source-type sermon
  python3 search_corpus.py stats
  python3 search_corpus.py themes
  python3 search_corpus.py scripture "Romans 8"
  python3 search_corpus.py random
        """
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search passages by keyword')
    search_parser.add_argument('query', nargs='?', help='Search query')
    search_parser.add_argument('--author', help='Filter by author (e.g., john-wesley, charles-wesley)')
    search_parser.add_argument('--source-type', dest='source_type',
                               help='Filter by source type (e.g., sermon, hymn)')
    search_parser.add_argument('--limit', type=int, default=10,
                               help='Number of results to show (default: 10)')

    # Theme command
    theme_parser = subparsers.add_parser('theme', help='Browse passages by theme')
    theme_parser.add_argument('theme', nargs='?', help='Theme name')
    theme_parser.add_argument('--limit', type=int, default=10,
                              help='Number of results to show (default: 10)')

    # Stats command
    subparsers.add_parser('stats', help='Show corpus statistics')

    # Themes command
    subparsers.add_parser('themes', help='List all themes with counts')

    # Random command
    subparsers.add_parser('random', help='Show a random passage')

    # Scripture command
    scripture_parser = subparsers.add_parser('scripture', help='Look up scripture references')
    scripture_parser.add_argument('scripture_ref', nargs='?', help='Scripture reference (e.g., "Romans 8")')
    scripture_parser.add_argument('--limit', type=int, default=10,
                                  help='Number of results to show (default: 10)')

    args = parser.parse_args()

    # Load corpus
    corpus_path = Path(__file__).parent / 'chunked' / 'cleaned_passages.jsonl'
    passages = load_corpus(str(corpus_path))

    # Handle commands
    if args.command == 'search':
        cmd_search(args, passages)
    elif args.command == 'theme':
        cmd_theme(args, passages)
    elif args.command == 'stats':
        cmd_stats(args, passages)
    elif args.command == 'themes':
        cmd_themes(args, passages)
    elif args.command == 'random':
        cmd_random(args, passages)
    elif args.command == 'scripture':
        cmd_scripture(args, passages)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
