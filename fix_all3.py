import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()


# remove _schedRetry
def remove_js_block(source, func_name):
    pattern = rf"(\s*{func_name}\(.*?\)\s*{{)"
    match = re.search(pattern, source)
    if not match:
        return source

    start_idx = match.start()

    brace_count = 0
    in_block = False
    end_idx = start_idx
    for i in range(start_idx, len(source)):
        if source[i] == "{":
            brace_count += 1
            in_block = True
        elif source[i] == "}":
            brace_count -= 1

        if in_block and brace_count == 0:
            end_idx = i + 1
            break

    if end_idx < len(source) and source[end_idx] == ",":
        end_idx += 1

    return source[:start_idx] + source[end_idx:]


text = remove_js_block(text, "_schedRetry")

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

with open("_cc_instant.py", "r", encoding="utf-8") as f:
    cc_py = f.read()

# Make sure we don't import uvicorn if it doesn't exist? No, _cc_instant.py needs uvicorn.
# We should probably run pip install -r requirements.txt if needed.

print("Done")
