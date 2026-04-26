#!/usr/bin/env bash
# LiveBand.Ru — full build
# Usage: bash scripts/build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pip install -r "$SCRIPT_DIR/../requirements.txt" -q
python3 "$SCRIPT_DIR/generate.py"
