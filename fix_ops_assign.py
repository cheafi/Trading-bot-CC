import re

text = open("src/api/templates/index.html", encoding="utf-8").read()

# Inside fetchCcStatus(), find the block where it parses d.
# Replace:
# const eng=d.engine||{};
# with:
# this.opsDetail = d; const eng=d.engine||{};

text2 = re.sub(
    r'(const d=await r\.json\(\);[ \n]*const eng=d\.engine\|\|\{\};)',
    r'this.opsDetail = d; \1',
    text
)

if text != text2:
    with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
        f.write(text2)
    print("Patched opsDetail assignment.")
else:
    print("Failed to find assignment hook.")
