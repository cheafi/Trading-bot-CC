import re
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

m = re.search(r'(function cc\(\)\s*\{[\s\S]*?\n\s*\})', text)
if m:
    cc_body = m.group(1)
    for k in ["data_sync", "confidence", "schedule", "system_health", "logs"]:
        if k in cc_body:
            print(f"{k} exists in cc()")
        else:
            print(f"{k} missing from cc()")
