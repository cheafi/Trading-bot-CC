import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

tabs_to_purge = [
    "opportunity",
    "notrade",
    "trade_intel",
    "trade_journal",
    "track",
    "rs",
    "flow",
    "catalog"
]

for tab in tabs_to_purge:
    # Need to match the multiple tabs condition e.g., tab==='trade_journal'||tab==='track'
    pattern = rf"<main x-show=\"(?:tab==='[^']+'\|\|)*tab==='{tab}'(?:\|\|tab==='[^']+')*\".*?</main>\s*(?=<!--|<main)"
    text = re.sub(pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

