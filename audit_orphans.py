import re

text = open("src/api/templates/index.html", encoding="utf-8").read()

m = re.search(r"function cc\(\)\{return\{([\s\S]*?)\n      pfRisk\(\)", text)
if not m:
    print("Could not isolate cc body")
    raise SystemExit(1)

cc_body = m.group(1)
keys = re.findall(r"^      ([a-zA-Z_]\w*)\s*:", cc_body, re.MULTILINE)
keys = list(dict.fromkeys(keys))

script_start = text.find("<script>")
html_part = text[:script_start]

orphans, used = [], []
for k in keys:
    if re.search(r"\b" + re.escape(k) + r"\b", html_part):
        used.append(k)
    else:
        orphans.append(k)

print(f"Total cc() keys: {len(keys)}")
print(f"Used in HTML:    {len(used)}")
print(f"Orphan (no UI):  {len(orphans)}")
print()
print("--- ORPHANS (no DOM binding) ---")
for o in orphans:
    print(f"  {o}")
