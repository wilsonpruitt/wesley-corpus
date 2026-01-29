# Wesley Corpus

Training data for the Wesley Index project.

## Directory Structure

```
wesley-corpus/
├── raw/                    # Original downloads, untouched
│   ├── john-wesley/
│   └── charles-wesley/
├── cleaned/                # OCR-corrected, standardized text
│   ├── john-wesley/
│   └── charles-wesley/
├── chunked/
│   └── passages.jsonl      # All passages in JSON Lines format
├── metadata/
│   ├── sources.csv         # Tracking spreadsheet for all sources
│   ├── themes.csv          # Theological theme taxonomy
│   └── annotations/        # Human-labeled training data (Phase 3)
├── process_corpus.py       # Processing tools
└── README.md               # This file
```

## Quick Start

### 1. Download a text

Save the raw text to `raw/john-wesley/` or `raw/charles-wesley/`:

```bash
# Example: download a sermon
curl -o raw/john-wesley/sermon-001-salvation-by-faith.txt \
  "https://wesley.nnu.edu/john-wesley/the-sermons-of-john-wesley-1872-edition/sermon-1-salvation-by-faith/"
```

Or just copy/paste from the website into a `.txt` file.

### 2. Clean the text

```bash
python process_corpus.py clean \
  raw/john-wesley/sermon-001-salvation-by-faith.txt \
  cleaned/john-wesley/sermon-001-salvation-by-faith.txt
```

This fixes OCR errors, normalizes whitespace, and removes page numbers.

### 3. Chunk the text

```bash
python process_corpus.py chunk \
  cleaned/john-wesley/sermon-001-salvation-by-faith.txt \
  --source-id jw-sermon-001 \
  --author john-wesley \
  --title "Salvation by Faith" \
  --type sermon \
  --year 1738 \
  --url "https://wesley.nnu.edu/..."
```

This creates passages in `chunked/passages.jsonl`.

### 4. For hymns, use the `--hymn` flag

```bash
python process_corpus.py chunk \
  cleaned/charles-wesley/wrestling-jacob.txt \
  --source-id cw-wrestling-jacob \
  --author charles-wesley \
  --title "Wrestling Jacob" \
  --type hymn \
  --year 1742 \
  --hymn
```

This creates both a full-hymn passage and individual stanza passages.

### 5. Check your progress

```bash
python process_corpus.py stats
python process_corpus.py validate
```

## Passage Schema

Each passage in `passages.jsonl` is a JSON object:

```json
{
  "id": "jw-sermon-001-003",
  "author": "john-wesley",
  "source_id": "jw-sermon-001",
  "source_title": "Salvation by Faith",
  "source_type": "sermon",
  "year": 1738,
  "chunk_index": 3,
  "text": "The actual passage text...",
  "word_count": 247,
  "source_url": "https://wesley.nnu.edu/...",
  "themes": ["justifying-grace", "faith"],
  "created_at": "2025-01-28T12:00:00"
}
```

## Source Types

| Type | Description | Author |
|------|-------------|--------|
| `sermon` | Wesley's sermons | John |
| `treatise` | Essays and pamphlets | John |
| `journal` | Diary entries | Both |
| `letter` | Correspondence | Both |
| `commentary` | Explanatory Notes | John |
| `hymn` | Full hymn text | Charles |
| `hymn-stanza` | Individual stanza | Charles |

## Theological Themes

See `metadata/themes.csv` for the full taxonomy. Key themes:

- `prevenient-grace` - Grace preceding conversion
- `justifying-grace` - Pardon and new birth
- `sanctifying-grace` - Growth in holiness
- `entire-sanctification` - Christian perfection
- `means-of-grace` - Prayer, Scripture, Eucharist
- `social-holiness` - Faith in community
- `assurance` - Witness of the Spirit

## Tracking Progress

Update `metadata/sources.csv` as you work:

1. Change `status` from `pending` to `downloaded`, `cleaned`, or `chunked`
2. Add `download_date` when you download
3. Add notes about any issues

## Tips

- **Start with the Standard Sermons** - they're the theological core
- **Wesley Center Online** has the cleanest text versions
- **Review chunks manually** - the automated chunking isn't perfect
- **Add themes as you go** - even rough tags help
- **Keep raw files** - you may need to re-process later

## Resources

- [Wesley Center Online](https://wesley.nnu.edu/) - Primary source
- [CCEL](https://www.ccel.org/ccel/wesley) - Alternative texts
- [Hymnary.org](https://hymnary.org/) - Charles Wesley hymns
- [Internet Archive](https://archive.org/) - Historical editions
