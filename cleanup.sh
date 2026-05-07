#!/usr/bin/env bash
# cleanup.sh — TradingAI Bot project cleanup
# Safe to run from project root. Removes caches, logs, build artefacts.
# Does NOT touch .git history or user data (models/*.json, data/brief-*.json).
set -euo pipefail

echo "🧹 TradingAI Bot — Project Cleanup"
echo "===================================="
echo "Before: $(du -sh . 2>/dev/null | cut -f1)"

echo ""
echo "→ Removing Python bytecode caches..."
find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -o -name "*.pyo" | grep -v ".git" | xargs rm -f 2>/dev/null || true
find . -name "*.egg-info" -type d -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true

echo "→ Removing log and temp files..."
find . -name "*.log" -not -path "./.git/*" -delete 2>/dev/null || true
find . -name "*.tmp" -o -name "*.bak" -o -name "*.swp" -o -name "*.swo" \
  | grep -v ".git" | xargs rm -f 2>/dev/null || true

echo "→ Removing pytest / coverage artefacts..."
rm -rf .pytest_cache .coverage htmlcov/ .mypy_cache/ .ruff_cache/ 2>/dev/null || true

echo "→ Removing JS/TS build artefacts..."
find . -type d \( -name ".turbo" -o -name ".next" \) \
  -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
# Note: dist/ intentionally excluded — may contain needed build outputs

echo "→ Compacting git objects..."
git gc --prune=now --quiet
git remote prune origin --dry-run 2>/dev/null || true

echo ""
echo "After:  $(du -sh . 2>/dev/null | cut -f1)"
echo ".git:   $(du -sh .git 2>/dev/null | cut -f1)"
echo ""
echo "✅ Cleanup complete"
echo ""
echo "Top 10 largest folders:"
du -d 3 -h . 2>/dev/null | sort -rh | head -11 | tail -10
