#!/bin/bash
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main
PYTHONUNBUFFERED=1 nohup ./venv/bin/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > _dashboard.log 2>&1 &
echo "Dashboard PID: $!"
