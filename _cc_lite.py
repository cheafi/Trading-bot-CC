"""
Lightweight CC server - serves dashboard with minimal imports.
Heavy modules load in background after server starts.
"""
import os, sys, logging
os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
sys.path.insert(0, ".")

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cc-lite")

app = FastAPI(title="CC Trading Intelligence")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TEMPLATES_DIR = Path("src/api/templates")
STATIC_DIR = Path("src/api/static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Track startup
_start = datetime.now(timezone.utc)
_full_app = None

@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "uptime_seconds": (datetime.now(timezone.utc) - _start).total_seconds(),
            "mode": "full" if _full_app else "lite"}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Load full app routes in background
import threading
def _load_full():
    global _full_app
    try:
        logger.info("Background: loading full app...")
        from src.api.main import app as full
        # Copy all routes from full app
        for route in full.routes:
            if hasattr(route, 'path') and route.path not in ('/', '/health', '/api/health', '/static'):
                app.routes.append(route)
        _full_app = full
        # Copy state
        if hasattr(full, 'state'):
            for k in dir(full.state):
                if not k.startswith('_'):
                    setattr(app.state, k, getattr(full.state, k))
        logger.info("Background: full app loaded! All routes available.")
    except Exception as e:
        logger.error(f"Background load failed: {e}")

threading.Thread(target=_load_full, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
