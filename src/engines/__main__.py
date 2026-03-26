"""
Allow running the engine via `python -m src.engines`.

Delegates to src.engines.main which handles:
- Structured logging setup
- Config validation
- Boot pre-flight checks
- Graceful shutdown via signal handlers
"""
from src.engines.main import main

if __name__ == "__main__":
    main()
