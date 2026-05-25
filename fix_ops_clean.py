import re

text = open("src/api/templates/index.html", encoding="utf-8").read()

# Replace the broken block
pattern = r"this\.opsDetail = d;\s*this\.opsDetail = d;\s*const d=await r\.json\(\);\s*const eng=d\.engine\|\|\{\};"
replacement = """const d=await r.json();
          this.opsDetail = d;
          this.ops = d.engine || {};
          const eng = d.engine || {};"""

text2 = re.sub(pattern, replacement, text)

# Just in case it was only duplicated once:
pattern2 = r"this\.opsDetail = d;\s*const d=await r\.json\(\);\s*const eng=d\.engine\|\|\{\};"
text2 = re.sub(pattern2, replacement, text2)

if text != text2:
    open("src/api/templates/index.html", "w", encoding="utf-8").write(text2)
    print("Fixed fetchCcStatus error.")
else:
    print("Could not find the exact pattern.")

