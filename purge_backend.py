import os
import re

main_path = "src/api/main.py"
with open(main_path, "r", encoding="utf-8") as f:
    main_py = f.read()

routers_to_remove = [
    "fund_lab",
    "fund_portfolio",
    "fund",
    "trade_review",
    "calibration_proof",
    "swing",
    "self_learn",
    "options_radar",
    "model_funds",
    "pm_arena",
    "trade_intelligence",
    "rs_hub",
    "phase9",
    "intelligence",
]

for r in routers_to_remove:
    # Match the whole block:
    # try:
    #     from src.api.routers.<r> import router as <r>_router
    #     app.include_router(<r>_router)
    # except Exception:
    #     logger...

    # We use a non-greedy regex to match the try/except block that imports this router
    pattern = rf"(#.*?\n)?try:\n\s*from src\.api\.routers\.{r} import.*?\s*app\.include_router.*?\nexcept Exception:\n\s*logger.*?\n\s*"
    main_py = re.sub(pattern, "", main_py, flags=re.DOTALL)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_py)

print("Removed orphaned routers from main.py")
