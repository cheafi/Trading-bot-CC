import re

with open("src/api/main.py", "r", encoding="utf-8") as f:
    content = f.read()

routers_to_remove = [
    "brief",
    "institutional",
    "agents",
    "decision_pipeline",
]

for r in routers_to_remove:
    pattern = r"(#\s*[^\n]*\n)?try:\n\s*from src\.api\.routers\." + r + r"\s+import[^\n]*\n\s*app\.include_router[^\n]*\nexcept[^\n]*\n\s*logger[^\n]*\n"
    content = re.sub(pattern, "", content)

with open("src/api/main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Parsed and replaced")
