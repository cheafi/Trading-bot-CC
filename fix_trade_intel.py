with open("src/api/routers/trade_intelligence.py", "r") as f:
    text = f.read()

import re
old_text = """def _load_trades(path: str | Path) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        # Filter out synthetics
    synthetic_tickers = {"A1", "A2", "C1", "X", "Y", "Z", "T1", "T2"}
    trades = [t for t in trades if t.get("ticker") not in synthetic_tickers]
    return trades
    seen: set = set()"""

new_text = """def _load_trades(path: str | Path) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return trades
        
    seen: set = set()"""

text = text.replace(old_text, new_text)

with open("src/api/routers/trade_intelligence.py", "w") as f:
    f.write(text)
