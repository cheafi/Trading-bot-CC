import json, sys

d = json.load(sys.stdin)
s = d.get("strategies", [])
print("strategies:", len(s), "· n_total:", d.get("meta", {}).get("n_total"))
for r in s[:5]:
    sid = r.get("strategy_id", "")[:18]
    print(
        f"  {sid:18} N={r.get('n_trades',0):3} "
        f"Sharpe={r.get('sharpe_trade'):>6} "
        f"Sortino={r.get('sortino_trade'):>6} "
        f"PF={r.get('profit_factor'):>6} "
        f"MaxDD={r.get('max_drawdown_r'):>7}R "
        f"curve_len={len(r.get('equity_curve_r') or [])}"
    )
