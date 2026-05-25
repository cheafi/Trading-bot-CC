import re
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

m = re.search(r'(function cc\(\)\s*\{[\s\S]*?\n\s*\})', text)
if m:
    cc_body = m.group(1)
    if "ccStatus" in cc_body:
        print("ccStatus exists")
    else:
        print("ccStatus missing")
