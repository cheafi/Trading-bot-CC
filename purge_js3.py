import json
import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()


def remove_js_block(source, func_name):
    pattern = rf"(\s*async {func_name}\(.*?\)\s*{{)"
    match = re.search(pattern, source)
    if not match:
        return source

    start_idx = match.start()

    # Simple curly brace matching
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

    # Remove trailing comma if exists
    if end_idx < len(source) and source[end_idx] == ",":
        end_idx += 1

    return source[:start_idx] + source[end_idx:]


funcs_to_purge = [
    "fetchTradeReview",
    "fetchCommand",
    "fetchDecision",
    "fetchAgent",
    "fetchAgentJournal",
    "fetchAgentReliability",
    "fetchMkt",
    "fetchBrief",
    "fetchTradeAdvice",
    "fetchOptions",
    "fetchBenchBT",
    "fetchPerfTracker",
    "fetchFundLab",
    "fetchFunds",
    "fetchPMStrip",
    "fetchModelFunds",
    "fetchModelFundAI",
    "fetchTradeIntel",
    "fetchSelectedTradeAIReview",
    "fetchTimeTravel",
    "fetchHealth",
    "fetchOpsDetail",
    "fetchRanked",
    "fetchRS",
    "fetchFlow",
    "fetchRejects",
    "fetchNoTrade",
    "fetchEndpoints",
    "fetchChangelog",
    "fetchSelfLearnStatus",
    "fetchCalibration",
    "fetchABStatus",
    "fetchExecMetrics",
    "fetchRiskSummary",
    "fetchThompson",
    "fetchFeatureIC",
    "fetchFeedbackStats",
]

for func in funcs_to_purge:
    text = remove_js_block(text, func)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("JS methods removed")
