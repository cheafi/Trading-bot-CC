import re
with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

script_block = re.search(r'<script>(.*?)</script>', text, re.DOTALL)
if script_block:
    code = script_block.group(0)
    with open("check_syntax.js", "w") as f2:
        f2.write(code.replace('<script>', '').replace('</script>', ''))

