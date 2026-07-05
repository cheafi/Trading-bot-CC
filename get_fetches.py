import re
text = open("src/api/templates/index.html", encoding="utf-8").read()

m = re.search(r'async fetchCcStatus\(\)\s*\{([\s\S]*?)\}(?=\s*async|$)', text)
if m:
    print("fetchCcStatus:", m.group(1)[:500])

