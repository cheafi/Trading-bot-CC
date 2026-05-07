import signal, sys, traceback, time

def handler(signum, frame):
    traceback.print_stack(frame)
    sys.exit(1)

signal.signal(signal.SIGALRM, handler)
signal.alarm(12)

t = time.time()
print(f"{time.time()-t:.1f}s importing starlette...", flush=True)
import starlette
print(f"{time.time()-t:.1f}s importing anyio...", flush=True)
import anyio
print(f"{time.time()-t:.1f}s importing pydantic...", flush=True)
import pydantic
print(f"{time.time()-t:.1f}s importing fastapi...", flush=True)
import fastapi
print(f"{time.time()-t:.1f}s importing numpy...", flush=True)
import numpy
print(f"{time.time()-t:.1f}s importing src.core.config...", flush=True)
from src.core.config import get_settings
print(f"{time.time()-t:.1f}s importing src.core.models...", flush=True)
from src.core.models import Signal
print(f"{time.time()-t:.1f}s importing src.api.main...", flush=True)
from src.api.main import app
print(f"{time.time()-t:.1f}s ALL DONE", flush=True)
