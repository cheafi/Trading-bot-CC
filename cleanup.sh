#!/usr/bin/env bash
# cleanup.sh — TradingAI Bot project cleanup
# Modes:
#   ./cleanup.sh inventory  # non-destructive repo/Git/doc inventory
#   ./cleanup.sh dry-run    # show removable cache/temp artefacts
#   ./cleanup.sh            # apply safe cleanup (same as "apply")
# Does NOT touch Git history or user data (models/*.json, data/brief-*.json).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-apply}"

print_header() {
  echo "🧹 TradingAI Bot — Project Cleanup"
  echo "===================================="
  echo "Mode: $MODE"
  echo "Root: $ROOT_DIR"
}

usage() {
  cat <<'EOF'
Usage:
  ./cleanup.sh inventory   # show repo/Git/doc cleanup opportunities
  ./cleanup.sh dry-run     # list safe-to-delete junk files and caches
  ./cleanup.sh apply       # remove safe caches/logs/temp artefacts
  ./cleanup.sh             # same as apply
EOF
}

report_sizes() {
  echo "Before/Current: $(du -sh "$ROOT_DIR" 2>/dev/null | cut -f1)"
  echo ".git:          $(du -sh "$ROOT_DIR/.git" 2>/dev/null | cut -f1)"
}

list_candidates() {
  find "$ROOT_DIR" \( -path "$ROOT_DIR/.git" -o -path "$ROOT_DIR/venv" \) -prune -o \
    \( -type f \( \
      -name "*.log" -o \
      -name "*.tmp" -o \
      -name "*.temp" -o \
      -name "*.bak" -o \
      -name "*.swp" -o \
      -name "*.swo" -o \
      -name ".DS_Store" -o \
      -name "Thumbs.db" -o \
      -name "*.pyc" -o \
      -name "*.pyo" -o \
      -name "*.tsbuildinfo" \
    \) -print \) -o \
    \( -type d \( \
      -name "__pycache__" -o \
      -name ".pytest_cache" -o \
      -name ".mypy_cache" -o \
      -name ".ruff_cache" -o \
      -name ".turbo" -o \
      -name ".cache" -o \
      -name ".next" -o \
      -name ".parcel-cache" -o \
      -name "htmlcov" -o \
      -name "coverage" \
    \) -print \)
}

run_inventory() {
  print_header
  report_sizes
  echo ""
  echo "Top 10 largest top-level folders:"
  pushd "$ROOT_DIR" >/dev/null
  du -hd 1 . 2>/dev/null | sort -hr | head -10
  echo ""
  echo "Git object store health:"
  git count-objects -vH
  echo ""
  echo "Largest blobs in Git history (top 10):"
  git rev-list --objects --all \
    | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
    | awk '$1=="blob"{print $3"\t"$4}' \
    | sort -nr \
    | head -10
  echo ""
  if [ -d docs ]; then
    echo "Docs untouched for 180+ days (top 20):"
    find docs -type f \( -name "*.md" -o -name "*.html" \) -mtime +180 | sort | head -20
  fi
  popd >/dev/null
}

run_dry() {
  print_header
  report_sizes
  echo ""
  echo "Safe cleanup candidates:"
  list_candidates | sed "s#^$ROOT_DIR/##" | sort
}

run_apply() {
  print_header
  report_sizes
  echo ""
  echo "→ Removing safe caches, logs, and temp artefacts..."
  list_candidates | while IFS= read -r path; do
    [ -z "$path" ] && continue
    rm -rf "$path"
    echo "removed ${path#$ROOT_DIR/}"
  done
  pushd "$ROOT_DIR" >/dev/null
  echo "→ Compacting git objects..."
  git gc --prune=now --quiet
  popd >/dev/null
  echo ""
  echo "After: $(du -sh "$ROOT_DIR" 2>/dev/null | cut -f1)"
  echo ".git:  $(du -sh "$ROOT_DIR/.git" 2>/dev/null | cut -f1)"
  echo "✅ Cleanup complete"
}

case "$MODE" in
  inventory)
    run_inventory
    ;;
  dry-run)
    run_dry
    ;;
  apply)
    run_apply
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage
    exit 1
    ;;
esac
