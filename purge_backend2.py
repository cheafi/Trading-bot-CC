import os

main_path = "src/api/main.py"
with open(main_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

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

in_try_block_for_removal = False

new_lines = []
skip_until_except_end = False

for line in lines:
    if skip_until_except_end:
        if "logger" in line or "exc_info=" in line:
            skip_until_except_end = False
        continue

    if line.strip() == "try:":
        # Peek at the next few lines to see if it's importing a router to remove
        pass  # Wait, we can't peek easily with this loop structure. Let's do block parsing.

# Simpler logic:
with open(main_path, "r", encoding="utf-8") as f:
    content = f.read()

import re

for r in routers_to_remove:
    # Pattern: a try block that contains the import of the specific router, up to the end of the except block.
    # We use non-greedy [^\#]*? to avoid eating too much.
    pattern = (
        r"(#\s*[^\n]*\n)?try:\n\s*from src\.api\.routers\."
        + r
        + r"\s+import[^\n]*\n\s*app\.include_router[^\n]*\nexcept[^\n]*\n\s*logger[^\n]*\n"
    )
    content = re.sub(pattern, "", content)

# Also phase9 is weirdly named: `from src.api.routers.phase9 import router as p9_router`
# The pattern should match it. Let's see if it works.

with open(main_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Parsed and replaced")
