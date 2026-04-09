#!/bin/bash
# Apply honcho-migrate patches to a Honcho repo clone.
#
# Usage:
#   bash apply-patches.sh /path/to/honcho
#   bash apply-patches.sh  # defaults to ~/Documents/honcho

set -e

HONCHO_DIR="${1:-$HOME/Documents/honcho}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATCHES_DIR="$SCRIPT_DIR/patches"

if [ ! -d "$HONCHO_DIR/src" ]; then
  echo "Error: $HONCHO_DIR does not look like a Honcho repo (no src/ directory)"
  exit 1
fi

echo "Applying patches to: $HONCHO_DIR"
cd "$HONCHO_DIR"

# Check for existing modifications
if ! git diff --quiet HEAD 2>/dev/null; then
  echo "Warning: Honcho repo has uncommitted changes."
  echo "Stashing them first..."
  git stash
  STASHED=1
fi

# Apply patches
for patch in "$PATCHES_DIR"/*.patch; do
  name=$(basename "$patch")
  echo "  Applying: $name"
  if git apply --check "$patch" 2>/dev/null; then
    git apply "$patch"
    echo "    OK"
  else
    echo "    CONFLICT — attempting 3-way merge..."
    if git apply --3way "$patch" 2>/dev/null; then
      echo "    OK (3-way merge)"
    else
      echo "    FAILED — manual resolution needed"
      echo "    Patch file: $patch"
      exit 1
    fi
  fi
done

# Pop stash if we stashed
if [ "${STASHED:-0}" = "1" ]; then
  echo "Restoring stashed changes..."
  git stash pop || echo "Warning: stash pop had conflicts. Resolve manually."
fi

echo ""
echo "Patches applied. Modified files:"
git diff --stat HEAD
echo ""
echo "Next: docker compose up -d --build"
