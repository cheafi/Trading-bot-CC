# Project Cleanup Checklist

Last audited: 2026-05-07

## Current repo hotspots

- Top-level disk usage snapshot: `.git` ≈ 12M, `src` ≈ 8.7M, `venv` ≈ 4.5M
- Git object store is healthy: `size-pack` ≈ 11.93 MiB, `garbage` = 0
- Largest historical blobs include `apps/web-roo-code/public/heroes/cloud-screen.png` and repeated versions of `pnpm-lock.yaml`
- The checked-in local `venv/` is a local cleanup target even though it is already ignored

## 1. File system cleanup

### Safe audit commands

```bash
make cleanup-inventory
make cleanup-dry-run
du -hd 1 . | sort -hr | head -10
```

### Safe delete command

```bash
make clean
```

### Dead code detection

JavaScript / TypeScript:

```bash
pnpm knip
```

Python:

```bash
./venv/bin/python -m pip install vulture ruff
./venv/bin/python -m vulture src tests --min-confidence 80
./venv/bin/python -m ruff check src tests --select F401,F841
```

## 2. Git hygiene

### Regular maintenance

```bash
make git-maintenance
```

### Inspect large historical blobs

```bash
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '$1=="blob"{print $3"\t"$4}' \
  | sort -nr \
  | head -20
```

### Remove mistaken large files from history

Preferred tool:

```bash
brew install git-filter-repo
git filter-repo --path path/to/large-file --invert-paths
git push origin --force --all
git push origin --force --tags
```

Use `--strip-blobs-bigger-than 20M` if the target is unknown.

## 3. Documentation cleanup

### Keep

- Runbooks used for current operations
- API or architecture docs that match live code
- One source-of-truth per topic

### Archive

- Sprint planning docs no longer used day-to-day
- Migration notes with historical value
- Older drafts superseded by a newer canonical doc

### Delete

- Conflicting or duplicate docs
- Stale guides that no longer match current setup
- Scratch notes without decisions or operational value

### Audit commands

```bash
find docs -type f \( -name "*.md" -o -name "*.html" \) -mtime +180 | sort
find docs -type f | sed 's#.*/##' | sort | uniq -d
```

## 4. Recommended structure

Keep core layers shallow:

```text
apps/        product entry points
src/         core business logic
tests/       automated tests
scripts/     maintenance and automation
docs/        active docs + archive
config/      versioned configuration
data/        local data and generated artifacts
docker/      runtime container definitions
```

## 5. Suggested cleanup cadence

Weekly:

```bash
make cleanup-dry-run
make clean
```

Monthly:

```bash
pnpm knip
./venv/bin/python -m vulture src tests --min-confidence 80
make git-maintenance
```

Quarterly:

```bash
find docs -type f \( -name "*.md" -o -name "*.html" \) -mtime +180 | sort
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '$1=="blob"{print $3"\t"$4}' \
  | sort -nr \
  | head -20
```