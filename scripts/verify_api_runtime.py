"""Read-only HTTP smoke checks; run inside the API container after startup.

No order, broker-connect, or state-changing endpoints are called.
This checks API availability, not live market-data freshness.
"""

import ast
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    base = "http://127.0.0.1:8000"
    paths = (
        "/health",
        "/healthz",
        "/readyz",
        "/api/health",
        "/api/ops/cc-header",
        "/api/ops/changelog",
        "/api/v7/warmup/brief-board",
        "/",
        "/static/cc-helpers.js",
    )
    for path in paths:
        with urlopen(base + path, timeout=15) as response:
            body = response.read()
            assert response.status == 200 and body, path
            if "json" in response.headers.get("Content-Type", ""):
                data = json.loads(body)
                if path == "/health":
                    assert data["mode"] == "full", "Backend not ready"
                if path == "/api/ops/cc-header":
                    engine = data.get("engine", {})
                    assert engine.get("running") is False, engine
                    assert engine.get("dry_run") is True, engine
            if path == "/":
                assert len(body) > 600000, "Only loader HTML returned"
                assert b"{{ api_key" not in body, "Unrendered template"
            print(path, response.status, len(body), flush=True)

    request = Request(f"{base}/", headers={"Accept-Encoding": "gzip"})
    with urlopen(request, timeout=15) as response:
        assert response.headers.get("Content-Encoding") == "gzip"
        body = gzip.decompress(response.read())
        assert len(body) > 600000, "Compressed dashboard incomplete"
        assert b"{{ api_key" not in body, "Unrendered gzip template"
        print("gzip dashboard:", len(body), "bytes", flush=True)

    root = Path("/app")
    files = [
        *root.joinpath("src").rglob("*.py"),
        *root.joinpath("scripts").glob("*.py"),
        root / "_cc_instant.py",
    ]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print("Syntax checks passed:", len(files), "Python files")


if __name__ == "__main__":
    main()
