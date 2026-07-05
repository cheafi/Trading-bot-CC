import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

tabs_to_delete = [
    "timetravel",
    "methodology",
    "factory",
    "options",
    "brief",
    "model_funds",
    "funds",
]

for tab in tabs_to_delete:
    pattern = rf'<main x-show="tab===\'{tab}\'".*?</main>'
    # count matches to warn
    matches = re.findall(pattern, text, flags=re.DOTALL)
    print(f"{tab}: found {len(matches)} match(es)")
    if len(matches) == 1:
        text = re.sub(pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)
