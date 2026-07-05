import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# Let's find function cc() and see if there are missing state variables for the ops tab

m = re.search(r'function cc\(\)\{return\{(.*?)\}\s*\}', text, re.DOTALL)
if m:
    print("Found cc()")
    cc_body = m.group(1)
    
    # check for ops block
    if "ops:" in cc_body:
        print("ops: exists in cc()")
    else:
        print("ops: missing from cc()")
