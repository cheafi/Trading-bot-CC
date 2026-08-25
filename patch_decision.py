import re

with open("src/api/routers/decision.py", "r", encoding="utf-8") as f:
    text = f.read()

# remove AI narrative from today
text = re.sub(
    r"# 8b\. AI-enhanced narrative is opt-in only(.*?)(?=^\s*# 9\. Tradeability)",
    "\n",
    text,
    flags=re.DOTALL | re.MULTILINE
)

# remove ai_narrative from the dict
text = re.sub(r'"ai_narrative": ai_narrative,', '', text)
text = re.sub(r'"ai_powered": ai_narrative is not None,', '"ai_powered": False,', text)

with open("src/api/routers/decision.py", "w", encoding="utf-8") as f:
    f.write(text)
