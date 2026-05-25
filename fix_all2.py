import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

funcs_to_purge = [
    "fetchAgent",
    "fetchBrief",
    "fetchBenchBT",
    "fetchPerfTracker",
    "fetchFundLab",
    "fetchPMStrip",
    "fetchModelFunds",
    "fetchModelFundAI",
    "fetchTradeIntel",
    "fetchTimeTravel",
    "fetchOpsDetail",
    "fetchOpps",
    "fetchRS",
    "fetchFlow",
    "fetchRejects",
    "fetchNoTrade",
    "fetchEndpoints",
    "fetchOppScanner",
]


def remove_js_block(source, func_name):
    pattern = rf"(\s*async {func_name}\(.*?\)\s*{{)"
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


for func in funcs_to_purge:
    text = remove_js_block(text, func)

# Button sweep for these specific ones
for f in funcs_to_purge:
    btn_pattern = rf"<[^>]*@click=\"{f}\(\)\"[^>]*>.*?</[^>]*>\s*"
    text = re.sub(btn_pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("done")
