import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# Replace the giant unused state block
# Let's target the known variables inside function cc() { return { ...
# We know the specific names from previous investigations.

removals = [
    r"\s*factory:\{[^}]*\},",
    r"\s*opt:\{[^}]*\},",
    r"\s*brief:\{[^}]*\},",
    r"\s*bt:\{[^}]*\},",
    r"\s*benchBT:\{[^}]*\},",
    r"\s*perfTracker:\{[^}]*\},",
    r"\s*fundLab:\{[^}]*\},",
    r"\s*fundMonitor:\{[^}]*\},",
    r"\s*pmStrip:\{[^}]*\},",
    r"\s*modelFunds:\{[^\}]*(?:aiMemoByFund:[^}]*\}|aiExpertByFund:[^}]*\})?[^\}]*\},",
    r"\s*tradeIntel:\{[^\}]*\},",
    r"\s*tradeJournal:\{[^\}]*\},",
    r"\s*tt:\{[^\}]*\},",
    r"\s*opsDetail:\{\},",
    r"\s*apiEndpoints:\[\],",
    r"\s*changelog:\[\],",
    r"\s*selfLearn:\{[^\}]*\},",
    r"\s*exec:\{[^\}]*\},",
    r"\s*risk:\{[^\}]*\},",
    r"\s*rl:\{[^\}]*\},",
    r"\s*notifyLog:\{[^\}]*\},",
    r"\s*scannerHub:\{[^\}]*\},",
    r"\s*rsData:\{[^\}]*\},",
    r"\s*rsFilter:\{[^\}]*\},",
    r"\s*flowData:\{[^\}]*\},",
    r"\s*rejectsData:\{[^\}]*\},",
    r"\s*noTradeData:\{[^\}]*\},",
]

for pattern in removals:
    text = re.sub(pattern, "", text, flags=re.DOTALL)

# Handle multi-line cmd block which is trickier
cmd_pattern = r"\s*cmd:\{\s*loading:false,\s*activeTicker:'',\s*decision:null,\s*insight:null,\s*journal:\[\],\s*reliability:null\s*\},"
text = re.sub(cmd_pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("JS state cleaned")
