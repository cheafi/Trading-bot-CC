import signal
import sys
import traceback
import time

def handler(signum, frame):
    traceback.print_stack(frame)
    sys.exit(1)

signal.signal(signal.SIGALRM, handler)
signal.alarm(12)

t = time.time()
print(f"{time.time()-t:.1f}s importing starlette...", flush=True)
print(f"{time.time()-t:.1f}s importing anyio...", flush=True)
print(f"{time.time()-t:.1f}s importing pydantic...", flush=True)
print(f"{time.time()-t:.1f}s importing fastapi...", flush=True)
print(f"{time.time()-t:.1f}s importing numpy...", flush=True)
print(f"{time.time()-t:.1f}s importing src.core.config...", flush=True)
print(f"{time.time()-t:.1f}s importing src.core.models...", flush=True)
print(f"{time.time()-t:.1f}s importing src.api.main...", flush=True)
print(f"{time.time()-t:.1f}s ALL DONE", flush=True)
