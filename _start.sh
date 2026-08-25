#!/bin/bash
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

# macOS: clear Gatekeeper quarantine from .so files to avoid 5-10 min import hang
if [[ "$(uname)" == "Darwin" ]]; then
    xattr -r -d com.apple.quarantine venv/ 2>/dev/null
    find venv -name '*.so' -exec xattr -c {} \; 2>/dev/null
fi

exec python3 _cc_instant.py
