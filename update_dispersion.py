import re

with open("src/engines/confidence_engine.py", "r") as f:
    code = f.read()

# Make final spread more dramatic. Example: shift (final-0.5)*1.5 + 0.5
# Or adjust raw penalties.
# We'll just change the weights or apply a dispersion multiplier.
replacement = """        raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution 

+ 0.15 * cb.data
        # Force dispersion by steepening the curve around 0.5
        raw_centered = raw - 0.5
        raw_dispersed = 0.5 + (raw_centered * 1.5)  # 1.5x dispersion multiplier
        cb.final = max(0, min(1.0, raw_dispersed - cb.penalties))"""

code = code.replace("""        raw = 0.35 * cb.thesis + 0.30 * cb.timing + 0.20 * cb.execution + 0.15 * cb.data
        cb.final = max(0, min(1.0, raw - cb.penalties))""", replacement)

with open("src/engines/confidence_engine.py", "w") as f:
    f.write(code)

