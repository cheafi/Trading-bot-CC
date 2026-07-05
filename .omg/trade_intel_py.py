import re

with open("src/api/routers/trade_intelligence.py", "r") as f:
    text = f.read()

# 1. Filter out synthetic trades
old_load = """    return trades"""
new_load = """    # Filter out synthetics
    synthetic_tickers = {"A1", "A2", "C1", "X", "Y", "Z", "T1", "T2"}
    trades = [t for t in trades if t.get("ticker") not in synthetic_tickers]
    return trades"""
if old_load in text:
    text = text.replace(old_load, new_load)
    print("Replaced load trades")

# 2. Mistake descriptions
old_mistakes = """_MISTAKE_DESCRIPTIONS = {
    "STOP_VIOLATION": "Held position past the 1R stop — loss exceeded planned risk",
    "WRONG_REGIME": "Entered a long trade in a BEAR/Crisis regime — directional headwind",
    "LOW_QUALITY_SETUP": "Took a grade-C setup — below minimum quality threshold",
    "REGIME_MISMATCH": "Applied momentum strategy in SIDEWAYS/CHOPPY regime",
    "PREMATURE_EXIT": "Exited same day for a loss — possibly panic-sold at noise",
}"""
new_mistakes = """_MISTAKE_DESCRIPTIONS = {
    "STOP_VIOLATION": "Action Rule: Never violate 1R stop under any conditions",
    "WRONG_REGIME": "Action Rule: Stop fighting strong directional regime headwinds",
    "LOW_QUALITY_SETUP": "Action Rule: Stop taking grade-C sub-optimal setups",
    "REGIME_MISMATCH": "Action Rule: Apply momentum strategies only in trending regimes",
    "PREMATURE_EXIT": "Action Rule: Exit only by system rule, not same-day noise panic",
}"""
if old_mistakes in text:
    text = text.replace(old_mistakes, new_mistakes)
    print("Replaced mistakes")

with open("src/api/routers/trade_intelligence.py", "w") as f:
    f.write(text)
