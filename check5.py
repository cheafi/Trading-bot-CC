import re
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

m = re.search(r'(function cc\(\)\s*\{[\s\S]*?\n\s*\})', text)
if m:
    cc_body = m.group(1)
    if 'selfLearn' in cc_body:
        print("selfLearn exists in cc()")
    else:
        print("selfLearn missing from cc()")
    
    if 'ops' in cc_body:
        print("ops exists in cc()")
    else:
        print("ops missing from cc()")
