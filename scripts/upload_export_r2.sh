#!/bin/sh
# Upload export/ to the wesley-corpus-export R2 bucket (Phase 6 hosting —
# see export/README.md "Hosting"). Run after scripts/build_export.py.
#
# Requires `npx wrangler` logged in (npx wrangler login) with R2 access on
# the account that owns the wesley-corpus-export bucket.
set -eu
cd "$(dirname "$0")/.."

BUCKET=wesley-corpus-export

for f in export/*.jsonl.gz export/*.tar.gz export/README.md export/manifest.json; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  case "$name" in
    *.gz) ct=application/gzip ;;
    *.md) ct=text/markdown ;;
    *.json) ct=application/json ;;
    *) ct=application/octet-stream ;;
  esac
  echo "uploading $name..."
  npx wrangler r2 object put "$BUCKET/$name" --file="$f" --remote --content-type="$ct"
done
