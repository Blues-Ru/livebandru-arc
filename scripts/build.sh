#!/usr/bin/env bash
# LiveBand.Ru — full build
# Usage: bash livebandru-arc/scripts/build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SITE="$ROOT/liveband-site"

# Rename old site if it exists
if [ -d "$SITE" ]; then
  BACKUP="$ROOT/liveband-site-$(date +%Y%m%d%H%M)"
  echo "Renaming old site → $BACKUP"
  mv "$SITE" "$BACKUP"
fi

echo "=== Running generator ==="
python3 "$SCRIPT_DIR/generate.py"

echo ""
echo "Build complete. To preview:"
echo "  python3 $SCRIPT_DIR/serve.py"
