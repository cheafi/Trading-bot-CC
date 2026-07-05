with open("src/engines/confidence_engine.py", "r") as f:
    text = f.read()

text = text.replace("                raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution + 0.15 * cb.data", "        raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution + 0.15 * cb.data")

with open("src/engines/confidence_engine.py", "w") as f:
    f.write(text)
