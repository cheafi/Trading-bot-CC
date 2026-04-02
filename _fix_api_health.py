"""Fix /api/health endpoint position in api/main.py"""
import pathlib, ast

ROOT = pathlib.Path(__file__).resolve().parent
API = ROOT / "src" / "api" / "main.py"
src = API.read_text()

# Remove the incorrectly appended health endpoint (after if __name__)
lines = src.split("\n")
new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == '@app.get("/api/health")' and i > 0:
        # Check if it's after if __name__ block
        before = "\n".join(lines[:i])
        if 'if __name__' in before:
            skip = True
            continue
    if skip:
        if line.strip() == "" or line.startswith("    "):
            continue
        else:
            skip = False
    new_lines.append(line)

src = "\n".join(new_lines)

# Now insert proper health endpoint before 'if __name__'
health_block = '''
@app.get("/api/health", tags=["monitoring"])
async def api_health():
    """Engine health-check endpoint for monitoring."""
    try:
        from src.engines.auto_trading_engine import AutoTradingEngine
        engine = AutoTradingEngine(dry_run=True)
        return await engine.health_check()
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

'''

main_guard = '\nif __name__ == "__main__":'
if '@app.get("/api/health"' not in src:
    src = src.replace(main_guard, "\n" + health_block + main_guard)
    print("OK: Inserted /api/health before __main__ guard")
else:
    print("SKIP: /api/health already in correct position")

API.write_text(src)
try:
    ast.parse(src)
    print("OK: api/main.py syntax valid")
except SyntaxError as e:
    print(f"FAIL: {e}")
