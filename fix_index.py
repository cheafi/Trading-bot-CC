import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

funcs_to_purge = [
    "fetchTradeReview",
    "fetchCommand",
    "fetchDecision",
    "fetchAgentJournal",
    "fetchAgentReliability",
    "fetchMkt",
    "fetchTradeAdvice",
    "fetchOptions",
    "fetchHealth",
    "fetchSelfLearnStatus",
    "fetchCalibration",
    "fetchABStatus",
    "fetchFeedbackStats",
    "fetchRiskSummary",
    "fetchExecMetrics",
    "fetchChangelog",
    "fetchThompson",
    "fetchFeatureIC",
    "fetchNotifyLog",
    "fetchFunds",
    "fetchSelectedTradeAIReview",
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

cmd_pattern = r"\s*cmd:\{\s*loading:false,\s*activeTicker:'',\s*decision:null,\s*insight:null,\s*journal:\[\],\s*reliability:null\s*\},"
text = re.sub(cmd_pattern, "", text, flags=re.DOTALL)

# Remove HTML references. Just a broad sweep for simple button references to these functions.
for f in funcs_to_purge:
    # A generic regex to remove buttons that purely call to these functions.
    btn_pattern = rf"<button[^>]*@click=\"{f}\(\)\"[^>]*>.*?</button>\s*"
    text = re.sub(btn_pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("done")
