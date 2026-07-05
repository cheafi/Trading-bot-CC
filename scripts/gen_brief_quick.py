#!/usr/bin/env python3
"""Quick brief generator — minimal imports, no src dependencies.
Generates data/brief-YYYY-MM-DD.json with entry/stop/target levels.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf

UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "TSLA",
    "AMD",
    "AVGO",
    "ORCL",
    "CRM",
    "ADBE",
    "NOW",
    "INTU",
    "PANW",
    "GS",
    "JPM",
    "MS",
    "BLK",
    "V",
    "MA",
    "LLY",
    "ABBV",
    "UNH",
    "ISRG",
    "XOM",
    "CVX",
    "FCX",
    "NEM",
    "COST",
    "HD",
    "NKE",
    "LULU",
    "QCOM",
    "TXN",
    "AMAT",
    "LRCX",
    "KLAC",
    "MRVL",
    "DDOG",
    "NET",
    "SNOW",
    "MDB",
    "TTD",
    "ZS",
    "SMCI",
    "AXON",
    "DECK",
    "CELH",
    "IBKR",
]

ROOT = Path(__file__).resolve().parent.parent


def main():
    print(f"[brief] Downloading {len(UNIVERSE)+1} tickers ...")
    tickers = UNIVERSE + ["SPY"]
    data = yf.download(
        " ".join(tickers),
        period="1y",
        interval="1d",
        progress=False,
        group_by="ticker",
        threads=True,
    )
    print("[brief] Download complete. Processing ...")

    spy_close = data["SPY"]["Close"].dropna().values.flatten().tolist()

    brief = {
        "date": date.today().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "universe_count": len(UNIVERSE),
        "actionable": [],
        "watch": [],
        "review": [],
        "metadata": {
            "generator": "gen_brief_quick.py",
            "spy_close": round(spy_close[-1], 2) if spy_close else None,
        },
    }

    for t in UNIVERSE:
        try:
            sub = data[t]
            c = sub["Close"].dropna().values.flatten().tolist()
            h = sub["High"].dropna().values.flatten().tolist()
            l = sub["Low"].dropna().values.flatten().tolist()
            v = sub["Volume"].dropna().values.flatten().tolist()
            if len(c) < 63:
                continue

            # RS score (63-day excess return vs SPY)
            sr = c[-1] / c[-63] - 1
            sp = spy_close[-1] / spy_close[-63] - 1
            rs = round((sr - sp) * 100, 2) if abs(sp) > 1e-9 else 0.0

            # ATR-14
            trs = [
                max(h[-i] - l[-i], abs(h[-i] - c[-i - 1]), abs(l[-i] - c[-i - 1]))
                for i in range(1, min(len(c), 15))
            ]
            atr = sum(trs) / len(trs) if trs else c[-1] * 0.02
            price = round(c[-1], 2)
            atr_pct = round(atr / price * 100, 2)

            # Volume ratio
            vol_avg = sum(v[-21:-1]) / 20 if len(v) >= 21 else 1
            vol_r = round(v[-1] / vol_avg, 2) if vol_avg > 0 else 1.0

            # Near 52-week high
            high_52 = max(c[-min(252, len(c)) :])
            near_high = c[-1] >= 0.95 * high_52

            # Actionable levels
            entry = price
            stop = round(entry - atr, 2)
            target_2r = round(entry + 2 * atr, 2)
            target_3r = round(entry + 3 * atr, 2)
            risk_pct = atr_pct

            # Conviction tiering
            if rs >= 15 and near_high and vol_r >= 1.2:
                conv, sec = "TRADE", "actionable"
            elif rs >= 6 and near_high:
                conv, sec = "LEADER", "watch"
            elif rs >= 0:
                conv, sec = "WATCH", "review"
            else:
                conv, sec = "AVOID", "review"

            brief[sec].append(
                {
                    "ticker": t,
                    "price": price,
                    "rs_score": rs,
                    "atr_pct": atr_pct,
                    "vol_ratio": vol_r,
                    "near_52w_high": near_high,
                    "conviction": conv,
                    "entry": entry,
                    "stop": stop,
                    "target_2r": target_2r,
                    "target_3r": target_3r,
                    "risk_1r_pct": risk_pct,
                    "atr_value": round(atr, 2),
                }
            )
        except Exception as e:
            print(f"[brief] skip {t}: {e}")

    for s in ("actionable", "watch", "review"):
        brief[s].sort(key=lambda x: x.get("rs_score", 0), reverse=True)

    out = ROOT / "data" / f"brief-{date.today().isoformat()}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(brief, indent=2))
    print(f"[brief] Saved: {out}")
    print(
        f"[brief] Actionable={len(brief['actionable'])} Watch={len(brief['watch'])} Review={len(brief['review'])}"
    )


if __name__ == "__main__":
    main()
