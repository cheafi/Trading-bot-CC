import re
with open('src/api/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'fetchToday7\(\)', text)
if m: print("Found fetchToday7()")
