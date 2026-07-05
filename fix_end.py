with open("src/api/routers/trade_intelligence.py", "r") as f:
    text = f.read()

import re
old = """        except Exception:
            continue

    return trades"""
new = """        except Exception:
            continue

    synthetic_tickers = {"A1", "A2", "C1", "X", "Y", "Z", "T1", "T2"}
    trades = [t for t in trades if t.get("ticker") not in synthetic_tickers]
    return trades"""

text = text.replace(old, new)
with open("src/api/routers/trade_intelligence.py", "w") as f:
    f.write(text)
