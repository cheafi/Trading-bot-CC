import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

tabs_to_purge = [
    "timetravel",
    "factory",
    "methodology",
    "options",
    "brief",
    "model_funds",
    "funds",
    "market",
    "internals",
    "deep",
    "events",
    "risk",
]

for tab in tabs_to_purge:
    pattern = rf"<main x-show=\"tab==='{tab}'(?:.*?)</main>\s*(?=<!--|<main)"
    text = re.sub(pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("Purged blocks.")
