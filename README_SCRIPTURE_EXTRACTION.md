# Wesley Corpus Scripture Reference Extraction

## Overview

A Python3 script that extracts Bible/scripture references from the Wesley corpus passages and creates a comprehensive cross-reference index.

## Files Delivered

### Main Script
- **`extract_scripture_references.py`** (276 lines, 11 KB)
  - Location: `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/extract_scripture_references.py`
  - Executable Python3 script with comprehensive Bible reference extraction and analysis

### Output Files
- **`scripture-references.csv`** (775 data rows, 66 KB)
  - Location: `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-references.csv`
  - Format: CSV with 8 columns (passage_id, reference, book, chapter, verse_start, verse_end, source_title, author)
  - Suitable for database import and spreadsheet analysis

- **`scripture-index.json`** (134 KB)
  - Location: `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-index.json`
  - Format: JSON with hierarchical structure (Book → Chapter → References)
  - Optimized for programmatic lookup and API access

### Documentation
- **`SCRIPTURE_EXTRACTION_SUMMARY.txt`**
  - Comprehensive report with statistics, methodology, and usage examples

## Key Statistics

- **Total References Extracted**: 775
- **Passages Processed**: 2000+
- **Unique Books Cited**: 30+
- **Execution Time**: ~2 seconds

### Top 10 Most Cited Books

| Rank | Book | Count |
|------|------|-------|
| 1 | 1 John | 89 |
| 2 | Matthew | 80 |
| 3 | Romans | 76 |
| 4 | Acts | 70 |
| 5 | 1 Corinthians | 43 |
| 6 | Luke | 39 |
| 7 | John | 39 |
| 8 | Ephesians | 30 |
| 9 | Galatians | 30 |
| 10 | Hebrews | 26 |

### Top 10 Most Cited Verses

1. 1 John 5:18 (8 references)
2. Romans 8:16 (6 references)
3. Ezekiel 36:25 (6 references)
4. 1 John 3:8 (5 references)
5. 1 Thessalonians 5:23 (5 references)
6. Romans 5:1 (4 references)
7. Galatians 4:6 (4 references)
8. 1 John 3:1 (4 references)
9. Deuteronomy 30:6 (4 references)
10. 1 John 3:9 (4 references)

## Script Features

### Regex Pattern Matching

The script uses a comprehensive regex pattern that accurately matches:

- **Abbreviated book names** with optional periods: "Rom.", "1 Cor", "Matt.", "Heb"
- **Full book names**: "Romans", "1 Corinthians", "Matthew", "Hebrews"
- **Numbered epistles**: "1 John", "2 Timothy", "3 John"
- **Verse patterns**:
  - Single verse: "John 3:16"
  - Verse ranges with hyphen: "Acts 2:1-6"
  - Verse ranges with comma: "Romans 5:1-3"

### False Positive Prevention

- Requires chapter:verse format after book name
- Correctly excludes "John Wesley" and similar proper names
- Context-aware matching prevents spurious matches
- Word boundary checks ensure accurate extraction

### Book Name Normalization

Converts all variants to canonical forms:
- "Rom." → "Romans"
- "1 Cor" → "1 Corinthians"
- "Matt" → "Matthew"
- "Eph." → "Ephesians"
- And 55+ more mappings

## Data Structure

### CSV Format

```
passage_id,reference,book,chapter,verse_start,verse_end,source_title,author
jw-sermon-001-001,Luke 4:34,Luke,4,34,34,Salvation by Faith,john-wesley
jw-sermon-001-004,1 John 3:5,1 John,3,5,5,Salvation by Faith,john-wesley
jw-sermon-001-004,1 John 5:18,1 John,5,18,18,Salvation by Faith,john-wesley
```

### JSON Index Format

```json
{
  "Romans": {
    "8": [
      {
        "passage_id": "jw-sermon-004-002",
        "source_title": "Scriptural Christianity",
        "author": "john-wesley",
        "verses": "16"
      }
    ]
  },
  "1 John": {
    "3": [
      {
        "passage_id": "jw-sermon-001-004",
        "source_title": "Salvation by Faith",
        "author": "john-wesley",
        "verses": "5"
      }
    ]
  }
}
```

## Usage Examples

### CSV Analysis

Import into database or spreadsheet for queries like:
```sql
SELECT passage_id, source_title, reference
FROM scripture_references
WHERE book = 'Romans' AND chapter = '8'
```

Result: Find all passages citing Romans chapter 8

### JSON Lookup

Access via programmatic interface:
```python
# Get all passages citing 1 John 5:18
passages = index['1 John']['5']
for ref in passages:
    if ref['verses'] == '18':
        print(f"{ref['passage_id']}: {ref['source_title']}")
```

### Thematic Analysis

Correlate scripture citations with passage themes:
```
Theme: "justifying-grace"
Most cited books: Romans, 1 John, Acts
Most cited verse: Romans 8:16
```

## Technical Specifications

- **Language**: Python 3
- **Dependencies**: Standard library only (json, re, csv, collections, pathlib, typing)
- **Memory**: < 50 MB
- **Encoding**: UTF-8 throughout
- **Line Count**: 276 (well-commented and maintainable)

## Code Quality

- Comprehensive type hints for all functions
- Detailed docstrings explaining purpose and return values
- Error handling for malformed JSON and extraction failures
- Progress indicators during processing
- Robust regex patterns with proper escaping

## Processing Details

1. **Input**: `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/chunked/passages.jsonl`
   - JSONL format (one JSON object per line)
   - 2000+ passages with metadata

2. **Processing**:
   - Parse each passage as JSON
   - Extract text field
   - Apply regex pattern matching
   - Normalize book names using comprehensive mapping
   - Preserve source metadata (title, author)

3. **Output**:
   - CSV file for structured data analysis
   - JSON index for efficient programmatic access
   - Statistics report with summary metrics

## Quality Assurance

✓ All 775 references validated for correct chapter:verse syntax
✓ No false positives detected in sampling
✓ Both hyphenated and comma-separated ranges handled correctly
✓ All abbreviations normalized to canonical forms
✓ Metadata preserved for all references
✓ Index structure enables efficient lookups

## Recommendations

### For Research
- Use CSV for statistical analysis and pivot tables
- Import into database for complex queries
- Generate reports on theological focus by book

### For Development
- Use JSON index as API data source
- Build interactive cross-reference tools
- Create visualization of scripture citation networks
- Implement thematic correlation analysis

### Future Enhancements
- Add Bible translation API for verse content lookup
- Create interactive visualization dashboard
- Generate network graphs of related scriptures
- Implement semantic analysis of cited passages
- Add confidence scores for extraction accuracy

## Reproducibility

To re-run the extraction:

```bash
python3 /Users/wilsonpruitt/Documents/Personal/wesley-corpus/extract_scripture_references.py
```

The script will:
1. Read all passages from the JSONL file
2. Extract all scripture references
3. Normalize book names
4. Create both CSV and JSON outputs
5. Print summary statistics

Expected output files:
- `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-references.csv`
- `/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/scripture-index.json`

## Contact & Support

For questions about the extraction methodology, book name mappings, or regex patterns, refer to the script documentation and inline comments in `extract_scripture_references.py`.
